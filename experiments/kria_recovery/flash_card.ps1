# Write an Ubuntu image to the KR260 card and verify it by reading it back. DESTRUCTIVE. Run elevated.
# usage: flash_card.ps1 -Disk <N> -ExpectBytes <win32 size> -Image <file.img> -BackupLog <done imaging log>
# Refuses unless: disk N is USB with exactly ExpectBytes, and the backup log shows a completed image.
param([Parameter(Mandatory)][int]$Disk,[Parameter(Mandatory)][int64]$ExpectBytes,[Parameter(Mandatory)][string]$Image,[string]$BackupLog='',[switch]$NoBackup,[int]$KillPid=0)
$ErrorActionPreference='Stop'
$log="$Image.flash.log"
function Log($m){ $line="$(Get-Date -Format s) $m"; Add-Content -Path $log -Value $line; $line }
trap { Log "FATAL $($_.Exception.GetType().FullName): $($_.Exception.Message)"; exit 9 }
$d=Get-CimInstance Win32_DiskDrive | Where-Object { $_.Index -eq $Disk }
if(-not $d -or [int64]$d.Size -ne $ExpectBytes -or $d.InterfaceType -ne 'USB'){ Log "ERROR disk $Disk does not match (size/interface)"; exit 3 }
if($KillPid){ Stop-Process -Id $KillPid -Force -ErrorAction SilentlyContinue; Start-Sleep 3; Log "stopped imaging pid $KillPid" }
if($NoBackup){ Log "NO_BACKUP: user chose to flash without a complete backup (2026-11-17)" }
elseif(-not (Select-String -Path $BackupLog -Pattern '^\S+ DONE bytes=125069950976 ' -Quiet)){ Log "ERROR backup image not complete; refusing to erase"; exit 4 }
$len=(Get-Item $Image).Length
if($len % 512){ Log "ERROR image not sector aligned"; exit 5 }
Log "START disk=$Disk model=$($d.Model) image=$Image bytes=$len"
# Removable media cannot be taken offline; remove its partition table so Windows
# holds no volumes on it, then raw-write (the image carries its own table).
$dp="$env:TEMP\kria-clean.txt"; Set-Content -Path $dp -Encoding ascii -Value "select disk $Disk`r`nattributes disk clear readonly`r`nclean`r`nexit"
$out=& diskpart /s $dp 2>&1 | Out-String; Log ("DISKPART " + ($out -replace "`r?`n",' | '))
if($out -notmatch 'succeeded in cleaning'){ Log "ERROR diskpart clean did not succeed"; exit 7 }
Start-Sleep 3
$buf=New-Object byte[] (4MB)
$src=[System.IO.File]::OpenRead($Image)
$dst=[System.IO.File]::Open("\\.\PhysicalDrive$Disk",[System.IO.FileMode]::Open,[System.IO.FileAccess]::ReadWrite,[System.IO.FileShare]::ReadWrite)
$shaIn=[System.Security.Cryptography.SHA256]::Create(); $total=[int64]0; $next=[int64]0
# Write everything after the first 4 MB first, and the first 4 MB (partition table) last,
# so Windows sees no partitions to auto-mount while the image is going down.
$head=New-Object byte[] (4MB); $hn=$src.Read($head,0,$head.Length)
$null=$shaIn.TransformBlock($head,0,$hn,$null,0); $total=[int64]$hn
try {
  $dst.Position=$hn
  while(($n=$src.Read($buf,0,$buf.Length)) -gt 0){
    $dst.Write($buf,0,$n); $null=$shaIn.TransformBlock($buf,0,$n,$null,0); $total+=$n
    if($total -ge $next){ Log ("WRITE {0:N2} GB" -f ($total/1GB)); $next+=512MB }
  }
  $dst.Flush()
  $dst.Position=0; $dst.Write($head,0,$hn); $dst.Flush(); Log "WROTE partition-table head last"
} finally { $src.Close(); $dst.Close() }
$null=$shaIn.TransformFinalBlock($buf,0,0); $hIn=([BitConverter]::ToString($shaIn.Hash) -replace '-','').ToLower()
Log "WRITTEN bytes=$total sha256=$hIn"
# Read back exactly the written length from the device and compare.
$rd=[System.IO.File]::Open("\\.\PhysicalDrive$Disk",[System.IO.FileMode]::Open,[System.IO.FileAccess]::Read,[System.IO.FileShare]::ReadWrite)
$shaOut=[System.Security.Cryptography.SHA256]::Create(); $got=[int64]0
try {
  while($got -lt $total){
    $want=[int][Math]::Min([int64]$buf.Length,[int64]($total-$got)); $n=$rd.Read($buf,0,$want); if($n -le 0){ break }
    $null=$shaOut.TransformBlock($buf,0,$n,$null,0); $got+=$n
  }
} finally { $rd.Close() }
$null=$shaOut.TransformFinalBlock($buf,0,0); $hOut=([BitConverter]::ToString($shaOut.Hash) -replace '-','').ToLower()
if($got -eq $total -and $hOut -eq $hIn){ Log "VERIFY_OK readback=$got sha256=$hOut" } else { Log "VERIFY_FAIL readback=$got sha256=$hOut expected=$hIn"; exit 6 }
