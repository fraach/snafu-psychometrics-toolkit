param(
    [string]$OutFile = ".\snafu.exe",
    [string]$IconPng = ".\logo.png",
    [string]$IconIco = ".\logo.ico"
)

$ErrorActionPreference = "Stop"
$root = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }

$csc = "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (-not (Test-Path $csc)) {
    $csc = "C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe"
}
if (-not (Test-Path $csc)) {
    throw "csc.exe non trovato."
}

$iconPngPath = if ([System.IO.Path]::IsPathRooted($IconPng)) { $IconPng } else { Join-Path $root $IconPng }
$iconIcoPath = if ([System.IO.Path]::IsPathRooted($IconIco)) { $IconIco } else { Join-Path $root $IconIco }
$srcPath = Join-Path $root "snafu_launcher.cs"

if (Test-Path $iconPngPath) {
    powershell -ExecutionPolicy Bypass -File (Join-Path $root "convert_png_to_ico.ps1") -PngPath $iconPngPath -IcoPath $iconIcoPath
}

$args = @(
    "/nologo",
    "/target:winexe",
    "/optimize+",
    "/out:$OutFile",
    "/r:System.dll",
    "/r:System.Windows.Forms.dll",
    "/r:System.Drawing.dll"
)

if (Test-Path $iconIcoPath) {
    $args += "/win32icon:$iconIcoPath"
}

$args += $srcPath

& $csc @args
if ($LASTEXITCODE -ne 0) {
    throw "Build GUI fallita (exit code $LASTEXITCODE)."
}

Write-Host "Creato: $OutFile"
