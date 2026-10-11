"""Stays: accommodation by night range (accommodation-feature.md §2)."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import AppError, not_found, validation_error
from app.models import Stay, Trip, User
from app.schemas.stays import StayIn, StayUpdateIn
from app.services.draft_service import touch
from app.services.ownership import assert_editable, get_owned_trip, parse_id

MAX_STAYS = 10
OPTIONAL = ("cost_per_night", "place_id", "kind", "stars", "lat", "lon", "address", "url")


def stays_of(db: Session, trip: Trip) -> list[Stay]:
    return list(db.scalars(select(Stay).where(Stay.trip_id == trip.id).order_by(Stay.check_in_day)))


def stay_for_day(stays: list[Stay], day: int) -> tuple[Stay | None, bool]:
    """(stay, return_to_it): the night's stay, or on check-out day the stay you leave from."""
    for stay in stays:
        if stay.check_in_day <= day < stay.check_out_day:
            return stay, True
    for stay in stays:
        if stay.check_out_day == day:
            return stay, False
    return None, False


def _check(db: Session, trip: Trip, check_in: int, check_out: int, except_id: Any = None) -> None:
    if check_in > trip.day_count:
        raise validation_error("checkInDay", f"Choose a day between 1 and {trip.day_count}.")
    if not check_in < check_out <= trip.day_count + 1:
        raise validation_error(
            "checkOutDay", f"Check-out must be after check-in and at most day {trip.day_count + 1}."
        )
    for other in stays_of(db, trip):
        if (
            other.id != except_id
            and check_in < other.check_out_day
            and other.check_in_day < check_out
        ):
            raise AppError(
                "STAY_OVERLAP",
                409,
                f"These nights overlap your stay at “{other.name}” "
                f"(nights {other.check_in_day}–{other.check_out_day - 1}).",
            )


def _owned_stay(db: Session, stay_id: str, user: User) -> Stay:
    stay = db.scalar(
        select(Stay).join(Trip).where(Stay.id == parse_id(stay_id), Trip.user_id == user.id)
    )
    if stay is None:
        raise not_found()
    return stay


def list_stays(db: Session, user: User, trip_id: str) -> list[Stay]:
    return stays_of(db, get_owned_trip(db, trip_id, user))


def create_stay(db: Session, user: User, trip_id: str, data: StayIn) -> Stay:
    trip = get_owned_trip(db, trip_id, user)
    assert_editable(trip)
    count = db.scalar(select(func.count()).select_from(Stay).where(Stay.trip_id == trip.id))
    if (count or 0) >= MAX_STAYS:
        raise AppError("STAY_LIMIT_REACHED", 409, f"A trip can have at most {MAX_STAYS} stays.")
    _check(db, trip, data.check_in_day, data.check_out_day)
    stay = Stay(trip_id=trip.id, **data.model_dump())
    db.add(stay)
    touch(trip)
    db.flush()
    db.refresh(stay)
    return stay


def update_stay(db: Session, user: User, stay_id: str, data: StayUpdateIn) -> Stay:
    stay = _owned_stay(db, stay_id, user)
    assert_editable(stay.trip)
    fields = data.model_fields_set
    for required, camel in (
        ("name", "name"),
        ("check_in_day", "checkInDay"),
        ("check_out_day", "checkOutDay"),
    ):
        if required in fields and getattr(data, required) is None:
            raise validation_error(camel, "This field can't be empty.")
    check_in = data.check_in_day or stay.check_in_day
    check_out = data.check_out_day or stay.check_out_day
    _check(db, stay.trip, check_in, check_out, except_id=stay.id)
    stay.check_in_day, stay.check_out_day = check_in, check_out
    if data.name is not None:
        stay.name = data.name
    for field in OPTIONAL:
        if field in fields:  # null clears
            setattr(stay, field, getattr(data, field))
    touch(stay.trip)
    db.flush()
    db.refresh(stay)
    return stay


def delete_stay(db: Session, user: User, stay_id: str) -> None:
    stay = _owned_stay(db, stay_id, user)
    assert_editable(stay.trip)
    touch(stay.trip)
    db.delete(stay)
    db.flush()
