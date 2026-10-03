"""Trip endpoints — api-contract-spec.md §5."""

from fastapi import APIRouter, Response, status

from app.errors import AppError
from app.models import Draft, TripStatus
from app.schemas.drafts import FinalizeIn
from app.schemas.trips import (
    TripCreateIn,
    TripListResponse,
    TripResponse,
    TripUpdateIn,
    TripUpdateResponse,
)
from app.security import CurrentUser, DbSession
from app.services import draft_service, trip_service
from app.services.ownership import get_owned_trip
from app.services.pdf_service import build_itinerary_pdf, pdf_filename

router = APIRouter(prefix="/trips", tags=["trips"])


@router.get("", response_model=TripListResponse)
def list_trips(
    user: CurrentUser, db: DbSession, status: TripStatus | None = None
) -> TripListResponse:
    return TripListResponse(trips=trip_service.list_trips(db, user, status))


@router.post("", status_code=status.HTTP_201_CREATED, response_model=TripResponse)
def create_trip(body: TripCreateIn, user: CurrentUser, db: DbSession) -> TripResponse:
    trip = trip_service.create_trip(db, user, body)
    return TripResponse(trip=trip_service.trip_detail(db, trip))


@router.get("/{trip_id}", response_model=TripResponse)
def get_trip(trip_id: str, user: CurrentUser, db: DbSession) -> TripResponse:
    trip = get_owned_trip(db, trip_id, user)
    return TripResponse(trip=trip_service.trip_detail(db, trip))


@router.patch("/{trip_id}", response_model=TripUpdateResponse)
def update_trip(
    trip_id: str, body: TripUpdateIn, user: CurrentUser, db: DbSession
) -> TripUpdateResponse:
    trip, deleted = trip_service.update_trip(db, user, trip_id, body)
    return TripUpdateResponse(
        trip=trip_service.trip_detail(db, trip), deleted_activity_count=deleted
    )


@router.post("/{trip_id}/finalize", response_model=TripResponse)
def finalize_trip(trip_id: str, body: FinalizeIn, user: CurrentUser, db: DbSession) -> TripResponse:
    trip = trip_service.finalize_trip(db, user, trip_id, body.draft_id)
    return TripResponse(trip=trip_service.trip_detail(db, trip))


@router.post("/{trip_id}/reopen", response_model=TripResponse)
def reopen_trip(trip_id: str, user: CurrentUser, db: DbSession) -> TripResponse:
    trip = trip_service.reopen_trip(db, user, trip_id)
    return TripResponse(trip=trip_service.trip_detail(db, trip))


@router.get("/{trip_id}/export.pdf", response_class=Response)
def export_pdf(trip_id: str, user: CurrentUser, db: DbSession) -> Response:
    trip = get_owned_trip(db, trip_id, user)
    if trip.status is not TripStatus.FINALIZED or trip.finalized_draft_id is None:
        raise AppError("TRIP_NOT_FINALIZED", 409, "Finalize this trip before exporting it.")
    draft = db.get(Draft, trip.finalized_draft_id)
    assert draft is not None  # finalized trips are locked, so the draft can't be deleted
    pdf = build_itinerary_pdf(
        trip_service.trip_detail(db, trip), draft_service.draft_out(db, draft)
    )
    filename = pdf_filename(trip.destination, trip.start_date.isoformat())
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trip(trip_id: str, user: CurrentUser, db: DbSession) -> Response:
    trip_service.delete_trip(db, user, trip_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
