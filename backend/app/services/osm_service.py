"""Free, keyless place data: OpenStreetMap Nominatim finds the destination; Wikipedia GeoSearch
lists notable places around it (ai-feature.md §5, backend-spec §7).

Fair use: identifying User-Agent, a handful of requests per destination, results cached 7 days in
`place_cache`. Attribution is required (Wikipedia CC BY-SA, OpenStreetMap ODbL).
"""

import json
import logging
import math
import urllib.parse
import urllib.request
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app import telemetry
from app.config import get_settings
from app.models import DestinationCache, PlaceCache

logger = logging.getLogger("app.places")

ATTRIBUTION = "Places: Wikipedia (CC BY-SA) · Location: © OpenStreetMap contributors"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
WIKIPEDIA_URL = "https://en.wikipedia.org/w/api.php"
TIMEOUT_SECONDS = 15
SEARCH_RADIUS_METRES = 10_000  # Wikipedia GeoSearch maximum
LARGE_AREA_DEGREES = 0.15  # bigger destinations are searched at 5 points
MAX_AREA_DEGREES = 1.0
CACHE_DAYS = 7
MAX_PLACES = 60

# Description/title keyword -> category. First match wins.
CATEGORY_RULES: list[tuple[str, str]] = [
    ("fort", "Fort"),
    ("castle", "Castle"),
    ("palace", "Palace"),
    ("museum", "Museum"),
    ("art gallery", "Gallery"),
    ("beach", "Beach"),
    ("waterfall", "Waterfall"),
    (" falls", "Waterfall"),
    ("basilica", "Place of worship"),
    ("cathedral", "Place of worship"),
    ("church", "Place of worship"),
    ("chapel", "Place of worship"),
    ("temple", "Place of worship"),
    ("mosque", "Place of worship"),
    ("shrine", "Place of worship"),
    ("convent", "Place of worship"),
    ("monastery", "Place of worship"),
    ("gurdwara", "Place of worship"),
    ("religious monument", "Place of worship"),
    ("wildlife sanctuary", "Nature reserve"),
    ("bird sanctuary", "Nature reserve"),
    ("national park", "Nature reserve"),
    ("nature reserve", "Nature reserve"),
    ("zoo", "Zoo"),
    ("aquarium", "Aquarium"),
    ("garden", "Garden"),
    ("park", "Park"),
    ("lake", "Lake"),
    ("viewpoint", "Viewpoint"),
    ("lighthouse", "Landmark"),
    ("monument", "Monument"),
    ("memorial", "Memorial"),
    ("ruins", "Ruins"),
    ("archaeological", "Archaeological site"),
    ("historic site", "Historic site"),
    ("heritage", "Historic site"),
    ("market", "Market"),
]
# Places that are not visits in themselves (unless the title names an attraction).
EXCLUDE = (
    "city",
    "town",
    "village",
    "district",
    "taluka",
    "neighborhood",
    "neighbourhood",
    "river",
    "institute",
    "university",
    "school",
    "college",
    "hospital",
    "company",
    "station",
    "airport",
    "constituency",
    "bridge",
    "road",
    "highway",
    "residence",
    "government",
    "facility",
    "island",
    "suburb",
    "census",
    "municipality",
    "panchayat",
    "headquarters",
    "office",
    "court",
)
FREE_CATEGORIES = {
    "Beach",
    "Park",
    "Garden",
    "Viewpoint",
    "Monument",
    "Memorial",
    "Place of worship",
    "Lake",
    "Landmark",
    "Market",
    "Historic site",
}


# Attraction-type sub-categories of "Category:Tourist attractions in X" -> category hint.
SUBCATEGORY_HINTS: list[tuple[str, str]] = [
    ("beach", "Beach"),
    ("fort", "Fort"),
    ("castle", "Castle"),
    ("palace", "Palace"),
    ("museum", "Museum"),
    ("temple", "Place of worship"),
    ("church", "Place of worship"),
    ("mosque", "Place of worship"),
    ("cathedral", "Place of worship"),
    ("waterfall", "Waterfall"),
    ("lake", "Lake"),
    ("protected area", "Nature reserve"),
    ("wildlife", "Nature reserve"),
    ("national park", "Nature reserve"),
    ("park", "Park"),
    ("garden", "Garden"),
    ("monument", "Monument"),
    ("archaeological", "Archaeological site"),
    ("zoo", "Zoo"),
    ("cave", "Historic site"),
    ("heritage", "Historic site"),
    ("market", "Market"),
]
MAX_SUBCATEGORIES = 10


class OSMUnavailable(Exception):
    """Nominatim or Wikipedia failed or timed out."""


def _user_agent() -> str:
    return f"GhumakkadYatri/1.0 (+{get_settings().osm_contact})"


