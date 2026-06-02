# InfinityRx Full Platform Service Launcher
# ==========================================
# Launches all 18 backend modules for local development testing.
# Mirrors the pattern from start-reference-services.ps1 exactly:
# per-service detached hidden window via Start-Process, logging to C:\Temp\ifx-logs\<service>.log
#
# DB mapping:
#   REFERENCE DB: postgresql+asyncpg://infinityrx:infinityrx_bootstrap@localhost:5432/infinityrx_reference
#   DEV DB:       postgresql+asyncpg://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev
#
# Port map:
#   8000 core-platform        DEV
#   8001 billing              DEV
#   8002 reclaimrx            DEV
#   8003 medical-claims       DEV
#   8004 member-management    DEV
#   8005 plan-design          DEV
#   8006 program-config       DEV
#   8007 rebate-management    DEV
#   8008 rules-engine         DEV
#   8009 pharmacy-directory   REFERENCE  (src.app:app)
#   8010 prescriber-directory REFERENCE
#   8011 drug-database        REFERENCE
#   8012 reporting            DEV
#   8013 dataiq               DEV
#   8014 adjudication-engine  DEV
#   8015 edi-compliance       DEV
#   8016 ebv-ebi-rtbc         DEV
#   8017 prior-authorization  DEV
#
# Usage: Run from PowerShell. Each service launches in a hidden detached window.
# Logs:  C:\Temp\ifx-logs\<service>.log
# Stop:  netstat -ano | Select-String ":8000|:8001|...|:8017" then Stop-Process -Id <PID>

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
`$env:ENCRYPTION_KEY_ACTIVE = "aWZ4LWRldi1lbmNyeXB0aW9uLWtleS0zMmNoYXJzISE="
`$env:REDIS_URL = "redis://localhost:6379/1"
`$env:RABBITMQ_URL = "amqp://infinityrx:infinityrx_bootstrap@localhost:5672/"
`$env:CORS_ALLOW_ORIGINS = "http://localhost:3000,http://localhost:3001"
"@

# =============================================================
# DEV SERVICES  (DB: infinityrx_dev, user: ifx_dev_app)
# =============================================================

