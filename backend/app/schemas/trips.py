"""Trip request/response bodies — api-contract-spec.md §5 (trip endpoints)."""

import uuid
from datetime import date
from typing import Annotated

from pydantic import StringConstraints

from app.models.enums import TripPriority, TripType
from app.schemas import TripDetailOut, TripOut
from app.schemas.base import ApiModel
from app.schemas.drafts import Cost

Destination = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class TripCreateIn(ApiModel):
    destination: Destination
    start_date: date
    end_date: date
    trip_type: TripType
    top_priority: TripPriority | None = None
    budget: Cost | None = None


class TripUpdateIn(ApiModel):
    """All fields optional; omitted fields are unchanged. `null` is not allowed for these."""

    destination: Destination | None = None
    start_date: date | None = None
    end_date: date | None = None
    trip_type: TripType | None = None
    top_priority: TripPriority | None = None  # null clears
    budget: Cost | None = None  # null clears
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


class SuggestionOut(ApiModel):
    place_id: str
    name: str
    address: str | None
    rating: float | None
    rating_count: int | None
    price_level: str | None
    maps_url: str | None


class SuggestionsResponse(ApiModel):
    suggestions: list[SuggestionOut]
    ordered_by: TripPriority | None
    attribution: str = "Google"
