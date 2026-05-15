from __future__ import annotations
import re
from typing import Optional

from PySide6.QtCore  import (QPropertyAnimation, QEasingCurve,
                              QRect, QPoint, QSize, Qt, QTimer,
                              QParallelAnimationGroup, QSequentialAnimationGroup)
from PySide6.QtGui   import (QColor, QPalette, QFont, QFontDatabase,
                              QLinearGradient, QBrush, QPainter, QPen,
                              QPixmap, QIcon)
from PySide6.QtWidgets import (QWidget, QGraphicsDropShadowEffect,
                                QGraphicsOpacityEffect, QApplication)

# COLOUR PALETTES

DARK_COLORS: dict[str, str] = {
    "app_bg":               "#0a0a0a",
    "topbar_bg":            "#181818",
    "sidebar_bg":           "#121212",
    "frame_bg":             "#141414",
    "card_bg":              "#1e1e1e",
    "card_hover":           "#282828",
    "text":                 "#f5f5f5",
    "text_secondary":       "#999999",
    "text_muted":           "#555555",
    "accent":               "#FF6600",
    "accent_hover":         "#CC5100",
    "accent_text":          "#0a0a0a",
    "accent_dim":           "#7A3000",
    "tab_selected":         "#FF6600",
    "tab_selected_hover":   "#E55B00",
    "tab_unselected":       "#141414",
    "tab_unselected_hover": "#1e1e1e",
    "success":              "#39E09B",
    "success_hover":        "#2AB87A",
    "warning":              "#ffa726",
    "error":                "#ff4444",
    "error_hover":          "#cc3636",
    "border":               "#2a2a2a",
    "border_focus":         "#FF6600",
    "separator":            "#1a1a1a",
    "overlay":              "rgba(10,10,10,0.85)",
    "glass_bg":             "rgba(20,20,20,0.75)",
}

LIGHT_COLORS: dict[str, str] = {
    "app_bg":               "#f2f2f2",
    "topbar_bg":            "#ffffff",
    "sidebar_bg":           "#e8e8e8",
    "frame_bg":             "#eeeeee",
    "card_bg":              "#ffffff",
    "card_hover":           "#f5f5f5",
    "text":                 "#1a1a1a",
    "text_secondary":       "#666666",
    "text_muted":           "#aaaaaa",
    "accent":               "#FF6600",
    "accent_hover":         "#CC5100",
    "accent_text":          "#ffffff",
    "accent_dim":           "#ffb380",
    "tab_selected":         "#FF6600",
    "tab_selected_hover":   "#E55B00",
    "tab_unselected":       "#e8e8e8",
    "tab_unselected_hover": "#dddddd",
    "success":              "#27ae60",
    "success_hover":        "#219a52",
    "warning":              "#e67e22",
    "error":                "#e74c3c",
    "error_hover":          "#c0392b",
    "border":               "#d0d0d0",
    "border_focus":         "#FF6600",
    "separator":            "#e0e0e0",
    "overlay":              "rgba(240,240,240,0.90)",
    "glass_bg":             "rgba(255,255,255,0.85)",
}

# Live colour dict — the only object the rest of the codebase imports.
COLORS: dict[str, str] = dict(DARK_COLORS)

# STYLESHEET REPLACEMENT MAPS
# Used by ThemeManager to patch every live widget's styleSheet() string when
# the user switches theme.  One map per direction.
#
# Disambiguation notes for values shared between semantic roles:
#   #0a0a0a = app_bg AND accent_text in dark.
#     → Mapped to app_bg light (#f2f2f2).  accent_text on rebuilt widgets
#       (topbar/sidebar) picks up the correct #ffffff via their rebuild.
#       On remaining widgets it becomes near-white which is acceptable on
#       orange buttons.
#   #141414 = frame_bg AND tab_unselected in dark.
#     → Mapped to frame_bg light (#eeeeee).  Tab nav rebuilds anyway.
#   #1e1e1e = card_bg AND tab_unselected_hover in dark.
#     → Mapped to card_bg light (#ffffff).  Tab nav rebuilds.
#   #ffffff = topbar_bg AND card_bg in light.
#     → For L2D, mapped to card_bg dark (#1e1e1e) because that's by far
#       the most common role in non-chrome widgets; topbar rebuilds.

