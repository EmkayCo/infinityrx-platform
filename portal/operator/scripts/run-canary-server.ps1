<#
.SYNOPSIS
Wave B10 W1.13 dual-bundler canary runner. ASCII-only.

.DESCRIPTION
Starts 'next dev' under the specified bundler, waits for Ready, HTTP-probes
7 routes (charter W1 lock crit c + W1.14a package-name canary), tree-kills
the server, verifies port 3000 + .next/dev/lock both released. Captures all
evidence to a per-bundler log + Werkbench wave dir.

Per codex ADVERSARIAL R1 #4 + R2 A4 + R3 A4: uses Start-Process -PassThru
for REAL Next PID (not wrapper), explicit -RedirectStandardOutput/-Error
flags, and 'taskkill /F /T /PID' for FULL process tree (Turbopack worker
pool spawns children that hold port + lockfile).

.PARAMETER Bundler
"turbopack" or "webpack". Required.

.EXAMPLE
./run-canary-server.ps1 -Bundler turbopack
./run-canary-server.ps1 -Bundler webpack
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("turbopack", "webpack")]
    [string]$Bundler
)

$ErrorActionPreference = "Stop"

# Resolve repo paths from script location for portability.
$repoRoot = Resolve-Path "$PSScriptRoot/../../.." -ErrorAction Stop
$operatorDir = Resolve-Path "$PSScriptRoot/.." -ErrorAction Stop

# Werkbench wave dir is side-by-side with infinityrx-platform.
$wavesDirCandidate = "$repoRoot/../../../Werkbench/projects/infinityrx-platform/waves/B10"
$wavesDir = $repoRoot
try {
    $resolved = Resolve-Path $wavesDirCandidate -ErrorAction Stop
    $wavesDir = $resolved
} catch {
    Write-Warning "Werkbench wave dir not at expected path; writing logs to repo root."
}

$logFile = Join-Path $wavesDir "w1-canary-$Bundler.log"
$resultsFile = Join-Path $wavesDir "w1-canary-$Bundler-results.json"

Write-Host "=== W1.13 canary runner -- bundler: $Bundler ==="
Write-Host "    repo root:   $repoRoot"
Write-Host "    operator:    $operatorDir"
Write-Host "    log file:    $logFile"
Write-Host "    results:     $resultsFile"

"" | Set-Content -LiteralPath $logFile

# Resolve npx.cmd specifically (Start-Process cannot exec .ps1 wrappers).
# Get-Command may return npx.ps1; we explicitly want the .cmd batch wrapper
# that's installed alongside it in the Node.js bin dir.
$npxCmd = $null
$candidate = (Get-Command npx -ErrorAction SilentlyContinue).Source
if ($candidate) {
    $cmdPath = [System.IO.Path]::ChangeExtension($candidate, "cmd")
    if (Test-Path -LiteralPath $cmdPath) {
        $npxCmd = $cmdPath
    } else {
        # Fallback: scan PATH for npx.cmd directly
        foreach ($dir in ($env:PATH -split [System.IO.Path]::PathSeparator)) {
            $try = Join-Path $dir "npx.cmd"
            if (Test-Path -LiteralPath $try) { $npxCmd = $try; break }
        }
    }
}
if (-not $npxCmd) {
    Write-Error "npx.cmd not found on PATH (Get-Command found: $candidate)"
    exit 7
}

$npxArgs = @("next", "dev")
if ($Bundler -eq "webpack") {
    $npxArgs += "--webpack"
} else {
    $npxArgs += "--turbopack"
}

Write-Host ""
Write-Host "[$Bundler] Starting: $npxCmd $($npxArgs -join ' ')"
Push-Location $operatorDir

