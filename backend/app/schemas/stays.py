"""Stay and hotel-suggestion bodies — api-contract-spec.md (stays, hotel-suggestions)."""

from typing import Annotated

from pydantic import Field, StringConstraints

from app.models.enums import TripPriority
from app.schemas import StayOut
from app.schemas.base import ApiModel
from app.schemas.drafts import Cost

StayName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Day = Annotated[int, Field(ge=1, le=31)]
Short = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]


class StayIn(ApiModel):
    name: StayName
    check_in_day: Day
    check_out_day: Day
    cost_per_night: Cost | None = None
    place_id: Annotated[str, StringConstraints(max_length=100)] | None = None
    kind: Annotated[str, StringConstraints(max_length=20)] | None = None
    stars: Annotated[int, Field(ge=1, le=7)] | None = None
    lat: Annotated[float, Field(ge=-90, le=90)] | None = None
    lon: Annotated[float, Field(ge=-180, le=180)] | None = None
    address: Short | None = None
    url: Annotated[str, StringConstraints(max_length=300, pattern=r"^https?://")] | None = None


class StayUpdateIn(ApiModel):
    """Omitted fields are unchanged; `null` clears optional fields (not name or days)."""

    name: StayName | None = None
    check_in_day: Day | None = None
    check_out_day: Day | None = None
    cost_per_night: Cost | None = None
    place_id: Annotated[str, StringConstraints(max_length=100)] | None = None
    kind: Annotated[str, StringConstraints(max_length=20)] | None = None
    stars: Annotated[int, Field(ge=1, le=7)] | None = None
    lat: Annotated[float, Field(ge=-90, le=90)] | None = None
    lon: Annotated[float, Field(ge=-180, le=180)] | None = None
    address: Short | None = None
    url: Annotated[str, StringConstraints(max_length=300, pattern=r"^https?://")] | None = None


class StayResponse(ApiModel):
    stay: StayOut


class StayListResponse(ApiModel):
    stays: list[StayOut]


class HotelOut(ApiModel):
    place_id: str
    name: str
    kind: str
    stars: int | None
    address: str | None
    website: str | None
    lat: float
    lon: float
    distance_km: float | None
    maps_url: str


class HotelSuggestionsResponse(ApiModel):
    hotels: list[HotelOut]
    ordered_by: TripPriority | None
    attribution: str = "© OpenStreetMap contributors"
