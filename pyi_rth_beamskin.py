"""
BeamSkin Studio - PyInstaller Runtime Hook
"""
import sys
import os

if getattr(sys, 'frozen', False):
    os.environ['BEAMSKIN_MEIPASS'] = sys._MEIPASS
