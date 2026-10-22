# Changelog

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
