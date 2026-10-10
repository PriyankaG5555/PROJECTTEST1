"""Shared response schemas — api-contract-spec.md §3.

Request schemas live next to their routers as each phase adds endpoints.
"""

import uuid
from datetime import date, datetime

from pydantic import field_serializer

from app.models.enums import TripPriority, TripStatus, TripType
from app.schemas.base import ApiModel, to_camel

__all__ = [
    "ActivityOut",
    "ApiModel",
    "DayOut",
    "DraftOut",
    "DraftSummaryOut",
    "TripDetailOut",
    "TripOut",
    "UserOut",
    "to_camel",
]


def _money(value: float | None) -> float | None:
    return None if value is None else round(float(value), 2)


class UserOut(ApiModel):
    id: uuid.UUID
    username: str
    created_at: datetime


class TripOut(ApiModel):
    id: uuid.UUID
    destination: str
    start_date: date
    end_date: date
    trip_type: TripType
    top_priority: TripPriority | None
    budget: float | None
    status: TripStatus
    finalized_draft_id: uuid.UUID | None
    day_count: int
    draft_count: int
    created_at: datetime
    updated_at: datetime

    @field_serializer("budget")
    def _ser_budget(self, v: float | None) -> float | None:
        return _money(v)


class DraftSummaryOut(ApiModel):
    id: uuid.UUID
    name: str
    is_final: bool
    activity_count: int
    total_cost: float
    updated_at: datetime

    @field_serializer("total_cost")
    def _ser_total(self, v: float) -> float | None:
        return _money(v)


class TripDetailOut(TripOut):
    drafts: list[DraftSummaryOut]


class ActivityOut(ApiModel):
    id: uuid.UUID
    day_number: int
    destination_name: str
    time: str | None
    duration_minutes: int | None
    cost: float | None

    @field_serializer("cost")
    def _ser_cost(self, v: float | None) -> float | None:
        return _money(v)


class DayOut(ApiModel):
    day_number: int
    date: date
    total_cost: float
    activities: list[ActivityOut]

    @field_serializer("total_cost")
    def _ser_total(self, v: float) -> float | None:
        return _money(v)


class DraftOut(ApiModel):
    id: uuid.UUID
    trip_id: uuid.UUID
    name: str
    is_final: bool
    total_cost: float
    days: list[DayOut]
    created_at: datetime
    updated_at: datetime

    @field_serializer("total_cost")
    def _ser_total(self, v: float) -> float | None:
        return _money(v)
