"""OpenTelemetry traces + business metrics (specs/observability-spec.md).

Off unless OTEL_EXPORTER_OTLP_ENDPOINT is set (e.g. http://localhost:4318 for a local SigNoz).
Never records usernames, passwords, tokens, IPs, costs or free text (spec §2.3).
"""

import hashlib
import logging
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from fastapi import FastAPI
from opentelemetry import metrics, trace

from app.config import get_settings

logger = logging.getLogger("app.telemetry")
tracer = trace.get_tracer("ghumakkadyatri")
_meter = metrics.get_meter("ghumakkadyatri")
_enabled = False

# Instruments work as no-ops until a meter provider is installed by setup().
PAGE_VIEWS = _meter.create_counter("gy.page_views", description="Logged-in page views by route")
LOGINS = _meter.create_counter("gy.logins", description="Successful logins")
SIGNUPS = _meter.create_counter("gy.signups", description="New accounts")
TRIPS_CREATED = _meter.create_counter("gy.trips.created", description="Trips created")
PLANS_GENERATED = _meter.create_counter("gy.plans.generated", description="Plan my day requests")
SUGGESTIONS = _meter.create_counter("gy.suggestions.requested", description="Place suggestions")
HOTELS = _meter.create_counter("gy.hotels.requested", description="Hotel suggestions")
EXTERNAL_DURATION = _meter.create_histogram(
    "gy.external.duration", unit="ms", description="Response time of external services"
)


def enabled() -> bool:
    return _enabled


def setup(app: FastAPI) -> None:
    """Install exporters and auto-instrumentation when an OTLP endpoint is configured."""
    global _enabled
    settings = get_settings()
    endpoint = (settings.otel_exporter_otlp_endpoint or "").rstrip("/")
    if not endpoint or _enabled:
        return
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.urllib import URLLibInstrumentor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    from app.db import get_engine

    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
            "service.version": "0.1.0",
            "deployment.environment": settings.environment,
        }
    )
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces"))
    )
    trace.set_tracer_provider(tracer_provider)
    reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=f"{endpoint}/v1/metrics"), export_interval_millis=10_000
    )
    metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[reader]))

    FastAPIInstrumentor.instrument_app(app, excluded_urls="api/v1/health")
    _trace_database(get_engine())
    URLLibInstrumentor().instrument()
    _enabled = True
    logger.info("telemetry enabled", extra={"endpoint": endpoint})


def _trace_database(engine: Any) -> None:
    """One span per SQL statement via SQLAlchemy events: operation and duration only, no SQL values.

    (The opentelemetry-instrumentation-sqlalchemy plugin does not support SQLAlchemy 2.1.)
    """
    from sqlalchemy import event

    @event.listens_for(engine, "before_cursor_execute")
    def _start(
        conn: Any, cursor: Any, statement: str, params: Any, context: Any, many: bool
    ) -> None:
        operation = (statement.split(None, 1) or ["QUERY"])[0].upper()
        span = tracer.start_span(
            f"db {operation}",
            kind=trace.SpanKind.CLIENT,
            attributes={"db.system": "postgresql", "db.operation": operation},
        )
        conn.info.setdefault("otel_spans", []).append(span)

    @event.listens_for(engine, "after_cursor_execute")
    def _end(conn: Any, cursor: Any, statement: str, params: Any, context: Any, many: bool) -> None:
        spans = conn.info.get("otel_spans") or []
        if spans:
            spans.pop().end()

    @event.listens_for(engine, "handle_error")
    def _error(context: Any) -> None:
        spans = context.connection.info.get("otel_spans") if context.connection else None
        if spans:
            span = spans.pop()
            span.set_status(trace.Status(trace.StatusCode.ERROR))
            span.end()


def hash_user(user_id: uuid.UUID | str) -> str:
    """Salted one-way hash so users can be counted but not identified."""
    settings = get_settings()
    salt = settings.telemetry_hash_salt or hashlib.sha256(settings.jwt_secret.encode()).hexdigest()
    return hashlib.sha256(f"{salt}:{user_id}".encode()).hexdigest()[:16]


def set_user(user_id: uuid.UUID | str) -> None:
    trace.get_current_span().set_attribute("enduser.id", hash_user(user_id))


def annotate(**attributes: Any) -> None:
    """Add business attributes to the current request span."""
    span = trace.get_current_span()
    for key, value in attributes.items():
        if value is not None:
            span.set_attribute(f"gy.{key}", value)


def destination_attrs(info: dict[str, Any] | None, destination: str) -> dict[str, str]:
    return {
        "destination": destination.strip().title()[:60],
        "destination_type": (info or {}).get("kind") or "unknown",
        "country": (info or {}).get("country") or "unknown",
    }


@contextmanager
def external_call(service: str) -> Iterator[None]:
    """Time a call to an external service (Nominatim, Wikipedia) into gy.external.duration."""
    started = time.perf_counter()
    outcome = "ok"
    try:
        yield
    except TimeoutError:
        outcome = "timeout"
        raise
    except Exception:
        outcome = "error"
        raise
    finally:
        EXTERNAL_DURATION.record(
            (time.perf_counter() - started) * 1000, {"service": service, "outcome": outcome}
        )
