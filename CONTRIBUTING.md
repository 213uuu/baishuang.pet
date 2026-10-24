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
- Source artwork may use `#00ff00` while cleaning; final runtime frames use the
  dark warm transparency key `#110703`.
- Document changes to frame directories or animation state names.

## Artwork changes

Large animation changes should include:

- source or generation notes
- frame count and canvas size
- a visual comparison
- confirmation that backgrounds were recolored to the exact runtime key `#110703`

## Commit style

Short imperative subjects are preferred, for example:

```text
Fix bubble clipping for multi-line text
Add DSH work detection
```
