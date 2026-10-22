# Runtime Assets

## Frame format

- Runtime canvas: `432 x 468`
- Chroma key: exact `#00ff00`
- Hard alpha: cutout edges are converted to opaque or transparent pixels
- Runtime animation rate: 12 fps for imported actions
- Normal state timing is configured in `desktop_pet.py`

Do not resample or recolor the green background. Tk transparency uses an exact
color match.

## Runtime directories

`frames/` contains:

- base states such as `idle`, `waving`, `running`, and `waiting`
- transition groups named `trans-*`
- imported action groups named `anim-*`
- `anim-work-start`, `anim-work-intro`, and `anim-work-hold`

`startup-animation/frames/` contains the optional 488-frame startup clip.

## Fonts

`fonts/Yozai-0.868/` contains Light, Regular, and Medium weights of the Yozai
font. The application privately registers `Yozai-Regular.ttf` at runtime.

The complete SIL Open Font License is in the same directory.

## Development tools

Run with Pillow installed:

```powershell
python -m pip install -r requirements-dev.txt
```

Prepare alpha frames for Tk transparency:

```powershell
python tools/prepare_frames.py <alpha-frame-directory> <output-directory>
```

Generate a bubble preview:

```powershell
python tools/make_bubble_preview.py docs/bubble-preview.png
```

Remove low-level green spill from frame edges:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/despill_animation_edges.ps1 `
  -InputRoot frames `
  -OutputRoot work/frames-despilled
```

The processing only modifies contour-edge pixels where the green channel exceeds
both red and blue. It preserves sprite interiors, alpha geometry, and exact
`#00ff00` backgrounds.

## Asset history

Development reports and color-matching metadata live under
`docs/development/`. They are documentation, not runtime dependencies.
