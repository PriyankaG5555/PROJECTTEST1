"""GET /health — see api-contract-spec.md §5."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    # Phase 1 adds the database check that returns 503 {"status": "degraded"}.
    return {"status": "ok"}
