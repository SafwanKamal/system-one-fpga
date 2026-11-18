$ErrorActionPreference='Stop'
if(Get-CimInstance Win32_Process -Filter "Name='vivado.exe'"){throw 'Preserve the active heavy job'}
$repoRoot=(Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$buildDir=Join-Path $repoRoot 'build/v2/kr260-opt-dot7-large'
$output=Join-Path $buildDir 'route-125mhz/xsa-export'
if(Test-Path $output){throw 'Existing XSA attempt must be reviewed, not repeated'}
& (Join-Path $repoRoot '.venv/Scripts/python.exe') (Join-Path $PSScriptRoot 'check_routed_evidence.py') `
    --timing (Join-Path $buildDir 'route-125mhz/export-recovery-2/timing.rpt') `
    --routes (Join-Path $buildDir 'route-125mhz/export-recovery-2/route-status.rpt') --mhz 125
if($LASTEXITCODE -ne 0){throw 'Qualified routed evidence required'}
New-Item -ItemType Directory -Path $output | Out-Null
function Save-Status($state,$detail){
    @{state=$state;detail=$detail;updated_utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json | Set-Content (Join-Path $output 'completion-status.json')
}
try{
    Save-Status 'exporting' 'XSA only from existing qualified DCP; space-free Tcl working directory'
    & 'C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat' -mode batch -nojournal `
        -log 'S:/build/v2/kr260-opt-dot7-large/route-125mhz/xsa-export/vivado.log' `
        -source 'S:/scripts/v2/kr260/export_dot7_xsa.tcl' *> (Join-Path $output 'console.log')
    if($LASTEXITCODE -ne 0){throw 'XSA-only export failed; preserve evidence'}
    Save-Status 'qualified' 'XSA exported; embedded bit matching and package verification remain'
}catch{Save-Status 'failed' $_.Exception.Message;throw}
