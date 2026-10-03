"""Database schema: migration matches models; constraints and cascades work (BE spec §3)."""

from datetime import date
from decimal import Decimal

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Activity, Base, Draft, Trip, TripStatus, TripType, User


def make_user(db: Session, name: str = "riya_travels") -> User:
    user = User(username=name, username_normalized=name.lower(), password_hash="x")
    db.add(user)
    db.flush()
    return user


def make_trip(db: Session, user: User) -> Trip:
    trip = Trip(
        user=user,
        destination="Goa",
        start_date=date(2026, 11, 14),
        end_date=date(2026, 11, 17),
        trip_type=TripType.FRIENDS,
    )
    trip.drafts.append(Draft(name="Draft 1", name_normalized="draft 1"))
    db.add(trip)
    db.flush()
    return trip


def test_migration_matches_models(db: Session) -> None:
    diff = compare_metadata(MigrationContext.configure(db.connection()), Base.metadata)
    assert diff == []


def test_trip_defaults(db: Session) -> None:
    trip = make_trip(db, make_user(db))
    db.refresh(trip)

    assert trip.status is TripStatus.DRAFT
    assert trip.day_count == 4
    assert trip.id is not None and trip.created_at is not None


def test_usernames_unique_case_insensitively(db: Session) -> None:
    make_user(db, "Riya")
    with pytest.raises(IntegrityError):
        make_user(db, "riya")


def test_end_date_before_start_rejected(db: Session) -> None:
    trip = make_trip(db, make_user(db))
    trip.end_date = date(2026, 11, 1)
    with pytest.raises(IntegrityError):
        db.flush()


@pytest.mark.parametrize(
    ("field", "value"),
    [("time", "25:00"), ("time", "9:30"), ("cost", Decimal("-1")), ("day_number", 31)],
)
def test_activity_constraints(db: Session, field: str, value: object) -> None:
    draft = make_trip(db, make_user(db)).drafts[0]
    activity = Activity(draft=draft, day_number=1, destination_name="Baga Beach")
    setattr(activity, field, value)
    db.add(activity)
    with pytest.raises(IntegrityError):
        db.flush()


def test_draft_names_unique_per_trip(db: Session) -> None:
    trip = make_trip(db, make_user(db))
    trip.drafts.append(Draft(name="DRAFT 1", name_normalized="draft 1"))
    with pytest.raises(IntegrityError):
        db.flush()


def test_deleting_user_cascades_to_everything(db: Session) -> None:
    user = make_user(db)
    trip = make_trip(db, user)
    db.add(
        Activity(
            draft=trip.drafts[0],
            day_number=1,
            destination_name="Baga Beach",
            time="09:30",
            cost=Decimal("0"),
        )
    )
    trip.finalized_draft_id = trip.drafts[0].id
    db.commit()

    db.delete(user)
    db.commit()

    for model in (Trip, Draft, Activity):
        assert db.scalar(select(func.count()).select_from(model)) == 0


def test_deleting_finalized_draft_clears_reference(db: Session) -> None:
    trip = make_trip(db, make_user(db))
    trip.drafts.append(Draft(name="Draft 2", name_normalized="draft 2"))
    db.flush()
    final = trip.drafts[1]
    trip.finalized_draft_id = final.id
    db.commit()

    db.delete(final)
    db.commit()
    db.refresh(trip)

    assert trip.finalized_draft_id is None
