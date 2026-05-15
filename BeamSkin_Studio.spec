# -*- mode: python ; coding: utf-8 -*-
# BeamSkin Studio - PyInstaller Spec File  (PySide6 edition)
# ─────────────────────────────────────────────────────────────────────────────
# HOW TO BUILD:
#   pip install pyinstaller
#   python -m PyInstaller BeamSkin_Studio.spec
#
# Make sure all runtime assets listed in datas[] exist before building.
# ─────────────────────────────────────────────────────────────────────────────

import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_all

# Root directory of the project (where this spec file lives)
spec_root = os.path.abspath(SPECPATH)


# ═══════════════════════════════════════════════════════════════════════════════
# DATA FILES
# Every folder / file your app reads at runtime must be listed here.
# Format: (source_path, dest_folder_inside_the_bundle)
# ═══════════════════════════════════════════════════════════════════════════════

datas = []

# ── Project assets ─────────────────────────────────────────────────────────── #
datas += [
    ('version.txt',                         '.'),
    ('gui/Icons',                           'gui/Icons'),
    ('imagesforgui',                        'imagesforgui'),
    ('vehicles',                            'vehicles'),
    ('data',                                'data'),
    # Language files — critical for the localisation system
    ('core/localization/languages',         'core/localization/languages'),
]

# ── PySide6 Qt plugins (required for fonts, image formats, platform) ─────── #
try:
    from PyInstaller.utils.hooks import collect_all as _ca
    _pyside6_datas, _pyside6_bins, _pyside6_hiddens = _ca('PySide6')
    datas    += _pyside6_datas
    print(f"[SPEC] PySide6 collected: {len(_pyside6_datas)} data entries")
except Exception as _e:
    _pyside6_bins    = []
    _pyside6_hiddens = []
    print(f"[SPEC] WARNING: Could not auto-collect PySide6: {_e}")

# ── certifi (SSL certificates used by requests) ────────────────────────────── #
try:
    import certifi
    datas += collect_data_files('certifi')
    print("[SPEC] certifi collected")
except ImportError:
    print("[SPEC] WARNING: certifi not found")


# ═══════════════════════════════════════════════════════════════════════════════
# HIDDEN IMPORTS
# Modules that PyInstaller cannot detect automatically must be declared here.
# ═══════════════════════════════════════════════════════════════════════════════

hiddenimports = [
    # ── Your own packages ──────────────────────────────────────────────────── #
    'core',
    'core.config',
    'core.settings',
    'core.updater',
    'core.file_ops',
    'core.localization',
    'core.localization.languages',
    'core.changelog',
    'core.colorable_ops',
    'core.add_vehicles',

    'gui',
    'gui.main_window',
    'gui.state',
    'gui.theme',
    'gui.widgets',
    'gui.icon_helper',
    'gui.confirmation_dialog',

    'gui.components',
    'gui.components.dialogs',
    'gui.components.navigation',
    'gui.components.preview',
    'gui.components.setup_wizard',
    'gui.components.path_configuration',
    'gui.components.changelog_dialog',
    'gui.components.connection_dialog',
    'gui.components.language_dialog',

    'gui.tabs',
    'gui.tabs.car_list',
    'gui.tabs.generator',
    'gui.tabs.settings',
    'gui.tabs.howto',
    'gui.tabs.about',
    'gui.tabs.add_vehicles',
    'gui.tabs.online_tab',

    'utils',
    'utils.debug',
    'utils.file_ops',
    'utils.single_instance',
    'utils.config_helper',
    'utils.connection',

    # ── PySide6 core modules ───────────────────────────────────────────────── #
    'PySide6',
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'PySide6.QtNetwork',
    'PySide6.QtSvg',
    'PySide6.QtSvgWidgets',

    # ── Pillow ────────────────────────────────────────────────────────────────  #
    'PIL',
    'PIL.Image',
    'PIL.ImageFilter',
    'PIL.ImageDraw',
    'PIL.ImageFont',

    # ── requests stack ────────────────────────────────────────────────────────  #
    'requests',
    'requests.adapters',
    'requests.auth',
    'requests.cookies',
    'requests.exceptions',
    'urllib3',
    'urllib3.util',
    'urllib3.util.retry',
    'certifi',
    'charset_normalizer',
    'idna',

    # ── Windows-specific ──────────────────────────────────────────────────────  #
    'win32gui',
    'win32con',
    'pywintypes',
    'ctypes',
    'ctypes.wintypes',

    # ── stdlib (sometimes missed by the analyser) ─────────────────────────────  #
    'json',
    're',
    'os',
    'sys',
    'threading',
    'webbrowser',
    'shutil',
    'zipfile',
    'tempfile',
    'datetime',
    'multiprocessing',
    'subprocess',
    'platform',
    'io',
    'time',
    'atexit',
    'typing',
]

# Merge any hidden imports auto-collected from PySide6 above
try:
    hiddenimports += _pyside6_hiddens
except NameError:
    pass

# Auto-collect submodules from your own packages
for _pkg in ['gui', 'gui.components', 'gui.tabs', 'core', 'utils']:
    try:
        _collected = collect_submodules(_pkg)
        hiddenimports.extend(_collected)
        print(f"[SPEC] Collected {len(_collected)} submodules from {_pkg}")
    except Exception as _e:
        print(f"[SPEC] Could not collect submodules from {_pkg}: {_e}")

# Deduplicate
hiddenimports = list(set(hiddenimports))


# ═══════════════════════════════════════════════════════════════════════════════
# ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

a = Analysis(
    ['main.py'],
    pathex=[spec_root],
    binaries=[] + (_pyside6_bins if '_pyside6_bins' in dir() else []),
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    # pyi_rth_beamskin.py runs before main.py inside the frozen EXE.
    runtime_hooks=['pyi_rth_beamskin.py'],
    excludes=[
        # Old GUI framework — no longer used
        'customtkinter',
        'tkinter',
        # Heavy scientific libs not needed
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        # Dev / test tools
        'pytest',
        'unittest',
        'notebook',
        'IPython',
        'sphinx',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)


# ═══════════════════════════════════════════════════════════════════════════════
# EXE  — single-file bundle
# ═══════════════════════════════════════════════════════════════════════════════

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='BeamSkin Studio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # No console window for the GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='gui/Icons/BeamSkin_Studio.ico',
    # version= intentionally omitted — version.txt is bundled via datas[].
    # To add Windows file-property metadata use PyInstaller's pyi-grab-version
    # tool to create a proper VERSIONINFO file, then: version='version_info.txt'
)
