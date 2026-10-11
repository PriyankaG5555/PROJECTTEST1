"""POST /telemetry/page-view — logged-in page views (observability-spec.md §3)."""

from typing import Annotated

from fastapi import APIRouter, Response, status
from pydantic import StringConstraints

from app import telemetry
from app.schemas.base import ApiModel
from app.security import CurrentUser

router = APIRouter(prefix="/telemetry", tags=["telemetry"])

RouteTemplate = Annotated[str, StringConstraints(max_length=100, pattern=r"^/[A-Za-z0-9/:_-]*$")]


class PageViewIn(ApiModel):
    route: RouteTemplate


@router.post("/page-view", status_code=status.HTTP_204_NO_CONTENT)
def page_view(body: PageViewIn, user: CurrentUser) -> Response:
    telemetry.PAGE_VIEWS.add(1, {"route": body.route})
    return Response(status_code=status.HTTP_204_NO_CONTENT)
