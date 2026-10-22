# Patch Archive

Base release: `33eea27` (`v0.1.2`)

## Incremental series

Apply in filename order:

```powershell
git am patches/0001-*.patch patches/0002-*.patch patches/0003-*.patch `
  patches/0004-*.patch patches/0005-*.patch patches/0006-*.patch `
  patches/0007-*.patch
```

| Patch | Release | Purpose |
| --- | --- | --- |
| `0001-Add-files-via-upload.patch` | - | Remote checksum file added through GitHub web UI |
| `0002-Fix-network-blocked-balance-bubble.patch` | 0.1.3 | Short, single-line network error |
| `0003-Prevent-desktop-pet-from-stealing-foreground-focus.patch` | 0.1.4 | Do not steal foreground focus |
| `0004-Keep-game-intro-looping-during-work-detection.patch` | 0.1.5 | Game loop priority over work queue |
| `0005-Restore-popup-menu-clicks-and-game-loop.patch` | 0.1.6 | Popup-menu click restoration |
| `0006-Prevent-timeout-from-cutting-off-game-intro.patch` | 0.1.7 | Finish one-shot animation before timeout |
| `0007-Add-self-contained-Windows-installer.patch` | 0.1.8 | Portable Python setup.exe tooling |

## Cumulative patch

To apply all changes in one operation:

```powershell
git apply patches/baishuang-since-0.1.2.patch
```

The incremental series preserves commit messages and is preferred when the
repository is at `v0.1.2`.
