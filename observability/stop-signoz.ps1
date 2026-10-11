# Stop local SigNoz but keep its data (start again with start-signoz.ps1).
# To delete all telemetry data as well: docker compose -f pours\deployment\compose.yaml down -v
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
docker compose -f "pours\deployment\compose.yaml" stop