def _get_json(url: str, params: dict[str, Any], timeout: float = TIMEOUT_SECONDS) -> Any:
    request = urllib.request.Request(
        f"{url}?{urllib.parse.urlencode(params)}", headers={"User-Agent": _user_agent()}
    )
    service = "nominatim" if "nominatim" in url else "wikipedia"
    try:
        with (
            telemetry.external_call(service),
            urllib.request.urlopen(  # noqa: S310
                request, timeout=timeout
            ) as response,
        ):
            return json.load(response)
    except (OSError, ValueError) as exc:  # URLError, HTTP errors, timeouts, bad JSON
        logger.warning("place data request failed", extra={"error": type(exc).__name__})
        raise OSMUnavailable from exc


def nominatim_search(
    query: str, limit: int = 1, extratags: bool = False, viewbox: str | None = None
) -> list[dict[str, Any]]:
    """Nominatim search; with viewbox ("west,north,east,south") results stay inside that area."""
    params: dict[str, Any] = {"q": query, "format": "jsonv2", "limit": limit}
    if extratags:
        params["extratags"] = 1
    if viewbox:
        params.update(viewbox=viewbox, bounded=1)
    result: list[dict[str, Any]] = _get_json(NOMINATIM_URL, params)
    return result


# Nominatim addresstype -> destination type for telemetry (observability-spec.md §2.2).
DESTINATION_KINDS = {
    "country": "country",
    "state": "state",
    "province": "state",
    "region": "state",
    "state_district": "state",
    "city": "city",
    "municipality": "city",
    "town": "town",
    "village": "village",
    "hamlet": "village",
    "suburb": "village",
}


def resolve_destination(db: Session, destination: str) -> dict[str, Any]:
    """Destination type and country, cached 30 days. Never raises; 'unknown' on failure."""
    key = destination.strip().lower()[:100]
    row = db.scalar(
        select(DestinationCache).where(
            DestinationCache.destination_key == key,
            DestinationCache.fetched_at > func.now() - timedelta(days=30),
        )
    )
    if row is not None:
        return {"kind": row.kind, "country": row.country}
    info: dict[str, Any] = {"kind": "unknown", "country": None}
    try:
        found = _get_json(
            NOMINATIM_URL,
            {"q": destination, "format": "jsonv2", "limit": 1, "addressdetails": 1},
            timeout=3,
        )
        if found:
            info = {
                "kind": DESTINATION_KINDS.get(found[0].get("addresstype", ""), "other"),
                "country": (found[0].get("address") or {}).get("country"),
            }
    except OSMUnavailable:
        return info  # not cached, so it is retried next time
    db.execute(
        insert(DestinationCache)
        .values(
            destination_key=key, kind=info["kind"], country=info["country"], fetched_at=func.now()
        )
        .on_conflict_do_update(
            index_elements=[DestinationCache.destination_key],
            set_={"kind": info["kind"], "country": info["country"], "fetched_at": func.now()},
        )
    )
    return info


def search_points(bbox: list[float]) -> list[tuple[float, float]]:
    """Centre only for small places; centre + 4 quadrant centres for large areas (capped)."""
    south, north, west, east = bbox
    lat, lon = (south + north) / 2, (west + east) / 2
    half_lat = min((north - south) / 2, MAX_AREA_DEGREES / 2)
    half_lon = min((east - west) / 2, MAX_AREA_DEGREES / 2)
    if max(half_lat, half_lon) * 2 <= LARGE_AREA_DEGREES:
        return [(lat, lon)]
    q_lat, q_lon = half_lat / 2, half_lon / 2
    return [(lat, lon)] + [(lat + a * q_lat, lon + b * q_lon) for a in (-1, 1) for b in (-1, 1)]


def fetch_places(destination: str) -> list[dict[str, Any]]:
    """Live lookup (no cache). Separate function so tests can replace it."""
    found = _get_json(NOMINATIM_URL, {"q": destination, "format": "jsonv2", "limit": 1})
    if not found:
        return []
    bbox = [float(x) for x in found[0]["boundingbox"]]  # south, north, west, east
    pages: dict[int, dict[str, Any]] = {}
    for lat, lon in search_points(bbox):
        result = _get_json(
            WIKIPEDIA_URL,
            {
                "action": "query",
                "format": "json",
                "formatversion": 2,
                "generator": "geosearch",
                "ggscoord": f"{lat:.5f}|{lon:.5f}",
                "ggsradius": SEARCH_RADIUS_METRES,
                "ggslimit": 500,
                "ggsprimary": "primary",
                "colimit": "max",
                "prop": "coordinates|description|info",
            },
        )
        for page in result.get("query", {}).get("pages", []):
            pages[page["pageid"]] = page
    for page in category_pages(found[0].get("name") or destination):
        pages.setdefault(page["pageid"], page)
    return normalize_pages(list(pages.values()))


