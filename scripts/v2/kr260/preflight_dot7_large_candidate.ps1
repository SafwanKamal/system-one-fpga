# Synthesis only, after numerical and focused OOC evidence; never queue routing.
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$buildDir = Join-Path $repoRoot 'build/v2/kr260-opt-dot7-large'
$pythonPath = Join-Path $repoRoot '.venv/Scripts/python.exe'
if (Get-Process -Name vivado -ErrorAction SilentlyContinue) { throw 'One Vivado job at a time; inspect the active job' }
if (Test-Path (Join-Path $buildDir 'sysone_v2_kr260.xpr')) { throw 'Existing dot7 project must be reviewed, not overwritten' }
foreach ($gate in @(
    @{path='simulation/v2/summarize_kr260_batch.py'; args=@('build/v2/rtl-dot7-check','3','1')},
    @{path='simulation/v2/summarize_large_attention_capacity.py'; args=@('build/v2/rtl-dot7-check','build/v2/rtl-dot7-large-check')},
    @{path='scripts/v2/kr260/check_axi_request_registers.py'; args=@()},
    @{path='scripts/v2/kr260/check_dot7_admission.py'; args=@()}
)) {
    $gateArguments = $gate.args
    & $pythonPath (Join-Path $repoRoot $gate.path) @gateArguments
    if ($LASTEXITCODE -ne 0) { throw "Admission failed: $($gate.path)" }
}
if (!(Test-Path $buildDir)) {
    & $pythonPath (Join-Path $PSScriptRoot 'freeze_dot6.py') dot7
    if ($LASTEXITCODE -ne 0) { throw 'Freeze/source/cycle comparison failed' }
} else {
    $statusPath = Join-Path $buildDir 'completion-status.json'
    if (!(Test-Path $statusPath) -or (Get-Content -LiteralPath $statusPath -Raw | ConvertFrom-Json).state -ne 'numerical_ready') {
        throw 'Existing candidate is not a fresh numerical_ready snapshot; inspect rather than overwrite'
    }
}
$watch = [Diagnostics.Stopwatch]::StartNew()
function Save-Status([string]$state, [string]$detail) {
    @{state=$state;detail=$detail;updated_utc=[DateTime]::UtcNow.ToString('o');elapsed_seconds=$watch.Elapsed.TotalSeconds;hardware_deployed=$false} |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $buildDir 'completion-status.json')
}
try {
    Save-Status 'synthesizing' 'Shared-read RAM/cursor full synthesis; 300 MHz exploratory constraint, routing disabled'
    & 'C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat' -mode batch -nojournal `
        -log 'S:/build/v2/kr260-opt-dot7-large/preflight-vivado.log' `
        -source 'S:/scripts/v2/kr260/create_project_kr260.tcl' `
        -tclargs preflight optimized 300 bram wide memory dot7 large *> (Join-Path $buildDir 'preflight-console.log')
    if ($LASTEXITCODE -ne 0) { throw 'Dot7 full synthesis failed; preserve logs/checkpoints' }
    & $pythonPath (Join-Path $PSScriptRoot 'check_batch_preflight.py') $buildDir
    if ($LASTEXITCODE -ne 0) { throw 'Review area relief, URAM, RAM inference or control fanout before placement' }
    Save-Status 'preflight_ready' 'Full synthesis/resource/RAM/fanout gates passed; placement/routing/hardware still required'
} catch {
    Save-Status 'failed' $_.Exception.Message
    throw
}
