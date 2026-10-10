# Implementation Plan — Trip Planner (GhumakkadYatri)

> Purpose: Turn the four specs into small, ordered tasks that one developer can finish in **2 weeks (10 working days)**. Each task names the spec sections it implements and a **Done when** check. Build order: **setup → backend (against the API contract) → early deploy → frontend → polish**.

**Specs:** [goal](goal-spec.md) · [frontend](frontend-spec.md) · [backend](backend-spec.md) · [API contract](api-contract-spec.md)

## How we work
- **One phase = one git branch** (e.g. `phase-2-auth`), merged into `main` when the phase's "Done when" checks pass. Commit after each task.
- **Spec first:** if a task shows a spec is wrong or incomplete, update the spec (and the contract's Change Log) **before** changing code.
- **Tests with code:** every backend endpoint gets pytest tests for its success case and every error code listed in the contract.
- **Definition of done (every task):** code + tests pass locally and in CI, `ruff`/`mypy` (backend) or `oxlint`/`tsc` (frontend) clean, no secrets committed.

## Timeline overview
| Day | Phase | Priority |
|-----|-------|----------|
| 1 | 0. Project setup | P0 |
| 1–2 | 1. Backend foundation | P0 |
| 2 | 2. Auth API | P0 |
| 3 | 3. Trips API | P0 |
| 4 | 4. Drafts, activities, finalize/reopen API | P0 / P1 |
| 5 | 5. PDF export | P0 |
| 5–6 | 6. First deployment (backend live) | P0 |
| 6 | 7. Frontend foundation + auth screens | P0 |
| 7 | 8. Trips screens | P0 / P1 |
| 8–9 | 9. Trip planner screen | P0 / P1 |
| 9 | 10. Drafts UI + compare | P1 / P2 |
| 10 | 11. Polish, end-to-end tests, release | P0 / P1 |

---

## Phase 0 — Project setup (Day 1)
| # | Task | Spec | Done when |
|---|------|------|-----------|
| 0.1 | Create repo layout: `backend/`, `frontend/`, `api/index.py`, root `requirements.txt`, `vercel.json` | BE §10, §11 | Folders exist and match the spec |
| 0.2 | Backend skeleton: `pyproject.toml` + `requirements*.txt` (FastAPI, SQLAlchemy, Alembic, psycopg, Pydantic, pydantic-settings, bcrypt, PyJWT, ReportLab, svglib, pytest, ruff, mypy), `app/main.py` with `GET /api/v1/health`, `config.py`, `.env.example` | BE §1, §8; API `/health` | `uvicorn app.main:app --port 8000` → `/api/v1/health` returns `{"status":"ok"}` |
| 0.3 | Local PostgreSQL: `docker-compose.yml` with `db` (dev) and a test database | BE §11 | `docker compose up db` works; app connects |
| 0.4 | Frontend skeleton: Vite + React + TypeScript + Tailwind, React Router, TanStack Query, brand tokens (light-blue palette), Poppins + Inter fonts, logo + favicon in `public/`, Vite proxy `/api` → `:8000` | FE §1, §8, §11, §12 | `npm run dev` shows a placeholder page with logo and brand colours; `/api/v1/health` works through the proxy |
| 0.5 | CI: GitHub Actions — backend (`ruff`, `mypy`, `pytest` with Postgres service) and frontend (`oxlint`, `tsc`, `vitest`, build) | BE §11 | CI passes on `main` |

## Phase 1 — Backend foundation (Day 1–2)
| # | Task | Spec | Done when |
|---|------|------|-----------|
| 1.1 | SQLAlchemy models: `users`, `trips`, `drafts`, `activities`, `auth_attempts` with all constraints, enums and indexes | BE §3 | Models match the spec tables |
| 1.2 | Alembic initial migration | BE §3, §11 | `alembic upgrade head` creates all tables; `downgrade` works |
| 1.3 | `db.py` (engine with `NullPool`, `get_db` session dependency) | BE §2 | Sessions commit/rollback per request |
| 1.4 | `AppError` + exception handlers; override FastAPI 422 → `400 VALIDATION_ERROR` with `details.fields` (camelCase); 500 handler | BE §2, §6; API §2 | Test: bad body returns contract error JSON |
| 1.5 | Pydantic base model with camelCase aliases; shared schemas `User`, `Trip`, `TripDetail`, `DraftSummary`, `Draft`, `Activity` | API §3 | Schema JSON matches contract examples |
| 1.6 | Middleware: request ID + JSON logging, security headers, 100 KB body limit | BE §6, §9 | Log line per request; headers present |
| 1.7 | Test fixtures: test DB reset per test, `client`, `logged_in_client`, `other_user_client` | BE §10 | `pytest` runs with an empty test suite |

## Phase 2 — Auth API (Day 2)
| # | Task | Spec | Done when |
|---|------|------|-----------|
| 2.1 | `security.py`: bcrypt hash/verify, JWT create/verify, cookie set/clear, `get_current_user` | BE §5 | Unit tests pass |
| 2.2 | `POST /auth/signup`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me` | API §5; US-1–3 | Tests: success, `USERNAME_TAKEN` (case-insensitive), `INVALID_CREDENTIALS`, `UNAUTHORIZED`, cookie flags |
| 2.3 | DB-backed rate limit (10/min/IP) on signup, login, delete-account | BE §4 | Test: 11th attempt → `429 RATE_LIMITED` |
| 2.4 | `DELETE /auth/me` with password check, cascade delete, cookie cleared | API §5; US-13 | Tests: wrong password → 401, success → user + trips gone |

## Phase 3 — Trips API (Day 3)
| # | Task | Spec | Done when |
|---|------|------|-----------|
| 3.1 | Ownership helpers `get_owned_trip/draft/activity`, `assert_editable` | BE §4 | Other user's IDs → `404 NOT_FOUND` |
| 3.2 | `POST /trips` (creates "Draft 1"), `GET /trips` (+ `status` filter), `GET /trips/{id}` | API §5; US-4, US-5 | Tests: 1–30 day rule, end ≥ start, `dayCount`/`draftCount` correct |
| 3.3 | `PATCH /trips/{id}` incl. shortening flow (`ACTIVITIES_WOULD_BE_DELETED` → confirm) | API §5; US-10 | Tests: lengthen, shorten with/without confirm, `deletedActivityCount` |
| 3.4 | `DELETE /trips/{id}` | API §5; US-11 | Test: cascade delete |

## Phase 4 — Drafts, activities, finalize/reopen API (Day 4)
| # | Task | Spec | Done when |
|---|------|------|-----------|
| 4.1 | `GET /drafts/{id}`: Day 1…N incl. empty days, sort by time (nulls last), day + draft totals | API §3; US-6 | Test with Goa example matches contract JSON |
| 4.2 | `POST/PATCH/DELETE` activities, `dayNumber` range, cost rounding (Decimal) | API §5; US-7, US-7a | Tests: required/optional fields, priority enum, move between days |
| 4.3 | `POST /trips/{id}/finalize`, `POST /trips/{id}/reopen`; finalized lock on every write | API §1, §5; US-8, US-9a | Tests: every write on a finalized trip → `409 TRIP_FINALIZED`; reopen restores editing |
| 4.4 | Drafts: list, create (blank/copy), rename, delete; limit 5, unique name, last draft | API §5; US-8a (P1) | Tests: `DRAFT_LIMIT_REACHED`, `DRAFT_NAME_TAKEN`, `LAST_DRAFT`, copy copies activities |

## Phase 5 — PDF export (Day 5)
| # | Task | Spec | Done when |
|---|------|------|-----------|
| 5.1 | Add fonts (Poppins, Inter) and logo to `backend/assets/` | BE §1, §10 | Files present (fonts under OFL licence) |
| 5.2 | `pdf_service` layout: header with logo, per-day tables, visit duration/end time when set, day totals, trip total in `₹` | BE §4; US-9 | PDF opens, `₹` renders, durations are shown when present, empty days say "No activities planned" |
| 5.3 | `GET /trips/{id}/export.pdf` with filename rule; `409 TRIP_NOT_FINALIZED` for drafts | API §5 | Tests: content type, filename, draft trip → 409; 30-day trip < 3 s |

## Phase 6 — First deployment (Day 5–6)
Deploy the backend early to catch serverless problems before the frontend is built.

| # | Task | Spec | Done when |
|---|------|------|-----------|
| 6.1 | 👤 **You:** create free **Neon** project; copy pooled + direct connection strings | BE §11 | Database exists |
| 6.2 | 👤 **You:** create free **Vercel** account, import the GitHub repo; set `DATABASE_URL`, `JWT_SECRET` env vars | BE §8, §11 | Project linked |
| 6.3 | `vercel.json` + `api/index.py`: build frontend, route `/api/*` to FastAPI | BE §11 | Preview deploy serves `/api/v1/health` |
| 6.4 | GitHub Actions migration job (`alembic upgrade head` on push to `main`, `DATABASE_URL` secret) | BE §11 | Tables exist in Neon |
| 6.5 | Smoke test on the live URL: signup → create trip → add activity → finalize → export PDF (with curl/HTTP client) | Goal §8 | All steps succeed; cookie works over HTTPS |

## Phase 7 — Frontend foundation + auth screens (Day 6)
| # | Task | Spec | Done when |
|---|------|------|-----------|
| 7.1 | Types from contract (`types/index.ts`); `api/client.ts` (credentials, error parsing, global 401 → `/login?next=`) | FE §5, §6 | Types compile; errors surface as `{code, message}` |
| 7.2 | Shared components: `AppLayout` (logo, user menu), `ProtectedRoute`, `ConfirmDialog`, `LoadingSpinner`, `EmptyState`, `ErrorState`, toasts | FE §4 | Used by at least one page |
| 7.3 | Login + Sign Up pages (`AuthForm`, Zod validation, server errors inline) | FE §2, §7, §9; US-1, US-2 | Can sign up, log in, reload stays logged in |
| 7.4 | Log out + My Account page with **Delete my account** dialog | FE Flow 7; US-3, US-13 | Delete with wrong password shows error; correct password deletes and goes to `/signup` |

## Phase 8 — Trips screens (Day 7)
| # | Task | Spec | Done when |
|---|------|------|-----------|
| 8.1 | My Trips page: `TripCard`, `StatusBadge`, empty/loading/error states | FE §2, §4; US-5 | Lists trips newest first with status |
| 8.2 | New Trip page (`TripForm`, Zod rules) → navigates to planner | FE Flow 2; US-4 | Trip created with Day 1…N |
| 8.3 | Edit Trip page with "activities will be deleted" warning + confirm resend | FE Flow 6; US-10 (P1) | Shortening shows affected list; confirm deletes them |
| 8.4 | Delete trip with confirmation | US-11 (P1) | Trip disappears from list |

## Phase 9 — Trip planner screen (Day 8–9)
| # | Task | Spec | Done when |
|---|------|------|-----------|
| 9.1 | Planner layout: `PlannerHeader`, `DayColumn` per day, responsive grid (phone stacked) | FE §2, §8; US-6 | Shows exactly N days on phone and laptop |
| 9.2 | Activities: `ActivityItem`, `ActivityForm` (add/edit/delete), sorted by time, `PriorityLabel`, `CostTotal` (₹ en-IN) | FE §4, §7; US-7, US-7a | Add/edit/delete works; totals update; data survives reload |
| 9.3 | Finalize / Reopen / Export PDF buttons; read-only mode when finalized | FE Flow 5; US-8, US-9, US-9a | Draft: no export; Finalized: no editing, PDF downloads; Reopen re-enables editing |

## Phase 10 — Drafts UI + compare (Day 9)
| # | Task | Spec | Done when |
|---|------|------|-----------|
| 10.1 | `DraftSwitcher`: switch (`?draft=` in URL), new (blank/copy), rename, delete; "Final" label | FE Flow 3; US-8a (P1) | Two drafts with different activities; switching works; errors shown as toasts |
| 10.2 | Compare Drafts page: pick 2 drafts, side-by-side days and totals, "Use this draft" | FE Flow 4; US-8b (**P2**) | Two drafts shown side by side; stacked on phone |

## Phase 11 — Polish, end-to-end tests, release (Day 10)
| # | Task | Spec | Done when |
|---|------|------|-----------|
| 11.1 | Responsive + accessibility pass: keyboard navigation, focus, labels, contrast, phone layout | FE §8, §10; US-12 | Manual check on phone + laptop; no axe critical issues |
| 11.2 | Playwright e2e for P0 flows: signup → create trip → add activities → finalize → export → reopen → delete account | FE §1 | Tests pass in CI |
| 11.3 | Cross-device check: create trip on laptop, open on phone | Goal G2 | Same data on both |
| 11.4 | Acceptance review against Goal §8 success metrics (table below) | Goal §8 | Every row ticked |
| 11.5 | Write `README.md` (what it is, local setup, env vars, deploy) | — | New developer can run it locally from README |

---

## Acceptance checklist (from Goal §8)
- [ ] Sign up, log in, log out work; wrong credentials show a clear error
- [ ] Created trip appears in the trip list immediately
- [ ] Trips created on device A appear on device B
- [ ] Plan shows exactly N days; activities persist after reload
- [ ] Trip can be finalized; status shown in list
- [ ] Finalized trip exports a PDF with all days, activities, costs (₹) and totals
- [ ] Draft trips cannot be exported (UI and API)
- [ ] Finalized trip can be reopened and edited again; editing without reopening is rejected
- [ ] A user cannot see another user's trips (test)
- [ ] Account deletion removes the user and all their trips
- [ ] All P0 user stories done within 2 weeks

## Cut line (if behind schedule)
Drop in this order — the app still works without them:
1. **Compare Drafts** (10.2, P2) → post-MVP
2. **Drafts UI** (10.1, P1) — backend still keeps "Draft 1", so the planner works with one draft
3. **Edit / delete trip UI** (8.3, 8.4, P1)

Never cut: auth, trips, planner, finalize/reopen, PDF export, account deletion, ownership checks.

## Things only you can do (👤)
- Create the free **Neon** and **Vercel** accounts and link the GitHub repo (6.1, 6.2).
- Add `DATABASE_URL` and `JWT_SECRET` as Vercel env vars and GitHub repository secrets.
- Download Poppins and Inter font files from Google Fonts if network access is blocked for me.
