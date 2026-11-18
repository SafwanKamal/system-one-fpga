$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$buildDir = Join-Path $repoRoot 'build/v2/kr260-opt-wide'
if (Test-Path (Join-Path $buildDir 'sysone_v2_kr260.xpr')) {
    throw 'Wide project already exists; inspect it before rebuilding'
}
if (!(Test-Path 'S:/scripts/v2/kr260/create_project_kr260.tcl')) {
    throw 'The short S: repository mapping is required'
}
New-Item -ItemType Directory -Path $buildDir -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $repoRoot 'build/v2/rtl-wide-check/summary.json') -Destination (Join-Path $buildDir 'regression.json')
& 'C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat' -mode batch -nojournal `
    -log 'S:/build/v2/kr260-opt-wide/build-vivado.log' `
    -source 'S:/scripts/v2/kr260/create_project_kr260.tcl' `
    -tclargs build optimized 125 bram wide *> (Join-Path $buildDir 'build-console.log')
if ($LASTEXITCODE -ne 0 -and !(Test-Path (Join-Path $buildDir 'sysone_v2_kr260.runs/impl_1/system_wrapper.bit'))) {
    throw 'Wide implementation failed; inspect build-console.log'
}
# A complete placement may miss 125 MHz. The finisher independently checks setup
# and hold and can export 100 MHz only if it passes; partial runs are refused.
& (Join-Path $PSScriptRoot 'finish_pipeline_build.ps1') -Wide
