# Deployment — GhumakkadYatri

Free, no-expiry setup (backend-spec.md §11): **Vercel** serves the React app and the Python API from one domain; **Neon** hosts PostgreSQL.

## One-time setup (you)

### 1. Neon (database)
1. Sign up at https://neon.tech → create project **ghumakkadyatri** (region near your users, e.g. AWS Singapore).
2. Branches: keep **main** (production); create **dev** and **test** from it.
3. For each branch, *Connect* → copy the connection string. Replace `postgresql://` with `postgresql+psycopg://`.
   - **Pooled** URL (host contains `-pooler`) → app runtime (`DATABASE_URL`)
   - **Direct** URL (no `-pooler`) → migrations (`MIGRATION_DATABASE_URL`)

### 2. Local `backend/.env` (never committed)
```
DATABASE_URL=<dev branch, pooled>
TEST_DATABASE_URL=<test branch>      # wiped by every test run
JWT_SECRET=<already generated>
```
Then: `cd backend && .venv/Scripts/alembic upgrade head && .venv/Scripts/python -m pytest -q`

### 3. GitHub secret (production migrations)
Repo → *Settings → Secrets and variables → Actions* → **New repository secret**:
`MIGRATION_DATABASE_URL` = Neon **main** branch, **direct** URL.
CI then runs `alembic upgrade head` on every push to `main` after tests pass.

### 4. Vercel (app + API)
1. Sign up at https://vercel.com with GitHub → *Add New → Project* → import **PROJECTTEST1**.
2. Framework preset: **Other** (settings come from `vercel.json`). Root directory: repository root.
3. *Environment Variables* (Production + Preview):
   - `DATABASE_URL` = Neon **main** branch, **pooled** URL
   - `JWT_SECRET` = a new random string (≥ 32 chars) — different from your local one
   - `ENVIRONMENT` = `production`
4. Deploy. Every push to `main` redeploys; other branches get preview URLs.

## Optional: AI day planning and Google suggestions
Add in Vercel → Settings → Environment Variables (Production), then redeploy:
- `GOOGLE_PLACES_API_KEY` — Google Cloud key restricted to Places API (New). Enables suggestions and grounded AI places.
- `AI_LLM_PROVIDER=anthropic`, `AI_LLM_API_KEY` (Anthropic Console key, with a monthly spend limit), optional `AI_LLM_MODEL` (default `claude-opus-5-5`), `AI_PLAN_DAILY_LIMIT` (default 10).
Without them the app works normally; the AI and suggestion buttons show a friendly "not available" message.

## Verify (task 6.5)
```
python backend/scripts/smoke_test.py https://<your-app>.vercel.app
```
Expect every line to say `PASS`. Order matters: push to `main` (runs migrations) before testing.

## Notes
- Vercel Hobby is for personal, non-commercial use. Re-check Vercel/Neon free-plan terms before launch.
- Fonts: `backend/assets/fonts/` holds Poppins-Bold and Inter (Google Fonts, SIL Open Font License — licence files included), so PDFs show `₹`. If they are missing, PDFs fall back to Helvetica and `Rs.`.