# core-platform  (port 8000)
$corePlatformScript = @"
$COMMON_ENV
`$env:DATABASE_URL = "postgresql+asyncpg://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev"
`$env:DATABASE_URL_SYNC = "postgresql://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev"
`$env:PYTHONPATH = "$REPO\modules\core-platform;$REPO"

& "$PYTHON" -m uvicorn src.main:app --host 127.0.0.1 --port 8000 2>&1 | Out-File $LOGDIR\core-platform.log -Encoding utf8
"@
$corePlatformScript | Out-File "$TMPDIR\ifx-core-platform.ps1" -Encoding utf8
Start-Process powershell -ArgumentList "-NonInteractive -File $TMPDIR\ifx-core-platform.ps1" -WindowStyle Hidden
Write-Host "Started: core-platform         port=8000  db=infinityrx_dev"

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

# medical-claims  (port 8003)
$medicalClaimsScript = @"
$COMMON_ENV
`$env:DATABASE_URL = "postgresql+asyncpg://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev"
`$env:DATABASE_URL_SYNC = "postgresql://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev"
`$env:MEDICAL_CLAIMS_DB_URL = "postgresql://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev"
`$env:MEMBER_MANAGEMENT_URL = "http://127.0.0.1:8004"
`$env:PHARMACY_DIRECTORY_URL = "http://127.0.0.1:8009"
`$env:PYTHONPATH = "$REPO\modules\medical-claims;$REPO"

& "$PYTHON" -m uvicorn src.main:app --host 127.0.0.1 --port 8003 2>&1 | Out-File $LOGDIR\medical-claims.log -Encoding utf8
"@
$medicalClaimsScript | Out-File "$TMPDIR\ifx-medical-claims.ps1" -Encoding utf8
Start-Process powershell -ArgumentList "-NonInteractive -File $TMPDIR\ifx-medical-claims.ps1" -WindowStyle Hidden
Write-Host "Started: medical-claims        port=8003  db=infinityrx_dev"

# member-management  (port 8004)
$memberMgmtScript = @"
$COMMON_ENV
`$env:DATABASE_URL = "postgresql+asyncpg://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev"
`$env:DATABASE_URL_SYNC = "postgresql://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev"
`$env:MEMBER_DB_URL = "postgresql://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev"
`$env:PYTHONPATH = "$REPO\modules\member-management;$REPO"

& "$PYTHON" -m uvicorn src.main:app --host 127.0.0.1 --port 8004 2>&1 | Out-File $LOGDIR\member-management.log -Encoding utf8
"@
$memberMgmtScript | Out-File "$TMPDIR\ifx-member-management.ps1" -Encoding utf8
Start-Process powershell -ArgumentList "-NonInteractive -File $TMPDIR\ifx-member-management.ps1" -WindowStyle Hidden
Write-Host "Started: member-management     port=8004  db=infinityrx_dev"

# plan-design  (port 8005)
$planDesignScript = @"
$COMMON_ENV
`$env:DATABASE_URL = "postgresql+asyncpg://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev"
`$env:DATABASE_URL_SYNC = "postgresql://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev"
`$env:PLAN_DESIGN_DATABASE_URL = "postgresql://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev"
`$env:PYTHONPATH = "$REPO\modules\plan-design;$REPO"

& "$PYTHON" -m uvicorn src.main:app --host 127.0.0.1 --port 8005 2>&1 | Out-File $LOGDIR\plan-design.log -Encoding utf8
"@
$planDesignScript | Out-File "$TMPDIR\ifx-plan-design.ps1" -Encoding utf8
Start-Process powershell -ArgumentList "-NonInteractive -File $TMPDIR\ifx-plan-design.ps1" -WindowStyle Hidden
Write-Host "Started: plan-design           port=8005  db=infinityrx_dev"

# program-config  (port 8006)
$programConfigScript = @"
$COMMON_ENV
`$env:DATABASE_URL = "postgresql+asyncpg://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev"
`$env:DATABASE_URL_SYNC = "postgresql://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev"
`$env:PYTHONPATH = "$REPO\modules\program-config;$REPO"

& "$PYTHON" -m uvicorn src.main:app --host 127.0.0.1 --port 8006 2>&1 | Out-File $LOGDIR\program-config.log -Encoding utf8
"@
$programConfigScript | Out-File "$TMPDIR\ifx-program-config.ps1" -Encoding utf8
Start-Process powershell -ArgumentList "-NonInteractive -File $TMPDIR\ifx-program-config.ps1" -WindowStyle Hidden
Write-Host "Started: program-config        port=8006  db=infinityrx_dev"

# rebate-management  (port 8007)
$rebateMgmtScript = @"
$COMMON_ENV
`$env:DATABASE_URL = "postgresql+asyncpg://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev"
`$env:DATABASE_URL_SYNC = "postgresql://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev"
`$env:REBATE_DATABASE_URL = "postgresql://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev"
`$env:PYTHONPATH = "$REPO\modules\rebate-management;$REPO"

& "$PYTHON" -m uvicorn src.main:app --host 127.0.0.1 --port 8007 2>&1 | Out-File $LOGDIR\rebate-management.log -Encoding utf8
"@
$rebateMgmtScript | Out-File "$TMPDIR\ifx-rebate-management.ps1" -Encoding utf8
Start-Process powershell -ArgumentList "-NonInteractive -File $TMPDIR\ifx-rebate-management.ps1" -WindowStyle Hidden
Write-Host "Started: rebate-management     port=8007  db=infinityrx_dev"

