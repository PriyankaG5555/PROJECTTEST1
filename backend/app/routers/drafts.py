"""Draft and activity endpoints — api-contract-spec.md §5."""

from fastapi import APIRouter, Response, status

from app.schemas import ActivityOut
from app.schemas.drafts import (
    ActivityCreateIn,
    ActivityResponse,
    ActivityUpdateIn,
    DraftCreateIn,
    DraftListResponse,
    DraftRenameIn,
    DraftResponse,
    DraftSummaryResponse,
)
from app.security import CurrentUser, DbSession
from app.services import activity_service, draft_service

router = APIRouter(tags=["drafts"])


# ---------- Drafts ----------
@router.get("/trips/{trip_id}/drafts", response_model=DraftListResponse)
def list_drafts(trip_id: str, user: CurrentUser, db: DbSession) -> DraftListResponse:
    return DraftListResponse(drafts=draft_service.list_drafts(db, user, trip_id))


@router.post(
    "/trips/{trip_id}/drafts", status_code=status.HTTP_201_CREATED, response_model=DraftResponse
)
def create_draft(
    trip_id: str, body: DraftCreateIn, user: CurrentUser, db: DbSession
) -> DraftResponse:
    draft = draft_service.create_draft(db, user, trip_id, body)
    return DraftResponse(draft=draft_service.draft_out(db, draft))


@router.get("/drafts/{draft_id}", response_model=DraftResponse)
def get_draft(draft_id: str, user: CurrentUser, db: DbSession) -> DraftResponse:
    draft = draft_service.get_draft(db, user, draft_id)
    return DraftResponse(draft=draft_service.draft_out(db, draft))


@router.patch("/drafts/{draft_id}", response_model=DraftSummaryResponse)
def rename_draft(
    draft_id: str, body: DraftRenameIn, user: CurrentUser, db: DbSession
) -> DraftSummaryResponse:
    draft = draft_service.rename_draft(db, user, draft_id, body.name)
    return DraftSummaryResponse(draft=draft_service.draft_summary(db, draft))


@router.delete("/drafts/{draft_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_draft(draft_id: str, user: CurrentUser, db: DbSession) -> Response:
    draft_service.delete_draft(db, user, draft_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Activities ----------
@router.post(
    "/drafts/{draft_id}/activities",
    status_code=status.HTTP_201_CREATED,
    response_model=ActivityResponse,
)
def add_activity(
    draft_id: str, body: ActivityCreateIn, user: CurrentUser, db: DbSession
) -> ActivityResponse:
    activity = activity_service.add_activity(db, user, draft_id, body)
    return ActivityResponse(activity=ActivityOut.model_validate(activity))


@router.patch("/activities/{activity_id}", response_model=ActivityResponse)
def update_activity(
    activity_id: str, body: ActivityUpdateIn, user: CurrentUser, db: DbSession
) -> ActivityResponse:
    activity = activity_service.update_activity(db, user, activity_id, body)
    return ActivityResponse(activity=ActivityOut.model_validate(activity))


@router.delete("/activities/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_activity(activity_id: str, user: CurrentUser, db: DbSession) -> Response:
    activity_service.delete_activity(db, user, activity_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
