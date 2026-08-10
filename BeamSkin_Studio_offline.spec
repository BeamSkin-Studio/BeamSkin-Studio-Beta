# -*- mode: python ; coding: utf-8 -*-

import os

block_cipher = None
PROJECT_ROOT = os.path.abspath(".")

ONLINE_EXCLUDES = [
    "gui.tabs.online_tab",
    "gui.components.account_settings_overlay",
    "gui.components.auth_overlay",
    "gui.components.connection_dialog",
    "utils.account_api",
    "utils.connection",
]

datas = [
    (os.path.join("gui", "Icons"),                         os.path.join("gui", "Icons")),
    (os.path.join("gui", "images"),                        os.path.join("gui", "images")),
    (os.path.join("core", "localization", "languages"),    os.path.join("core", "localization", "languages")),
    (os.path.join("vehicles_templates"),                    "vehicles_templates"),
    ("version.txt",                                         "."),
    ("LICENSE",                                              "."),
]

datas = [d for d in datas if os.path.exists(d[0])]

a = Analysis(
    ["main.py"],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "PySide6.QtSvg",
        "PySide6.QtNetwork",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=["pyi_rth_beamskin.py"],
    excludes=ONLINE_EXCLUDES,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="BeamSkin_Studio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join("gui", "Icons", "BeamSkin_Studio.ico"),
    version="version_info.txt" if os.path.exists("version_info.txt") else None,
)
