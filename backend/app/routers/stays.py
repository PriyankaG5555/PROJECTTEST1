"""Stay endpoints by ID — api-contract-spec.md (stays)."""

from fastapi import APIRouter, Response, status

from app.schemas import StayOut
from app.schemas.stays import StayResponse, StayUpdateIn
from app.security import CurrentUser, DbSession
from app.services import stay_service

router = APIRouter(prefix="/stays", tags=["stays"])


@router.patch("/{stay_id}", response_model=StayResponse)
def update_stay(stay_id: str, body: StayUpdateIn, user: CurrentUser, db: DbSession) -> StayResponse:
    stay = stay_service.update_stay(db, user, stay_id, body)
    return StayResponse(stay=StayOut.model_validate(stay))


@router.delete("/{stay_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_stay(stay_id: str, user: CurrentUser, db: DbSession) -> Response:
    stay_service.delete_stay(db, user, stay_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
