$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
Set-Location -LiteralPath $repo
$status = Join-Path $repo 'build/v2/operand-prototype-gates-status.json'
$jobs = @('rtl-probability-input-check', 'rtl-input-embed-check')
@{state='waiting_existing_regressions'; started_utc=[DateTime]::UtcNow.ToString('o'); pid=$PID} |
    ConvertTo-Json | Set-Content -LiteralPath $status
try {
    while ($true) {
        $ready = $true
        foreach ($job in $jobs) {
            $completion = Join-Path $repo "build/v2/$job/completion-status.json"
            if (-not (Test-Path -LiteralPath $completion)) { $ready = $false; continue }
            $result = Get-Content -LiteralPath $completion -Raw | ConvertFrom-Json
            if ($result.exit_code -ne 0 -or -not $result.complete) { throw "Regression failed: $job" }
        }
        if ($ready) { break }
        Start-Sleep -Seconds 10
    }
    & "$repo/.venv/Scripts/python.exe" scripts/v2/kr260/review_operand_cut_prototypes.py
    if ($LASTEXITCODE -ne 0) { throw 'Numerical, cycle or source review failed' }
    @{state='prototype_integration_ready'; completed_utc=[DateTime]::UtcNow.ToString('o'); pid=$PID;
      next_action='Integrate distinct default-off input capture and embedding parameters, then parameterized regression before freezing or synthesis';
      synthesis_started=$false; routing_approved=$false; hardware_qualified=$false} |
        ConvertTo-Json | Set-Content -LiteralPath $status
} catch {
    @{state='failed'; updated_utc=[DateTime]::UtcNow.ToString('o'); message=$_.Exception.Message; pid=$PID} |
        ConvertTo-Json | Set-Content -LiteralPath $status
    throw
}
