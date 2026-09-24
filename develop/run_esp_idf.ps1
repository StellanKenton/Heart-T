param(
    [Parameter(Mandatory = $true)][string]$Action,
    [Parameter(Mandatory = $true)][string]$IdfPath,
    [Parameter(Mandatory = $true)][string]$ToolsPath,
    [string]$Port = ''
)
$ErrorActionPreference = 'Stop'
$env:IDF_PATH = $IdfPath
$env:IDF_TOOLS_PATH = $ToolsPath
$pythonEnv = Get-ChildItem -LiteralPath (Join-Path $ToolsPath 'python_env') -Directory |
    Where-Object { $_.Name -like 'idf5.5_py3.12_env' } | Select-Object -First 1
if ($null -ne $pythonEnv) {
    $env:PATH = "$(Join-Path $pythonEnv.FullName 'Scripts');$env:PATH"
}
. (Join-Path $IdfPath 'export.ps1')
$compiler = Get-ChildItem -LiteralPath (Join-Path $ToolsPath 'tools/xtensa-esp-elf') -Recurse -Filter 'xtensa-esp32s3-elf-gcc.exe' |
    Select-Object -First 1
if ($null -eq $compiler) {
    throw 'ESP32-S3 compiler not found in ESP-IDF tools.'
}
$env:PATH = "$($compiler.Directory.FullName);$env:PATH"
$project = Join-Path (Split-Path $PSScriptRoot -Parent) 'HeartThirdESP'
$idf = Join-Path $IdfPath 'tools/idf.py'
if ($Action -eq 'build') {
    & python $idf -C $project build
} elseif ($Action -eq 'flash') {
    if (-not $Port) { throw 'Set HEART_ESP_PORT to the ESP32-S3 USB port, for example COM8.' }
    & python $idf -C $project -p $Port flash
} elseif ($Action -eq 'reset') {
    if (-not $Port) { throw 'Set HEART_ESP_PORT to the ESP32-S3 USB port, for example COM8.' }
    & python -m esptool --chip esp32s3 --port $Port run
} else {
    throw "Unsupported ESP action: $Action"
}
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
