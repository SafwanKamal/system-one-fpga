# A single local dependency job, not a recurring automation. No routing/deploy.
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$statusPath = Join-Path $repoRoot 'build/v2/dot7-queue-status.json'
$lockPath = Join-Path $repoRoot 'build/v2/dot7-queue.started'
New-Item -ItemType File -Path $lockPath -ErrorAction Stop | Out-Null
$watch = [Diagnostics.Stopwatch]::StartNew()
function Save-Queue([string]$state,[string]$detail) {
    @{state=$state;detail=$detail;updated_utc=[DateTime]::UtcNow.ToString('o');elapsed_seconds=$watch.Elapsed.TotalSeconds;routing_queued=$false;hardware_deployed=$false} |
        ConvertTo-Json | Set-Content -LiteralPath $statusPath
}
try {
    Save-Queue 'waiting_for_regressions' 'Require complete 53-case/source/OOC gates before one full synthesis job'
    $summary = Join-Path $repoRoot 'build/v2/rtl-dot7-large-check/summary.json'
    while (!(Test-Path $summary)) {
        if ($watch.Elapsed.TotalHours -ge 2) { throw 'Regression dependency timed out; inspect existing jobs, do not duplicate' }
        foreach ($dir in @('build/v2/rtl-dot7-check','build/v2/rtl-dot7-large-check')) {
            $logs = Get-ChildItem -LiteralPath (Join-Path $repoRoot $dir) -Filter '*.log' -ErrorAction SilentlyContinue
            if ($logs | Select-String -Pattern '^%Error|^FAIL:|Assertion failed|^Aborting|fatal error:|make: \*\*\*') {
                throw "Regression failure found in $dir; full synthesis not started"
            }
        }
        Start-Sleep -Seconds 10
    }
    if (!(Test-Path (Join-Path $repoRoot 'build/v2/dot7-ooc-summary.json'))) { throw 'Complete OOC summary missing; review before synthesis' }
    Save-Queue 'running_preflight' 'Numerical summary available; revalidate all gates and run synthesis only'
    & (Join-Path $PSScriptRoot 'preflight_dot7_large_candidate.ps1')
    $result = Get-Content -LiteralPath (Join-Path $repoRoot 'build/v2/kr260-opt-dot7-large/completion-status.json') -Raw | ConvertFrom-Json
    if ($result.state -ne 'preflight_ready') { throw "Preflight did not pass: $($result.state)" }
    Save-Queue 'preflight_ready' 'Full synthesis passed; placement/timing review still required. No routing or upload queued.'
} catch {
    Save-Queue 'failed' $_.Exception.Message
    throw
}
