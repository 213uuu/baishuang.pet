# Publishing to GitHub

This directory is prepared as a standalone Git repository.

## Before publishing

1. Review `LICENSE`, `ASSET_LICENSE.md`, and `THIRD_PARTY_NOTICES.md`.
2. Decide whether commercial reuse of the artwork should remain allowed.
3. Confirm the repository owner name in the license files.
4. Search for secrets before the first push:

```powershell
git grep -n -I -E "sk-[A-Za-z0-9]|Bearer [A-Za-z0-9]|OPENAI_API_KEY"
```

## Create the GitHub repository

Configure your Git author identity once:

```powershell
git config user.name "Your Name"
git config user.email "you@example.com"
git commit -m "Initial open-source release"
```

Create an empty repository on GitHub, then:

```powershell
git remote add origin https://github.com/<user>/<repo>.git
git push -u origin main
```

Suggested repository description:

> A Windows desktop pet with Codex and DeepSeek Harness integration.

Suggested topics:

```text
desktop-pet python tkinter windows codex deepseek-harness
```

## Repository size

The complete runtime asset set is about 330 MB. No individual file exceeds
GitHub's 100 MB limit.

Git LFS is optional. If future changes add more large binary assets or video
files, install Git LFS before adding them:

```powershell
git lfs install
git lfs track "*.png" "*.webp" "*.ttf" "*.mp4"
```

## Release checklist

- CI passes on Windows.
- The app starts by double-clicking `start-pet.cmd`.
- Balance lookup works outside the sandbox.
- Work detection works for Codex and DSH.
- No `pet.log`, `pet.pid`, `auth.json`, `config.toml`, or `*.lnk` is tracked.
- README screenshots and animation previews render correctly.
