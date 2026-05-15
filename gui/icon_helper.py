from __future__ import annotations
import os, sys
from PySide6.QtGui   import QIcon
from PySide6.QtWidgets import QWidget

print("[DEBUG] icon_helper module loaded")

def _resolve_icon_path() -> str:
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS           # type: ignore[attr-defined]
    else:
        base = os.getcwd()
    path = os.path.join(base, "gui", "Icons", "BeamSkin_Studio.ico")
    print(f"[DEBUG] _resolve_icon_path: resolved to {path!r}")
    return path


_ICO_PATH: str = _resolve_icon_path()


def set_window_icon(window: QWidget) -> None:
    """Apply the application icon to any top-level window."""
    print(f"[DEBUG] set_window_icon: applying icon to {type(window).__name__}")
    if os.path.exists(_ICO_PATH):
        window.setWindowIcon(QIcon(_ICO_PATH))
        print(f"[DEBUG] set_window_icon: icon applied successfully")
    else:
        print(f"[ICON] Warning: icon not found at {_ICO_PATH!r}")
