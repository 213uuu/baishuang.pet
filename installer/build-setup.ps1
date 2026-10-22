param(
    [string]$RepositoryRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$PythonRoot = "C:\Python314",
    [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"
$root = [System.IO.Path]::GetFullPath($RepositoryRoot)
$buildRoot = Join-Path $root "installer\.build"
$payloadRoot = Join-Path $buildRoot "payload"
$runtimeRoot = Join-Path $payloadRoot "runtime\python"
$payloadArchive = Join-Path $buildRoot "payload.zip"
$stubPath = Join-Path $buildRoot "BaishuangSetup.exe"
$sourcePath = Join-Path $PSScriptRoot "Installer.cs"
$iconPath = Join-Path $root "assets\baishuang.ico"
$csc = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"

if (-not $OutputPath) {
    $OutputPath = Join-Path (Split-Path -Parent $root) "Baishuang-Setup-0.1.8.exe"
}
$OutputPath = [System.IO.Path]::GetFullPath($OutputPath)

if (-not (Test-Path -LiteralPath $csc)) {
    throw "C# compiler not found: $csc"
}
if (-not (Test-Path -LiteralPath $PythonRoot)) {
    throw "Python runtime not found: $PythonRoot"
}

if (Test-Path -LiteralPath $buildRoot) {
    $resolved = [System.IO.Path]::GetFullPath($buildRoot)
    if (-not $resolved.StartsWith($root, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove build directory outside repository: $resolved"
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}
New-Item -ItemType Directory -Path $payloadRoot -Force | Out-Null
New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
Write-Output "STAGE payload-directories"

$files = @(
    "desktop_pet.py",
    "bubble_shape.py",
    "pet-tray.py",
    "pet-control.ps1",
    "start-pet.cmd",
    "start-pet-silent.vbs",
    "stop-pet.cmd",
    "README.md",
    "LICENSE",
    "ASSET_LICENSE.md",
    "THIRD_PARTY_NOTICES.md"
)
foreach ($file in $files) {
    $source = Join-Path $root $file
    if (Test-Path -LiteralPath $source) {
        Copy-Item -LiteralPath $source -Destination (Join-Path $payloadRoot $file)
    }
}
foreach ($directory in @("frames", "startup-animation", "fonts", "assets")) {
    Copy-Item -LiteralPath (Join-Path $root $directory) `
        -Destination (Join-Path $payloadRoot $directory) -Recurse
}
Write-Output "STAGE app-files"
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "install.ps1") `
    -Destination (Join-Path $payloadRoot "install.ps1")
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "uninstall.ps1") `
    -Destination (Join-Path $payloadRoot "uninstall.ps1")

$pythonFiles = @(
    "python.exe",
    "pythonw.exe",
    "python3.dll",
    "python314.dll",
    "LICENSE.txt"
)
foreach ($file in $pythonFiles) {
    Copy-Item -LiteralPath (Join-Path $PythonRoot $file) `
        -Destination (Join-Path $runtimeRoot $file)
}
Write-Output "STAGE python-files"
foreach ($file in @("vcruntime140.dll", "vcruntime140_1.dll")) {
    $source = Join-Path $env:WINDIR "System32\$file"
    $destination = Join-Path $runtimeRoot $file
    $sourceStream = [System.IO.File]::OpenRead($source)
    try {
        $destinationStream = [System.IO.File]::Create($destination)
        try {
            $sourceStream.CopyTo($destinationStream)
        }
        finally {
            $destinationStream.Dispose()
        }
    }
    finally {
        $sourceStream.Dispose()
    }
}
foreach ($directory in @("DLLs", "Lib", "tcl")) {
    Copy-Item -LiteralPath (Join-Path $PythonRoot $directory) `
        -Destination (Join-Path $runtimeRoot $directory) -Recurse
}
Write-Output "STAGE python-directories"

foreach ($relative in @(
    "Lib\site-packages",
    "Lib\test",
    "Lib\idlelib",
    "Lib\turtledemo",
    "Lib\ensurepip"
)) {
    $target = Join-Path $runtimeRoot $relative
    if (Test-Path -LiteralPath $target) {
        Remove-Item -LiteralPath $target -Recurse -Force
    }
}
Get-ChildItem -LiteralPath $runtimeRoot -Directory -Filter "__pycache__" -Recurse |
    Remove-Item -Recurse -Force
Get-ChildItem -LiteralPath $runtimeRoot -File -Recurse |
    Where-Object { $_.Extension -eq ".pyc" } |
    Remove-Item -Force
Write-Output "STAGE prune-runtime"

tar -a -c -f $payloadArchive -C $payloadRoot .
if ($LASTEXITCODE -ne 0) {
    throw "Failed to create payload zip."
}
Write-Output "STAGE payload-archive"

$outputDirectory = Split-Path -Parent $OutputPath
if (-not (Test-Path -LiteralPath $outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}
if (Test-Path -LiteralPath $OutputPath) {
    Remove-Item -LiteralPath $OutputPath -Force
}

& $csc `
    /nologo `
    /target:winexe `
    /platform:anycpu `
    /optimize+ `
    /codepage:65001 `
    "/win32icon:$iconPath" `
    "/out:$stubPath" `
    "/resource:$payloadArchive,payload.zip" `
    "/r:System.Windows.Forms.dll" `
    "/r:System.IO.Compression.dll" `
    "/r:System.IO.Compression.FileSystem.dll" `
    $sourcePath
if ($LASTEXITCODE -ne 0) {
    throw "C# installer compilation failed."
}
Write-Output "STAGE compile-stub"
Copy-Item -LiteralPath $stubPath -Destination $OutputPath -Force

$hash = (Get-FileHash -LiteralPath $OutputPath -Algorithm SHA256).Hash
Write-Output "SETUP=$OutputPath"
Write-Output "SIZE_MB=$([Math]::Round((Get-Item $OutputPath).Length / 1MB, 2))"
Write-Output "SHA256=$hash"
