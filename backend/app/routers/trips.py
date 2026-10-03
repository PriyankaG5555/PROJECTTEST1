"""Trip endpoints — api-contract-spec.md §5."""

from fastapi import APIRouter, Response, status

from app.models import TripStatus
from app.schemas.trips import (
    TripCreateIn,
    TripListResponse,
    TripResponse,
    TripUpdateIn,
    TripUpdateResponse,
)
from app.security import CurrentUser, DbSession
from app.services import trip_service
from app.services.ownership import get_owned_trip

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


@router.delete("/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trip(trip_id: str, user: CurrentUser, db: DbSession) -> Response:
    trip_service.delete_trip(db, user, trip_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
