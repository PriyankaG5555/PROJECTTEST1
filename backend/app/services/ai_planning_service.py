"""AI day planning: generate a transient proposal, apply selected items once (ai-feature.md)."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from sqlalchemy import delete, func, literal, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_engine
from app.errors import AppError, not_found, validation_error
from app.models import Activity, AIPlanApplication, AIPlanUsage, Draft, Trip, User
from app.schemas.ai_planning import AIPlanIn, AIPlanItemOut, AIPlanOut, BulkApplyIn
from app.services import ai_providers, suggestion_service
from app.services.draft_service import touch
from app.services.ownership import assert_editable, get_owned_draft, get_owned_trip

TOKEN_TYPE = "ai_proposal"
TOKEN_TTL = timedelta(minutes=15)
MAX_ITEMS = 10
MIN_DURATION, MAX_DURATION = 15, 600
TRAVEL_WARNING = "Travel time between places is not verified — leave extra time to move around."
DURATION_NOTE = "Visit durations are AI estimates. Check opening hours and prices with each place."

Interval = tuple[int, int]


def _min(hhmm: str) -> int:
    return int(hhmm[:2]) * 60 + int(hhmm[3:])


def _hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def unavailable() -> AppError:
    return AppError(
        "AI_PLANNING_UNAVAILABLE",
        503,
        "AI planning isn't available right now. You can still add activities yourself.",
    )


def out_of_date() -> AppError:
    return AppError(
        "AI_PROPOSAL_INVALID",
        409,
        "This plan is out of date or was already used. Generate a new one.",
    )


# ---------- Fixed schedule constraints ----------
def busy_intervals(
    activities: list[Activity], window: Interval
) -> tuple[list[Interval], list[str]]:
    """Existing timed activities as busy blocks. Unknown durations block the rest of the window."""
    busy: list[Interval] = []
    warnings: list[str] = []
    for a in activities:
        if a.time is None:
            continue
        start = _min(a.time)
        if a.duration_minutes is not None:
            busy.append((start, start + a.duration_minutes))
        else:
            busy.append((start, max(window[1], start + 1)))
            warnings.append(
                f"“{a.destination_name}” at {a.time} has no duration, so the rest of the day "
                "after it is kept free. Add a duration and generate again to plan around it."
            )
    return busy, warnings


def _overlaps(a: Interval, b: Interval) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def _day_activities(db: Session, draft_id: uuid.UUID, day: int) -> list[Activity]:
    return list(
        db.scalars(
            select(Activity).where(Activity.draft_id == draft_id, Activity.day_number == day)
        )
    )


def _count_request(user: User, limit: int) -> None:
    upsert = (
        insert(AIPlanUsage)
        .values(user_id=user.id, day=datetime.now(UTC).date(), count=1)
        .on_conflict_do_update(
            index_elements=[AIPlanUsage.user_id, AIPlanUsage.day],
            set_={"count": AIPlanUsage.count + literal(1)},
        )
        .returning(AIPlanUsage.count)
    )
    with get_engine().begin() as conn:  # own transaction: counts even when providers fail
        count = conn.execute(upsert).scalar_one()
    if count > limit:
        raise AppError(
            "RATE_LIMITED", 429, f"You've used today's {limit} AI plans. Try again tomorrow."
        )


def _candidates(trip: Trip, data: AIPlanIn) -> list[dict[str, Any]]:
    settings = get_settings()
    if settings.ai_location_provider != "google_places" or not settings.google_places_api_key:
        return []  # only the traveller's must-visit names can be scheduled (unverified)
    query = trip.destination + (f" {', '.join(data.interests)}" if data.interests else "")
    try:
        raw = suggestion_service.fetch_places(query, settings.google_places_api_key)
    except (OSError, ValueError) as exc:  # URLError and timeouts are OSErrors
        raise unavailable() from exc
    avoid = [a.lower() for a in data.avoid]
    places = [suggestion_service.normalize(p) for p in raw if p.get("displayName")]
    return [p for p in places if not any(a in p["name"].lower() for a in avoid)]


# ---------- Generate ----------
def generate(db: Session, user: User, trip_id: str, data: AIPlanIn) -> AIPlanOut:
    trip = get_owned_trip(db, trip_id, user)
    draft = db.get(Draft, data.draft_id)
    if draft is None or draft.trip_id != trip.id:
        raise not_found()
    assert_editable(trip)
    if data.day_number > trip.day_count:
        raise validation_error("dayNumber", f"Choose a day between 1 and {trip.day_count}.")
    window = (_min(data.start_time), _min(data.end_time))
    if window[1] <= window[0]:
        raise validation_error("endTime", "End time must be after the start time.")

    settings = get_settings()
    if settings.ai_llm_provider is None or not settings.ai_llm_api_key:
        raise unavailable()
    _count_request(user, settings.ai_plan_daily_limit)

    busy, warnings = busy_intervals(_day_activities(db, draft.id, data.day_number), window)
    candidates = _candidates(trip, data)
    context = {
        "destination": trip.destination,
        "date": (trip.start_date + timedelta(days=data.day_number - 1)).isoformat(),
        "time_window": {"start": data.start_time, "end": data.end_time},
        "fixed_busy_blocks": [{"start": _hhmm(s), "end": _hhmm(e)} for s, e in busy],
        "candidates": [
            {
                "candidate_index": i,
                "name": c["name"],
                "rating": c["rating"],
                "price_level": c["price_level"],
            }
            for i, c in enumerate(candidates)
        ],
        "must_visit": data.must_visit,
        "interests": data.interests,
        "top_priority": trip.top_priority.value if trip.top_priority else None,
        "budget_inr": float(trip.budget) if trip.budget is not None else None,
    }
    try:
        plan = ai_providers.plan_with_llm(context)
    except ai_providers.ProviderUnavailable:
        raise unavailable() from None

    items = _validate_plan(plan, candidates, data, window, busy)
    if not items:
        warnings.append(
            "No suggestions fit this time window. Try a longer window or fewer constraints."
        )
    proposal_id = uuid.uuid4()
    valid_until = datetime.now(UTC) + TOKEN_TTL
    token = jwt.encode(
        {
            "typ": TOKEN_TYPE,
            "pid": str(proposal_id),
            "sub": str(user.id),
            "trip": str(trip.id),
            "draft": str(draft.id),
            "day": data.day_number,
            "window": [data.start_time, data.end_time],
            "items": [
                {
                    "id": i.item_id,
                    "name": i.destination_name,
                    "time": i.time,
                    "duration": i.duration_minutes,
                }
                for i in items
            ],
            "exp": valid_until,
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    return AIPlanOut(
        proposal_token=token,
        valid_until=valid_until,
        day_number=data.day_number,
        activities=items,
        warnings=[*warnings, TRAVEL_WARNING, DURATION_NOTE],
    )


def _validate_plan(
    plan: ai_providers.LLMPlan,
    candidates: list[dict[str, Any]],
    data: AIPlanIn,
    window: Interval,
    busy: list[Interval],
) -> list[AIPlanItemOut]:
    """Reject the whole plan if any item is ungrounded or does not fit (ai-feature.md §4)."""
    if len(plan.items) > MAX_ITEMS:
        raise unavailable()
    must_visit = {m.lower(): m for m in data.must_visit}
    avoid = [a.lower() for a in data.avoid]
    taken: list[Interval] = list(busy)
    items: list[AIPlanItemOut] = []
    for n, item in enumerate(sorted(plan.items, key=lambda i: i.start_time), start=1):
        if item.candidate_index is not None:
            if not 0 <= item.candidate_index < len(candidates):
                raise unavailable()
            place = candidates[item.candidate_index]
            name, verified = place["name"], True
        elif item.must_visit_name and item.must_visit_name.strip().lower() in must_visit:
            place, name, verified = None, must_visit[item.must_visit_name.strip().lower()], False
        else:
            raise unavailable()  # invented place
        if any(a in name.lower() for a in avoid):
            raise unavailable()
        try:
            start = _min(item.start_time)
            valid_time = len(item.start_time) == 5 and item.start_time[2] == ":"
        except ValueError:
            raise unavailable() from None
        if not valid_time or not MIN_DURATION <= item.duration_minutes <= MAX_DURATION:
            raise unavailable()
        slot = (start, start + item.duration_minutes)
        if slot[0] < window[0] or slot[1] > window[1] or any(_overlaps(slot, t) for t in taken):
            raise unavailable()
        taken.append(slot)
        items.append(
            AIPlanItemOut(
                item_id=f"item-{n}",
                destination_name=name[:100],
                time=_hhmm(start),
                duration_minutes=item.duration_minutes,
                cost=None,  # the LLM never sets or estimates costs
                place_id=place["place_id"] if place else None,
                verified=verified,
                reason=item.reason.strip()[:200] or None,
                source="Google Places" if verified else "Your must-visit list",
                attribution="Powered by Google" if verified else None,
                maps_url=place["maps_url"] if place else None,
            )
        )
    return items


# ---------- Apply ----------
def apply(db: Session, user: User, draft_id: str, data: BulkApplyIn) -> list[Activity]:
    draft = get_owned_draft(db, draft_id, user)
    try:
        claims = jwt.decode(
            data.proposal_token,
            get_settings().jwt_secret,
            algorithms=["HS256"],
            options={"require": ["exp", "pid", "sub", "typ"]},
        )
    except jwt.PyJWTError:
        raise out_of_date() from None
    trip = draft.trip
    if (
        claims["typ"] != TOKEN_TYPE
        or claims["sub"] != str(user.id)
        or claims.get("draft") != str(draft.id)
        or claims.get("trip") != str(trip.id)
    ):
        raise out_of_date()
    assert_editable(trip)

    selected = data.selected_item_ids
    by_id = {i["id"]: i for i in claims.get("items", [])}
    if len(set(selected)) != len(selected) or any(s not in by_id for s in selected):
        raise validation_error("selectedItemIds", "Choose items from this plan, each once.")

    day = int(claims["day"])
    if day > trip.day_count:
        raise out_of_date()
    window = (_min(claims["window"][0]), _min(claims["window"][1]))
    busy, _ = busy_intervals(_day_activities(db, draft.id, day), window)
    for item_id in selected:
        start = _min(by_id[item_id]["time"])
        if any(_overlaps((start, start + by_id[item_id]["duration"]), b) for b in busy):
            raise out_of_date()  # the day changed since the plan was generated

    db.execute(
        delete(AIPlanApplication).where(
            AIPlanApplication.applied_at < func.now() - timedelta(days=1)
        )
    )
    db.add(AIPlanApplication(proposal_id=uuid.UUID(claims["pid"]), user_id=user.id))
    try:
        db.flush()  # primary key makes each proposal single-use, even under concurrency
    except IntegrityError:
        db.rollback()
        raise out_of_date() from None

    added = [
        Activity(
            draft_id=draft.id,
            day_number=day,
            destination_name=by_id[i]["name"],
            time=by_id[i]["time"],
            duration_minutes=by_id[i]["duration"],
        )
        for i in selected
    ]
    db.add_all(added)
    touch(trip, draft)
    db.flush()
    for activity in added:
        db.refresh(activity)
    return added
