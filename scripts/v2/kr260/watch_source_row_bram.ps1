$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$output=Join-Path $repo 'build/v2/source-row-bram-gates-status.json'
$gate=Join-Path $repo 'build/v2/rtl-source-row-bram-check/completion-status.json'
@{state='waiting_existing_regression';pid=$PID;started_utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath $output
try {
    while(-not (Test-Path -LiteralPath $gate)){Start-Sleep -Seconds 10}
    $result=Get-Content -LiteralPath $gate -Raw | ConvertFrom-Json
    if(-not $result.complete -or $result.exit_code -ne 0){throw 'Grouped prototype regression failed'}
    & (Join-Path $repo '.venv/Scripts/python.exe') (Join-Path $PSScriptRoot 'review_source_row.py') --bram
    if($LASTEXITCODE -ne 0){throw 'Grouped output/cycle/source review failed'}
    @{state='prototype_integration_ready';pid=$PID;completed_utc=[DateTime]::UtcNow.ToString('o');
      next_action='Integrate default-off row-address and explicit linear BRAM parameters with distinct profile; parameterized proof before full synthesis';
      synthesis_started=$false;routing_approved=$false} | ConvertTo-Json | Set-Content -LiteralPath $output
} catch {
    @{state='failed';pid=$PID;updated_utc=[DateTime]::UtcNow.ToString('o');message=$_.Exception.Message} | ConvertTo-Json | Set-Content -LiteralPath $output
    throw
}
