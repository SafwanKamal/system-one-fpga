param(
    [Parameter(Mandatory=$true)][string]$OutputPath,
    [int]$Seconds = 180
)
$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $OutputPath) { throw 'Refusing to overwrite capture' }
$uartPort = [System.IO.Ports.SerialPort]::new('COM9',115200,[System.IO.Ports.Parity]::None,8,[System.IO.Ports.StopBits]::One)
$uartPort.Handshake = [System.IO.Ports.Handshake]::None
$uartPort.DtrEnable = $false
$uartPort.RtsEnable = $false
$uartPort.ReadTimeout = 100
$uartLog = [System.IO.StreamWriter]::new($OutputPath,$false,[System.Text.UTF8Encoding]::new($false))
try {
    $uartPort.Open()
    $uartLog.WriteLine('# Passive COM9 capture start ' + [DateTime]::UtcNow.ToString('o'))
    $uartLog.Flush()
    $uartTimer = [System.Diagnostics.Stopwatch]::StartNew()
    while ($uartTimer.Elapsed.TotalSeconds -lt $Seconds -and -not (Test-Path -LiteralPath ($OutputPath + '.stop'))) {
        $uartText = $uartPort.ReadExisting()
        if ($uartText.Length -gt 0) { $uartLog.Write($uartText); $uartLog.Flush() }
        Start-Sleep -Milliseconds 100
    }
    $uartLog.WriteLine('# Passive capture end ' + [DateTime]::UtcNow.ToString('o'))
} finally {
    if ($uartPort.IsOpen) { $uartPort.Close() }
    $uartPort.Dispose()
    $uartLog.Dispose()
}
