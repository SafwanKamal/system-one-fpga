$ErrorActionPreference = 'Stop'
if (Get-Process -Name vivado -ErrorAction SilentlyContinue) { throw 'One heavy Vivado job at a time; inspect the active job' }
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$buildDir = Join-Path $repoRoot 'build/v2/kr260-opt-dot7-large'
$output = Join-Path $buildDir 'placement'
if (Test-Path $output) { throw 'Existing dot7-large placement must be reviewed, not overwritten' }
& (Join-Path $repoRoot '.venv/Scripts/python.exe') (Join-Path $repoRoot 'simulation/v2/summarize_kr260_batch.py') (Join-Path $repoRoot 'build/v2/rtl-dot7-check') 3 1
if ($LASTEXITCODE -ne 0) { throw 'Frozen base regression/source gate failed' }
& (Join-Path $repoRoot '.venv/Scripts/python.exe') (Join-Path $repoRoot 'simulation/v2/summarize_large_attention_capacity.py') 'build/v2/rtl-dot7-check' 'build/v2/rtl-dot7-large-check'
if ($LASTEXITCODE -ne 0) { throw 'Frozen H1024 regression/source gate failed' }
& (Join-Path $repoRoot '.venv/Scripts/python.exe') (Join-Path $PSScriptRoot 'check_axi_request_registers.py')
if ($LASTEXITCODE -ne 0) { throw 'Protocol/timing-cut gate failed' }
& (Join-Path $repoRoot '.venv/Scripts/python.exe') (Join-Path $PSScriptRoot 'check_batch_preflight.py') $buildDir
if ($LASTEXITCODE -ne 0) { throw 'Synthesis resource/fanout/register gates failed' }
$regression = Get-Content (Join-Path $buildDir 'regression.json') -Raw | ConvertFrom-Json
foreach ($property in $regression.rtl_sha256.PSObject.Properties) {
    $relative = $property.Name.Substring('rtl/v2/'.Length)
    $source = Join-Path (Join-Path $buildDir 'rtl-snapshot') $relative
    if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant() -ne $property.Value) {
        throw "Synthesis snapshot hash mismatch: $relative"
    }
}
New-Item -ItemType Directory -Path $output | Out-Null
function Save-Status([string]$state, [string]$detail) {
    @{state=$state; detail=$detail; updated_utc=[DateTime]::UtcNow.ToString('o')} |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $output 'completion-status.json')
}
try {
    Save-Status 'placing' 'Frozen dot7-large; full optimization/placement only, no routing'
    & 'C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat' -mode batch -nojournal `
        -log 'S:/build/v2/kr260-opt-dot7-large/placement/vivado.log' `
        -source 'S:/scripts/v2/kr260/place_dot7_large_candidate.tcl' *> (Join-Path $output 'console.log')
    if ($LASTEXITCODE -ne 0) { throw 'Dot7 large placement failed; preserve evidence and inspect' }
    Save-Status 'placement_ready' 'Review placed timing/congestion; no routing or deployment authorized by this script'
} catch {
    Save-Status 'failed' $_.Exception.Message
    throw
}
