$ErrorActionPreference = 'Stop'

$RepoRoot = (Get-Location).Path
$PatchScript = Join-Path $RepoRoot 'rozgaar_one_shot_realtime_fix.py'

if (-not (Test-Path (Join-Path $RepoRoot 'backend'))) {
    throw "Run this script from the Rozgaar repository root."
}
if (-not (Test-Path $PatchScript)) {
    throw "Missing rozgaar_one_shot_realtime_fix.py in the repository root."
}

Write-Host "[1/4] Applying targeted Realtime code fixes..." -ForegroundColor Cyan
python $PatchScript $RepoRoot

Write-Host "[2/4] Rebuilding/recreating the current local stack..." -ForegroundColor Cyan
docker compose up -d --build --force-recreate backend redis celery consumer worker admin

Write-Host "[3/4] Checking service status..." -ForegroundColor Cyan
docker compose ps

Write-Host "[4/4] Checking backend health and required Realtime environment..." -ForegroundColor Cyan
$health = curl.exe -fsS http://127.0.0.1:8000/health
Write-Host "Health: $health" -ForegroundColor Green

docker compose exec backend sh -c 'for v in SUPABASE_URL SUPABASE_ANON_KEY SUPABASE_JWT_SECRET; do if [ -n "$(printenv "$v")" ]; then echo "$v=PRESENT"; else echo "$v=MISSING"; fi; done'

Write-Host "" 
Write-Host "Runtime is rebuilt and the targeted code fixes are applied." -ForegroundColor Green
Write-Host "Next test: open the Admin site and verify /api/v1/realtime/token returns HTTP 200." -ForegroundColor Yellow
