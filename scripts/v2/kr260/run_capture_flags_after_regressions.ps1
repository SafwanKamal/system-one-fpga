# Follow through numerical completion to one synthesis job; never auto-route.
$ErrorActionPreference='Stop'
$repoRoot=(Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$pythonPath=Join-Path $repoRoot '.venv/Scripts/python.exe'
$gate=Join-Path $repoRoot 'build/v2/rtl-capture-flags-check/completion-status.json'
$controller=Join-Path $repoRoot 'build/v2/capture-flags-controller-status.json'
$buildDir=Join-Path $repoRoot 'build/v2/kr260-opt-capture-flags-large'
$watch=[Diagnostics.Stopwatch]::StartNew()
function Save-Status($state,$detail){
    @{state=$state;detail=$detail;updated_utc=[DateTime]::UtcNow.ToString('o');elapsed_seconds=$watch.Elapsed.TotalSeconds;target_mhz=200} |
        ConvertTo-Json | Set-Content $controller
}
try {
    Save-Status 'waiting_regression' 'Wait frozen five-cycle encoder regression, then freeze and synthesize once at 200 MHz'
    while(!(Test-Path $gate)){
        if($watch.Elapsed.TotalHours -gt 3){throw 'Regression completion timeout; inspect existing processes before retry'}
        Start-Sleep -Seconds 15
    }
    $status=Get-Content $gate -Raw | ConvertFrom-Json
    if(!$status.complete -or $status.exit_code -ne 0){throw 'Frozen encoder regression failed; no full synthesis launched'}
    if(Get-CimInstance Win32_Process -Filter "Name='vivado.exe'"){throw 'Preserve active Vivado job; do not launch competing synthesis'}
    & $pythonPath (Join-Path $PSScriptRoot 'freeze_capture.py') --flags
    if($LASTEXITCODE -ne 0){throw 'Numerical/source/inference admission failed'}
    Save-Status 'synthesizing' '19-source frozen capture-flags-large, target 200 MHz; routing disabled'
    & 'C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat' -mode batch -nojournal `
        -log 'S:/build/v2/kr260-opt-capture-flags-large/preflight-vivado.log' `
        -source 'S:/scripts/v2/kr260/create_project_kr260.tcl' `
        -tclargs preflight optimized 200 bram wide memory capture-flags large *> (Join-Path $buildDir 'preflight-console.log')
    if($LASTEXITCODE -ne 0){throw 'Capture full synthesis failed; preserve snapshot/reports'}
    & $pythonPath (Join-Path $PSScriptRoot 'check_batch_preflight.py') $buildDir
    if($LASTEXITCODE -ne 0){throw 'Resource/pipeline/URAM/fanout admission failed; no placement/route'}
    $done=@{state='preflight_ready';target_mhz=200;updated_utc=[DateTime]::UtcNow.ToString('o');detail='Review full synthesis timing and packing, then placement before any route';hardware_deployed=$false}
    $done | ConvertTo-Json | Set-Content (Join-Path $buildDir 'completion-status.json')
    Save-Status 'preflight_ready' 'Full synthesis gates passed; placement and routed setup/hold remain required'
}catch{
    Save-Status 'failed' $_.Exception.Message
    throw
}
