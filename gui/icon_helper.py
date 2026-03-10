"""
icon_helper.py
==============
Single shared utility for applying the BeamSkin Studio icon to every
CTkToplevel window in the application.

CustomTkinter re-applies its own icon some milliseconds after a Toplevel
is created, so a plain `after(10, iconbitmap)` always gets overwritten.

The reliable fix is to hook the window's <Map> event (which fires the first
time the OS actually draws the window — after CTk has finished its own
setup) and also schedule a 300 ms backup call.  A `_done` flag guarantees
`iconbitmap` is called exactly once no matter which fires first.

Usage (same pattern everywhere):
    from gui.icon_helper import set_window_icon
    ...
    self.dialog = ctk.CTkToplevel(parent)
    set_window_icon(self.dialog)
"""

import os
import sys


def _resolve_icon_path() -> str:
    """
    Return the absolute path to BeamSkin_Studio.ico.

    main.py calls os.chdir(script_dir) on startup, so os.getcwd() always
    points to the project root — the most reliable anchor regardless of
    which sub-module is calling us.
    """
    # PyInstaller bundle: resources are under sys._MEIPASS
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        # In dev mode the cwd is always the project root (set by main.py)
        base = os.getcwd()

    return os.path.join(base, "gui", "Icons", "BeamSkin_Studio.ico")


# Cache the resolved path so we only compute it once
_ICO_PATH: str = _resolve_icon_path()


def set_window_icon(window) -> None:
    """
    Apply BeamSkin_Studio.ico to a CTkToplevel window.

    Call this immediately after creating the window — the actual
    iconbitmap() call is deferred until the window is mapped.
    """
    ico = _ICO_PATH

    if not os.path.exists(ico):
        print(f"[ICON] Warning: icon not found at {ico!r}")
        return

    _done = [False]

    def _apply(event=None):
        if _done[0]:
            return
        _done[0] = True
        try:
            window.iconbitmap(ico)
        except Exception as e:
            print(f"[ICON] iconbitmap failed: {e}")

    # Primary trigger: <Map> fires after CTk has finished its own init
    window.bind("<Map>", _apply, add="+")
    # Belt-and-suspenders: 300 ms backup in case <Map> was already past
    window.after(300, _apply)
