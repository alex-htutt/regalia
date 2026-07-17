"""External folder registry — folders that live outside the vault but that
Regalia can work on.

The folder itself is never scaffolded or restructured: Regalia keeps all of its
context for an external folder inside the vault under external/<name>/ (the
app scaffolds that part), and reaches the real folder read/write through:

  - the in-process agent tools, via the "ext:<name>/..." path prefix
    (agent._safe_path resolves it against the registered root, traversal-safe);
  - the Claude CLI tier, via --add-dir <path> (router appends one per entry).

Store shape: {"name": "C:/abs/path", ...} in the gitignored .external.json in
the per-user data dir — same atomic-write pattern as config.py. stdlib only.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from pathlib import Path

import paths

EXTERNALS_PATH = paths.data_dir() / ".external.json"

# Same charset rule as project areas: a plain name, no dots/slashes — it doubles
# as the vault-side context folder name (external/<name>/), so traversal is
# impossible by construction.
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _-]{0,63}$")

_lock = threading.Lock()


def load() -> dict:
    """name -> absolute path. Missing/corrupt file degrades to empty."""
    try:
        data = json.loads(EXTERNALS_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {
                str(k): str(v)
                for k, v in data.items()
                if _NAME_RE.match(str(k)) and Path(str(v)).is_absolute()
            }
    except (OSError, ValueError):
        pass
    return {}


def _save(data: dict) -> None:
    EXTERNALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(EXTERNALS_PATH.parent), prefix=".external-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, EXTERNALS_PATH)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def list_folders() -> list[dict]:
    """UI-facing view: [{name, path, exists}]."""
    return [
        {"name": name, "path": path, "exists": Path(path).is_dir()}
        for name, path in sorted(load().items(), key=lambda kv: kv[0].lower())
    ]


def add(name: str, path: str, vault_root: Path) -> dict:
    """Register an external folder. Raises ValueError with a UI-safe message."""
    name = str(name or "").strip()
    if not _NAME_RE.match(name):
        raise ValueError("Name must be a plain folder name (letters, numbers, spaces, - or _).")
    raw = str(path or "").strip().strip('"')
    if not raw:
        raise ValueError("A folder path is required.")
    target = Path(raw).expanduser()
    if not target.is_absolute():
        raise ValueError("Use an absolute path (e.g. C:\\Users\\me\\my-project).")
    target = target.resolve()
    if not target.is_dir():
        raise ValueError(f"'{target}' is not an existing folder.")
    root = vault_root.resolve()
    if target == root or root in target.parents or target in root.parents:
        raise ValueError(
            "External folders can't contain or live inside the vault. "
            "Choose a separate folder."
        )
    with _lock:
        data = load()
        if name.lower() in {k.lower() for k in data}:
            raise ValueError(f"An external folder named '{name}' is already connected.")
        for existing_name, existing_path in data.items():
            existing = Path(existing_path).resolve()
            if target == existing or target in existing.parents or existing in target.parents:
                raise ValueError(
                    f"That folder overlaps connected external folder '{existing_name}'. "
                    "Connect separate, non-nested roots."
                )
        data[name] = str(target)
        _save(data)
    return {"name": name, "path": str(target), "exists": True}


def remove(name: str) -> bool:
    """Disconnect an entry. The vault-side context folder is left in place."""
    with _lock:
        data = load()
        for k in list(data):
            if k.lower() == str(name or "").lower():
                del data[k]
                _save(data)
                return True
    return False


def roots() -> dict[str, Path]:
    """name -> Path for entries whose folder still exists on disk."""
    return {name: Path(p) for name, p in load().items() if Path(p).is_dir()}


def resolve(rel: str):
    """Resolve an 'ext:<name>/sub/path' reference to a real Path, traversal-safe.

    Returns None if rel doesn't carry the ext: prefix. Raises ValueError for an
    unknown name or a path that escapes the registered root."""
    rel = (rel or "").replace("\\", "/").strip()
    if not rel.lower().startswith("ext:"):
        return None
    body = rel[4:].strip("/")
    name, _, sub = body.partition("/")
    match = next((p for n, p in load().items() if n.lower() == name.lower()), None)
    if match is None:
        raise ValueError(f"No external folder named '{name}' is connected.")
    base = Path(match).resolve()
    target = (base / sub).resolve() if sub else base
    if target != base and base not in target.parents:
        raise ValueError(f"Path '{rel}' escapes the external folder.")
    return target
