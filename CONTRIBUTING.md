# Contributing

## Development setup

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
python -m py_compile desktop_pet.py bubble_shape.py pet-tray.py
```

## Pull requests

- Keep runtime dependencies limited to the Python standard library.
- Do not commit credentials, logs, PID files, or local configuration.
- Include a regression test for behavioral fixes when possible.
- Preserve the exact chroma key `#00ff00` in runtime sprite frames.
- Document changes to frame directories or animation state names.

## Artwork changes

Large animation changes should include:

- source or generation notes
- frame count and canvas size
- a visual comparison
- confirmation that backgrounds remain exactly `#00ff00`

## Commit style

Short imperative subjects are preferred, for example:

```text
Fix bubble clipping for multi-line text
Add DSH work detection
```
