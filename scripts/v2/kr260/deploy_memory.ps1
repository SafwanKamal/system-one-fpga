param([string]$BoardHost = '192.168.0.239')
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$archive = Join-Path $repoRoot 'build/v2/kr260-app-memory.tar.gz'
if (!(Test-Path -LiteralPath $archive)) { throw 'UltraRAM package missing' }
Write-Host 'Transfer and SSH will request your KR260 password. Validation takes several minutes.'
& scp $archive "ubuntu@${BoardHost}:~/kr260-app-memory.tar.gz"
if ($LASTEXITCODE -ne 0) { throw 'Transfer failed; FPGA was not changed' }
& ssh -t "ubuntu@$BoardHost" 'mkdir -p ~/sysone-kr260-memory && tar -xzf ~/kr260-app-memory.tar.gz -C ~/sysone-kr260-memory && bash ~/sysone-kr260-memory/deploy_memory.sh'
if ($LASTEXITCODE -ne 0) { throw 'Deployment or validation failed; inspect the printed board output' }
