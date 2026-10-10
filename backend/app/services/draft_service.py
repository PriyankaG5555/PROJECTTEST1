"""Drafts: list, create (blank/copy), get with days, rename, delete (backend-spec.md §4)."""

from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import AppError, validation_error
from app.models import Activity, Draft, Trip, User
from app.schemas import ActivityOut, DayOut, DraftOut, DraftSummaryOut
from app.schemas.drafts import DraftCreateIn
from app.services.ownership import assert_editable, get_owned_draft, get_owned_trip
from app.services.trip_service import draft_summaries

MAX_DRAFTS_PER_TRIP = 5


def _name_taken() -> AppError:
    return AppError("DRAFT_NAME_TAKEN", 409, "This trip already has a draft with that name.")


def _check_name_free(db: Session, trip: Trip, name: str, except_id: object = None) -> None:
    query = select(Draft.id).where(Draft.trip_id == trip.id, Draft.name_normalized == name.lower())
    if except_id is not None:
        query = query.where(Draft.id != except_id)
    if db.scalar(query) is not None:
        raise _name_taken()


def _flush_or_name_taken(db: Session) -> None:
    try:
        db.flush()  # concurrent requests: the unique constraint decides
    except IntegrityError:
        db.rollback()
        raise _name_taken() from None


def touch(trip: Trip, draft: Draft | None = None) -> None:
    trip.updated_at = func.now()
    if draft is not None:
        draft.updated_at = func.now()


# ---------- Output ----------
def draft_out(db: Session, draft: Draft) -> DraftOut:
    db.flush()
    db.refresh(draft)
    trip = draft.trip
    activities = db.scalars(
        select(Activity)
        .where(Activity.draft_id == draft.id)
        .order_by(
            Activity.day_number,
            Activity.time.asc().nulls_last(),
            Activity.created_at,
            Activity.id,
        )
    ).all()
    by_day: dict[int, list[Activity]] = {}
    for activity in activities:
        by_day.setdefault(activity.day_number, []).append(activity)

    days = []
    trip_total = Decimal(0)
    for number in range(1, trip.day_count + 1):
        items = by_day.get(number, [])
        day_total = sum((a.cost or Decimal(0) for a in items), Decimal(0))
        trip_total += day_total
        days.append(
            DayOut(
                day_number=number,
                date=trip.start_date + timedelta(days=number - 1),
                total_cost=day_total,
                activities=[ActivityOut.model_validate(a) for a in items],
            )
        )
    return DraftOut(
        id=draft.id,
        trip_id=trip.id,
        name=draft.name,
        is_final=draft.id == trip.finalized_draft_id,
        total_cost=trip_total,
        days=days,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
    )


def draft_summary(db: Session, draft: Draft) -> DraftSummaryOut:
    db.flush()
    return next(s for s in draft_summaries(db, draft.trip) if s.id == draft.id)


# ---------- Operations ----------
def list_drafts(db: Session, user: User, trip_id: str) -> list[DraftSummaryOut]:
    return draft_summaries(db, get_owned_trip(db, trip_id, user))


def create_draft(db: Session, user: User, trip_id: str, data: DraftCreateIn) -> Draft:
    trip = get_owned_trip(db, trip_id, user)
    assert_editable(trip)
    count = db.scalar(select(func.count()).select_from(Draft).where(Draft.trip_id == trip.id))
    if (count or 0) >= MAX_DRAFTS_PER_TRIP:
        raise AppError(
            "DRAFT_LIMIT_REACHED",
            409,
            f"A trip can have at most {MAX_DRAFTS_PER_TRIP} drafts. Delete one first.",
        )

    source: Draft | None = None
    if data.copy_from_draft_id is not None:
        source = db.get(Draft, data.copy_from_draft_id)
        if source is None or source.trip_id != trip.id:
            raise validation_error("copyFromDraftId", "Choose a draft from this trip to copy.")

    _check_name_free(db, trip, data.name)
    draft = Draft(trip_id=trip.id, name=data.name, name_normalized=data.name.lower())
    db.add(draft)
    _flush_or_name_taken(db)

    if source is not None:
        for a in db.scalars(select(Activity).where(Activity.draft_id == source.id)):
            db.add(
                Activity(
                    draft_id=draft.id,
                    day_number=a.day_number,
                    destination_name=a.destination_name,
                    time=a.time,
                    duration_minutes=a.duration_minutes,
                    cost=a.cost,
                )
            )
    touch(trip)
    db.flush()
    return draft


def get_draft(db: Session, user: User, draft_id: str) -> Draft:
    return get_owned_draft(db, draft_id, user)


def rename_draft(db: Session, user: User, draft_id: str, name: str) -> Draft:
    draft = get_owned_draft(db, draft_id, user)
    assert_editable(draft.trip)
    _check_name_free(db, draft.trip, name, except_id=draft.id)
    draft.name, draft.name_normalized = name, name.lower()
    touch(draft.trip, draft)
    _flush_or_name_taken(db)
    return draft


def delete_draft(db: Session, user: User, draft_id: str) -> None:
    draft = get_owned_draft(db, draft_id, user)
    trip = draft.trip
    assert_editable(trip)
    count = db.scalar(select(func.count()).select_from(Draft).where(Draft.trip_id == trip.id))
    if (count or 0) <= 1:
        raise AppError("LAST_DRAFT", 409, "A trip needs at least one draft.")
    db.delete(draft)
    touch(trip)
    db.flush()
