param(
    [Parameter(Mandatory = $true)]
    [string]$InstallDir
)

$ErrorActionPreference = "Stop"
$InstallDir = [System.IO.Path]::GetFullPath($InstallDir)
$appIcon = Join-Path $InstallDir "assets\baishuang.ico"
$launcher = Join-Path $InstallDir "start-pet.cmd"
$uninstallScript = Join-Path $InstallDir "uninstall.ps1"

$control = Join-Path $InstallDir "pet-control.ps1"
if (Test-Path -LiteralPath $control) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $control close |
        Out-Null
}

$shell = New-Object -ComObject WScript.Shell
$warnings = New-Object System.Collections.Generic.List[string]

function Add-Warning {
    param([string]$Message)
    $warnings.Add($Message)
}

function New-Shortcut {
    param(
        [string]$Path,
        [string]$Target,
        [string]$Arguments,
        [string]$WorkingDirectory,
        [string]$Icon
    )
    try {
        $shortcut = $shell.CreateShortcut($Path)
        $shortcut.TargetPath = $Target
        $shortcut.Arguments = $Arguments
        $shortcut.WorkingDirectory = $WorkingDirectory
        $shortcut.IconLocation = "$Icon,0"
        $shortcut.WindowStyle = 7
        $shortcut.Save()
    }
    catch {
        Add-Warning "Shortcut failed: $Path - $($_.Exception.Message)"
    }
}

$desktopCandidates = @(
    [Environment]::GetFolderPath("Desktop"),
    (Join-Path $env:USERPROFILE "OneDrive\Desktop"),
    (Join-Path $env:USERPROFILE "OneDrive\桌面"),
    (Join-Path $env:USERPROFILE "Desktop")
) | Where-Object { $_ }
$desktop = $desktopCandidates |
    Where-Object { Test-Path -LiteralPath $_ -PathType Container } |
    Select-Object -First 1
if (-not $desktop) {
    Add-Warning "Desktop folder was not found; desktop shortcut skipped."
}
if ($desktop) {
    New-Shortcut `
        -Path (Join-Path $desktop "Baishuang.lnk") `
        -Target $env:ComSpec `
        -Arguments "/c `"`"$launcher`"`"" `
        -WorkingDirectory $InstallDir `
        -Icon $appIcon
}

$programs = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$appMenu = Join-Path $programs "Baishuang"
try {
    New-Item -ItemType Directory -Path $appMenu -Force | Out-Null
    New-Shortcut `
        -Path (Join-Path $appMenu "Baishuang.lnk") `
        -Target $env:ComSpec `
        -Arguments "/c `"`"$launcher`"`"" `
        -WorkingDirectory $InstallDir `
        -Icon $appIcon

    $uninstallTarget = $env:ComSpec
    $uninstallArgs = (
        "/c powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$uninstallScript`" " +
        "-InstallDir `"$InstallDir`""
    )
    New-Shortcut `
        -Path (Join-Path $appMenu "Uninstall Baishuang.lnk") `
        -Target $uninstallTarget `
        -Arguments $uninstallArgs `
        -WorkingDirectory $InstallDir `
        -Icon $appIcon
}
catch {
    Add-Warning "Start Menu shortcuts failed: $($_.Exception.Message)"
}

try {
    $version = "0.1.9"
    $uninstallKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\Baishuang"
    New-Item -Path $uninstallKey -Force | Out-Null
    Set-ItemProperty -Path $uninstallKey -Name DisplayName -Value "Baishuang"
    Set-ItemProperty -Path $uninstallKey -Name DisplayVersion -Value $version
    Set-ItemProperty -Path $uninstallKey -Name DisplayIcon -Value $appIcon
    Set-ItemProperty -Path $uninstallKey -Name InstallLocation -Value $InstallDir
    Set-ItemProperty -Path $uninstallKey -Name Publisher -Value "213uuu"
    Set-ItemProperty `
        -Path $uninstallKey `
        -Name UninstallString `
        -Value (
            "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$uninstallScript`" " +
            "-InstallDir `"$InstallDir`""
        )
}
catch {
    Add-Warning "Registry uninstall entry failed: $($_.Exception.Message)"
}

if ($warnings.Count -gt 0) {
    $warnings | Set-Content -LiteralPath (Join-Path $InstallDir "install-warnings.log") `
        -Encoding utf8
}
