"""Response shapes match api-contract-spec.md §3 (camelCase, money as numbers)."""

import uuid
from datetime import date
from decimal import Decimal

from app.schemas import ActivityOut, DayOut


def test_activity_serializes_camel_case_with_money_as_number() -> None:
    activity = ActivityOut(
        id=uuid.uuid4(),
        day_number=1,
        destination_name="Baga Beach",
        time="09:30",
        cost=Decimal("1250.50"),  # ORM gives Decimal
    )

    data = activity.model_dump(mode="json", by_alias=True)

    assert data["dayNumber"] == 1
    assert data["destinationName"] == "Baga Beach"
    assert data["cost"] == 1250.5
    assert "priority" not in data
    assert "day_number" not in data


def test_optional_fields_are_present_as_null() -> None:
    activity = ActivityOut(
        id=uuid.uuid4(), day_number=2, destination_name="Walk", time=None, cost=None
    )

    data = activity.model_dump(mode="json", by_alias=True)

    assert data["time"] is None and data["cost"] is None


def test_day_dates_are_iso_strings() -> None:
    day = DayOut(day_number=1, date=date(2026, 11, 14), total_cost=0, activities=[])

    data = day.model_dump(mode="json", by_alias=True)

    assert data == {"dayNumber": 1, "date": "2026-11-14", "totalCost": 0.0, "activities": []}