def _category_members(title: str) -> list[dict[str, Any]]:
    result = _get_json(
        WIKIPEDIA_URL,
        {
            "action": "query",
            "format": "json",
            "formatversion": 2,
            "generator": "categorymembers",
            "gcmtitle": title,
            "gcmlimit": 200,
            "gcmtype": "page|subcat",
            "prop": "coordinates|description|info",
            "colimit": "max",
        },
    )
    pages: list[dict[str, Any]] = result.get("query", {}).get("pages", [])
    return pages


def category_pages(place_name: str) -> list[dict[str, Any]]:
    """Pages in "Category:Tourist attractions in <place>" plus attraction-type sub-categories."""
    members = _category_members(f"Category:Tourist attractions in {place_name}")
    pages = [p for p in members if p.get("ns") == 0]
    subcats = [p["title"] for p in members if p.get("ns") == 14]
    hinted = [
        (title, hint)
        for title in subcats
        for word, hint in SUBCATEGORY_HINTS
        if word in title.lower()
    ]
    seen: set[str] = set()
    for title, hint in hinted:
        if title in seen or len(seen) >= MAX_SUBCATEGORIES:
            continue
        seen.add(title)
        for page in _category_members(title):
            if page.get("ns") == 0:
                pages.append({**page, "category_hint": hint})
    return pages


def classify(title: str, description: str) -> str | None:
    text = f" {title} {description} ".lower()
    category = next((label for word, label in CATEGORY_RULES if word in text), None)
    if category is None:
        return None
    title_names_attraction = any(word in f" {title.lower()} " for word, _ in CATEGORY_RULES)
    if not title_names_attraction and any(w in description.lower() for w in EXCLUDE):
        return None
    return category


def normalize_pages(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Wikipedia GeoSearch pages -> places (attractions only), most notable first."""
    places = []
    for page in pages:
        title = page.get("title", "")
        coords = (page.get("coordinates") or [{}])[0]
        category = classify(title, page.get("description") or "") or page.get("category_hint")
        if not title or category is None or "lat" not in coords:
            continue
        length = int(page.get("length") or 0)
        places.append(
            {
                "place_id": f"wikipedia:{page['pageid']}",
                "name": title[:100],
                "category": category,
                "lat": float(coords["lat"]),
                "lon": float(coords["lon"]),
                # Every place has a Wikipedia article (notable); longer articles rank higher.
                "notability": 3 + min(3, int(math.log10(max(length, 1)) - 3))
                if length > 1000
                else 3,
                "free": category in FREE_CATEGORIES,
                "address": None,
                "url": f"https://www.openstreetmap.org/?mlat={coords['lat']}&mlon={coords['lon']}#map=16/"
                f"{coords['lat']}/{coords['lon']}",
                "wiki_url": "https://en.wikipedia.org/wiki/"
                + urllib.parse.quote(title.replace(" ", "_")),
            }
        )
    places.sort(key=lambda p: (-p["notability"], p["name"]))
    return places[:MAX_PLACES]


def places_for(db: Session, destination: str) -> list[dict[str, Any]]:
    """Cached places for a destination (refreshed after 7 days)."""
    key = destination.strip().lower()[:100]
    cached = db.scalar(
        select(PlaceCache.places).where(
            PlaceCache.destination_key == key,
            PlaceCache.fetched_at > func.now() - timedelta(days=CACHE_DAYS),
        )
    )
    span = telemetry.tracer.start_span("places.fetch")
    span.set_attribute("gy.cache_hit", cached is not None)
    try:
        if cached is not None:
            return list(cached)
        places = fetch_places(destination)
        span.set_attribute("gy.results", len(places))
    finally:
        span.end()
    db.execute(
        insert(PlaceCache)
        .values(destination_key=key, places=places, fetched_at=func.now())
        .on_conflict_do_update(
            index_elements=[PlaceCache.destination_key],
            set_={"places": places, "fetched_at": func.now()},
        )
    )
    return places


def lookup_place(name: str, destination: str, near: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Find a must-visit place on Wikipedia (with coordinates) near the destination's places."""
    result = _get_json(
        WIKIPEDIA_URL,
        {
            "action": "query",
            "format": "json",
            "formatversion": 2,
            "generator": "search",
            "gsrsearch": f"{name} {destination}",
            "gsrlimit": 3,
            "prop": "coordinates|description|info",
        },
    )
    pages = sorted(result.get("query", {}).get("pages", []), key=lambda p: p.get("index", 99))
    for page in pages:
        if not page.get("coordinates"):
            continue
        place = normalize_pages([{**page, "category_hint": "Attraction"}])
        if not place:
            continue
        candidate = place[0]
        # Must be in the same area as the destination's other places (within ~150 km).
        if (
            near
            and min(
                abs(candidate["lat"] - p["lat"]) + abs(candidate["lon"] - p["lon"]) for p in near
            )
            > 1.5
        ):
            continue
        return candidate
    return None
