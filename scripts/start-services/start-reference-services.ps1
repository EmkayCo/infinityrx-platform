# InfinityRx Reference + Operational Service Launcher
# =====================================================
# Launches the three reference-data services against infinityrx_reference,
# and the two operational services against infinityrx_dev.
#
# DB/port mapping:
#   pharmacy-directory   port 8009  DB: infinityrx_reference  env: DATABASE_URL (asyncpg)
#   prescriber-directory port 8010  DB: infinityrx_reference  env: PRESCRIBER_DB_URL (psycopg2/sync)
#   drug-database        port 8011  DB: infinityrx_reference  env: DRUG_DB_DATABASE_URL (psycopg2/sync)
#   billing              port 8001  DB: infinityrx_dev         env: BILLING_DATABASE_URL
#   reclaimrx            port 8002  DB: infinityrx_dev         env: RECLAIMRX_DATABASE_URL
#
# Credentials:
#   Reference DB user  : infinityrx / infinityrx_bootstrap  (superuser, has access to all reference schemas)
#   Dev DB user        : ifx_dev_app / dev_password          (app user for operational data)
#   NOTE: ifx_dev_app does NOT have USAGE on drug_database/prescriber_dir/pharmacy_dir schemas
#         in infinityrx_reference. Use infinityrx superuser for reference services.
#
# Usage: Run this script from PowerShell. Each service launches in a hidden window.
# Logs:  C:\Temp\ifx-logs\<service>.log
# Stop:  netstat -ano | Select-String ":8009|:8010|:8011|:8001|:8002" then Stop-Process -Id <PID>

$REPO = "C:\Users\MK\Documents\Code Projects\InfinityRx\infinityrx-platform"
$PYTHON = "$REPO\.venv\Scripts\python.exe"
$LOGDIR = "C:\Temp\ifx-logs"
$TMPDIR = "C:\Temp"

if (-not (Test-Path $LOGDIR)) { New-Item -ItemType Directory -Path $LOGDIR -Force | Out-Null }

# --- Shared env vars for all services ---
$COMMON_ENV = @"
`$env:INFINITYRX_ENV = "development"
`$env:ENVIRONMENT = "development"
`$env:JWT_SECRET = "ifx-dev-jwt-secret-2026-local-only-do-not-use-in-prod-32plus"
`$env:ENCRYPTION_KEY_ACTIVE = "ifx-dev-encryption-key-32chars!!"
`$env:REDIS_URL = "redis://localhost:6379/1"
`$env:RABBITMQ_URL = "amqp://infinityrx:infinityrx_bootstrap@localhost:5672/"
`$env:CORS_ORIGINS = "http://localhost:3000"
"@

# =============================================================
# REFERENCE SERVICES  (DB: infinityrx_reference, user: infinityrx)
# Uses the PostgreSQL superuser because ifx_dev_app lacks USAGE
# on the reference schemas in infinityrx_reference.
# =============================================================

# drug-database  (port 8011)
$drugScript = @"
$COMMON_ENV
`$env:DATABASE_URL = "postgresql+asyncpg://infinityrx:infinityrx_bootstrap@localhost:5432/infinityrx_reference"
`$env:DATABASE_URL_SYNC = "postgresql://infinityrx:infinityrx_bootstrap@localhost:5432/infinityrx_reference"
`$env:DRUG_DB_DATABASE_URL = "postgresql://infinityrx:infinityrx_bootstrap@localhost:5432/infinityrx_reference"
`$env:PYTHONPATH = "$REPO\modules\drug-database;$REPO"

& "$PYTHON" -m uvicorn src.main:app --host 127.0.0.1 --port 8011 2>&1 | Out-File $LOGDIR\drug-database.log -Encoding utf8
"@
$drugScript | Out-File "$TMPDIR\ifx-drug-database.ps1" -Encoding utf8
Start-Process powershell -ArgumentList "-NonInteractive -File $TMPDIR\ifx-drug-database.ps1" -WindowStyle Hidden
Write-Host "Started: drug-database        port=8011  db=infinityrx_reference"

# prescriber-directory  (port 8010)
$prescriberScript = @"
$COMMON_ENV
`$env:DATABASE_URL = "postgresql+asyncpg://infinityrx:infinityrx_bootstrap@localhost:5432/infinityrx_reference"
`$env:DATABASE_URL_SYNC = "postgresql://infinityrx:infinityrx_bootstrap@localhost:5432/infinityrx_reference"
`$env:PRESCRIBER_DB_URL = "postgresql://infinityrx:infinityrx_bootstrap@localhost:5432/infinityrx_reference"
`$env:PYTHONPATH = "$REPO\modules\prescriber-directory;$REPO"

& "$PYTHON" -m uvicorn src.main:app --host 127.0.0.1 --port 8010 2>&1 | Out-File $LOGDIR\prescriber-directory.log -Encoding utf8
"@
$prescriberScript | Out-File "$TMPDIR\ifx-prescriber-directory.ps1" -Encoding utf8
Start-Process powershell -ArgumentList "-NonInteractive -File $TMPDIR\ifx-prescriber-directory.ps1" -WindowStyle Hidden
Write-Host "Started: prescriber-directory  port=8010  db=infinityrx_reference"

# pharmacy-directory  (port 8009)
# NOTE: pharmacy_dir.pharmacies does NOT exist in infinityrx_reference (or infinityrx_dev).
# Reference data (dataq_master, ncpdp_*) is present (82,643 rows). The pharmacies table
# requires migrations to be run: cd modules/pharmacy-directory && alembic upgrade head
# The service starts and /health passes; search/lookup endpoints return 500 until migrated.
$pharmacyScript = @"
$COMMON_ENV
`$env:DATABASE_URL = "postgresql+asyncpg://infinityrx:infinityrx_bootstrap@localhost:5432/infinityrx_reference"
`$env:DATABASE_URL_SYNC = "postgresql://infinityrx:infinityrx_bootstrap@localhost:5432/infinityrx_reference"
`$env:PYTHONPATH = "$REPO\modules\pharmacy-directory;$REPO"

