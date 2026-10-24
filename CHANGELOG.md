# Changelog

## 0.1.9 - 2026-10-24

- Suppressed dark green-screen residue throughout all 1,421 runtime sprite frames.
- Darkened green-biased shadow residue while neutralizing green casts on bright
  highlights without reducing their luminance.
- Added a pixel-exact NumPy/Pillow residue-suppression tool.
- Added regression checks for chroma-key, alpha, and non-edge green suppression.
- Applied the same green-cast cleanup to the 488-frame startup / animation-view scene.
- Removed the subtle green fringe around animation-mode character silhouettes.
- Added an idempotence guard so repeated asset processing cannot keep darkening frames.
- Changed the Tk transparency key from bright green to dark warm `#110703`,
  eliminating the runtime green fringe caused by semi-transparent edge blending.

## 0.1.8 - 2026-10-22

- Added a self-contained single-file Windows installer.
- Bundled a portable Python runtime so users do not need Python installed.
- Added per-user installation under `%LOCALAPPDATA%\Baishuang`.
- Added desktop and Start Menu shortcuts plus a current-user uninstall entry.
- Added installer source and reproducible build tooling.

## 0.1.7 - 2026-10-22

- Fixed a timeout race that reset the game intro to idle before its final frame.
- One-shot imported animations now always finish before generic state timeout can return to idle.
- Added a regression test for timeout occurring on the penultimate game-intro frame.

## 0.1.6 - 2026-10-22

- Restored reliable popup-menu clicks by briefly forcing focus only for user-opened menus.
- Restored the previous foreground application immediately after the menu closes.
- Added a real Tk menu regression test that clicks “玩游戏” and verifies the repeating game loop.

## 0.1.5 - 2026-10-22

- Fixed the gaming intro being diverted to work animation by pending work state.
- Ensured the gaming intro always enters the repeating game loop.
- Prevented pending work entry from interrupting an active game loop.
- Added a regression test for gaming under active work detection.

## 0.1.4 - 2026-10-22

- Prevented the pet from stealing foreground focus during startup, balance updates, and periodic topmost refreshes.
- Kept the pet window topmost with non-activating Win32 flags.
- Restored the previous foreground application after startup and tray-menu interaction.
- Added regression tests covering focus and activation behavior.

## 0.1.3 - 2026-10-22

- Shortened the network-blocked balance message to a single line.
- Stopped appending the pricing-period subtitle to failed balance lookups.
- Added regression tests for failed and successful balance responses.

## 0.1.2 - 2026-10-22

- Removed low-level green spill from sprite contour edges for clean compositing on dark backgrounds.
- Rebuilt all 1,421 runtime frame files with edge-only despill processing.
- Preserved original sprite interiors, alpha shapes, and exact `#00ff00` key backgrounds.
- Added the reproducible edge-despill tool and dark-background comparison.

## 0.1.1 - 2026-10-22

- Fixed startup animation replaying twice when the pet and tray start together.
- Rejected replay requests while the startup animation is already active.
- Added a short cooldown for rapid duplicate startup requests.
- Increased speech-bubble line width to reduce excessive line wrapping.
- Added regression tests for startup deduplication and wide bubble text.
- Restored and verified the complete 1,421-frame runtime asset set.

## 0.1.0 - 2026-10-22

- Packaged the complete Baishuang desktop pet as a standalone repository.
- Added Codex real-time work detection with session-file fallback.
- Added DeepSeek Harness work detection and DSH liveness handling.
- Added dual-work reaction path and stable post-entry work loop.
- Added deferred work entry after casual animations finish.
- Added adaptive speech bubble containment.
- Bundled Yozai font with private runtime loading.
- Added portable launchers, tests, documentation, and open-source licenses.
