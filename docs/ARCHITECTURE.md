# Architecture

## Runtime

`desktop_pet.py` is a Tk application. The sprite is drawn on a transparent
canvas with the exact chroma key `#00ff00`. Speech bubbles are polygons built
from `bubble_shape.py`.

`pet-control.ps1` owns process startup and shutdown. `pet-tray.py` provides an
optional Windows notification-area entry.

## Animation state machine

Frames are loaded from directories under `frames/`. Action names are mapped to
directories in `Pet._extra_action_dirs`.

Important work-related states:

| State | Purpose |
| --- | --- |
| `anim-work-start` | Complete normal work-entry animation |
| `anim-work-intro` | Short work-entry section used by the dual-work path |
| `anim-work-hold` | Stable loop after entering work |
| `anim-multi-click-a` | Reaction A in the dual-work path |
| `anim-work-success-a/b` | Work-completion sequence |

The normal work path is:

```text
anim-work-start -> anim-work-hold
```

The Codex + DSH dual-work path is:

```text
anim-multi-click-a -> anim-work-intro -> anim-work-hold
```

No `trans-*` state is inserted between these stages.

## Work detection

### Codex

`Pet.codex_working()` combines two signals:

- real-time turn activity from `~/.codex/logs_2.sqlite`
- recent writes under `~/.codex/sessions/`

The real-time log is required because session JSONL may not flush until much
later.

### DeepSeek Harness

`Pet.dsh_working()` scans:

```text
$DSH_HOME/sessions/<workspace>/<session>/session*.jsonl*
```

When `DSH_HOME` is not set, `~/.dsh` is used.

## Deferred work entry

When work starts during a casual animation such as eating or gaming, the state
machine stores a pending work-entry mode. The current animation is allowed to
finish first. If both Codex and DSH are working, the pending mode upgrades to
the dual-work path.

## Balance lookup

`Pet.api_credentials()` reads the local Codex configuration. The token is used
only in memory for an HTTPS request to `/user/balance`. The repository never
contains credentials.

The application must run outside a network-restricted sandbox. On Windows, the
supported path is to launch `start-pet.cmd` from File Explorer.
