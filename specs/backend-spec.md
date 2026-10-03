# Backend Spec — Trip Planner (GhumakkadYatri)

> Purpose: Define server-side architecture, data model, and business logic. Must implement every endpoint in `api-contract-spec.md` and support the goals in `goal-spec.md`.

## 1. Tech Stack
- **Language / runtime:** Python 3.12 on Vercel (code must also run on newer versions, e.g. 3.14 used locally)
- **Framework:** FastAPI (ASGI) — deployed as a Vercel Python serverless function; Uvicorn for local development
- **Database:** PostgreSQL 16 (Neon, free plan)
- **ORM / data access:** SQLAlchemy 2.0 (sync) + psycopg 3; **Alembic** for migrations
- **Validation:** Pydantic v2 models for every request/response (same rules as the frontend's Zod schemas)
- **Auth:** Username + password; passwords hashed with **bcrypt** (cost 12, `bcrypt` package); session = **JWT** (HS256, `PyJWT`) in the `gy_session` httpOnly cookie
- **PDF generation:** **ReportLab** + `svglib` (logo) with embedded Poppins/Inter TTF fonts (both include the `₹` glyph). Pure Python — no headless browser.
- **Rate limiting:** Stored in PostgreSQL (`auth_attempts` table) — in-memory limiters don't work on serverless, where each request may hit a different instance.
- **Logging:** Python `logging` with a JSON formatter (`python-json-logger`)
- **External services / APIs:** None in MVP (no paid third-party APIs).
- **Testing:** pytest + FastAPI `TestClient` (`httpx2`) against a separate test PostgreSQL database; `ruff` (lint/format) and `mypy` (type-check)

## 2. Architecture Overview
Layered, one module per resource:

```
HTTP request
   │
   ▼
routers/       → URL + method → handler; dependencies: get_db, get_current_user
   │
   ▼
schemas/       → Pydantic request/response models (validation + JSON shape, camelCase aliases)
   │
   ▼
services/      → business rules (ownership, finalized lock, draft limit, date changes, totals)
   │
   ▼
models/        → SQLAlchemy ORM models → PostgreSQL
```
- **Dependencies (FastAPI `Depends`):** `get_db` (one session per request, committed or rolled back at the end), `get_current_user` (verifies the JWT in `gy_session`, loads the user, else `UNAUTHORIZED`).
- **Errors:** services raise `AppError(code, http_status, message, details=None)`; exception handlers turn it into the standard error JSON (contract §2).
  - FastAPI's default `422` validation response is **overridden** → `400 VALIDATION_ERROR` with `details.fields` (field → message, camelCase names).
  - Unknown exceptions → `500 INTERNAL_ERROR`, logged with a request ID.
- **JSON naming:** Python code uses snake_case; Pydantic models use `alias_generator=to_camel` so the API is camelCase as the contract requires.
- **Days are not stored.** Day 1…N is computed from the trip's dates; activities store only their `day_number`.
- **Serverless-friendly:** no in-memory state; DB connections use Neon's **pooled** connection string with SQLAlchemy `NullPool`.

## 3. Data Model
### Entity: User (`users`)
| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, default `gen_random_uuid()` | |
| username | VARCHAR(30) | NOT NULL | As typed by the user (for display) |
| username_normalized | VARCHAR(30) | NOT NULL, UNIQUE | Lower-case, for case-insensitive uniqueness and login |
| password_hash | VARCHAR(100) | NOT NULL | bcrypt hash — never returned by the API |
| created_at | TIMESTAMPTZ | NOT NULL, default now() | |

### Entity: Trip (`trips`)
| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | |
| user_id | UUID | FK → users.id, ON DELETE CASCADE, indexed | Owner |
| destination | VARCHAR(100) | NOT NULL | |
| start_date | DATE | NOT NULL | |
| end_date | DATE | NOT NULL, CHECK `end_date >= start_date` | Length 1–30 days (checked in service) |
| trip_type | ENUM `trip_type` | NOT NULL | `solo`, `couple`, `family`, `friends` |
| status | ENUM `trip_status` | NOT NULL, default `draft` | `draft`, `finalized` |
| finalized_draft_id | UUID | NULL, FK → drafts.id ON DELETE SET NULL | Set only when `status = finalized` |
| created_at | TIMESTAMPTZ | NOT NULL | |
| updated_at | TIMESTAMPTZ | NOT NULL | Bumped on any change to the trip, its drafts or activities |

### Entity: Draft (`drafts`)
| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | |
| trip_id | UUID | FK → trips.id, ON DELETE CASCADE, indexed | |
| name | VARCHAR(50) | NOT NULL | Display name |
| name_normalized | VARCHAR(50) | NOT NULL, UNIQUE (`trip_id`, `name_normalized`) | Lower-case, for case-insensitive uniqueness |
| created_at | TIMESTAMPTZ | NOT NULL | |
| updated_at | TIMESTAMPTZ | NOT NULL | |

### Entity: Activity (`activities`)
| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | |
| draft_id | UUID | FK → drafts.id, ON DELETE CASCADE, indexed | |
| day_number | SMALLINT | NOT NULL, CHECK 1–30 | Day within the trip |
| destination_name | VARCHAR(100) | NOT NULL | |
| time | CHAR(5) | NULL, CHECK matches `HH:mm` | Stored as text; sorts correctly as a string |
| cost | NUMERIC(12,2) | NULL, CHECK `>= 0` | INR |
| priority | ENUM `priority` | NULL | `high`, `medium`, `low` |
| created_at | TIMESTAMPTZ | NOT NULL | Tie-breaker for ordering |
| updated_at | TIMESTAMPTZ | NOT NULL | |

Index: (`draft_id`, `day_number`, `time`) for loading a draft in display order.

### Entity: AuthAttempt (`auth_attempts`) — rate limiting
| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| ip | VARCHAR(45) | PK (with `window_start`) | Client IP (from `X-Forwarded-For` set by Vercel) |
| window_start | TIMESTAMPTZ | PK | Start of the 1-minute window |
| count | INTEGER | NOT NULL | Attempts in that window |

Rows older than 1 hour are deleted opportunistically on each auth request.

### Relationships
- User 1 — * Trip (deleting a user deletes their trips, drafts and activities)
- Trip 1 — * Draft (1 to 5 drafts; at least one always exists)
- Draft 1 — * Activity
- Trip 0..1 → Draft (`finalized_draft_id`, the draft the trip was finalized from)

## 4. Business Logic / Services
| Service | Responsibility | Rules / edge cases |
|---------|----------------|--------------------|
| `auth_service` | Signup, login, session tokens, account deletion | Username normalized to lower-case; duplicate → `USERNAME_TAKEN`. Login compares bcrypt hash; wrong username **or** password → same `INVALID_CREDENTIALS` (and still runs a dummy bcrypt check to avoid timing differences). JWT payload `{ "sub": user_id }`, 7-day expiry. **Delete account:** re-checks the password (`INVALID_CREDENTIALS` if wrong), deletes the user (cascades to all trips, drafts, activities), clears the cookie. |
| `rate_limit` | Limit auth attempts | 10 attempts/minute per IP on signup, login and delete-account → `429 RATE_LIMITED`. Upsert into `auth_attempts`. |
| `trip_service.create` | Create trip | Validates dates and 1–30 day length; creates trip **and** "Draft 1" in one transaction. |
| `trip_service.list / get` | Read trips | Only `user_id = current_user.id`; otherwise `NOT_FOUND`. List sorted by `updated_at` desc; optional `status` filter. Computes `dayCount`, `draftCount`. |
| `trip_service.update` | Edit details | `TRIP_FINALIZED` if finalized. If the new `dayCount` is smaller, find activities (all drafts) with `day_number > new_day_count`. If any and `confirmDeleteActivities` is not `true` → `ACTIVITIES_WOULD_BE_DELETED` with `details.affected`. Otherwise delete them and update the trip in one transaction; return `deletedActivityCount`. Activities keep their `day_number` (Day 2 stays Day 2, with the new date). |
| `trip_service.delete` | Delete trip | Allowed in any status; cascades to drafts and activities. |
| `trip_service.finalize` | Draft → Finalized | `TRIP_FINALIZED` if already finalized; `draftId` must belong to the trip (else `VALIDATION_ERROR`). Sets `status`, `finalized_draft_id`. Empty drafts may be finalized. |
| `trip_service.reopen` | Finalized → Draft | `TRIP_NOT_FINALIZED` if draft. Clears `finalized_draft_id`. |
| `draft_service` | Create, get, rename, delete drafts | Finalized lock on all writes. Max 5 per trip → `DRAFT_LIMIT_REACHED`. Name unique per trip (case-insensitive) → `DRAFT_NAME_TAKEN`. Copy duplicates all activities in one transaction. Deleting the only draft → `LAST_DRAFT`. `get` builds Day 1…N (including empty days), sorts activities by `time` (nulls last, then `created_at`), computes day and draft totals. |
| `activity_service` | Add, edit, delete activities | Ownership via draft → trip → user. Finalized lock. `dayNumber` must be 1…`dayCount`. Trims strings; rounds cost to 2 decimals (`Decimal`, never float). |
| `pdf_service` | Itinerary PDF | `TRIP_NOT_FINALIZED` unless finalized. Uses the finalized draft. A4 portrait: logo + trip header (destination, dates, trip type, day count), then each day (date heading, activities as table rows: time, destination name, priority label, cost), day total, and the trip total at the end. Empty days show "No activities planned". Costs formatted `₹1,250.00` (Indian grouping). Built in memory and returned as `application/pdf`. |
| **Ownership helpers** | `get_owned_trip(db, trip_id, user)` / `get_owned_draft` / `get_owned_activity` | Single place that raises `NOT_FOUND` for missing **or** other users' resources. Used by every service. |
| **Finalized lock helper** | `assert_editable(trip)` | Raises `TRIP_FINALIZED` when `status = finalized`. Called before every write except reopen and delete. |

## 5. Authentication & Authorization
- **Auth mechanism:** On signup/login the server signs a JWT (`sub` = user ID, `exp` = 7 days) with `JWT_SECRET` and sets it as cookie `gy_session`: `HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=604800`. Logout and account deletion clear the cookie. No refresh tokens in MVP — users log in again after 7 days.
- **Roles / permissions:** One role (traveller). No admin features in MVP.
- **Resource ownership rules:** Every trip, draft and activity query is scoped to the logged-in user through the ownership helpers; other users' data returns `404 NOT_FOUND`.
- **Password rules:** 8–128 characters; stored only as a bcrypt hash; never logged.
- **Account deletion:** Permanent and immediate; requires the current password. No soft-delete or recovery in MVP.

## 6. Validation & Error Handling
- **Input validation approach:** Pydantic model per endpoint (body, path, query). Extra fields are ignored. Failures → `400 VALIDATION_ERROR` with `details.fields`. Database constraints (CHECK, UNIQUE) are a second safety net.
- **Error response format:** Exactly as `api-contract-spec.md` §2. SQLAlchemy `IntegrityError` on unique constraints is mapped to `USERNAME_TAKEN` / `DRAFT_NAME_TAKEN`.
- **Logging:** One JSON log line per request (method, path, status, duration, request ID, user ID if any). Errors logged with tracebacks. **Never log** passwords, cookies, or JWTs.

## 7. External Integrations
| Service | Purpose | Failure / fallback behavior |
|---------|---------|-----------------------------|
| PostgreSQL (Neon) | Data storage | DB unavailable → `500 INTERNAL_ERROR`; `/health` returns `503 { "status": "degraded" }` |
| — | No third-party APIs in MVP | — |

## 8. Configuration & Environment
| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `DATABASE_URL` | PostgreSQL connection string (Neon **pooled** URL in production) | Yes | — |
| `JWT_SECRET` | Secret for signing session JWTs (≥ 32 random chars) | Yes | — |
| `ENVIRONMENT` | `development` \| `test` \| `production` | No | `development` |
| `SESSION_TTL_DAYS` | Session length in days | No | `7` |
| `COOKIE_SECURE` | Set `Secure` on cookie (`false` only for local http) | No | `true` |
| `LOG_LEVEL` | Logging level | No | `INFO` |

Settings are loaded and validated with `pydantic-settings`. `backend/.env.example` lists all variables with safe placeholder values; real `.env` files are git-ignored. In production, variables are set in the Vercel project settings.

## 9. Non-Functional Requirements
- **Performance:** p95 < 300 ms for JSON endpoints when warm; cold start ≈ 1–2 s; PDF for a 30-day trip generated in < 3 s.
- **Security:**
  - HTTPS only (provided by Vercel).
  - Frontend and API are served from the **same Vercel domain**, so **no CORS** is needed. In development, the Vite dev server proxies `/api` → `http://localhost:8000`.
  - Rate limit: 10 requests/minute per IP on signup, login and delete-account → `429 RATE_LIMITED`.
  - Security headers (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Strict-Transport-Security`) set by middleware; request body limit 100 KB.
  - Secrets only in environment variables.
- **Scalability:** Stateless functions (session in JWT, rate limits in DB); Vercel scales instances automatically. Not a concern at MVP scale.
- **Observability:** Structured logs in the Vercel dashboard; `/health` for uptime checks.

## 10. Folder Structure
```
PROJECTTEST1/
  vercel.json             # build frontend + route /api/* to the Python function
  requirements.txt        # `-r backend/requirements.txt` (read by Vercel's Python runtime)
  docker-compose.yml      # local dev + test PostgreSQL
  .github/workflows/ci.yml
  api/
    index.py              # Vercel entry point: `from app.main import app`
  frontend/               # see frontend-spec.md
  backend/
    pyproject.toml        # project metadata, ruff/mypy/pytest config
    requirements.txt      # runtime dependencies (single source of truth)
    requirements-dev.txt  # + uvicorn, alembic, pytest, httpx2, ruff, mypy
    .env.example
    alembic.ini
    alembic/
      versions/           # migrations
    assets/
      logo.svg            # copied from specs/assets/logo.svg
      fonts/              # Poppins & Inter TTF files
    app/
      main.py             # FastAPI app, routers, exception handlers, middleware
      config.py           # pydantic-settings
      db.py               # engine (NullPool), session dependency
      security.py         # bcrypt, JWT, cookie helpers, get_current_user
      errors.py           # AppError + exception handlers
      models/             # SQLAlchemy models: user, trip, draft, activity, auth_attempt
      schemas/            # Pydantic models (camelCase aliases)
      routers/
        health.py
        auth.py
        trips.py
        drafts.py
        activities.py
      services/
        auth_service.py
        rate_limit.py
        trip_service.py
        draft_service.py
        activity_service.py
        pdf_service.py
        ownership.py      # get_owned_*, assert_editable
      utils/
        dates.py          # day_count, day → date
        money.py          # INR formatting, totals
    scripts/
      seed.py             # demo user + sample Goa trip for local dev
    tests/
      conftest.py         # test DB, client, logged-in user fixtures
      test_auth.py
      test_trips.py
      test_drafts.py
      test_activities.py
      test_export.py
```

## 11. Deployment
```
                ┌────────────────── Vercel project (free Hobby plan) ──────────────────┐
Browser ─HTTPS─▶│ ghumakkadyatri.vercel.app                                            │
                │   /          → React app (static files from frontend/dist)           │
                │   /api/*     → Python serverless function (api/index.py → FastAPI)   │
                └───────────────────────────────────┬──────────────────────────────────┘
                                                    ▼
                                    Neon PostgreSQL (free plan, pooled connection)
```
- **Why this setup:** All parts are on **free plans with no expiry date**, and there is **no 30–60 s sleep** — serverless cold starts are about 1–2 s. Neon's free database pauses when idle and wakes in under a second. Frontend and API share one domain, so the login cookie works without extra configuration.
- **Hosting:**
  - **Frontend + backend:** one Vercel project linked to the GitHub repo; auto-deploys on push to `main`, with a preview URL for every branch/PR.
  - **Database:** Neon PostgreSQL free plan (0.5 GB storage — far more than MVP needs).
- **Free-plan limits to be aware of:** Vercel Hobby is for **personal, non-commercial** use; function duration limit applies (PDF generation stays well under it). If the app becomes commercial, move to Vercel Pro or another host — the code doesn't change.
- **Migrations:** A GitHub Actions job runs `alembic upgrade head` against the production database (using the `DATABASE_URL` repository secret) on every push to `main`, before Vercel finishes deploying. Migrations must be backward-compatible (add columns before using them).
- **Local development:** PostgreSQL on **Neon branches** (decided: no Docker needed) — a `dev` branch for `backend/.env` and a `test` branch for `pytest` (`TEST_DATABASE_URL`); production uses Neon's `main` branch. `docker-compose.yml` remains as an optional alternative. `uvicorn app.main:app --reload --port 8000` in `backend/`; Vite dev server proxies `/api` to it.
- **CI:** GitHub Actions on every push and pull request: `ruff`, `mypy`, `pytest` (with a PostgreSQL service container), and frontend lint + tests.
- **Before first deploy:** re-check current Vercel and Neon free-plan terms, as providers change them.

## 12. Open Questions
- [x] **Language:** **Resolved:** Python (FastAPI).
- [x] **Hosting:** **Resolved:** long-term free hosting — Vercel (frontend + Python API) and Neon (database); no 30–60 s sleep.
- [x] **Account deletion:** **Resolved:** in MVP — `DELETE /auth/me` with password confirmation.
