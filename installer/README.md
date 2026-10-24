# Windows Installer

Build a self-contained `setup.exe`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File installer\build-setup.ps1
```

The generated installer:

- installs per-user to `%LOCALAPPDATA%\Baishuang`
- requires no administrator rights
- bundles a portable Python runtime
- creates Desktop and Start Menu shortcuts
- registers an uninstall entry under the current user

The executable is a standard .NET WinExe with the compressed payload embedded
as a managed resource:

```text
.NET installer executable
embedded payload.zip resource
```

Silent installation:

```powershell
.\Baishuang-Setup-0.1.9.exe --silent --no-launch
```

The installer is unsigned unless a code-signing certificate is supplied
separately, so Windows SmartScreen may show an unknown-publisher warning.
