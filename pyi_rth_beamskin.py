"""
BeamSkin Studio - PyInstaller Runtime Hook
Fixes resource paths so they resolve correctly inside a frozen one-file EXE.
Place this file in the same folder as BeamSkin_Studio.spec
"""
import sys
import os

if getattr(sys, 'frozen', False):
    # _MEIPASS is the temp directory PyInstaller extracts everything into.
    # Expose it so any module can find bundled resources.
    os.environ['BEAMSKIN_MEIPASS'] = sys._MEIPASS
