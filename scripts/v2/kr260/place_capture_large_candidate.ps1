$ErrorActionPreference='Stop'
if(Get-CimInstance Win32_Process -Filter "Name='vivado.exe'"){throw 'Preserve active Vivado job'}
$repoRoot=(Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$buildDir=Join-Path $repoRoot 'build/v2/kr260-opt-capture-large'
$output=Join-Path $buildDir 'placement'
if(Test-Path $output){throw 'Preserve existing capture placement'}
$status=Get-Content (Join-Path $buildDir 'completion-status.json') -Raw | ConvertFrom-Json
if($status.state -ne 'preflight_ready'){throw 'Review synthesis admission before placement'}
& (Join-Path $repoRoot '.venv/Scripts/python.exe') (Join-Path $PSScriptRoot 'check_batch_preflight.py') $buildDir
if($LASTEXITCODE -ne 0){throw 'Synthesis resource/pipeline/fanout/capture gate failed'}
$regression=Get-Content (Join-Path $buildDir 'regression.json') -Raw | ConvertFrom-Json
if($regression.numerical_cases -ne 32 -or $regression.read_latency -ne 5 -or $regression.target_mhz -ne 200){throw 'Wrong numerical profile'}
foreach($property in $regression.rtl_sha256.PSObject.Properties){
    $source=Join-Path (Join-Path $buildDir 'rtl-snapshot') $property.Name.Substring('rtl/v2/'.Length)
    if((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant() -ne $property.Value){throw "Snapshot mismatch: $($property.Name)"}
}
New-Item -ItemType Directory -Path $output | Out-Null
function Save-Status($state,$detail){
    @{state=$state;detail=$detail;updated_utc=[DateTime]::UtcNow.ToString('o');target_mhz=200} | ConvertTo-Json | Set-Content (Join-Path $output 'completion-status.json')
}
try{
    Save-Status 'placing' 'Frozen capture H1024 at 200 MHz; diagnostic placement, no route'
    & 'C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat' -mode batch -nojournal `
        -log 'S:/build/v2/kr260-opt-capture-large/placement/vivado.log' `
        -source 'S:/scripts/v2/kr260/place_capture_large_candidate.tcl' *> (Join-Path $output 'console.log')
    if($LASTEXITCODE -ne 0){throw 'Capture placement failed; preserve reports'}
    Save-Status 'placement_ready' 'Review 200 MHz setup paths, hold, density and congestion before routing'
}catch{Save-Status 'failed' $_.Exception.Message;throw}