$proc = $null
try {
    $proc = Start-Process -FilePath $npxCmd `
        -ArgumentList $npxArgs `
        -PassThru `
        -NoNewWindow `
        -RedirectStandardOutput $logFile `
        -RedirectStandardError "$logFile.err"
    Write-Host "[$Bundler] Started PID: $($proc.Id)"
} catch {
    Pop-Location
    Write-Error "[$Bundler] Failed to start: $_"
    exit 2
}

$startTime = Get-Date
$readyTimeout = 90
$ready = $false
while (((Get-Date) - $startTime).TotalSeconds -lt $readyTimeout) {
    Start-Sleep -Milliseconds 500
    if (Test-Path $logFile) {
        $content = Get-Content -LiteralPath $logFile -Raw -ErrorAction SilentlyContinue
        if ($content -and ($content -match "Ready in" -or $content -match "started server on")) {
            $ready = $true
            break
        }
        if ($content -and $content -match "EADDRINUSE") {
            Write-Error "[$Bundler] Port 3000 already in use; aborting."
            try { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue } catch {}
            Pop-Location
            exit 3
        }
    }
}

if (-not $ready) {
    Write-Error "[$Bundler] Timed out after $readyTimeout seconds waiting for Ready signal."
    & taskkill /F /T /PID $proc.Id 2>&1 | Out-Null
    Pop-Location
    exit 4
}

$elapsedReady = ((Get-Date) - $startTime).TotalSeconds
Write-Host "[$Bundler] Ready in $elapsedReady seconds"

$canaryRoutes = @(
    "/login",
    "/",
    "/dashboard",
    "/admin/paysync/cycles",
    "/api/auth/session",
    "/analytics/claims",
    "/api/b10-canary"
)

$probeResults = @()
foreach ($route in $canaryRoutes) {
    $url = "http://127.0.0.1:3000$route"
    $probeStart = Get-Date
    $statusCode = -1
    $bodyExcerpt = ""
    try {
        $resp = Invoke-WebRequest -Uri $url -UseBasicParsing -MaximumRedirection 0 -TimeoutSec 15 -ErrorAction Stop
        $statusCode = $resp.StatusCode
        # PS 5.1: 30x responses come back successfully (no throw) with Content as Byte[].
        # Decode to string when Content is bytes; otherwise use directly.
        $contentStr = if ($resp.Content -is [byte[]]) {
            if ($resp.Content.Length -gt 0) { [System.Text.Encoding]::UTF8.GetString($resp.Content) } else { "" }
        } else {
            [string]$resp.Content
        }
        $bodyExcerpt = $contentStr.Substring(0, [Math]::Min(200, $contentStr.Length))
        # If 30x, capture the Location header for evidence.
        if ($statusCode -ge 300 -and $statusCode -lt 400) {
            $loc = $resp.Headers["Location"]
            if ($loc) { $bodyExcerpt = "(redirect to: $loc)" }
        }
    } catch {
        if ($_.Exception.Response) {
            $statusCode = [int]$_.Exception.Response.StatusCode
            $bodyExcerpt = "(redirect/HTTP error: $($_.Exception.Response.StatusCode))"
        } else {
            $statusCode = -1
            # Capture exception type + full message for diagnosis
            $exType = $_.Exception.GetType().FullName
            $exMsg = $_.Exception.Message
            $innerMsg = if ($_.Exception.InnerException) { $_.Exception.InnerException.Message } else { "" }
            $bodyExcerpt = "($exType : $exMsg | inner: $innerMsg)"
        }
    }
    $probeMs = [int]((Get-Date) - $probeStart).TotalMilliseconds
    $isFatal = ($statusCode -ge 500) -or ($statusCode -lt 0)
    $probeResults += [pscustomobject]@{
        route       = $route
        status_code = $statusCode
        response_ms = $probeMs
        body_excerpt = $bodyExcerpt
        fatal       = $isFatal
    }
    $statusLabel = "OK"
    if ($isFatal) { $statusLabel = "FATAL" } elseif ($statusCode -lt 200 -or $statusCode -ge 400) { $statusLabel = "WARN" }
    Write-Host "  [$statusLabel] $route -> $statusCode in $probeMs ms"
}

Write-Host ""
Write-Host "[$Bundler] Killing process tree PID=$($proc.Id) ..."
$killOutput = & taskkill /F /T /PID $proc.Id 2>&1
Write-Host "  taskkill: $killOutput"

$cleanupTimeout = 30
$cleanupStart = Get-Date
$portFree = $false
$lockFree = $false
while (((Get-Date) - $cleanupStart).TotalSeconds -lt $cleanupTimeout) {
    Start-Sleep -Milliseconds 500
    $portInUse = $null -ne (Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue)
    $lockExists = Test-Path -LiteralPath (Join-Path $operatorDir ".next/dev/lock")
    if (-not $portInUse) { $portFree = $true }
    if (-not $lockExists) { $lockFree = $true }
    if ($portFree -and $lockFree) { break }
}

if (-not $portFree) {
    Write-Warning "[$Bundler] Port 3000 still in use after $cleanupTimeout seconds cleanup wait."
}
if (-not $lockFree) {
    Write-Warning "[$Bundler] .next/dev/lock still present after $cleanupTimeout seconds cleanup wait."
}

$summary = [pscustomobject]@{
    bundler        = $Bundler
    pid            = $proc.Id
    ready_seconds  = $elapsedReady
    routes         = $probeResults
    cleanup        = @{
        port_3000_free = $portFree
        lock_file_free = $lockFree
    }
    timestamp      = (Get-Date).ToUniversalTime().ToString("o")
    repo_root      = $repoRoot.Path
}
$summary | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $resultsFile

Pop-Location

$fatalRoutes = @($probeResults | Where-Object { $_.fatal })
if ($fatalRoutes.Count -gt 0) {
    Write-Host ""
    Write-Host "[$Bundler] FAIL: $($fatalRoutes.Count) route(s) returned 5xx or connection error."
    exit 5
}
if (-not ($portFree -and $lockFree)) {
    Write-Host ""
    Write-Host "[$Bundler] FAIL: cleanup verification failed (port free: $portFree, lock free: $lockFree)."
    exit 6
}

Write-Host ""
Write-Host "[$Bundler] PASS: all 7 routes returned non-fatal; cleanup verified."
exit 0
