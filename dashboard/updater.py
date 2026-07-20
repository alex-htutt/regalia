"""Self-update: check GitHub for a newer release and, when asked, replace the
running desktop binary in place and relaunch.

Design (mirrors app.py's other background flows — connect/pull/claude-test):

- **The check runs once, at launch.** `startup()` spins a daemon thread that
  fetches `releases/latest` from GitHub (stdlib urllib, short timeout, fully
  offline-safe) and caches the result in `_STATE`. The Flask routes only ever
  read that cache — hitting `/api/update` never triggers a network call, so the
  "only check on launch" contract holds. Set `REGALIA_UPDATE_CHECK=0` to skip
  the launch check entirely (the smoke suite does this to stay network-free).

- **Applying an update only self-replaces a frozen (packaged) build.** Running
  from source there is no binary to swap, so `apply()` is a safe no-op that tells
  the user to `git pull`. Frozen, it downloads the platform asset zip, extracts
  the new binary, **backs up** the current one (rename-in-place — the one Windows
  operation allowed on a running exe), moves the new binary into its place,
  relaunches, and exits. If the swap fails partway it **rolls back** from the
  backup so a bad download can never brick the install. A leftover backup from a
  previous successful update is cleaned up on the next launch.

stdlib only — urllib, zipfile, tempfile, shutil, subprocess. No new deps.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

import paths
import version

_API_URL = f"https://api.github.com/repos/{version.REPO}/releases/latest"
_RELEASES_URL = f"https://github.com/{version.REPO}/releases"
_UA = "Regalia-Updater/1.0 (+https://github.com/" + version.REPO + ")"
_HTTP_TIMEOUT = 10          # launch check — short, never blocks the user
_DOWNLOAD_TIMEOUT = 300     # asset download — big binary, generous

# The release asset filename for each platform (matches release.yml's `pack`).
_ASSET_FOR_PLATFORM = {
    "win32": "Regalia-windows.zip",
    "darwin": "Regalia-macos-arm64.zip",
}

# Cached launch-check result. Read by the /api/update route; written only by the
# background check thread. `apply` mirrors the single-flight state shape used by
# the connect/pull flows so the UI can poll one status field.
_STATE: dict = {
    "checked": False,          # has the launch check completed (ok or error)?
    "current": version.__version__,
    "latest": "",              # newest release tag on GitHub (without the 'v')
    "out_of_date": False,
    "can_self_update": None,   # None until known; True only for a frozen build
    "releases_url": _RELEASES_URL,
    "error": "",               # network/parse error from the launch check
    "apply": {"state": "idle", "detail": ""},  # idle|running|done|error
}
_LOCK = threading.Lock()
_APPLY_LOCK = threading.Lock()


def is_frozen() -> bool:
    return paths.is_frozen()


def _asset_name() -> str:
    return _ASSET_FOR_PLATFORM.get(sys.platform, "")


def _http_json(url: str) -> dict:
    req = urllib.request.Request(
        url, headers={"User-Agent": _UA, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def check_latest() -> dict:
    """Query GitHub for the latest release and fold it into `_STATE`.

    Best-effort: any failure lands in `_STATE['error']` and leaves `out_of_date`
    False — a stale-check is never worse than the app not launching. Returns a
    snapshot of the resulting state."""
    try:
        data = _http_json(_API_URL)
        tag = str(data.get("tag_name") or "").strip()
        latest = tag.lstrip("vV")
        out_of_date = bool(tag) and version.is_newer(tag)
        asset_url = ""
        want = _asset_name()
        for asset in data.get("assets") or []:
            if isinstance(asset, dict) and asset.get("name") == want:
                asset_url = asset.get("browser_download_url") or ""
                break
        with _LOCK:
            _STATE.update(
                checked=True,
                latest=latest,
                out_of_date=out_of_date,
                can_self_update=is_frozen(),
                releases_url=str(data.get("html_url") or _RELEASES_URL),
                asset_url=asset_url,   # kept out of the public snapshot() shape
                error="",
            )
    except Exception as e:  # noqa: BLE001 — offline / rate-limited / bad JSON
        with _LOCK:
            _STATE.update(checked=True, can_self_update=is_frozen(),
                          error=f"{type(e).__name__}: {e}")
    return snapshot()


def snapshot() -> dict:
    """A copy of the public update state (no internal asset_url) for the API."""
    with _LOCK:
        return {
            "checked": _STATE["checked"],
            "current": _STATE["current"],
            "latest": _STATE["latest"],
            "out_of_date": _STATE["out_of_date"],
            "can_self_update": _STATE["can_self_update"],
            "releases_url": _STATE["releases_url"],
            "error": _STATE["error"],
            "apply": dict(_STATE["apply"]),
        }


def _cleanup_old_backup() -> None:
    """Delete the `.old` backup a previous successful update left beside the
    binary. Best-effort — a locked/absent file is fine to ignore."""
    if not is_frozen():
        return
    try:
        target = _install_target()[1]
        backup = target.with_name(target.name + ".old")
        if backup.exists():
            if backup.is_dir():
                shutil.rmtree(backup, ignore_errors=True)
            else:
                backup.unlink()
    except Exception:  # noqa: BLE001 — never let cleanup break launch
        pass


def startup(autoupdate: bool = False) -> None:
    """Launch hook: clean up any prior backup, then (unless disabled) run the
    release check on a daemon thread. If `autoupdate` is on and a frozen build is
    out of date, apply the update right after the check completes.

    Called once from app import. Non-blocking and offline-safe by construction."""
    _cleanup_old_backup()
    if os.environ.get("REGALIA_UPDATE_CHECK", "1") == "0":
        return

    def _work():
        check_latest()
        if autoupdate and is_frozen():
            with _LOCK:
                stale = _STATE["out_of_date"] and _STATE.get("asset_url")
            if stale:
                apply()

    threading.Thread(target=_work, daemon=True).start()


# ── Applying an update (frozen builds only) ──────────────────────────────────

def _install_target() -> tuple[str, Path]:
    """(kind, path) of the thing an update replaces.

    Windows: the onefile exe itself. macOS: the whole `.app` bundle (three
    parents up from the inner Mach-O at Regalia.app/Contents/MacOS/Regalia)."""
    exe = Path(sys.executable).resolve()
    if sys.platform == "darwin":
        # …/Regalia.app/Contents/MacOS/Regalia → …/Regalia.app
        for parent in exe.parents:
            if parent.suffix == ".app":
                return "app", parent
        return "app", exe  # not bundle-shaped; fall back to the binary
    return "exe", exe


def _download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=_DOWNLOAD_TIMEOUT) as resp, \
            open(dest, "wb") as f:
        shutil.copyfileobj(resp, f)


def _extract_payload(zip_path: Path, work: Path, kind: str) -> Path:
    """Unzip and return the path to the new binary (exe) or bundle (app)."""
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(work)
    if kind == "app":
        for p in work.rglob("*.app"):
            return p
        raise RuntimeError("The downloaded archive did not contain a .app bundle.")
    for p in work.rglob("*.exe"):
        return p
    raise RuntimeError("The downloaded archive did not contain a Regalia.exe.")


def _swap_and_relaunch(new_payload: Path, kind: str, target: Path) -> None:
    """Back up the current install, move the new one into its place, relaunch,
    and exit. Rolls back from the backup if the move fails so a failed swap can
    never leave the install without a runnable binary."""
    backup = target.with_name(target.name + ".old")
    # Clear a stale backup first (a previous run that never got cleaned up).
    if backup.exists():
        if backup.is_dir():
            shutil.rmtree(backup, ignore_errors=True)
        else:
            backup.unlink()

    # Rename-in-place: the one mutation Windows permits on a running image.
    os.rename(target, backup)
    try:
        shutil.move(str(new_payload), str(target))
    except Exception:
        # Roll back — put the original binary back where it was.
        try:
            if target.exists():
                if target.is_dir():
                    shutil.rmtree(target, ignore_errors=True)
                else:
                    target.unlink()
            os.rename(backup, target)
        except Exception:  # noqa: BLE001
            pass
        raise

    # Relaunch the freshly-installed binary, detached, then exit this process so
    # the file is no longer in use (lets the next launch delete the .old backup).
    launch = target if kind == "exe" else target / "Contents" / "MacOS" / target.stem
    try:
        subprocess.Popen([str(launch)], close_fds=True)
    except Exception:  # noqa: BLE001 — new binary is in place; just can't relaunch
        pass
    # Give the OS a beat to spawn the child before we drop the process.
    time.sleep(0.4)
    os._exit(0)


def _apply_worker(asset_url: str) -> None:
    kind, target = _install_target()
    tmp = Path(tempfile.mkdtemp(prefix="regalia-update-"))
    try:
        with _LOCK:
            _STATE["apply"].update(state="running", detail="Downloading the latest release…")
        zip_path = tmp / (_asset_name() or "update.zip")
        _download(asset_url, zip_path)

        with _LOCK:
            _STATE["apply"].update(detail="Unpacking…")
        payload = _extract_payload(zip_path, tmp / "unpacked", kind)

        with _LOCK:
            _STATE["apply"].update(detail="Installing and relaunching…")
        _swap_and_relaunch(payload, kind, target)  # never returns on success
    except Exception as e:  # noqa: BLE001 — surface anything to the UI
        with _LOCK:
            _STATE["apply"].update(state="error", detail=f"Update failed: {e}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def apply() -> dict:
    """Kick off a self-update on a background thread (single-flight).

    Only a frozen build self-replaces. From source it's a no-op that points the
    user at `git pull`. Returns a small status dict for the caller."""
    if not is_frozen():
        with _LOCK:
            _STATE["apply"].update(
                state="error",
                detail="Running from source — update with `git pull` in the repo.")
        return {"started": False, "reason": "source"}

    with _LOCK:
        asset_url = _STATE.get("asset_url") or ""
        if not asset_url:
            _STATE["apply"].update(
                state="error",
                detail="No downloadable build for this platform was found in the "
                       "latest release.")
            return {"started": False, "reason": "no-asset"}

    with _APPLY_LOCK:
        with _LOCK:
            if _STATE["apply"]["state"] == "running":
                return {"started": False, "reason": "already-running"}
            _STATE["apply"].update(state="running", detail="Starting update…")
        threading.Thread(target=_apply_worker, args=(asset_url,), daemon=True).start()
    return {"started": True}
