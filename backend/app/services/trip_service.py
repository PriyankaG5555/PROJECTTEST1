"""Trips: create, list, get, update (incl. shortening), delete (backend-spec.md §4)."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.errors import AppError, validation_error
from app.models import Activity, Draft, Trip, TripStatus, User
from app.schemas import DraftSummaryOut, TripDetailOut, TripOut
from app.schemas.base import to_camel
from app.schemas.trips import AffectedActivity, TripCreateIn, TripUpdateIn
from app.services.ownership import assert_editable, get_owned_trip

MAX_TRIP_DAYS = 30
FIRST_DRAFT_NAME = "Draft 1"


# ---------- Validation ----------
def check_dates(start: date, end: date) -> None:
    if end < start:
        raise validation_error("endDate", "End date must be on or after the start date.")
    if (end - start).days + 1 > MAX_TRIP_DAYS:
        raise validation_error("endDate", f"A trip can be at most {MAX_TRIP_DAYS} days long.")


# ---------- Output ----------
def _trip_fields(trip: Trip, draft_count: int) -> dict[str, object]:
    return {
        "id": trip.id,
        "destination": trip.destination,
        "start_date": trip.start_date,
        "end_date": trip.end_date,
        "trip_type": trip.trip_type,
        "status": trip.status,
        "finalized_draft_id": trip.finalized_draft_id,
        "day_count": trip.day_count,
        "draft_count": draft_count,
        "created_at": trip.created_at,
        "updated_at": trip.updated_at,
    }


def draft_summaries(db: Session, trip: Trip) -> list[DraftSummaryOut]:
    rows = db.execute(
        select(
            Draft,
            func.count(Activity.id),
            func.coalesce(func.sum(Activity.cost), Decimal(0)),
        )
        .outerjoin(Activity, Activity.draft_id == Draft.id)
        .where(Draft.trip_id == trip.id)
        .group_by(Draft.id)
        .order_by(Draft.created_at, Draft.id)
    ).all()
    return [
        DraftSummaryOut(
            id=draft.id,
            name=draft.name,
            is_final=draft.id == trip.finalized_draft_id,
            activity_count=count,
            total_cost=total,
            updated_at=draft.updated_at,
        )
        for draft, count, total in rows
    ]


def trip_detail(db: Session, trip: Trip) -> TripDetailOut:
    db.flush()
    db.refresh(trip)  # server-side timestamps
    drafts = draft_summaries(db, trip)
    return TripDetailOut.model_validate({**_trip_fields(trip, len(drafts)), "drafts": drafts})


# ---------- Operations ----------
def create_trip(db: Session, user: User, data: TripCreateIn) -> Trip:
    check_dates(data.start_date, data.end_date)
    trip = Trip(
        user_id=user.id,
        destination=data.destination,
        start_date=data.start_date,
        end_date=data.end_date,
        trip_type=data.trip_type,
        status=TripStatus.DRAFT,
    )
    trip.drafts.append(Draft(name=FIRST_DRAFT_NAME, name_normalized=FIRST_DRAFT_NAME.lower()))
    db.add(trip)
    db.flush()
    return trip


def list_trips(db: Session, user: User, status: TripStatus | None) -> list[TripOut]:
    counts = select(Draft.trip_id, func.count().label("n")).group_by(Draft.trip_id).subquery()
    query = (
        select(Trip, func.coalesce(counts.c.n, 0))
        .outerjoin(counts, counts.c.trip_id == Trip.id)
        .where(Trip.user_id == user.id)
        .order_by(Trip.updated_at.desc(), Trip.id)
    )
    if status is not None:
        query = query.where(Trip.status == status)
    return [TripOut.model_validate(_trip_fields(t, n)) for t, n in db.execute(query).all()]


def update_trip(db: Session, user: User, trip_id: str, data: TripUpdateIn) -> tuple[Trip, int]:
    trip = get_owned_trip(db, trip_id, user)
    assert_editable(trip)

    for field in ("destination", "start_date", "end_date", "trip_type"):
        if field in data.model_fields_set and getattr(data, field) is None:
            raise validation_error(to_camel(field), "This field can't be empty.")

    start = data.start_date or trip.start_date
    end = data.end_date or trip.end_date
    check_dates(start, end)
    new_day_count = (end - start).days + 1

    deleted = 0
    if new_day_count < trip.day_count:
        affected = db.execute(
            select(Activity, Draft)
            .join(Draft, Activity.draft_id == Draft.id)
            .where(Draft.trip_id == trip.id, Activity.day_number > new_day_count)
            .order_by(Draft.created_at, Activity.day_number, Activity.created_at)
        ).all()
        if affected and not data.confirm_delete_activities:
            n = len(affected)
            raise AppError(
                "ACTIVITIES_WOULD_BE_DELETED",
                409,
                f"Shortening this trip will delete {n} {'activity' if n == 1 else 'activities'}.",
                {
                    "affected": [
                        AffectedActivity(
                            draft_id=d.id,
                            draft_name=d.name,
                            day_number=a.day_number,
                            activity_id=a.id,
                            destination_name=a.destination_name,
                        ).model_dump(mode="json", by_alias=True)
                        for a, d in affected
                    ]
                },
            )
        if affected:
            db.execute(delete(Activity).where(Activity.id.in_([a.id for a, _ in affected])))
            deleted = len(affected)

    if data.destination is not None:
        trip.destination = data.destination
    if data.trip_type is not None:
        trip.trip_type = data.trip_type
    trip.start_date, trip.end_date = start, end
    trip.updated_at = func.now()  # also bump when only dates move
    db.flush()
    return trip, deleted


def finalize_trip(db: Session, user: User, trip_id: str, draft_id: uuid.UUID) -> Trip:
    trip = get_owned_trip(db, trip_id, user)
    assert_editable(trip)  # already finalized -> TRIP_FINALIZED
    draft = db.get(Draft, draft_id)
    if draft is None or draft.trip_id != trip.id:
        raise validation_error("draftId", "Choose a draft from this trip to finalize.")
    trip.status = TripStatus.FINALIZED
    trip.finalized_draft_id = draft.id
    trip.updated_at = func.now()
    db.flush()
    return trip


def reopen_trip(db: Session, user: User, trip_id: str) -> Trip:
    trip = get_owned_trip(db, trip_id, user)
    if trip.status is not TripStatus.FINALIZED:
        raise AppError("TRIP_NOT_FINALIZED", 409, "This trip is already a draft.")
    trip.status = TripStatus.DRAFT
    trip.finalized_draft_id = None
    trip.updated_at = func.now()
    db.flush()
    return trip


def delete_trip(db: Session, user: User, trip_id: str) -> None:
    trip = get_owned_trip(db, trip_id, user)  # allowed in any status
    db.delete(trip)
    db.flush()
