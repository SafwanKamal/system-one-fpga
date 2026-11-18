$ErrorActionPreference='Stop'
if(Get-CimInstance Win32_Process -Filter "Name='vivado.exe'"){throw 'Preserve active Vivado job'}
$repoRoot=(Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$output=Join-Path $repoRoot 'build/v2/activation-capture-ooc'
if(Test-Path $output){throw 'Preserve existing OOC evidence'}
& 'C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat' -mode batch -nojournal `
    -log 'S:/build/v2/activation-capture-ooc-vivado.log' `
    -source 'S:/scripts/v2/kr260/check_activation_capture_ooc.tcl' *> (Join-Path $repoRoot 'build/v2/activation-capture-ooc-console.log')
$state=if($LASTEXITCODE -eq 0){'complete'}else{'failed'}
@{state=$state;exit_code=$LASTEXITCODE;updated_utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json | Set-Content (Join-Path $output 'completion-status.json')
if($LASTEXITCODE -ne 0){throw 'OOC inference failed; preserve logs'}