_DARK_TO_LIGHT: dict[str, str] = {
    "#0a0a0a":                "#f2f2f2",
    "#181818":                "#ffffff",
    "#121212":                "#e8e8e8",
    "#141414":                "#eeeeee",
    "#1e1e1e":                "#ffffff",
    "#282828":                "#f5f5f5",
    "#f5f5f5":                "#1a1a1a",
    "#999999":                "#666666",
    "#555555":                "#aaaaaa",
    "#7a3000":                "#ffb380",
    "#7A3000":                "#ffb380",
    "#39e09b":                "#27ae60",
    "#39E09B":                "#27ae60",
    "#2ab87a":                "#219a52",
    "#2AB87A":                "#219a52",
    "#ffa726":                "#e67e22",
    "#ff4444":                "#e74c3c",
    "#cc3636":                "#c0392b",
    "#2a2a2a":                "#d0d0d0",
    "#1a1a1a":                "#e0e0e0",
    "rgba(10,10,10,0.85)":    "rgba(240,240,240,0.90)",
    "rgba(20,20,20,0.75)":    "rgba(255,255,255,0.85)",
}

_LIGHT_TO_DARK: dict[str, str] = {
    "#f2f2f2":                "#0a0a0a",
    "#ffffff":                "#1e1e1e",   # topbar_bg/card_bg → card_bg dark
    "#e8e8e8":                "#121212",
    "#eeeeee":                "#141414",
    "#f5f5f5":                "#282828",
    "#dddddd":                "#1e1e1e",
    "#1a1a1a":                "#f5f5f5",
    "#666666":                "#999999",
    "#aaaaaa":                "#555555",
    "#ffb380":                "#7A3000",
    "#27ae60":                "#39E09B",
    "#219a52":                "#2AB87A",
    "#e67e22":                "#ffa726",
    "#e74c3c":                "#ff4444",
    "#c0392b":                "#cc3636",
    "#d0d0d0":                "#2a2a2a",
    "#e0e0e0":                "#1a1a1a",
    "rgba(240,240,240,0.90)": "rgba(10,10,10,0.85)",
    "rgba(255,255,255,0.85)": "rgba(20,20,20,0.75)",
}


def _build_pattern(mapping: dict[str, str]) -> re.Pattern:
    """Compile a single regex that matches all keys (longest first)."""
    keys = sorted(mapping.keys(), key=len, reverse=True)
    return re.compile("|".join(re.escape(k) for k in keys), re.IGNORECASE)


_PATTERN_D2L: re.Pattern = _build_pattern(_DARK_TO_LIGHT)
_PATTERN_L2D: re.Pattern = _build_pattern(_LIGHT_TO_DARK)

# Lowercased lookup tables for the case-insensitive match callback.
_D2L_LOWER: dict[str, str] = {k.lower(): v for k, v in _DARK_TO_LIGHT.items()}
_L2D_LOWER: dict[str, str] = {k.lower(): v for k, v in _LIGHT_TO_DARK.items()}


def _apply_mapping(ss: str, pattern: re.Pattern, lower_map: dict[str, str]) -> str:
    """Replace all matching colour tokens in *ss* in one regex pass."""
    if not ss:
        return ss
    return pattern.sub(lambda m: lower_map.get(m.group(0).lower(), m.group(0)), ss)


# THEME MANAGER

