param(
    [Parameter(Mandatory = $true)]
    [string]$InstallDir
)

$ErrorActionPreference = "SilentlyContinue"
$InstallDir = [System.IO.Path]::GetFullPath($InstallDir)
Add-Type -AssemblyName System.Windows.Forms

$answer = [System.Windows.Forms.MessageBox]::Show(
    "Uninstall Baishuang?",
    "Baishuang",
    [System.Windows.Forms.MessageBoxButtons]::YesNo,
    [System.Windows.Forms.MessageBoxIcon]::Question
)
if ($answer -ne [System.Windows.Forms.DialogResult]::Yes) {
    exit 0
}

$control = Join-Path $InstallDir "pet-control.ps1"
if (Test-Path -LiteralPath $control) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $control close |
        Out-Null
}

$desktop = [Environment]::GetFolderPath("Desktop")
if (-not $desktop) {
    $desktop = Join-Path $env:USERPROFILE "Desktop"
}
$desktopShortcut = Join-Path $desktop "Baishuang.lnk"
Remove-Item -LiteralPath $desktopShortcut -Force

$appMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Baishuang"
Remove-Item -LiteralPath $appMenu -Recurse -Force
Remove-Item -LiteralPath "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\Baishuang" `
    -Recurse -Force

$command = Join-Path $env:TEMP ("BaishuangUninstall-" + [guid]::NewGuid().ToString("N") + ".cmd")
$cleanup = "@echo off`r`ntimeout /t 2 /nobreak >nul`r`nrmdir /s /q `"$InstallDir`"`r`n"
[System.IO.File]::WriteAllText($command, $cleanup, [System.Text.Encoding]::Default)
Start-Process -FilePath $env:ComSpec -ArgumentList "/c", "`"$command`"" `
    -WindowStyle Hidden
