# PyInstaller spec — packages Regalia's desktop shell (desktop.py) into a
# standalone app, so users install a binary instead of running a Python script.
#
#   pip install -r requirements.txt -r requirements-dev.txt
#   pyinstaller regalia.spec            (run from the dashboard/ folder)
#
# Output: dist/Regalia/ (onedir — data files beside the executable; faster
# startup and fewer frozen-path surprises than onefile). Per-user state moves
# to the OS data dir via paths.py when frozen; the vault defaults to
# ~/RegaliaVault until pointed elsewhere in Settings.

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
    ],
    excludes=["mcp"],  # only the CLI-spawned mail_mcp.py subprocess needs it
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="Regalia",
    console=False,                      # windowed app — no terminal
    icon=str(HERE / "Assets" / "Regalia_Icon.png"),  # Pillow converts per-platform
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    name="Regalia",
)

# macOS: also wrap the collected app into a proper .app bundle.
import sys
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Regalia.app",
        icon=str(HERE / "Assets" / "Regalia_Icon.png"),
        bundle_identifier="com.regalia.dashboard",
    )
