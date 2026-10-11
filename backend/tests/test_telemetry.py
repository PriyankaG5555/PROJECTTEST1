"""Observability — observability-spec.md §6 (privacy and off-by-default)."""

import uuid

import pytest
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app import telemetry
from app.config import get_settings
from tests.helpers import API


def test_telemetry_is_off_without_endpoint() -> None:
    assert telemetry.enabled() is False


def test_user_ids_are_hashed_on_spans() -> None:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    user_id = uuid.uuid4()

    with provider.get_tracer("test").start_as_current_span("request"):
        telemetry.set_user(user_id)
        telemetry.annotate(destination="Goa", top_priority="budget", missing=None)

    attrs = dict(exporter.get_finished_spans()[0].attributes or {})
    assert attrs["enduser.id"] == telemetry.hash_user(user_id)
    assert str(user_id) not in str(attrs)
    assert len(attrs["enduser.id"]) == 16 and attrs["gy.destination"] == "Goa"
    assert "gy.missing" not in attrs


def test_hash_is_stable_and_salted(monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = uuid.uuid4()
    first = telemetry.hash_user(user_id)

    assert telemetry.hash_user(user_id) == first
    monkeypatch.setattr(get_settings(), "telemetry_hash_salt", "other-salt")
    assert telemetry.hash_user(user_id) != first


def test_destination_attributes_have_no_personal_data() -> None:
    attrs = telemetry.destination_attrs({"kind": "state", "country": "India"}, "  goa ")

    assert attrs == {"destination": "Goa", "destination_type": "state", "country": "India"}
    assert telemetry.destination_attrs(None, "X")["destination_type"] == "unknown"


def test_page_view_requires_login_and_route_template(
    client: TestClient, logged_in_client: TestClient
) -> None:
    url = f"{API}/telemetry/page-view"

    assert client.post(url, json={"route": "/trips"}).status_code == 401
    assert logged_in_client.post(url, json={"route": "/trips/:tripId"}).status_code == 204
    bad = logged_in_client.post(url, json={"route": "https://evil.example/?q=secret"})
    assert bad.status_code == 400
