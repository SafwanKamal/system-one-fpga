# Finish the active simulation before launching one synthesis-only job.
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$evidence = Join-Path $repoRoot 'build/v2/rtl-dot-check'
$deadline = [DateTime]::UtcNow.AddHours(2)
do {
    $lastLog = Join-Path $evidence 'boundary-1024.log'
    if ((Test-Path $lastLog) -and (Select-String -LiteralPath $lastLog -Pattern 'PASS: KR260 block bit-exact, 3 cases, 384 words compared' -Quiet)) { break }
    foreach ($log in Get-ChildItem -LiteralPath $evidence -Filter '*.log') {
        if (Select-String -LiteralPath $log.FullName -Pattern '^%Error|^FAIL:|Assertion failed|^Aborting' -Quiet) {
            throw "Simulation failed; inspect $($log.FullName)"
        }
    }
    if ([DateTime]::UtcNow -gt $deadline) { throw 'Simulation wait timed out; do not synthesize without evidence' }
    Start-Sleep -Seconds 20
} while ($true)
& (Join-Path $PSScriptRoot 'preflight_dot_candidate.ps1')
