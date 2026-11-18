$ErrorActionPreference='Stop'
if(Get-CimInstance Win32_Process -Filter "Name='vivado.exe'"){throw 'Preserve active Vivado'}
$taskRoot='C:\Users\user\OneDrive - Texas Tech University\Desktop\Code\FPGA Project\system-one-fpga\system-one-fpga'
$taskOut=Join-Path $taskRoot 'build/v2/attention-context-capture-ooc'
if(Test-Path $taskOut){throw 'Preserve existing OOC'}
New-Item -ItemType Directory -Path $taskOut | Out-Null
try {
 & 'C:/AMDDesignTools/2025.2/Vivado/bin/vivado.bat' -mode batch -nojournal -log 'S:/build/v2/attention-context-capture-ooc/vivado.log' -source 'S:/scripts/v2/kr260/check_attention_context_capture_ooc.tcl' *> (Join-Path $taskOut 'console.log')
 if($LASTEXITCODE -ne 0){throw 'OOC comparison failed'}
 @{complete=$true;updated_utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json | Set-Content (Join-Path $taskOut 'completion-status.json')
}catch{ @{complete=$false;error=$_.Exception.Message} | ConvertTo-Json | Set-Content (Join-Path $taskOut 'completion-status.json');throw}