& "$PYTHON" -m uvicorn src.app:app --host 127.0.0.1 --port 8009 2>&1 | Out-File $LOGDIR\pharmacy-directory.log -Encoding utf8
"@
$pharmacyScript | Out-File "$TMPDIR\ifx-pharmacy-directory.ps1" -Encoding utf8
Start-Process powershell -ArgumentList "-NonInteractive -File $TMPDIR\ifx-pharmacy-directory.ps1" -WindowStyle Hidden
Write-Host "Started: pharmacy-directory    port=8009  db=infinityrx_reference  (search needs migrations)"

# =============================================================
# OPERATIONAL SERVICES  (DB: infinityrx_dev, user: ifx_dev_app)
# =============================================================

# billing  (port 8001)
$billingScript = @"
$COMMON_ENV
`$env:DATABASE_URL = "postgresql+asyncpg://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev"
`$env:DATABASE_URL_SYNC = "postgresql://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev"
`$env:BILLING_DATABASE_URL = "postgresql://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev"
`$env:PYTHONPATH = "$REPO\modules\billing;$REPO"

& "$PYTHON" -m uvicorn src.main:app --host 127.0.0.1 --port 8001 2>&1 | Out-File $LOGDIR\billing.log -Encoding utf8
"@
$billingScript | Out-File "$TMPDIR\ifx-billing.ps1" -Encoding utf8
Start-Process powershell -ArgumentList "-NonInteractive -File $TMPDIR\ifx-billing.ps1" -WindowStyle Hidden
Write-Host "Started: billing               port=8001  db=infinityrx_dev"

# reclaimrx  (port 8002)
$reclaimrxScript = @"
$COMMON_ENV
`$env:DATABASE_URL = "postgresql+asyncpg://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev"
`$env:DATABASE_URL_SYNC = "postgresql://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev"
`$env:RECLAIMRX_DATABASE_URL = "postgresql://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev"
`$env:PYTHONPATH = "$REPO\modules\reclaimrx;$REPO"

& "$PYTHON" -m uvicorn src.main:app --host 127.0.0.1 --port 8002 2>&1 | Out-File $LOGDIR\reclaimrx.log -Encoding utf8
"@
$reclaimrxScript | Out-File "$TMPDIR\ifx-reclaimrx.ps1" -Encoding utf8
Start-Process powershell -ArgumentList "-NonInteractive -File $TMPDIR\ifx-reclaimrx.ps1" -WindowStyle Hidden
Write-Host "Started: reclaimrx             port=8002  db=infinityrx_dev"

Write-Host ""
Write-Host "All services launched. Logs: $LOGDIR"
Write-Host "Health checks (allow ~10s for startup):"
Write-Host "  Invoke-WebRequest http://127.0.0.1:8011/health"
Write-Host "  Invoke-WebRequest http://127.0.0.1:8010/health"
Write-Host "  Invoke-WebRequest http://127.0.0.1:8009/health"
Write-Host "  Invoke-WebRequest http://127.0.0.1:8001/health"
Write-Host "  Invoke-WebRequest http://127.0.0.1:8002/health"
