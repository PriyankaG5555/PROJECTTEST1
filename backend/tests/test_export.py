"""PDF export — api-contract-spec.md §5 and pdf_service formatting."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.models.enums import Priority, TripStatus, TripType
from app.schemas import ActivityOut, DayOut, DraftOut, TripOut
from app.services.pdf_service import build_itinerary_pdf, format_inr, pdf_filename
from tests.helpers import API, add_activity, create_trip, finalize, first_draft_id


@pytest.mark.parametrize(
    ("amount", "text"),
    [
        (0, "₹0.00"),
        (1250.5, "₹1,250.50"),
        (123456, "₹1,23,456.00"),
        (12345678.9, "₹1,23,45,678.90"),
    ],
)
def test_indian_number_format(amount: float, text: str) -> None:
    assert format_inr(Decimal(str(amount))) == text


def test_filename_replaces_unsafe_characters() -> None:
    assert pdf_filename("North Goa / Panjim!", "2026-11-14") == (
        "GhumakkadYatri-North-Goa-Panjim-2026-11-14.pdf"
    )


def _sample(days: int) -> tuple[TripOut, DraftOut]:
    now = datetime.now(UTC)
    trip = TripOut(
        id=uuid.uuid4(),
        destination="Goa",
        start_date=date(2026, 11, 1),
        end_date=date(2026, 11, days),
        trip_type=TripType.FRIENDS,
        status=TripStatus.FINALIZED,
        finalized_draft_id=None,
        day_count=days,
        draft_count=1,
        created_at=now,
        updated_at=now,
    )
    activity = ActivityOut(
        id=uuid.uuid4(),
        day_number=1,
        destination_name="Baga Beach & Fort <Aguada>",
        time="09:30",
        cost=Decimal("1250.50"),
        priority=Priority.HIGH,
    )
    day_list = [
        DayOut(
            day_number=n,
            date=date(2026, 11, n),
            total_cost=Decimal("1250.50") * 3,
            activities=[activity, activity, activity] if n % 2 else [],
        )
        for n in range(1, days + 1)
    ]
    draft = DraftOut(
        id=uuid.uuid4(),
        trip_id=trip.id,
        name="Draft 1",
        is_final=True,
        total_cost=Decimal("56272.50"),
        days=day_list,
        created_at=now,
        updated_at=now,
    )
    return trip, draft


def test_pdf_builds_for_a_30_day_trip_quickly() -> None:
    trip, draft = _sample(30)
    started = datetime.now(UTC)

    pdf = build_itinerary_pdf(trip, draft)

    assert pdf.startswith(b"%PDF-") and len(pdf) > 2000
    assert (datetime.now(UTC) - started).total_seconds() < 3


def test_export_finalized_trip(logged_in_client: TestClient) -> None:
    trip = create_trip(logged_in_client)
    add_activity(logged_in_client, first_draft_id(trip), time="09:30", cost=300)
    finalize(logged_in_client, trip)

    response = logged_in_client.get(f"{API}/trips/{trip['id']}/export.pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == (
        'attachment; filename="GhumakkadYatri-Goa-2026-11-14.pdf"'
    )
    assert response.content.startswith(b"%PDF-")


def test_export_draft_trip_rejected(logged_in_client: TestClient) -> None:
    trip = create_trip(logged_in_client)

    response = logged_in_client.get(f"{API}/trips/{trip['id']}/export.pdf")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "TRIP_NOT_FINALIZED"


def test_export_other_users_trip_not_found(
    logged_in_client: TestClient, other_user_client: TestClient
) -> None:
    trip = create_trip(logged_in_client)
    finalize(logged_in_client, trip)

    assert other_user_client.get(f"{API}/trips/{trip['id']}/export.pdf").status_code == 404
