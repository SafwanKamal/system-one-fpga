$ErrorActionPreference='Stop'
$taskRoot='C:\Users\user\OneDrive - Texas Tech University\Desktop\Code\FPGA Project\system-one-fpga\system-one-fpga'
& wsl.exe -d Ubuntu-24.04 --cd $taskRoot -- env PATH=/opt/verilator-5.040/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin bash simulation/v2/run_kr260_attention_context_capture.sh
if($LASTEXITCODE -ne 0){throw 'Private context capture regression failed; preserve evidence'}

