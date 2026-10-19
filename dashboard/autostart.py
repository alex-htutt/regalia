"""Open Regalia at sign-in, and keep a shortcut on the desktop (Windows).

Both are plain `.lnk` shortcuts, so the files on disk *are* the setting — there
is no config key to drift out of sync, and removing a shortcut by hand in
Explorer is reflected the next time Settings loads:

  login    %APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\Startup\\Regalia.lnk
  desktop  <the user's Desktop, OneDrive-redirected or not>\\Regalia.lnk

Both point at the desktop window, never the browser server: the packaged
Regalia.exe when frozen, otherwise `pythonw desktop.py` (no console window).

Shortcuts are written through PowerShell's WScript.Shell COM object, which
ships with every Windows install — no pywin32 dependency. Paths are handed to
the script through environment variables, not string-spliced into it, so a
folder name with quotes or `$` can't break (or inject into) the command.

CLI:  python autostart.py [--login on|off] [--desktop on|off]   (no args = status)
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import paths

HERE = Path(__file__).parent
LINK_NAME = "Regalia.lnk"
_NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW — don't flash a console from the GUI


class LaunchError(Exception):
    """A UI-safe failure to change a shortcut."""


def supported() -> bool:
    return sys.platform == "win32"


def _ps(script: str, env: dict | None = None) -> str:
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-Command", script],
        capture_output=True, text=True, timeout=30,
        env={**os.environ, **(env or {})},
        creationflags=_NO_WINDOW if supported() else 0,
    )
    if proc.returncode != 0:
        raise LaunchError((proc.stderr or proc.stdout or "PowerShell failed").strip()[:300])
    return proc.stdout.strip()


def startup_dir() -> Path:
    base = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
    return base / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def desktop_dir() -> Path:
    # Ask the shell rather than assuming ~/Desktop: OneDrive "Known Folder Move"
    # relocates the Desktop, and a shortcut in the stale folder is invisible.
    return Path(_ps("[Environment]::GetFolderPath('Desktop')"))


def _link_path(kind: str) -> Path:
    if kind == "login":
        return startup_dir() / LINK_NAME
    if kind == "desktop":
        return desktop_dir() / LINK_NAME
    raise ValueError(f"unknown shortcut kind: {kind!r}")


def _icon_path() -> str:
    """An .ico for the source-run shortcut (a .lnk can't use the PNG directly)."""
    ico = paths.data_dir() / ".regalia.ico"
    if ico.exists():
        return str(ico)
    try:
        from PIL import Image
        Image.open(HERE / "Assets" / "Regalia_Icon.png").save(
            ico, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
        )
        return str(ico)
    except Exception:  # Pillow missing or the asset moved: default icon, still works
        return ""


def launch_target() -> dict:
    """What a shortcut should run: {target, args, workdir, icon}."""
    if paths.is_frozen():
        exe = Path(sys.executable)
        return {"target": str(exe), "args": "", "workdir": str(exe.parent), "icon": str(exe)}
    py = Path(sys.executable)
    pythonw = py.with_name("pythonw.exe")
    return {
        "target": str(pythonw if pythonw.exists() else py),
        "args": f'"{HERE / "desktop.py"}"',
        "workdir": str(HERE),
        "icon": _icon_path(),
    }


_MAKE_LINK = r"""
$ws = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut($env:RG_LINK)
$lnk.TargetPath = $env:RG_TARGET
$lnk.Arguments = $env:RG_ARGS
$lnk.WorkingDirectory = $env:RG_WORKDIR
$lnk.Description = 'Regalia'
if ($env:RG_ICON) { $lnk.IconLocation = $env:RG_ICON }
$lnk.Save()
"""


def set_shortcut(kind: str, enabled: bool) -> None:
    if not supported():
        raise LaunchError("Launch shortcuts are only supported on Windows.")
    link = _link_path(kind)
    if not enabled:
        link.unlink(missing_ok=True)
        return
    link.parent.mkdir(parents=True, exist_ok=True)
    t = launch_target()
    _ps(_MAKE_LINK, {
        "RG_LINK": str(link), "RG_TARGET": t["target"], "RG_ARGS": t["args"],
        "RG_WORKDIR": t["workdir"], "RG_ICON": t["icon"],
    })


def state() -> dict:
    if not supported():
        return {"supported": False, "login": False, "desktop": False}
    try:
        desktop = _link_path("desktop").exists()
    except LaunchError:
        desktop = False
    return {"supported": True, "login": _link_path("login").exists(), "desktop": desktop}


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--login", choices=("on", "off"))
    ap.add_argument("--desktop", choices=("on", "off"))
    ns = ap.parse_args(argv)
    try:
        for kind in ("login", "desktop"):
            choice = getattr(ns, kind)
            if choice:
                set_shortcut(kind, choice == "on")
    except LaunchError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(state())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
