# Serialize behind the active checkpoint report job to avoid concurrent memory use.
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$buildDir = Join-Path $repoRoot 'build/v2/kr260-opt-batch3'
$deadline = [DateTime]::UtcNow.AddMinutes(30)
while ($true) {
    $status = Get-Content (Join-Path $buildDir 'completion-status.json') -Raw | ConvertFrom-Json
    if ($status.state -eq 'placement_ready') { break }
    if ([DateTime]::UtcNow -gt $deadline) { throw 'Placement report wait timed out; inspect recovery job' }
    Start-Sleep -Seconds 10
}
& 'C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat' -mode batch -nojournal `
    -log 'S:/build/v2/kr260-opt-batch3/frequency-diagnostics-vivado.log' `
    -source 'S:/scripts/v2/kr260/diagnose_batch3_frequency.tcl' *> (Join-Path $buildDir 'frequency-diagnostics-console.log')
if ($LASTEXITCODE -ne 0) { throw 'Frequency diagnosis failed; inspect log' }
