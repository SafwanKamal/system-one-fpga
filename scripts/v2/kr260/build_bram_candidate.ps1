param([int]$AfterProcessId = 0)
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$buildDir = Join-Path $repoRoot 'build/v2/kr260-opt-bram'
if ($AfterProcessId -gt 0) {
    Wait-Process -Id $AfterProcessId -ErrorAction SilentlyContinue
    $previous = Get-Content (Join-Path $repoRoot 'build/v2/kr260-opt/completion-status.json') -Raw | ConvertFrom-Json
    if ($previous.state -ne 'ready') { throw 'First candidate did not complete successfully; BRAM build not started' }
}
if (Test-Path (Join-Path $buildDir 'sysone_v2_kr260.xpr')) {
    throw 'BRAM candidate project already exists; inspect it before rebuilding'
}
if (!(Test-Path 'S:/scripts/v2/kr260/create_project_kr260.tcl')) {
    throw 'The short S: repository mapping is required'
}
New-Item -ItemType Directory -Path $buildDir -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $repoRoot 'build/v2/rtl-bram-check/summary.json') -Destination (Join-Path $buildDir 'regression.json')
& 'C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat' -mode batch -nojournal `
    -log 'S:/build/v2/kr260-opt-bram/build-vivado.log' `
    -source 'S:/scripts/v2/kr260/create_project_kr260.tcl' `
    -tclargs build optimized 125 bram *> (Join-Path $buildDir 'build-console.log')
if ($LASTEXITCODE -ne 0) { throw 'BRAM implementation failed; inspect build-console.log' }
& (Join-Path $PSScriptRoot 'finish_pipeline_build.ps1') -Bram
