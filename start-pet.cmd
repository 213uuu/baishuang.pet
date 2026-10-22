@echo off
rem Baishuang desktop pet launcher.
rem Usage: double-click this file in File Explorer (do not paste it into Codex).
rem Exit the pet: right-click her, then Exit.  Log: pet.log in this folder.
rem Keep this file pure ASCII for compatibility with cmd.exe OEM code pages.
setlocal
if exist "%~dp0runtime\python\pythonw.exe" set "PYW=%~dp0runtime\python\pythonw.exe"
if not defined PYW set "PYW=%BAISHUANG_PYTHONW%"
if not defined PYW (
  for /f "delims=" %%P in ('where pythonw.exe 2^>nul') do (
    if not defined PYW set "PYW=%%P"
  )
)
if not defined PYW if exist "C:\Python314\pythonw.exe" set "PYW=C:\Python314\pythonw.exe"
if not defined PYW if exist "%LocalAppData%\Programs\Python\Python314\pythonw.exe" set "PYW=%LocalAppData%\Programs\Python\Python314\pythonw.exe"
if not defined PYW if exist "%LocalAppData%\Programs\Python\Python313\pythonw.exe" set "PYW=%LocalAppData%\Programs\Python\Python313\pythonw.exe"
if not defined PYW (
  echo [ERROR] cannot find pythonw.exe
  echo Install Python 3.10+ or set BAISHUANG_PYTHONW to its full path.
  pause
  exit /b 1
)

rem Stop a running instance, using pet.pid (written by desktop_pet.py itself).
rem No WMI here on purpose: Get-CimInstance Win32_Process is denied on this machine,
rem which silently made the old launcher leave the previous pet alive and start another one.
set "PIDF=%~dp0pet.pid"
if exist "%PIDF%" (
  set "OLDPID="
  set /p OLDPID=<"%PIDF%"
)
rem taskkill is denied here (same as WMI/tasklist), so kill through PowerShell's own API.
if defined OLDPID powershell -NoProfile -Command "Stop-Process -Id %OLDPID% -Force -ErrorAction SilentlyContinue" >nul 2>&1
rem NOTE: do not delete pet.pid here. If the kill above fails, the fresh instance sees the
rem still-alive PID and exits by itself -- that is what keeps exactly one pet on screen.
rem Fallback for a missing/stale pet.pid: WMI (works on normal desktops, silently no-ops here).
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe'\" | Where-Object { $_.CommandLine -like '*desktop_pet*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1

start "" "%PYW%" "%~dp0desktop_pet.py" "%~dp0frames"
echo Baishuang is starting; she appears at the bottom-right of your screen.
echo If she does not appear, check pet.log in this folder.
