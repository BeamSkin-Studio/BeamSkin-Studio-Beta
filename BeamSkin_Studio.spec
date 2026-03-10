# -*- mode: python ; coding: utf-8 -*-
# BeamSkin Studio - PyInstaller Spec File
# ─────────────────────────────────────────────────────────────────────────────
# HOW TO BUILD:
#   python -m PyInstaller BeamSkin_Studio.spec
#
# BEFORE BUILDING, make sure you have also applied the localization.py fix.
# See localization.py (the patched version) — replace core/localization.py
# with it so that the frozen EXE finds language files via sys._MEIPASS.
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
    ('version.txt',                        '.'),
    ('gui/Icons',                          'gui/Icons'),
    ('imagesforgui',                       'imagesforgui'),
    ('vehicles',                           'vehicles'),
    ('data',                               'data'),
    # Language files — critical for the localisation system
    ('core/localization/languages',        'core/localization/languages'),
]

# ── flagpy (the "flag" module) ─────────────────────────────────────────────── #
# flagpy ships its own data (emoji/flag images). Bundle the whole package.
try:
    import flagpy as _flagpy
    _flagpy_dir = os.path.dirname(_flagpy.__file__)
    datas += [(_flagpy_dir, 'flagpy')]
    print(f"[SPEC] flagpy found at: {_flagpy_dir}")
except ImportError:
    print("[SPEC] WARNING: flagpy not installed — 'flag' check in main.py will fail at runtime!")

# ── deep_translator ────────────────────────────────────────────────────────── #
# deep_translator may ship JSON/cert data files — collect them all.
try:
    import deep_translator as _dt
    _dt_datas, _dt_bins, _dt_hiddens = collect_all('deep_translator')
    datas     += _dt_datas
    # _dt_bins and _dt_hiddens handled below
    print(f"[SPEC] deep_translator collected: {len(_dt_datas)} data entries")
except ImportError:
    _dt_bins    = []
    _dt_hiddens = []
    print("[SPEC] WARNING: deep_translator not installed — translation will be disabled at runtime!")

# ── customtkinter (ships its own theme JSON files) ─────────────────────────── #
try:
    import customtkinter as _ctk
    _ctk_dir = os.path.dirname(_ctk.__file__)
    datas += [(_ctk_dir, 'customtkinter')]
    print(f"[SPEC] customtkinter found at: {_ctk_dir}")
except ImportError:
    print("[SPEC] ERROR: customtkinter not installed!")

# ── certifi (SSL certificates used by requests) ────────────────────────────── #
try:
    import certifi
    datas += collect_data_files('certifi')
except ImportError:
    print("[SPEC] WARNING: certifi not found")


# ═══════════════════════════════════════════════════════════════════════════════
# HIDDEN IMPORTS
# Modules that PyInstaller cannot detect automatically (dynamic imports,
# lazy imports, etc.) must be declared here.
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

    # ── Third-party ────────────────────────────────────────────────────────── #
    'PIL',
    'PIL._tkinter_finder',
    'PIL.Image',
    'PIL.ImageTk',
    'PIL.ImageFilter',

    'customtkinter',
    'customtkinter.windows',
    'customtkinter.windows.widgets',
    'customtkinter.windows.widgets.theme',

    'requests',
    'requests.adapters',
    'requests.auth',
    'requests.cookies',
    'requests.exceptions',
    'requests.packages',
    'urllib3',
    'urllib3.util',
    'urllib3.util.retry',
    'certifi',
    'charset_normalizer',
    'idna',

    # flagpy — the "flag" module your main.py checks for
    'flag',
    'flagpy',

    # deep_translator
    'deep_translator',
    'deep_translator.google',
    'deep_translator.base',
    'deep_translator.exceptions',

    # darkdetect (pulled in by customtkinter)
    'darkdetect',

    # Windows-specific
    'win32gui',
    'win32con',
    'pywintypes',
    'ctypes',
    'ctypes.wintypes',

    # stdlib (sometimes missed)
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

# Merge any hidden imports collected from deep_translator above
try:
    hiddenimports += _dt_hiddens
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
    binaries=[] + (_dt_bins if '_dt_bins' in dir() else []),
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    # pyi_rth_beamskin.py runs before main.py inside the frozen EXE.
    # It exposes sys._MEIPASS so any module can find bundled resources.
    runtime_hooks=['pyi_rth_beamskin.py'],
    excludes=[
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'pytest',
        'unittest',
        'tkinter.test',
        'test',
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
# NOTE: version= is intentionally removed.
#       Your version.txt plain-text file cannot be used here; this field
#       requires a special Windows VERSIONINFO resource format.
#       Your app still reads version.txt at runtime (it is bundled in datas).
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
    # version= removed — version.txt is not a valid Windows VERSIONINFO file.
    # To add Windows file-properties metadata, create a proper version_info.txt
    # using PyInstaller's "pyi-grab-version" tool, then set version='version_info.txt'
)
