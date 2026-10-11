# Start local SigNoz (specs/observability-spec.md §5). Requires Docker Desktop running.
# First run downloads Foundry (SigNoz's installer) and ~1-2 GB of images.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$foundry = ".tools\foundry_windows_amd64\bin\foundryctl.exe"
if (-not (Test-Path $foundry)) {
    New-Item -ItemType Directory -Force ".tools" | Out-Null
    Invoke-WebRequest -UseBasicParsing -OutFile ".tools\foundry.tar.gz" `
        -Uri "https://github.com/SigNoz/foundry/releases/latest/download/foundry_windows_amd64.tar.gz"
    tar -xzf ".tools\foundry.tar.gz" -C ".tools"
}

if (Test-Path "pours\deployment\compose.yaml") {
    docker compose -f "pours\deployment\compose.yaml" up -d
} else {
    & $foundry cast -f casting.yaml
}
Write-Host "SigNoz UI: http://localhost:8080  |  OTLP HTTP: http://localhost:4318"
