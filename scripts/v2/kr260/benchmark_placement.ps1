param(
    [ValidateSet(4,8)][int]$Threads = 4,
    [string]$Vivado = 'C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat'
)
$ErrorActionPreference = 'Stop'
if (!(Test-Path -LiteralPath $Vivado)) { throw 'Install Vivado 2025.2 with K26 device support, or specify -Vivado with its path' }
$checkpoint = Join-Path $PSScriptRoot 'system_wrapper_opt.dcp'
$manifest = Get-Content (Join-Path $PSScriptRoot 'benchmark-manifest.json') -Raw | ConvertFrom-Json
if ((Get-FileHash -LiteralPath $checkpoint -Algorithm SHA256).Hash.ToLowerInvariant() -ne $manifest.checkpoint_sha256) {
    throw 'Checkpoint transfer hash mismatch'
}
$output = Join-Path $PSScriptRoot ('result-' + [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss') + '-threads' + $Threads)
New-Item -ItemType Directory -Path $output | Out-Null
$cpu = Get-CimInstance Win32_Processor
$os = Get-CimInstance Win32_OperatingSystem
@{cpu=@($cpu | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors);
  ram_gib=[Math]::Round($os.TotalVisibleMemorySize/1MB,2);
  available_ram_gib=[Math]::Round($os.FreePhysicalMemory/1MB,2);
  threads=$Threads;checkpoint_sha256=$manifest.checkpoint_sha256;vivado=$Vivado} |
    ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $output 'machine.json')
Write-Host 'Placement-only benchmark. Use AC power and the same performance mode. No routing will run.'
& $Vivado -mode batch -nojournal -log (Join-Path $output 'vivado.log') `
    -source (Join-Path $PSScriptRoot 'benchmark_placement.tcl') `
    -tclargs $checkpoint $output $Threads *> (Join-Path $output 'console.log')
if ($LASTEXITCODE -ne 0) { throw "Benchmark failed; inspect $output/console.log" }
Get-Content (Join-Path $output 'placement-result.json')
Write-Host "Return machine.json and placement-result.json from $output"
