$ErrorActionPreference='Stop'
$repoRoot=(Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$status=Join-Path $repoRoot 'build/v2/attention16-resume-controller-status.json'
function Save-Status($state,$detail) {
    @{state=$state;detail=$detail;pid=$PID;updated_utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath $status
}
try {
    Save-Status 'resuming' 'Reuse compiled binary and preserve completed wide/L12 cases; no RTL edits or Vivado build'
    & wsl.exe -d Ubuntu-24.04 --cd $repoRoot -- bash simulation/v2/resume_kr260_attention16.sh
    if($LASTEXITCODE -ne 0){throw 'Resume gate failed; preserve evidence'}
    Save-Status 'checking_head_groups' 'Existing full cases complete; compare new32head fixture on preserved baseline/16lane binaries'
    & wsl.exe -d Ubuntu-24.04 --cd $repoRoot -- bash simulation/v2/run_attention16_head_groups.sh
    if($LASTEXITCODE -ne 0){throw 'Head-group numerical comparison failed'}
    Save-Status 'numerical_logs_ready' 'Review exact outputs/cycles and hashes before combining cuts; no automatic full build'
} catch {Save-Status 'failed' $_.Exception.Message;throw}
