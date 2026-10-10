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
from app.models import Activity, AIPlanApplication, AIPlanUsage, Draft, User
from app.schemas.ai_planning import AIPlanIn, AIPlanItemOut, AIPlanOut, BulkApplyIn
from app.services import osm_service, planner_service
from app.services.draft_service import touch
from app.services.ownership import assert_editable, get_owned_draft, get_owned_trip

TOKEN_TYPE = "ai_proposal"
TOKEN_TTL = timedelta(minutes=15)
TRAVEL_WARNING = (
    "Travel times are estimated from straight-line distance (about 25 km/h plus 10 minutes) "
    "— check routes before you go."
)
DURATION_NOTE = "Visit durations are estimates. Check opening hours and prices with each place."

Interval = tuple[int, int]


def _min(hhmm: str) -> int:
    return int(hhmm[:2]) * 60 + int(hhmm[3:])


def _hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def unavailable() -> AppError:
    return AppError(
        "AI_PLANNING_UNAVAILABLE",
        503,
        "Day planning isn't available right now (map data didn't respond). "
        "You can still add activities yourself.",
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


def _with_must_visit_places(
    places: list[dict[str, Any]], destination: str, must_visit: list[str]
) -> list[dict[str, Any]]:
    """Look up must-visit places that are not among the destination's places (best effort)."""
    extra: list[dict[str, Any]] = []
    for name in must_visit:
        low = name.lower()
        if any(low in p["name"].lower() or p["name"].lower() in low for p in places + extra):
            continue
        try:
            found = osm_service.lookup_place(name, destination, places)
        except osm_service.OSMUnavailable:
            continue  # stays an unverified must-visit place
        if found is not None:
            extra.append(found)
    return places + extra


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

    _count_request(user, get_settings().ai_plan_daily_limit)
    busy, warnings = busy_intervals(_day_activities(db, draft.id, data.day_number), window)
    try:
        places = osm_service.places_for(db, trip.destination)
    except osm_service.OSMUnavailable:
        raise unavailable() from None
    places = _with_must_visit_places(places, trip.destination, data.must_visit)
    if not places:
        warnings.append(
            f"We couldn't find places for “{trip.destination}” on the map, so only your "
            "must-visit places can be planned."
        )
    plan = planner_service.plan_day(
        places,
        must_visit=data.must_visit,
        avoid=data.avoid,
        interests=data.interests,
        priority=trip.top_priority,
        window=window,
        busy=busy,
    )
    warnings.extend(plan.warnings)
    items = [
        AIPlanItemOut(
            item_id=f"item-{n}",
            destination_name=i.name[:100],
            time=_hhmm(i.start),
            duration_minutes=i.duration,
            cost=None,  # the planner never sets or estimates costs
            place_id=i.place["place_id"] if i.place else None,
            verified=i.place is not None,
            reason=i.reason[:200],
            source="Wikipedia" if i.place else "Your must-visit list",
            attribution=osm_service.ATTRIBUTION if i.place else None,
            maps_url=i.place["url"] if i.place else None,
        )
        for n, i in enumerate(plan.items, start=1)
    ]
    if any(not i.verified for i in items):
        warnings.append(
            "Unverified places weren't found on the map — check their location yourself."
        )
    if not items:
        warnings.append(
            "No suggestions fit this time window. Try a longer window or fewer constraints."
        )

    settings = get_settings()
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