class ThemeManager:
    """
    Singleton that owns the current theme mode and switches it.

    After ``set_mode()`` is called the global ``COLORS`` dict is mutated,
    the app QSS is re-applied, and every live widget's inline stylesheet is
    patched in-place — no per-widget or per-tab refresh hook required.
    """

    _inst: Optional["ThemeManager"] = None

    @classmethod
    def instance(cls) -> "ThemeManager":
        if cls._inst is None:
            cls._inst = cls()
        return cls._inst

    def __init__(self) -> None:
        print(f"[DEBUG] __init__() called")
        self._mode = "dark"

    @property
    def mode(self) -> str:
        return self._mode

    def set_mode(self, mode: str) -> None:
        print(f"[DEBUG] ThemeManager.set_mode: switching to {mode!r}")
        if mode not in ("dark", "light"):
            raise ValueError(f"Unknown theme mode: {mode!r}")
        if mode == self._mode:
            return
        self._mode = mode
        COLORS.clear()
        COLORS.update(DARK_COLORS if mode == "dark" else LIGHT_COLORS)
        self._apply_to_app()

    def toggle(self) -> str:
        print(f"[DEBUG] ThemeManager.toggle: toggling theme")
        new = "light" if self._mode == "dark" else "dark"
        self.set_mode(new)
        return new


    def _apply_to_app(self) -> None:
        app = QApplication.instance()
        if not app:
            return

        # Step 1 — re-apply the global QSS (scrollbars, tooltips, base bg).
        app.setStyleSheet(build_app_qss())

        # Step 2 — patch every live widget's baked-in stylesheet string.
        if self._mode == "light":
            pattern, lower_map = _PATTERN_D2L, _D2L_LOWER
        else:
            pattern, lower_map = _PATTERN_L2D, _L2D_LOWER

        for top in app.topLevelWidgets():
            _restyle_subtree(top, pattern, lower_map)


def _restyle_subtree(
    root: QWidget,
    pattern: re.Pattern,
    lower_map: dict[str, str],
) -> None:
    """Patch ``root`` and all its QWidget descendants in-place."""
    _restyle_one(root, pattern, lower_map)
    for child in root.findChildren(QWidget):
        _restyle_one(child, pattern, lower_map)


def _restyle_one(w: QWidget, pattern: re.Pattern, lower_map: dict[str, str]) -> None:
    ss = w.styleSheet()
    if not ss:
        return
    new_ss = _apply_mapping(ss, pattern, lower_map)
    if new_ss != ss:
        w.setStyleSheet(new_ss)


# TYPOGRAPHY

FONT_FAMILY = "Segoe UI"
FONT_MONO   = "Consolas"


def font(size: int = 13, weight: str = "normal", italic: bool = False) -> QFont:
    f = QFont(FONT_FAMILY, size)
    if weight == "bold":
        f.setWeight(QFont.Weight.Bold)
    elif weight == "semibold":
        f.setWeight(QFont.Weight.DemiBold)
    f.setItalic(italic)
    return f


# GLOBAL QSS

def build_app_qss() -> str:
    """Generate the global QSS from the *current* COLORS dict."""
    return f"""
QWidget {{
    background-color: {COLORS['app_bg']};
    color: {COLORS['text']};
    font-family: "{FONT_FAMILY}";
    font-size: 13px;
    border: none;
    outline: none;
}}
QScrollBar:vertical {{
    background: {COLORS['frame_bg']};
    width: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {COLORS['border']};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {COLORS['accent']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: {COLORS['frame_bg']};
    height: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:horizontal {{
    background: {COLORS['border']};
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {COLORS['accent']};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QToolTip {{
    background-color: {COLORS['card_bg']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border']};
    padding: 4px 8px;
    border-radius: 6px;
    font-size: 12px;
}}
"""


# Backward-compat constant — dark-theme snapshot.  Use build_app_qss() for
# anything that needs the current theme's QSS.
APP_QSS = build_app_qss()

# WIDGET-SPECIFIC STYLESHEET GENERATORS

def card_style(radius: int = 12, border: bool = True) -> str:
    b = f"1px solid {COLORS['border']};" if border else "none;"
    return f"background-color:{COLORS['card_bg']};border-radius:{radius}px;border:{b}"


def frame_style(radius: int = 12) -> str:
    return (f"background-color:{COLORS['frame_bg']};"
            f"border-radius:{radius}px;border:1px solid {COLORS['border']};")


