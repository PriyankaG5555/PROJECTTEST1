"""Fake OpenStreetMap data (normalised places around Panaji, Goa). Tests never call OSM."""

from typing import Any

import pytest

from app.services import osm_service


def place(
    pid: str, name: str, category: str, notability: int, free: bool, lat: float, lon: float
) -> dict[str, Any]:
    return {
        "place_id": f"osm:node/{pid}",
        "name": name,
        "category": category,
        "lat": lat,
        "lon": lon,
        "notability": notability,
        "free": free,
        "address": "Goa",
        "url": f"https://www.openstreetmap.org/node/{pid}",
    }


FORT = place("1", "Fort Aguada", "Fort", 4, False, 15.4925, 73.7735)
MUSEUM = place("2", "Goa State Museum", "Museum", 3, False, 15.4989, 73.8278)
CALANGUTE = place("3", "Calangute Beach", "Beach", 3, True, 15.5439, 73.7553)
CASINO = place("4", "Casino Royale", "Attraction", 1, False, 15.5000, 73.8300)
MIRAMAR = place("5", "Miramar Beach", "Beach", 1, True, 15.4825, 73.8075)
PLACES = [FORT, MUSEUM, CALANGUTE, CASINO, MIRAMAR]


class FakeOSM:
    def __init__(self) -> None:
        self.places: list[dict[str, Any]] = PLACES
        self.calls: list[str] = []
        self.fail = False

    def __call__(self, destination: str) -> list[dict[str, Any]]:
        self.calls.append(destination)
        if self.fail:
            raise osm_service.OSMUnavailable
        return self.places


@pytest.fixture
def osm(monkeypatch: pytest.MonkeyPatch) -> FakeOSM:
    fake = FakeOSM()
    monkeypatch.setattr(osm_service, "fetch_places", fake)
    return fake
