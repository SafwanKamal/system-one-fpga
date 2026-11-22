param(
    [string[]] $Variants = @('v9h','base','aux','aux-lim','bram','bram-tmx-aux','p2','p2-aux','p2-aux-lim','tmx','perturbed-add-order')
)

$amd = 'C:/AMDDesignTools/2025.2'
$vitis = "$amd/Vitis"
$mingw = "$vitis/tps/mingw/10.0.0/win64.o/nt"
$libraries = "$amd/win64/lib/csim"
$fpo = "$vitis/win64/tools/fpo_v7_1"
$env:Path = "$mingw/bin;$libraries;$fpo;$vitis/lib/win64.o;$amd/lib/win64.o;$amd/win64/tools/vcxx/libexec;$env:Path"
$clang = "$vitis/win64/tools/clang-16/bin/clang++.exe"

foreach ($name in $Variants) {
    $source = if ($name -eq 'v9h-repeat') { 'v9h' } else { $name }
    $exe = Join-Path $PSScriptRoot "probe-$name.exe"
    $args = @('--target=x86_64-w64-windows-gnu', "--sysroot=$mingw", '-std=c++14',
        '-O1', '-DNDEBUG', '-fpermissive', '-ffp-contract=off', '-Wno-unknown-pragmas',
        '-D__HLS_CSIM__', '-D__VITIS_HLS__', '-D__SIM_FPO__',
        "-I$vitis/include", "-I$PSScriptRoot/sources/$source", "$PSScriptRoot/attention_probe.cpp",
        "-L$libraries", "-L$fpo", '-lhlsm-GCC95-x64', '-lhlsmc++-GCC95-x64',
        '-lgmp', '-lmpfr', '-lIp_floating_point_v7_1_bitacc_cmodel', '-lwinpthread', '-o', $exe)
    & $clang @args
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $exe > "$PSScriptRoot/probe-$name.csv"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Output "Completed attention probe for $name"
}
