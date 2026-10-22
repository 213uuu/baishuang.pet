# Security Policy

## Credentials

Baishuang reads API credentials from the local Codex configuration at runtime.
The repository must never contain:

- API keys or bearer tokens
- `~/.codex/auth.json`
- `~/.codex/config.toml`
- logs that contain authorization headers
- personal shortcuts containing absolute user paths

If a credential is committed accidentally, revoke it immediately and remove it
from Git history before publishing.

## Reporting

For a security issue, avoid opening a public issue with exploit details.
Contact the repository owner privately with a minimal reproduction and the
affected version.

## Runtime boundary

The desktop pet executes local Python code and reads local Codex/DSH session
metadata. Review changes that add subprocess execution, network requests, or
new credential sources.
