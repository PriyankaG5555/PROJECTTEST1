"""Rule-based planner and OSM parsing — ai-feature.md §5 (pure unit tests, no network/DB)."""

from typing import Any

from app.models import TripPriority
from app.services.osm_service import normalize_pages, search_points
from app.services.planner_service import (
    DURATIONS,
    Plan,
    earliest_slot,
    plan_day,
    travel_minutes,
)
from tests.osm_fixtures import CALANGUTE, CASINO, FORT, MIRAMAR, MUSEUM, PLACES

NINE, SIX = 9 * 60, 18 * 60


def plan(**kwargs: Any) -> Plan:
    args: dict[str, Any] = {
        "must_visit": [],
        "avoid": [],
        "interests": [],
        "priority": None,
        "window": (NINE, SIX),
        "busy": [],
    }
    return plan_day(PLACES, **{**args, **kwargs})


def test_items_fit_window_without_overlap_and_with_travel_gaps() -> None:
    result = plan(window=(NINE, 13 * 60), busy=[(10 * 60, 10 * 60 + 30)])

    slots = [(i.start, i.start + i.duration) for i in result.items]
    assert slots and all(s >= NINE and e <= 13 * 60 for s, e in slots)
    assert all(not (s < 10 * 60 + 30 and e > 10 * 60) for s, e in slots)  # avoids busy block
    for a, b in zip(result.items, result.items[1:], strict=False):
        assert b.start >= a.start + a.duration + travel_minutes(a.place, b.place) - 5
    assert all(i.start % 5 == 0 for i in result.items)


def test_durations_come_from_category_table() -> None:
    first = plan().items[0]

    assert first.name == "Fort Aguada" and first.duration == DURATIONS["Fort"] == 90


def test_budget_priority_prefers_free_places() -> None:
    items = plan(priority=TripPriority.BUDGET).items
    names = [i.name for i in items]

    assert names[0] == "Calangute Beach" and "Miramar Beach" in names
    assert "free to visit" in items[0].reason


def test_time_priority_has_at_most_four_stops() -> None:
    assert len(plan(priority=TripPriority.TIME).items) <= 3


def test_interests_boost_matching_places() -> None:
    assert plan(interests=["museums"]).items[0].name == "Goa State Museum"


def test_avoided_places_are_excluded() -> None:
    assert "Casino Royale" not in [i.name for i in plan(avoid=["casino"]).items]


def test_must_visit_first_matched_to_map_or_unverified() -> None:
    result = plan(must_visit=["miramar", "Aunty's Cafe"])

    assert [i.name for i in result.items][:2] == ["Miramar Beach", "Aunty's Cafe"]
    assert result.items[0].place is MIRAMAR and result.items[1].place is None
    assert "must-visit" in result.items[0].reason


def test_must_visit_that_cannot_fit_is_reported() -> None:
    result = plan(must_visit=["Goa State Museum"], window=(NINE, NINE + 60))

    assert result.items == [] or result.items[0].name != "Goa State Museum"
    assert any("Goa State Museum" in w for w in result.warnings)


def test_reasons_mention_distance_from_previous_stop() -> None:
    reasons = [i.reason for i in plan().items]

    assert "km from the previous stop" in reasons[1]


def test_earliest_slot_skips_taken_time() -> None:
    assert earliest_slot(NINE, 60, (NINE, SIX), [(NINE, NINE + 45)]) == NINE + 45
    assert earliest_slot(NINE, 600, (NINE, SIX), []) is None


def test_travel_minutes_rounded_with_buffer() -> None:
    minutes = travel_minutes(FORT, CALANGUTE)  # ~6 km

    assert minutes % 5 == 0 and 20 <= minutes <= 30
    assert travel_minutes(None, MUSEUM) == 15
    assert CASINO["notability"] == 1  # fixture sanity


def test_normalize_wikipedia_pages() -> None:
    pages = [
        {
            "pageid": 1,
            "title": "Fort Aguada",
            "description": "Historic site in Goa, India",
            "coordinates": [{"lat": 15.49, "lon": 73.77}],
            "length": 25000,
        },
        {
            "pageid": 2,
            "title": "Calangute",
            "description": "Town in Goa, India",
            "coordinates": [{"lat": 15.54, "lon": 73.76}],
            "length": 9000,
        },  # a town, not a visit
        {
            "pageid": 3,
            "title": "Calangute Beach",
            "description": "",
            "coordinates": [{"lat": 15.54, "lon": 73.75}],
            "length": 500,
        },
        {"pageid": 4, "title": "Some Chapel", "description": "Church in Goa"},  # no coordinates
        {
            "pageid": 5,
            "title": "Hidden Spot",
            "description": "",
            "category_hint": "Waterfall",
            "coordinates": [{"lat": 15.3, "lon": 74.3}],
        },
    ]

    places = normalize_pages(pages)

    assert [p["name"] for p in places] == ["Fort Aguada", "Calangute Beach", "Hidden Spot"]
    fort = places[0]
    assert (
        fort["place_id"] == "wikipedia:1" and fort["category"] == "Fort" and fort["notability"] == 4
    )
    assert fort["url"].startswith("https://www.openstreetmap.org/?mlat=15.49&mlon=73.77")
    assert fort["wiki_url"] == "https://en.wikipedia.org/wiki/Fort_Aguada"
    assert places[1]["category"] == "Beach" and places[1]["free"] is True
    assert places[2]["category"] == "Waterfall"


def test_large_areas_are_searched_at_five_points() -> None:
    assert len(search_points([15.40, 15.45, 73.80, 73.85])) == 1  # a town
    goa = search_points([14.752, 15.800, 73.675, 74.336])
    assert len(goa) == 5 and all(14.75 <= lat <= 15.80 for lat, _ in goa)
