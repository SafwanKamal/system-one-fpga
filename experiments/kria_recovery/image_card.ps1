# Read-only raw image of the old KR260 boot card. Run elevated.
# usage: image_card.ps1 -Disk <N> -ExpectBytes <size> -Out C:\kria-recovery\old-card.img
# Refuses unless the disk's size and model match what was confirmed beforehand.
param([Parameter(Mandatory)][int]$Disk,[Parameter(Mandatory)][int64]$ExpectBytes,[Parameter(Mandatory)][int64]$TrueBytes,[Parameter(Mandatory)][string]$Out,[int]$KillPid=0)
$ErrorActionPreference='Stop'
$log="$Out.log"
if($KillPid){ Stop-Process -Id $KillPid -Force -ErrorAction SilentlyContinue; Start-Sleep 2 }function Log($m){ $line="$(Get-Date -Format s) $m"; Add-Content -Path $log -Value $line; $line }
Start-Transcript -Path "$Out.transcript.txt" | Out-Null
trap { Log "FATAL $($_.Exception.GetType().FullName): $($_.Exception.Message)"; Stop-Transcript | Out-Null; exit 9 }
$d=Get-CimInstance Win32_DiskDrive | Where-Object { $_.Index -eq $Disk }
if(-not $d){ Log "ERROR no disk $Disk"; exit 2 }
if([int64]$d.Size -ne $ExpectBytes){ Log "ERROR disk $Disk size $($d.Size) != expected $ExpectBytes"; exit 3 }
if($d.InterfaceType -ne 'USB'){ Log "ERROR disk $Disk interface $($d.InterfaceType) is not USB"; exit 4 }
if(Test-Path $Out){ Log "ERROR output exists"; exit 5 }
Log "START disk=$Disk model=$($d.Model) size=$($d.Size)"
$src=[System.IO.File]::Open("\\.\PhysicalDrive$Disk",[System.IO.FileMode]::Open,[System.IO.FileAccess]::Read,[System.IO.FileShare]::ReadWrite)
$dst=[System.IO.File]::Open($Out,[System.IO.FileMode]::CreateNew,[System.IO.FileAccess]::Write)
$sha=[System.Security.Cryptography.SHA256]::Create()
$buf=New-Object byte[] (8MB); $total=[int64]0; $next=[int64]0; $errors=0
try {
  # Win32 size is CHS-rounded; copy exactly TrueBytes (sector count seen by the board's kernel).
  Log "TRUE_BYTES $TrueBytes"
  while($total -lt $TrueBytes){
    $want=[int][Math]::Min([int64]$buf.Length,[int64]($TrueBytes-$total))
    $t0=Get-Date
    try { $n=$src.Read($buf,0,$want); $dt=((Get-Date)-$t0).TotalSeconds; if($dt -gt 5){ Log ("SLOW_READ offset={0} seconds={1:N1}" -f $total,$dt) } } catch {
      # unreadable region: record it, write zeros, skip ahead
      $errors++; Log "READ_ERROR offset=$total len=$want $($_.Exception.Message)"
      [Array]::Clear($buf,0,$want); $n=$want; $src.Position=$total+$want
    }
    if($n -le 0){ break }
    $dst.Write($buf,0,$n); $null=$sha.TransformBlock($buf,0,$n,$null,0); $total+=$n
    if($total -ge $next){ Log ("PROGRESS {0:N2} GB" -f ($total/1GB)); $next+=512MB }
  }
  $null=$sha.TransformFinalBlock($buf,0,0)
  $hash=([BitConverter]::ToString($sha.Hash) -replace '-','').ToLower()
  Log "DONE bytes=$total read_errors=$errors sha256=$hash"
} finally { $src.Close(); $dst.Close() }
