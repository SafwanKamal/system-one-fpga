$ErrorActionPreference='Stop'
if(Get-CimInstance Win32_Process -Filter "Name='vivado.exe'"){throw 'Preserve active Vivado'}
$taskRoot='C:\Users\user\OneDrive - Texas Tech University\Desktop\Code\FPGA Project\system-one-fpga\system-one-fpga'
$taskBuild=Join-Path $taskRoot 'build/v2/kr260-opt-attention-context-capture-large'
try {
 & 'C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat' -mode batch -nojournal -log 'S:/build/v2/kr260-opt-attention-context-capture-large/preflight-recovery2-vivado.log' -source 'S:/scripts/v2/kr260/resume_context_capture_preflight.tcl' *> (Join-Path $taskBuild 'preflight-recovery2-console.log')
 if($LASTEXITCODE -ne 0){throw 'Report-only preflight recovery failed'}
 & (Join-Path $taskRoot '.venv/Scripts/python.exe') (Join-Path $taskRoot 'scripts/v2/kr260/check_batch_preflight.py') $taskBuild
 if($LASTEXITCODE -ne 0){throw 'Recovered synthesis gates failed'}
 @{state='preflight_ready';target_mhz=200;hardware_deployed=$false;updated_utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json | Set-Content (Join-Path $taskBuild 'completion-status.json')
 @{state='preflight_ready';detail='Report-only recovery after audited inherited BREG1; no resynthesis';pid=$PID;updated_utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json | Set-Content (Join-Path $taskRoot 'build/v2/attention-context-capture-controller-status.json')
}catch{ @{state='failed';detail=$_.Exception.Message;pid=$PID;updated_utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json | Set-Content (Join-Path $taskRoot 'build/v2/attention-context-capture-controller-status.json');throw}