# rules-engine  (port 8008)
$rulesEngineScript = @"
$COMMON_ENV
`$env:DATABASE_URL = "postgresql+asyncpg://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev"
`$env:DATABASE_URL_SYNC = "postgresql://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev"
`$env:PYTHONPATH = "$REPO\modules\rules-engine;$REPO"

& "$PYTHON" -m uvicorn src.main:app --host 127.0.0.1 --port 8008 2>&1 | Out-File $LOGDIR\rules-engine.log -Encoding utf8
"@
$rulesEngineScript | Out-File "$TMPDIR\ifx-rules-engine.ps1" -Encoding utf8
Start-Process powershell -ArgumentList "-NonInteractive -File $TMPDIR\ifx-rules-engine.ps1" -WindowStyle Hidden
Write-Host "Started: rules-engine          port=8008  db=infinityrx_dev"

# =============================================================
# REFERENCE SERVICES  (DB: infinityrx_reference, user: infinityrx)
# Uses the PostgreSQL superuser because ifx_dev_app lacks USAGE
# on the reference schemas in infinityrx_reference.
# =============================================================

# pharmacy-directory  (port 8009)  -- NOTE: src.app:app not src.main:app
$pharmacyScript = @"
$COMMON_ENV
`$env:DATABASE_URL = "postgresql+asyncpg://infinityrx:infinityrx_bootstrap@localhost:5432/infinityrx_reference"
`$env:DATABASE_URL_SYNC = "postgresql://infinityrx:infinityrx_bootstrap@localhost:5432/infinityrx_reference"
`$env:PYTHONPATH = "$REPO\modules\pharmacy-directory;$REPO"

& "$PYTHON" -m uvicorn src.app:app --host 127.0.0.1 --port 8009 2>&1 | Out-File $LOGDIR\pharmacy-directory.log -Encoding utf8
"@
$pharmacyScript | Out-File "$TMPDIR\ifx-pharmacy-directory.ps1" -Encoding utf8
Start-Process powershell -ArgumentList "-NonInteractive -File $TMPDIR\ifx-pharmacy-directory.ps1" -WindowStyle Hidden
Write-Host "Started: pharmacy-directory    port=8009  db=infinityrx_reference  (src.app:app)"

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

# drug-database  (port 8011)
$drugScript = @"
$COMMON_ENV
`$env:DATABASE_URL = "postgresql+asyncpg://infinityrx:infinityrx_bootstrap@localhost:5432/infinityrx_reference"
`$env:DATABASE_URL_SYNC = "postgresql://infinityrx:infinityrx_bootstrap@localhost:5432/infinityrx_reference"
`$env:DRUG_DB_DATABASE_URL = "postgresql://infinityrx:infinityrx_bootstrap@localhost:5432/infinityrx_reference"
`$env:DRUG_DATABASE_URL = "postgresql://infinityrx:infinityrx_bootstrap@localhost:5432/infinityrx_reference"
`$env:PYTHONPATH = "$REPO\modules\drug-database;$REPO"

& "$PYTHON" -m uvicorn src.main:app --host 127.0.0.1 --port 8011 2>&1 | Out-File $LOGDIR\drug-database.log -Encoding utf8
"@
$drugScript | Out-File "$TMPDIR\ifx-drug-database.ps1" -Encoding utf8
Start-Process powershell -ArgumentList "-NonInteractive -File $TMPDIR\ifx-drug-database.ps1" -WindowStyle Hidden
Write-Host "Started: drug-database         port=8011  db=infinityrx_reference"

# =============================================================
# MORE DEV SERVICES
# =============================================================

# reporting  (port 8012)
$reportingScript = @"
$COMMON_ENV
`$env:DATABASE_URL = "postgresql+asyncpg://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev"
`$env:DATABASE_URL_SYNC = "postgresql://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev"
`$env:PYTHONPATH = "$REPO\modules\reporting;$REPO"

& "$PYTHON" -m uvicorn src.main:app --host 127.0.0.1 --port 8012 2>&1 | Out-File $LOGDIR\reporting.log -Encoding utf8
"@
$reportingScript | Out-File "$TMPDIR\ifx-reporting.ps1" -Encoding utf8
Start-Process powershell -ArgumentList "-NonInteractive -File $TMPDIR\ifx-reporting.ps1" -WindowStyle Hidden
Write-Host "Started: reporting             port=8012  db=infinityrx_dev"

