param([int]$ParentProcessId = 0, [switch]$Bram, [switch]$Wide)
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$candidateName = if ($Bram) { 'kr260-opt-bram' } else { 'kr260-opt' }
$archiveName = if ($Bram) { 'kr260-app-bram.tar.gz' } else { 'kr260-app-pipe.tar.gz' }
if ($Wide) {
    $Bram = $true
    $candidateName = 'kr260-opt-wide'
    $archiveName = 'kr260-app-wide.tar.gz'
}
$candidateDir = Join-Path $repoRoot "build/v2/$candidateName"
$vivadoExe = 'C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat'
$pythonExe = Join-Path $repoRoot '.venv/Scripts/python.exe'
$statusFile = Join-Path $candidateDir 'completion-status.json'
function Save-Status([string]$state, [string]$detail) {
    @{state=$state; detail=$detail; updated_utc=[DateTime]::UtcNow.ToString('o')} |
        ConvertTo-Json | Set-Content -LiteralPath $statusFile
}
function Invoke-CandidateVivado([string]$name, [string]$source, [string[]]$extra = @()) {
    $vivadoArgs = @('-mode','batch','-nojournal','-log',"S:/build/v2/$candidateName/$name-vivado.log",'-source',$source) + $extra
    & $vivadoExe @vivadoArgs *> (Join-Path $candidateDir "$name-console.log")
    if ($LASTEXITCODE -ne 0) { throw "Vivado $name failed; inspect $name-console.log" }
}
try {
    if (!(Test-Path -LiteralPath 'S:/scripts/v2/kr260/report_clock_candidates.tcl')) {
        throw 'The verified short S: repository mapping is required'
    }
    Save-Status 'waiting' 'Waiting for the existing implementation/export process'
    if ($ParentProcessId -gt 0 -and (Get-Process -Id $ParentProcessId -ErrorAction SilentlyContinue)) {
        Wait-Process -Id $ParentProcessId
    }
    Save-Status 'checking' 'Measuring routed setup and hold at candidate clock rates'
    $variantArgs = if ($Bram) { @('-tclargs','bram') } else { @() }
    if ($Wide) { $variantArgs += 'wide' }
    Invoke-CandidateVivado 'clock-candidates' 'S:/scripts/v2/kr260/report_clock_candidates.tcl' $variantArgs
    $clockChecks = Get-Content -LiteralPath (Join-Path $candidateDir 'clock-candidates.json') -Raw | ConvertFrom-Json
    $chosenClock = $clockChecks | Where-Object { $_.passes -and $_.mhz -in @(100,125) } |
        Sort-Object mhz -Descending | Select-Object -First 1
    if (!$chosenClock) { throw 'No tested 100/125 MHz profile passes both setup and hold; no package produced' }
    # Recheck both PL clocks at the Linux runtime rate, including a PL1 preset
    # that may differ from PL0 in the original block-design constraints.
    Save-Status 'exporting' "Exporting the passing $($chosenClock.mhz) MHz profile"
    $runtimeArgs = @('-tclargs','optimized',"$($chosenClock.mhz)","$($chosenClock.mhz)")
    if ($Bram) { $runtimeArgs += 'bram' }
    if ($Wide) { $runtimeArgs += 'wide' }
    Invoke-CandidateVivado 'runtime-export' 'S:/scripts/v2/kr260/validate_runtime_clock.tcl' $runtimeArgs
    Save-Status 'packaging' "Packaging the passing $($chosenClock.mhz) MHz candidate"
    $env:PATH = 'C:/AMDDesignTools/2025.2/Vivado/bin;C:/AMDDesignTools/2025.2/Vivado/bin/unwrapped/win64.o;' + $env:PATH
    $packageArgs = @((Join-Path $PSScriptRoot 'package_app.py'),'--optimized')
    if ($Bram) { $packageArgs += '--bram' }
    if ($Wide) { $packageArgs += '--wide' }
    & $pythonExe @packageArgs *> (Join-Path $candidateDir 'package-console.log')
    if ($LASTEXITCODE -ne 0) { throw 'Packaging failed; inspect package-console.log' }
    Save-Status 'ready' "Routed checks passed at $($chosenClock.mhz) MHz; $archiveName is ready for board validation"
} catch {
    Save-Status 'failed' $_.Exception.Message
    throw
}
