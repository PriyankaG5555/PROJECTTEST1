# GhumakkadYatri

Plan a trip day by day, compare draft plans, finalize one and export a clean PDF itinerary.
**Plan · Pack · Go.**

Built spec-first: see [`specs/`](specs/) — goal, frontend, backend, API contract and the implementation plan.

| Part | Tech |
|------|------|
| Frontend | React 19 + TypeScript + Vite + Tailwind v4, TanStack Query, React Router |
| Backend | Python 3.12 + FastAPI, SQLAlchemy + Alembic, PostgreSQL, ReportLab (PDF) |
| Hosting | Vercel (app + Python API, one domain) and Neon (PostgreSQL) — see [DEPLOYMENT.md](DEPLOYMENT.md) |

## Run locally

Prerequisites: Python 3.12+, Node 24+, a PostgreSQL database (Neon `dev`/`test` branches or `docker compose up -d db db-test`).

```bash
# Backend (http://localhost:8000/api/v1/docs)
cd backend
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt   # macOS/Linux: .venv/bin/
cp .env.example .env            # then set DATABASE_URL, TEST_DATABASE_URL, JWT_SECRET
.venv/Scripts/alembic upgrade head
.venv/Scripts/uvicorn app.main:app --reload --port 8000

# Frontend (http://localhost:5173, proxies /api to :8000)
cd frontend
npm install
npm run dev
```

## Tests

| Command | What |
|---------|------|
| `cd backend && .venv/Scripts/pytest -q` | API tests (database tests need `TEST_DATABASE_URL`; that database is wiped) |
| `cd backend && .venv/Scripts/ruff check . && .venv/Scripts/mypy app tests` | Lint + types |
| `cd frontend && npm test && npm run lint && npm run typecheck` | Unit tests, lint, types |
| `cd frontend && npx playwright install chromium && npm run e2e` | End-to-end journey (API must be running) |

GitHub Actions runs all of these on every push, plus migrations on `main` once the `MIGRATION_DATABASE_URL` secret exists.

## Project layout

```
specs/       goal, frontend, backend, API contract, implementation plan, logo
backend/     FastAPI app (app/), migrations (alembic/), tests, scripts/smoke_test.py
frontend/    React app (src/), Playwright tests (e2e/)
api/index.py Vercel entry point for the Python API
```
