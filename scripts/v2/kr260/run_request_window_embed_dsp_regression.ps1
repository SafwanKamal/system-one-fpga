$ErrorActionPreference='Stop'
$repoRoot=(Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
& wsl.exe -d Ubuntu-24.04 --cd $repoRoot -- env PATH=/opt/verilator-5.040/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin bash simulation/v2/run_kr260_request_window_embed_dsp.sh
if($LASTEXITCODE -ne 0){throw 'Private request-window/embedding address regression failed; preserve evidence'}
