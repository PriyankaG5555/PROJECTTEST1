"""Activities: add, edit/move, delete (backend-spec.md §4)."""

from sqlalchemy.orm import Session

from app.errors import validation_error
from app.models import Activity, Trip, User
from app.schemas.drafts import ActivityCreateIn, ActivityUpdateIn
from app.services.draft_service import touch
from app.services.ownership import assert_editable, get_owned_activity, get_owned_draft


def _minutes(hhmm: str) -> int:
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def check_duration(time: str | None, duration: int | None) -> None:
    """Duration needs a start time and must end by midnight (ai-feature.md §4, contract)."""
    if duration is None:
        return
    if time is None:
        raise validation_error("durationMinutes", "Add a start time to set a duration.")
    if _minutes(time) + duration > 24 * 60:
        raise validation_error("durationMinutes", "The activity must end by midnight.")


def _check_day(trip: Trip, day_number: int) -> None:
    if not 1 <= day_number <= trip.day_count:
        raise validation_error(
            "dayNumber", f"Choose a day between 1 and {trip.day_count} for this trip."
        )


def add_activity(db: Session, user: User, draft_id: str, data: ActivityCreateIn) -> Activity:
    draft = get_owned_draft(db, draft_id, user)
    assert_editable(draft.trip)
    _check_day(draft.trip, data.day_number)
    check_duration(data.time, data.duration_minutes)
    activity = Activity(
        draft_id=draft.id,
        day_number=data.day_number,
        destination_name=data.destination_name,
        time=data.time,
        duration_minutes=data.duration_minutes,
        cost=data.cost,
    )
    db.add(activity)
    touch(draft.trip, draft)
    db.flush()
    db.refresh(activity)
    return activity


def update_activity(db: Session, user: User, activity_id: str, data: ActivityUpdateIn) -> Activity:
    activity = get_owned_activity(db, activity_id, user)
    draft = activity.draft
    assert_editable(draft.trip)

    fields = data.model_fields_set
    for required, camel in (("day_number", "dayNumber"), ("destination_name", "destinationName")):
        if required in fields and getattr(data, required) is None:
            raise validation_error(camel, "This field can't be empty.")
    if data.day_number is not None:
        _check_day(draft.trip, data.day_number)
        activity.day_number = data.day_number
    if data.destination_name is not None:
        activity.destination_name = data.destination_name
    for optional in ("time", "duration_minutes", "cost"):
        if optional in fields:  # null clears the value
            setattr(activity, optional, getattr(data, optional))

    check_duration(activity.time, activity.duration_minutes)
    touch(draft.trip, draft)
    db.flush()
    db.refresh(activity)
    return activity


def delete_activity(db: Session, user: User, activity_id: str) -> None:
    activity = get_owned_activity(db, activity_id, user)
    draft = activity.draft
    assert_editable(draft.trip)
    db.delete(activity)
    touch(draft.trip, draft)
    db.flush()
