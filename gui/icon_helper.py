from __future__ import annotations
import os, sys
from PySide6.QtGui   import QIcon
from PySide6.QtWidgets import QWidget

print("[DEBUG] icon_helper module loaded")

def _resolve_icon_path() -> str:
    try:
        from core.settings import get_bundle_path
        base = get_bundle_path()
    except ImportError as _exc:
        print(f"[WARNING] _resolve_icon_path: {type(_exc).__name__}: {_exc}")
        if getattr(sys, 'frozen', False):
            base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(sys.executable)))
        else:
            base = os.getcwd()
    path = os.path.join(base, "gui", "Icons", "BeamSkin_Studio.ico")
    print(f"[DEBUG] _resolve_icon_path: resolved to {path!r}")
    return path


_ICO_PATH: str = _resolve_icon_path()


def set_window_icon(window: QWidget) -> None:
    print(f"[DEBUG] set_window_icon: applying icon to {type(window).__name__}")
    if os.path.exists(_ICO_PATH):
        window.setWindowIcon(QIcon(_ICO_PATH))
        print("[DEBUG] set_window_icon: icon applied successfully")
    else:
        print(f"[ICON] Warning: icon not found at {_ICO_PATH!r}")
