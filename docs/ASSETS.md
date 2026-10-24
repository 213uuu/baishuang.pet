# Runtime Assets

## Frame format

- Runtime canvas: `432 x 468`
- Source chroma key: exact `#00ff00`
- Runtime transparency key: exact `#110703`
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

Suppress green-biased residue throughout runtime frames:

```powershell
python tools/suppress_green_residue.py `
  frames `
  work/frames-green-suppressed
```

The residue processor leaves exact `#00ff00` source-key pixels and fully transparent pixels
unchanged. Dark pixels with material green bias are desaturated and darkened
into neutral gray. Bright highlights keep their luminance while only the green
cast is neutralized. This removes both contour spill and the darker green screen
noise visible on dark desktops without creating dark blotches in white hair.
For frames with a real transparent or chroma-key background, every foreground
pixel touching that background also has `G` clamped to `max(R, B)`, removing the
one-pixel green fringe around animation-mode silhouettes without changing alpha.
The processing is idempotent.

Convert the cleaned source-key pixels to the dark runtime key used by Tk:

```powershell
python tools/recolor_runtime_key.py `
  frames `
  work/frames-runtime-key
```

This final recolor is required: Tk blends semi-transparent sprite edges with the
window background, so retaining a bright green key causes a visible green fringe.

The RGB startup / “watch animation” scene can use the same processor. It receives
the same green-cast neutralization while retaining its opaque scene background:

```powershell
python tools/suppress_green_residue.py `
  startup-animation/frames `
  work/startup-animation-green-suppressed
```

## Asset history

Development reports and color-matching metadata live under
`docs/development/`. They are documentation, not runtime dependencies.