def button_style(
    fg: str = None, fg_hover: str = None, text: str = None,
    radius: int = 8, border: str = None, font_size: int = 13,
    padding: str = "8px 16px",
) -> str:
    fg       = fg       or COLORS["accent"]
    fg_hover = fg_hover or COLORS["accent_hover"]
    text     = text     or COLORS["accent_text"]
    b        = f"border: {border};" if border else "border: none;"
    return f"""
        QPushButton {{
            background-color:{fg};color:{text};border-radius:{radius}px;{b}
            padding:{padding};font-size:{font_size}px;font-weight:bold;
        }}
        QPushButton:hover {{ background-color:{fg_hover}; }}
        QPushButton:pressed {{ background-color:{COLORS['accent_dim']}; }}
        QPushButton:disabled {{ background-color:{COLORS['border']};color:{COLORS['text_muted']}; }}
    """


def ghost_button_style(radius: int = 8, font_size: int = 13) -> str:
    return f"""
        QPushButton {{
            background-color:transparent;color:{COLORS['text_secondary']};
            border-radius:{radius}px;border:1px solid {COLORS['border']};
            padding:8px 16px;font-size:{font_size}px;
        }}
        QPushButton:hover {{
            background-color:{COLORS['card_hover']};color:{COLORS['text']};
            border-color:{COLORS['accent']};
        }}
        QPushButton:pressed {{ background-color:{COLORS['card_bg']}; }}
    """


def entry_style(radius: int = 8) -> str:
    return f"""
        QLineEdit, QTextEdit, QPlainTextEdit {{
            background-color:{COLORS['frame_bg']};color:{COLORS['text']};
            border:1px solid {COLORS['border']};border-radius:{radius}px;
            padding:6px 10px;font-size:13px;
            selection-background-color:{COLORS['accent']};
        }}
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
            border-color:{COLORS['border_focus']};
        }}
        QLineEdit:read-only {{ color:{COLORS['text_secondary']}; }}
    """


def label_style(size: int = 13, color: str = None, weight: str = "normal") -> str:
    c = color or COLORS["text"]
    w = "bold" if weight == "bold" else "normal"
    return f"color:{c};font-size:{size}px;font-weight:{w};background:transparent;"


def separator_style() -> str:
    return f"background-color:{COLORS['separator']};border:none;"


def scrollarea_style() -> str:
    return ("QScrollArea{background:transparent;border:none;}"
            "QScrollArea>QWidget>QWidget{background:transparent;}")


def tab_nav_button_style(active: bool = False) -> str:
    if active:
        return f"""
            QPushButton {{
                background-color:{COLORS['accent']};color:{COLORS['accent_text']};
                border-radius:8px;border:none;padding:8px 18px;
                font-size:13px;font-weight:bold;
            }}
            QPushButton:hover {{ background-color:{COLORS['accent_hover']}; }}
        """
    return f"""
        QPushButton {{
            background-color:transparent;color:{COLORS['text_secondary']};
            border-radius:8px;border:none;padding:8px 18px;font-size:13px;
        }}
        QPushButton:hover {{
            background-color:{COLORS['card_hover']};color:{COLORS['text']};
        }}
    """


def radio_style() -> str:
    return f"""
        QRadioButton {{
            color:{COLORS['text']};font-size:13px;spacing:8px;
        }}
        QRadioButton::indicator {{
            width:16px;height:16px;border-radius:8px;
            border:2px solid {COLORS['border']};background:{COLORS['frame_bg']};
        }}
        QRadioButton::indicator:checked {{
            border-color:{COLORS['accent']};background:{COLORS['accent']};
        }}
        QRadioButton::indicator:hover {{ border-color:{COLORS['accent']}; }}
    """


