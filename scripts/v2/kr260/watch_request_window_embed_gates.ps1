$ErrorActionPreference='Stop'
$repoRoot=(Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$folder=Join-Path $repoRoot 'build/v2/rtl-request-window-embed-check'
$completion=Join-Path $folder 'completion-status.json'
$status=Join-Path $repoRoot 'build/v2/request-window-embed-gates-status.json'
function Save-Status($state,$detail){
    @{state=$state;detail=$detail;pid=$PID;updated_utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json | Set-Content $status
}
try{
    Save-Status 'waiting_regression' 'Private window limit; no public integration or full synthesis'
    $watch=[Diagnostics.Stopwatch]::StartNew()
    while(!(Test-Path $completion)){
        if($watch.Elapsed.TotalHours -gt 3){throw 'Regression timeout; preserve active simulation'}
        Start-Sleep -Seconds 15
    }
    $result=Get-Content $completion -Raw | ConvertFrom-Json
    if($result.complete -ne $true -or $result.exit_code -ne 0){throw 'Regression failed; no isolated synthesis'}
    & (Join-Path $repoRoot '.venv/Scripts/python.exe') (Join-Path $PSScriptRoot 'review_request_window_embed.py')
    if($LASTEXITCODE -ne 0){throw 'Numerical/cycle/source gate failed'}
    if(Get-CimInstance Win32_Process -Filter "Name='vivado.exe'"){throw 'Preserve active heavy job; isolated gate may be resumed later'}
    Save-Status 'isolated_synthesis' 'One request-admission composition comparison; no full build or route'
    & 'C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat' -mode batch -nojournal `
        -log S:/build/v2/embed-address-ooc-vivado.log `
        -source S:/scripts/v2/kr260/check_embed_address_ooc.tcl *> (Join-Path $repoRoot 'build/v2/embed-address-ooc-console.log')
    if($LASTEXITCODE -ne 0){throw 'Isolated comparison failed; preserve evidence'}
    Save-Status 'isolated_ready' 'Review real mapped resource/timing tradeoff before any production changes'
}catch{Save-Status 'failed' $_.Exception.Message;throw}
