$ErrorActionPreference='Stop'
if(Get-CimInstance Win32_Process -Filter "Name='vivado.exe'"){throw 'Preserve active heavy job'}
$repoRoot=(Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$output=Join-Path $repoRoot 'build/v2/kr260-opt-dot7-large/routed-memory-inspection'
if(Test-Path $output){throw 'Existing inspection must be read, not repeated'}
New-Item -ItemType Directory -Path $output | Out-Null
function Save-Status($state,$detail){
    @{state=$state;detail=$detail;updated_utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json | Set-Content (Join-Path $output 'completion-status.json')
}
try{
    Save-Status 'inspecting' 'Read existing routed memory properties and paths; no build or optimization'
    & 'C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat' -mode batch -nojournal `
        -log 'S:/build/v2/kr260-opt-dot7-large/routed-memory-inspection/vivado.log' `
        -source 'S:/scripts/v2/kr260/inspect_dot7_routed_memory.tcl' *> (Join-Path $output 'console.log')
    if($LASTEXITCODE -ne 0){throw 'Inspection failed; preserve reports/log'}
    Save-Status 'complete' 'Review actual URAM cascade/output properties and paths before choosing RTL cut'
}catch{Save-Status 'failed' $_.Exception.Message;throw}