def combobox_style() -> str:
    return f"""
        QComboBox {{
            background-color:{COLORS['frame_bg']};color:{COLORS['text']};
            border:1px solid {COLORS['border']};border-radius:8px;
            padding:6px 10px;font-size:13px;
        }}
        QComboBox:focus {{ border-color:{COLORS['border_focus']}; }}
        QComboBox::drop-down {{ border:none;width:20px; }}
        QComboBox::down-arrow {{ width:10px;height:10px; }}
        QComboBox QAbstractItemView {{
            background-color:{COLORS['card_bg']};color:{COLORS['text']};
            border:1px solid {COLORS['border']};
            selection-background-color:{COLORS['accent']};
            selection-color:{COLORS['accent_text']};border-radius:4px;
        }}
    """


def checkbox_style() -> str:
    return f"""
        QCheckBox {{
            color:{COLORS['text']};font-size:13px;spacing:8px;
        }}
        QCheckBox::indicator {{
            width:16px;height:16px;border-radius:4px;
            border:2px solid {COLORS['border']};background:{COLORS['frame_bg']};
        }}
        QCheckBox::indicator:checked {{
            background:{COLORS['accent']};border-color:{COLORS['accent']};
        }}
    """


# EFFECTS  &  ANIMATIONS

def drop_shadow(
    widget: QWidget,
    blur: int = 20,
    offset: tuple[int, int] = (0, 4),
    color: str = "#00000066",
) -> QGraphicsDropShadowEffect:
    fx = QGraphicsDropShadowEffect(widget)
    fx.setBlurRadius(blur)
    fx.setOffset(*offset)
    fx.setColor(QColor(color))
    widget.setGraphicsEffect(fx)
    return fx


def fade_in(
    widget: QWidget,
    duration: int = 250,
    start: float = 0.0,
    end: float = 1.0,
) -> QPropertyAnimation:
    existing = widget.graphicsEffect()
    if isinstance(existing, QGraphicsDropShadowEffect):
        widget.show()
        return QPropertyAnimation(widget)

    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(start)
    widget.setGraphicsEffect(effect)
    widget.show()
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(start)
    anim.setEndValue(end)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    # Remove the opacity effect once the animation is done.
    # QGraphicsEffect uses an offscreen render buffer that breaks widget
    # painting inside QScrollArea during scrolling — cards disappear.
    anim.finished.connect(lambda: widget.setGraphicsEffect(None))
    anim.start(QPropertyAnimation.DeleteWhenStopped)
    return anim


def slide_in(
    widget: QWidget,
    direction: str = "left",
    duration: int = 300,
) -> QPropertyAnimation:
    widget.show()
    rect: QRect = widget.geometry()
    if direction == "left":
        start = QRect(rect.x() - rect.width(), rect.y(), rect.width(), rect.height())
    elif direction == "right":
        start = QRect(rect.x() + rect.width(), rect.y(), rect.width(), rect.height())
    elif direction == "top":
        start = QRect(rect.x(), rect.y() - rect.height(), rect.width(), rect.height())
    else:
        start = QRect(rect.x(), rect.y() + rect.height(), rect.width(), rect.height())
    anim = QPropertyAnimation(widget, b"geometry", widget)
    anim.setDuration(duration)
    anim.setStartValue(start)
    anim.setEndValue(rect)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    anim.start(QPropertyAnimation.DeleteWhenStopped)
    return anim


def pulse_scale(widget: QWidget, duration: int = 150) -> QSequentialAnimationGroup:
    rect = widget.geometry()
    shrink = 4
    small = QRect(rect.x() + shrink, rect.y() + shrink,
                  rect.width() - shrink * 2, rect.height() - shrink * 2)
    grp = QSequentialAnimationGroup(widget)
    a1 = QPropertyAnimation(widget, b"geometry")
    a1.setDuration(duration // 2)
    a1.setStartValue(rect)
    a1.setEndValue(small)
    a1.setEasingCurve(QEasingCurve.InQuad)
    a2 = QPropertyAnimation(widget, b"geometry")
    a2.setDuration(duration // 2)
    a2.setStartValue(small)
    a2.setEndValue(rect)
    a2.setEasingCurve(QEasingCurve.OutQuad)
    grp.addAnimation(a1)
    grp.addAnimation(a2)
    grp.start(QSequentialAnimationGroup.DeleteWhenStopped)
    return grp


