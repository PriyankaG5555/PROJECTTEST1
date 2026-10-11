# Observability — local SigNoz

Traces, metrics and dashboards for GhumakkadYatri using **SigNoz** (open source) and **OpenTelemetry**. Spec: [`specs/observability-spec.md`](../specs/observability-spec.md).

## What you get
- **Traces** for every API request, with database queries and calls to Nominatim and Wikipedia (response times, errors).
- **Metrics**: logged-in page views, logins, sign-ups, trips created by destination type (country/state/city) and country, top priority, Plan-my-day and suggestion usage, external API latency.
- **Privacy**: logged-in users only; user IDs are salted hashes; no usernames, passwords, tokens, IPs, costs or free text.

## Run it (Windows, Docker Desktop)
1. Start Docker Desktop.
2. Start SigNoz:
   ```powershell
   .\observability\start-signoz.ps1
   ```
3. First time only: open **http://localhost:8080** and create the SigNoz admin account (stored only in your local Docker). SigNoz accepts data only after this step.
4. Turn on telemetry for the app — in `backend/.env`:
   ```
   OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
   ```
   Restart the backend. Remove the line to switch telemetry off.
5. Use the app (http://localhost:5173), then open SigNoz → **Services → ghumakkadyatri-api** or **Traces**.

Stop SigNoz (keeps data): `.\observability\stop-signoz.ps1`

## Files
| Path | Purpose |
|------|---------|
| `casting.yaml` | SigNoz install definition for Foundry (SigNoz's installer) |
| `start-signoz.ps1` / `stop-signoz.ps1` | Start/stop the local stack |
| `dashboards/README.md` | Panels for the "GhumakkadYatri — Overview" dashboard |
| `.tools/`, `pours/` | Downloaded installer and generated Docker Compose files (git-ignored) |

## Troubleshooting
- **Nothing arrives / exporter "connection aborted"**: SigNoz has no organization yet — do step 3.
- **`clickhouse-keeper` keeps restarting (exit 139)**: a known Docker Desktop issue; SigNoz recommends Docker Engine inside WSL 2 instead.
- **Port 8080 or 4317/4318 in use**: stop the other program or change ports in `pours/deployment/compose.yaml`.
- The live Vercel site does not send telemetry (it cannot reach your computer). To include it, run SigNoz on a reachable server (or SigNoz Cloud) and set `OTEL_EXPORTER_OTLP_ENDPOINT` in Vercel.
