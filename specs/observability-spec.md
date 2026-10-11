# Observability Spec — GhumakkadYatri

> Purpose: let the team see how the app is used and how fast it is — logged-in users, which destinations are planned (states, cities, countries), which priorities people choose, and response times of our API, database and the external services we call (Nominatim, Wikipedia; no LLM is used). Supplements `goal-spec.md` G6/F14 and the backend/frontend specs.

## 1. Decisions (2026-10-11)
| Topic | Decision |
|-------|----------|
| Platform | **SigNoz** (open source, self-hosted) running **locally** with Docker Compose. UI: `http://localhost:8080`. Receives OpenTelemetry on `localhost:4317` (gRPC) / `localhost:4318` (HTTP). |
| Standard | **OpenTelemetry** (vendor-neutral). The app only knows an OTLP endpoint, so another backend can replace SigNoz later without code changes. |
| Who is counted | **Logged-in users only.** No anonymous visitor tracking, no third-party trackers, no cookies added. |
| Where it runs | Local development by default. Telemetry is **off** unless `OTEL_EXPORTER_OTLP_ENDPOINT` is set, so the live Vercel site sends nothing until a reachable SigNoz (self-hosted server or SigNoz Cloud) is configured. |
| Prerequisite | Docker Desktop (Windows: with WSL2). SigNoz does not run without Docker. |

## 2. What is collected
### 2.1 Traces (every API request)
- Automatic spans: incoming HTTP requests (FastAPI), database queries (SQLAlchemy events: operation + duration, no SQL values), outgoing HTTP calls (urllib → Nominatim, Wikipedia).
- Custom spans: `places.fetch` (destination, cache hit, number of places), `destination.resolve` (destination type and country), `planner.plan_day` (priority, candidates, items, warnings, hotel used), `hotels.fetch` (destination, cache hit, results), `pdf.build` (days, activities).
- Resource attributes: `service.name=ghumakkadyatri-api`, `service.version`, `deployment.environment`.

### 2.2 Business attributes and metrics
| Signal | Type | Attributes | Answers |
|--------|------|------------|---------|
| `gy.page_views` | counter | `route` (template, e.g. `/trips/:tripId`) | Which screens logged-in users visit |
| `gy.logins`, `gy.signups` | counters | — | Sign-ups and logins over time |
| `gy.trips.created` | counter | `destination`, `destination_type` (country/state/city/town/village/other/unknown), `country`, `top_priority` | Trips by state/city/country and by priority |
| `gy.plans.generated` | counter | `destination_type`, `country`, `top_priority`, `has_stay` | Plan-my-day usage |
| `gy.suggestions.requested`, `gy.hotels.requested` | counters | `destination_type`, `country` | Suggestion usage |
| `gy.external.duration` | histogram (ms) | `service` (nominatim/wikipedia), `outcome` (ok/error/timeout) | Response time of connected APIs |
| Span attribute `enduser.id` | — | **one-way hash** of the user ID | Distinct active users (count distinct) |

Destination type and country come from Nominatim (`addresstype`, `address.country`), resolved once per destination and cached 30 days (`destination_cache`). If unavailable, `unknown` — telemetry never blocks or slows trip creation by more than 3 s.

### 2.3 Logs
- The backend's Python logs (INFO and above: one `request` line per API call with method, path, status, duration; warnings such as failed place lookups; unhandled errors with stack trace) are exported over OTLP (`/v1/logs`) with the same resource attributes.
- Each log carries the trace and span ID of its request, so a trace in SigNoz shows its logs. A `user_id` field is replaced by the same salted hash as `enduser.id`; the console log is unchanged.

### 2.4 Never collected
Usernames, passwords, session cookies/JWTs, IP addresses, activity names, costs or budgets, free-text inputs (interests, must-visit lists). User IDs are only sent as a salted SHA-256 hash.

## 3. Frontend
- When a **logged-in** user changes route, the frontend sends `POST /api/v1/telemetry/page-view` with the **route template** (IDs replaced, e.g. `/trips/:tripId/compare`). Not sent when logged out. Failures are ignored silently.
- No browser SDK, no third-party scripts.

## 4. Dashboard: "GhumakkadYatri — Overview" (SigNoz)
Provided as panel definitions in `observability/dashboards/README.md` (built in SigNoz's query builder):
1. Active users (count distinct `enduser.id`, per day)
2. Logins and sign-ups (per day)
3. Page views by route
4. Trips created by `destination_type` (country / state / city)
5. Top destinations and top countries (table)
6. Trips by `top_priority` (pie)
7. Plan-my-day requests by priority and with/without hotel
8. API latency p50/p95/p99 by route; error rate (4xx/5xx)
9. External API latency p95 by `service` (Nominatim, Wikipedia) and error/timeout count
10. Database query p95

## 5. Running it locally
`observability/README.md`: start Docker Desktop → `observability/start-signoz.ps1` (downloads SigNoz's installer **Foundry** into `observability/.tools/`, which generates Docker Compose files into `observability/pours/` from `observability/casting.yaml` and starts them; both folders git-ignored) → first run only: create the SigNoz admin account at http://localhost:8080 (SigNoz accepts telemetry only once an organization exists) → set `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318` in `backend/.env` → run the app → open SigNoz.

## 6. Acceptance criteria
1. With the endpoint unset, the app behaves exactly as before (no exporter, no errors).
2. With SigNoz running, a request produces a trace with request, DB and (when applicable) Nominatim/Wikipedia spans.
3. Creating a trip records `gy.trips.created` with destination type, country and priority.
4. External call durations appear in `gy.external.duration` by service.
5. No forbidden data (§2.4) appears in any span, log or metric (tested).
7. Request logs appear in SigNoz Logs, linked to their traces, with hashed user IDs.
6. Page views are recorded only for logged-in users, with route templates.

## 7. Change Log
| Date | Change | Author |
|------|--------|--------|
| 2026-10-11 | Logs exported to SigNoz (OTLP), linked to traces, user IDs hashed | Priyanka Ghate (with Claude) |
| 2026-10-11 | Install via SigNoz Foundry (compose manifests deprecated upstream); first-run admin account required; DB spans via SQLAlchemy events (the OTel SQLAlchemy plugin does not support SQLAlchemy 2.1) | Priyanka Ghate (with Claude) |
| 2026-10-11 | Initial spec: SigNoz (local), OpenTelemetry, logged-in usage, destination/priority metrics, external API latency | Priyanka Ghate (with Claude) |
