# Baishuang Desktop Pet

Baishuang is a Windows desktop pet built with Python and Tk. It combines transparent always-on-top rendering, frame animation, adaptive cloud-shaped speech bubbles, Codex / DeepSeek Harness work detection, and DeepSeek balance lookup.

![Preview](docs/images/baishuang-preview.png)

## Requirements

- Windows 10 or 11
- Python 3.10+
- No third-party packages are needed to run the pet
- Pillow is only needed for asset-generation tools

## Run

Double-click `start-pet.cmd` from File Explorer.

If `pythonw.exe` is not on `PATH`:

```powershell
$env:BAISHUANG_PYTHONW = "C:\Path\To\pythonw.exe"
.\start-pet.cmd
```

Do not launch the pet from a network-restricted sandbox if balance lookup is required.

## Features

- Transparent draggable desktop pet window
- Frame-based action state machine
- Adaptive cloud-shaped speech bubbles
- Codex work detection through real-time logs and session files
- DSH work detection through `DSH_HOME`
- A dedicated dual-work animation path
- Deferred work entry after casual animations finish
- DeepSeek balance lookup from local credentials
- Optional Windows tray launcher

## Test

```powershell
python -m unittest discover -s tests -v
python -m py_compile desktop_pet.py bubble_shape.py pet-tray.py
```

## Licenses

- Source code: MIT
- Original character artwork and animation frames: CC BY 4.0
- Yozai font: SIL Open Font License 1.1

See `LICENSE`, `ASSET_LICENSE.md`, and `THIRD_PARTY_NOTICES.md`.
