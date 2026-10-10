"""AI day-planning bodies — api-contract-spec.md (ai-plans, activities/bulk), ai-feature.md §4."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import Field, StringConstraints

from app.schemas import ActivityOut
from app.schemas.base import ApiModel
from app.schemas.drafts import DayNumber, Time

Interest = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
PlaceName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class AIPlanIn(ApiModel):
    draft_id: uuid.UUID
    day_number: DayNumber
    start_time: Time
    end_time: Time
    interests: Annotated[list[Interest], Field(max_length=5)] = []
    must_visit: Annotated[list[PlaceName], Field(max_length=10)] = []
    avoid: Annotated[list[PlaceName], Field(max_length=10)] = []


class AIPlanItemOut(ApiModel):
    item_id: str
    destination_name: str
    time: str
    duration_minutes: int
    cost: float | None = None
    place_id: str | None
    verified: bool
    reason: str | None
    source: str
    attribution: str | None
    maps_url: str | None


class AIPlanOut(ApiModel):
    proposal_token: str
    valid_until: datetime
    day_number: int
    activities: list[AIPlanItemOut]
    warnings: list[str]


class BulkApplyIn(ApiModel):
    proposal_token: Annotated[str, StringConstraints(min_length=1, max_length=20_000)]
    selected_item_ids: Annotated[list[str], Field(min_length=1, max_length=10)]


class BulkApplyOut(ApiModel):
    activities: list[ActivityOut]