# dataiq  (port 8013)
$dataiqScript = @"
$COMMON_ENV
`$env:DATABASE_URL = "postgresql+asyncpg://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev"
`$env:DATABASE_URL_SYNC = "postgresql://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev"
`$env:PYTHONPATH = "$REPO\modules\dataiq;$REPO"

& "$PYTHON" -m uvicorn src.main:app --host 127.0.0.1 --port 8013 2>&1 | Out-File $LOGDIR\dataiq.log -Encoding utf8
"@
$dataiqScript | Out-File "$TMPDIR\ifx-dataiq.ps1" -Encoding utf8
Start-Process powershell -ArgumentList "-NonInteractive -File $TMPDIR\ifx-dataiq.ps1" -WindowStyle Hidden
Write-Host "Started: dataiq                port=8013  db=infinityrx_dev"

# adjudication-engine  (port 8014)
$adjudicationScript = @"
$COMMON_ENV
`$env:DATABASE_URL = "postgresql+asyncpg://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev"
`$env:DATABASE_URL_SYNC = "postgresql://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev"
`$env:ADMIN_DATABASE_URL = "postgresql://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev"
`$env:PYTHONPATH = "$REPO\modules\adjudication-engine;$REPO"

& "$PYTHON" -m uvicorn src.main:app --host 127.0.0.1 --port 8014 2>&1 | Out-File $LOGDIR\adjudication-engine.log -Encoding utf8
"@
$adjudicationScript | Out-File "$TMPDIR\ifx-adjudication-engine.ps1" -Encoding utf8
Start-Process powershell -ArgumentList "-NonInteractive -File $TMPDIR\ifx-adjudication-engine.ps1" -WindowStyle Hidden
Write-Host "Started: adjudication-engine   port=8014  db=infinityrx_dev"

# edi-compliance  (port 8015)
$ediScript = @"
$COMMON_ENV
`$env:DATABASE_URL = "postgresql+asyncpg://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev"
`$env:DATABASE_URL_SYNC = "postgresql://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev"
`$env:PYTHONPATH = "$REPO\modules\edi-compliance;$REPO"

& "$PYTHON" -m uvicorn src.main:app --host 127.0.0.1 --port 8015 2>&1 | Out-File $LOGDIR\edi-compliance.log -Encoding utf8
"@
$ediScript | Out-File "$TMPDIR\ifx-edi-compliance.ps1" -Encoding utf8
Start-Process powershell -ArgumentList "-NonInteractive -File $TMPDIR\ifx-edi-compliance.ps1" -WindowStyle Hidden
Write-Host "Started: edi-compliance        port=8015  db=infinityrx_dev"

# ebv-ebi-rtbc  (port 8016)
$ebvScript = @"
$COMMON_ENV
`$env:DATABASE_URL = "postgresql+asyncpg://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev"
`$env:DATABASE_URL_SYNC = "postgresql://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev"
`$env:PYTHONPATH = "$REPO\modules\ebv-ebi-rtbc;$REPO"

& "$PYTHON" -m uvicorn src.main:app --host 127.0.0.1 --port 8016 2>&1 | Out-File $LOGDIR\ebv-ebi-rtbc.log -Encoding utf8
"@
$ebvScript | Out-File "$TMPDIR\ifx-ebv-ebi-rtbc.ps1" -Encoding utf8
Start-Process powershell -ArgumentList "-NonInteractive -File $TMPDIR\ifx-ebv-ebi-rtbc.ps1" -WindowStyle Hidden
Write-Host "Started: ebv-ebi-rtbc          port=8016  db=infinityrx_dev"

# prior-authorization  (port 8017)
$priorAuthScript = @"
$COMMON_ENV
`$env:DATABASE_URL = "postgresql+asyncpg://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev"
`$env:DATABASE_URL_SYNC = "postgresql://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev"
`$env:PYTHONPATH = "$REPO\modules\prior-authorization;$REPO"

& "$PYTHON" -m uvicorn src.main:app --host 127.0.0.1 --port 8017 2>&1 | Out-File $LOGDIR\prior-authorization.log -Encoding utf8
"@
$priorAuthScript | Out-File "$TMPDIR\ifx-prior-authorization.ps1" -Encoding utf8
Start-Process powershell -ArgumentList "-NonInteractive -File $TMPDIR\ifx-prior-authorization.ps1" -WindowStyle Hidden
Write-Host "Started: prior-authorization   port=8017  db=infinityrx_dev"

Write-Host ""
Write-Host "All 18 services launched. Logs: $LOGDIR"
Write-Host "Allow ~20s for startup before health checks."
Write-Host "Kill all: Get-Process python | Stop-Process"
