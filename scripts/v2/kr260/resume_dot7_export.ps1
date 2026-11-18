param([ValidateSet('export-recovery','export-recovery-2')][string]$Attempt='export-recovery')
$ErrorActionPreference='Stop'
if (Get-CimInstance Win32_Process -Filter "Name='vivado.exe'") { throw 'Preserve the active heavy job' }
$repoRoot=(Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$buildDir=Join-Path $repoRoot 'build/v2/kr260-opt-dot7-large'
$route=Join-Path $buildDir 'route-125mhz'
$output=Join-Path $route $Attempt
if(Test-Path $output){throw 'Existing export recovery must be reviewed, not repeated'}
& (Join-Path $repoRoot '.venv/Scripts/python.exe') (Join-Path $PSScriptRoot 'check_routed_evidence.py') `
    --timing (Join-Path $buildDir 'timing.rpt') --routes (Join-Path $route 'route-status.rpt') --mhz 125
if($LASTEXITCODE -ne 0){throw 'Actual routed timing/legality gate failed'}
$reg=Get-Content (Join-Path $buildDir 'regression.json') -Raw | ConvertFrom-Json
foreach($entry in $reg.rtl_sha256.PSObject.Properties){
    $source=Join-Path (Join-Path $buildDir 'rtl-snapshot') $entry.Name.Substring('rtl/v2/'.Length)
    if((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value){throw 'Frozen source changed'}
}
New-Item -ItemType Directory -Path $output | Out-Null
@{routed_checkpoint_sha256=(Get-FileHash -LiteralPath (Join-Path $route 'system_wrapper_routed.dcp') -Algorithm SHA256).Hash.ToLowerInvariant();routing_repeated=$false} |
    ConvertTo-Json | Set-Content (Join-Path $output 'input-evidence.json')
function Save-Status($state,$detail){
    @{state=$state;detail=$detail;updated_utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json | Set-Content (Join-Path $output 'completion-status.json')
}
try{
    Save-Status 'exporting' 'Resume verified routed checkpoint only; preserve original guard failure'
    & 'C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat' -mode batch -nojournal `
        -log "S:/build/v2/kr260-opt-dot7-large/route-125mhz/$Attempt/vivado.log" `
        -source 'S:/scripts/v2/kr260/resume_dot7_export.tcl' -tclargs $Attempt *> (Join-Path $output 'console.log')
    if($LASTEXITCODE -ne 0){throw 'Export recovery failed; preserve evidence'}
    Save-Status 'qualified' 'Export complete; package and hardware qualification remain'
}catch{Save-Status 'failed' $_.Exception.Message;throw}
