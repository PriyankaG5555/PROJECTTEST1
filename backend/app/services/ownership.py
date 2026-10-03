"""Ownership and finalized-lock checks used by every service (backend-spec.md §4).

Missing resources and other users' resources both raise NOT_FOUND, so IDs can't be probed.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import AppError, not_found
from app.models import Activity, Draft, Trip, TripStatus, User


def parse_id(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise not_found() from None


def get_owned_trip(db: Session, trip_id: str, user: User) -> Trip:
    trip = db.scalar(select(Trip).where(Trip.id == parse_id(trip_id), Trip.user_id == user.id))
    if trip is None:
        raise not_found()
    return trip


def get_owned_draft(db: Session, draft_id: str, user: User) -> Draft:
    draft = db.scalar(
        select(Draft)
        .join(Trip, Draft.trip_id == Trip.id)
        .where(Draft.id == parse_id(draft_id), Trip.user_id == user.id)
    )
    if draft is None:
        raise not_found()
    return draft


def get_owned_activity(db: Session, activity_id: str, user: User) -> Activity:
    activity = db.scalar(
        select(Activity)
        .join(Draft, Activity.draft_id == Draft.id)
        .join(Trip, Draft.trip_id == Trip.id)
        .where(Activity.id == parse_id(activity_id), Trip.user_id == user.id)
    )
    if activity is None:
        raise not_found()
    return activity


def assert_editable(trip: Trip) -> None:
    if trip.status is TripStatus.FINALIZED:
        raise AppError(
            "TRIP_FINALIZED", 409, "This trip is finalized. Reopen it for editing to make changes."
        )
