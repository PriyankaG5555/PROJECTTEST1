"""Trip request/response bodies — api-contract-spec.md §5 (trip endpoints)."""

import uuid
from datetime import date
from typing import Annotated

from pydantic import StringConstraints

from app.models.enums import TripType
from app.schemas import TripDetailOut, TripOut
from app.schemas.base import ApiModel

Destination = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class TripCreateIn(ApiModel):
    destination: Destination
    start_date: date
    end_date: date
    trip_type: TripType


class TripUpdateIn(ApiModel):
    """All fields optional; omitted fields are unchanged. `null` is not allowed for these."""

    destination: Destination | None = None
    start_date: date | None = None
    end_date: date | None = None
    trip_type: TripType | None = None
    confirm_delete_activities: bool = False


class TripResponse(ApiModel):
    trip: TripDetailOut


class TripUpdateResponse(ApiModel):
    trip: TripDetailOut
    deleted_activity_count: int


class TripListResponse(ApiModel):
    trips: list[TripOut]


class AffectedActivity(ApiModel):
    draft_id: uuid.UUID
    draft_name: str
    day_number: int
    activity_id: uuid.UUID
    destination_name: str
