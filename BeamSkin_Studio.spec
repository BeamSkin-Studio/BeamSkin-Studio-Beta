# -*- mode: python ; coding: utf-8 -*-
# BeamSkin Studio - Final Comprehensive PyInstaller Spec File

import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Get the directory where the spec file is located
spec_root = os.path.abspath(SPECPATH)

# Define all data files to include
datas = [
    ('version.txt', '.'),                           # Version file at root
    ('gui/Icons', 'gui/Icons'),                     # All icons
    ('imagesforgui', 'imagesforgui'),               # All GUI images
    ('vehicles', 'vehicles'),                       # Vehicle templates
    ('data', 'data'),                               # App settings
]

# Comprehensive list of all hidden imports
hiddenimports = [
    # Core modules
    'core',
    'core.config',
    'core.settings',
    'core.updater',
    'core.file_ops',
    
    # GUI main
    'gui',
    'gui.main_window',
    'gui.state',
    
    # GUI components
    'gui.components',
    'gui.components.dialogs',
    'gui.components.navigation',
    'gui.components.preview',
    'gui.components.setup_wizard',
    'gui.components.confirmation_dialog',
    'gui.components.path_configuration',
    
    # GUI tabs
    'gui.tabs',
    'gui.tabs.car_list',
    'gui.tabs.generator',
    'gui.tabs.settings',
    'gui.tabs.howto',
    'gui.tabs.about',
    'gui.tabs.developer',
    
    # GUI views
    'gui.views',
    
    # Utils
    'utils',
    'utils.debug',
    'utils.file_ops',
    'utils.single_instance',
    'utils.config_helper',
    
    # Third-party core
    'PIL',
    'PIL._tkinter_finder',
    'PIL.Image',
    'PIL.ImageTk',
    'customtkinter',
    'requests',
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
    
    # Windows-specific (optional but good to include)
    'win32gui',
    'win32con',
    'pywintypes',
    'ctypes',
    'ctypes.wintypes',
]

# Try to auto-collect submodules
for package in ['gui', 'gui.components', 'gui.tabs', 'core', 'utils']:
    try:
        collected = collect_submodules(package)
        hiddenimports.extend(collected)
        print(f"Collected submodules from {package}: {len(collected)} modules")
    except Exception as e:
        print(f"Could not collect submodules from {package}: {e}")

# Remove duplicates
hiddenimports = list(set(hiddenimports))

a = Analysis(
    ['main.py'],
    pathex=[spec_root],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'pytest',
        'unittest',
        'tkinter.test',
        'test',
    ],
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
    name='BeamSkin Studio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window for GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='gui/Icons/BeamSkin_Studio.ico',
    version='version.txt'  # Optional: Windows version info
)