"""Where Regalia keeps its per-user state (config, chats, tokens, uploads).

Running from source, everything stays inside dashboard/ exactly as before —
gitignored dot-folders next to the code. Running as a packaged app (PyInstaller
sets sys.frozen), the install dir may be read-only (Program Files, /Applications),
so state moves to the platform's user-data directory instead:

    Windows:  %APPDATA%/Regalia
    macOS:    ~/Library/Application Support/Regalia
    Linux:    $XDG_DATA_HOME/regalia (or ~/.local/share/regalia)

stdlib only; imported by config/chats/mailbox/app, imports none of them.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def data_dir() -> Path:
    """The directory per-user state lives in. Created lazily by callers."""
    if not is_frozen():
        return Path(__file__).parent
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
        return base / "Regalia"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Regalia"
    base = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    return base / "regalia"


def default_vault() -> Path:
    """Where a packaged app puts the vault when none is configured yet.
    From source this is never used — the repo root is the vault."""
    return Path.home() / "RegaliaVault"
