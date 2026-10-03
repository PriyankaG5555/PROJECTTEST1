"""Draft, activity and finalize request/response bodies — api-contract-spec.md §5."""

import uuid
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated

from pydantic import AfterValidator, Field, StringConstraints

from app.schemas import ActivityOut, DraftOut, DraftSummaryOut
from app.schemas.base import ApiModel

DraftName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
DestinationName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
Time = Annotated[str, StringConstraints(pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$")]
DayNumber = Annotated[int, Field(ge=1, le=30)]


def _round_cost(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


Cost = Annotated[Decimal, Field(ge=0, le=10_000_000), AfterValidator(_round_cost)]


# ---------- Drafts ----------
class DraftCreateIn(ApiModel):
    name: DraftName
    copy_from_draft_id: uuid.UUID | None = None


class DraftRenameIn(ApiModel):
    name: DraftName


class DraftResponse(ApiModel):
    draft: DraftOut


class DraftSummaryResponse(ApiModel):
    draft: DraftSummaryOut


class DraftListResponse(ApiModel):
    drafts: list[DraftSummaryOut]


# ---------- Activities ----------
class ActivityCreateIn(ApiModel):
    day_number: DayNumber
    destination_name: DestinationName
    time: Time | None = None
    cost: Cost | None = None


class ActivityUpdateIn(ApiModel):
    """Omitted fields are unchanged; `null` clears time/cost/priority."""

    day_number: DayNumber | None = None
    destination_name: DestinationName | None = None
    time: Time | None = None
    cost: Cost | None = None


class ActivityResponse(ApiModel):
    activity: ActivityOut


# ---------- Finalize ----------
class FinalizeIn(ApiModel):
    draft_id: uuid.UUID
