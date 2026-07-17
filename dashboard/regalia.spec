# PyInstaller spec — packages Regalia's desktop shell (desktop.py) into a
# standalone app, so users install a binary instead of running a Python script.
#
#   pip install -r requirements.txt -r requirements-dev.txt
#   pyinstaller regalia.spec            (run from the dashboard/ folder)
#
# Output: dist/Regalia.exe (onefile — a single self-contained binary users can
# download and double-click; templates/static/Assets are bundled inside and
# extracted to a temp dir at launch). Per-user state moves to the OS data dir
# via paths.py when frozen; the vault defaults to ~/RegaliaVault until pointed
# elsewhere in Settings.

from pathlib import Path

block_cipher = None
HERE = Path(SPECPATH)  # noqa: F821 — provided by PyInstaller

a = Analysis(
    ["desktop.py"],
    pathex=[str(HERE)],
    datas=[
        ("templates", "templates"),
        ("static", "static"),
        ("Assets", "Assets"),
    ],
    hiddenimports=[
        # Imported lazily at runtime (inbox connect), so Analysis can't see them.
        "google_auth_oauthlib.flow",
        "msal",
        # The frozen --mail-mcp entrypoint imports these only in MCP mode.
        "mail_mcp",
        "mcp.server.fastmcp",
    ],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# onefile: bundle scripts, binaries, zipfiles and datas all into one EXE (no
# COLLECT). The bootloader unpacks them to a temp dir (sys._MEIPASS) at launch.
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="Regalia",
    runtime_tmpdir=None,
    console=False,                      # windowed app — no terminal
    icon=str(HERE / "Assets" / "Regalia_Icon.png"),  # Pillow converts per-platform
)

# macOS: wrap the single binary into a proper .app bundle.
import sys
if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="Regalia.app",
        icon=str(HERE / "Assets" / "Regalia_Icon.png"),
        bundle_identifier="com.regalia.dashboard",
    )
