@echo off
rem Baishuang desktop pet - stop script.
rem Kills only processes whose command line mentions desktop_pet; never other pythonw.
rem Keep this file pure ASCII (cmd.exe parses it with the OEM code page).
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe'\" | Where-Object { $_.CommandLine -like '*desktop_pet*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1
echo Baishuang stopped.
