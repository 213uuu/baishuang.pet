param(
    [ValidateSet('open', 'close', 'status', 'restart')]
    [string]$Action = 'open'
)

$ErrorActionPreference = 'Stop'

$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pidPath = Join-Path $dir 'pet.pid'
$logPath = Join-Path $dir 'pet.log'
$localPythonw = Join-Path $dir 'runtime\python\pythonw.exe'
$pythonw = if (Test-Path -LiteralPath $localPythonw) {
    $localPythonw
} else {
    $env:BAISHUANG_PYTHONW
}
if ([string]::IsNullOrWhiteSpace($pythonw)) {
    $pythonw = Get-Command pythonw.exe -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty Source
}
if ([string]::IsNullOrWhiteSpace($pythonw) -and (Test-Path 'C:\Python314\pythonw.exe')) {
    $pythonw = 'C:\Python314\pythonw.exe'
}
$petScript = Join-Path $dir 'desktop_pet.py'
$framesDir = Join-Path $dir 'frames'

function Get-RecordedPid {
    if (-not (Test-Path -LiteralPath $pidPath)) { return $null }
    $raw = Get-Content -LiteralPath $pidPath -Raw -ErrorAction SilentlyContinue
    if ($null -eq $raw) { return $null }
    $raw = $raw.Trim()
    if ($raw -match '^\d+$') { return [int]$raw }
    return $null
}

function Get-PetProcess {
    $processId = Get-RecordedPid
    if ($null -eq $processId) { return $null }
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if ($null -eq $process) { return $null }
    if ($process.ProcessName -notmatch '^python') { return $null }
    return $process
}

function Show-LogTail {
    if (Test-Path -LiteralPath $logPath) {
        Write-Output 'LOG_TAIL'
        Get-Content -LiteralPath $logPath -Tail 20 -Encoding UTF8 -ErrorAction SilentlyContinue
    }
}

function Stop-Pet {
    $process = Get-PetProcess
    if ($null -eq $process) {
        Write-Output 'NOT_RUNNING'
        return
    }

    $processId = $process.Id
    Stop-Process -Id $processId -Force -ErrorAction Stop

    $deadline = (Get-Date).AddSeconds(5)
    do {
        Start-Sleep -Milliseconds 200
        $alive = Get-Process -Id $processId -ErrorAction SilentlyContinue
    } while ($null -ne $alive -and (Get-Date) -lt $deadline)

    if ($null -ne $alive) {
        Write-Output "STOP_FAILED $processId"
        return
    }

    if (Test-Path -LiteralPath $pidPath) {
        Remove-Item -LiteralPath $pidPath -Force -ErrorAction SilentlyContinue
    }
    Write-Output "STOPPED $processId"
}

function Start-Pet {
    $running = Get-PetProcess
    if ($null -ne $running) {
        Write-Output "ALREADY_RUNNING $($running.Id)"
        return
    }

    if ([string]::IsNullOrWhiteSpace($pythonw) -or -not (Test-Path -LiteralPath $pythonw)) {
        Write-Output "START_FAILED missing $pythonw"
        return
    }
    if (-not (Test-Path -LiteralPath $petScript)) {
        Write-Output "START_FAILED missing $petScript"
        return
    }
    if (-not (Test-Path -LiteralPath $framesDir)) {
        Write-Output "START_FAILED missing $framesDir"
        return
    }

    if (Test-Path -LiteralPath $pidPath) {
        Remove-Item -LiteralPath $pidPath -Force -ErrorAction SilentlyContinue
    }

    $arguments = @(
        ('"' + $petScript + '"'),
        ('"' + $framesDir + '"')
    )
    Start-Process -FilePath $pythonw -ArgumentList $arguments -WorkingDirectory $dir -WindowStyle Hidden

    $deadline = (Get-Date).AddSeconds(12)
    do {
        Start-Sleep -Milliseconds 300
        $newId = Get-RecordedPid
        if ($null -ne $newId) {
            $newProcess = Get-Process -Id $newId -ErrorAction SilentlyContinue
        }
    } while (($null -eq $newId -or $null -eq $newProcess) -and (Get-Date) -lt $deadline)

    if ($null -ne $newId -and $null -ne $newProcess) {
        Write-Output "STARTED $newId"
        return
    }

    Write-Output 'START_FAILED no pid file appeared'
    Show-LogTail
}

switch ($Action) {
    'open'    { Start-Pet }
    'close'   { Stop-Pet }
    'restart' { Stop-Pet | Out-Null; Start-Pet }
    'status'  {
        $process = Get-PetProcess
        if ($null -ne $process) {
            Write-Output "RUNNING $($process.Id)"
        }
        else {
            Write-Output 'NOT_RUNNING'
        }
    }
}
