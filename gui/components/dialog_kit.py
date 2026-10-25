from __future__ import annotations
import os as _os
import sys as _sys
from typing import Callable, Optional, Tuple

from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QApplication, QDialog, QFrame, QGraphicsOpacityEffect, QHBoxLayout,
    QLabel, QLayout, QPushButton, QVBoxLayout, QWidget, QCheckBox,
    QScrollArea,
)

from gui.theme import COLORS, font, drop_shadow
from gui.widgets import AnimButton

SHADOW_MARGIN = 16
CARD_RADIUS   = 14


def _c(key: str, fallback: str | None = None) -> str:
    return COLORS.get(key, COLORS.get(fallback, "#888888") if fallback else "#888888")


def muted() -> str:
    return COLORS.get("text_muted", COLORS["text_secondary"])


def platform_supports_transparency() -> bool:
    if _sys.platform in ("win32", "darwin"):
        return True
    try:
        app = QApplication.instance()
        name = app.platformName().lower() if app else ""
        if app and "wayland" in name:
            return True
        import subprocess
        display = _os.environ.get("DISPLAY", ":0")
        screen_num = display.split(".")[-1] if "." in display else "0"
        result = subprocess.run(
            ["xprop", "-root", f"_NET_WM_CM_S{screen_num}"],
            capture_output=True, text=True, timeout=1,
        )
        return "window id" in result.stdout.lower()
    except Exception as e:
        print(f"[DEBUG] dialog_kit: transparency probe failed ({e}), assuming opaque")
        return False


def lbl_qss(color_key: str = "text") -> str:
    return f"color:{COLORS[color_key]};background:transparent;border:none;"


def panel_qss(name: str, radius: int = 10, inset: bool = False) -> str:
    bg = COLORS["frame_bg"] if inset else COLORS["card_bg"]
    return f"""
        QFrame#{name} {{
            background:{bg};
            border:1px solid {COLORS['border']};
            border-radius:{radius}px;
        }}
    """


def input_qss() -> str:
    return f"""
        QLineEdit {{
            background:{COLORS['frame_bg']};
            color:{COLORS['text']};
            border:1px solid {COLORS['border']};
            border-radius:8px;
            padding:4px 10px;
            font-size:12px;
            selection-background-color:{COLORS['accent']};
        }}
        QLineEdit:focus {{ border-color:{COLORS.get('border_focus', COLORS['accent'])}; }}
        QLineEdit:read-only {{ color:{COLORS['text_secondary']}; }}
    """


def outline_qss() -> str:
    return f"""
        QPushButton {{
            background:transparent;
            color:{COLORS['text']};
            border:1px solid {COLORS['border']};
            border-radius:8px; padding:4px 18px;
        }}
        QPushButton:hover {{
            background:{COLORS.get('card_hover', COLORS['card_bg'])};
            border-color:{COLORS['accent']};
        }}
        QPushButton:disabled {{ color:{muted()}; }}
    """


def danger_qss() -> str:
    err = COLORS["error"]
    return f"""
        QPushButton {{
            background:{err}; color:#ffffff; border:none;
            border-radius:8px; padding:4px 18px;
        }}
        QPushButton:hover   {{ background:{COLORS.get('error_hover', err)}; }}
        QPushButton:pressed {{ background:#7a1c1c; }}
        QPushButton:disabled {{ background:{COLORS['border']}; color:{muted()}; }}
    """


def checkbox_qss() -> str:
    return f"""
        QCheckBox {{ color:{COLORS['text_secondary']}; background:transparent; spacing:8px; }}
        QCheckBox::indicator {{
            width:16px; height:16px;
            border:1px solid {COLORS['border']};
            border-radius:4px; background:{COLORS['frame_bg']};
        }}
        QCheckBox::indicator:hover   {{ border-color:{COLORS['accent']}; }}
        QCheckBox::indicator:checked {{ background:{COLORS['accent']}; border-color:{COLORS['accent']}; }}
    """


SCROLL_QSS = f"""
    QScrollArea {{ background:transparent; border:none; }}
    QScrollArea > QWidget > QWidget {{ background:transparent; }}
    QScrollBar:vertical {{ background:transparent; width:8px; margin:2px; }}
    QScrollBar::handle:vertical {{
        background:{COLORS['border']}; border-radius:4px; min-height:24px;
    }}
    QScrollBar::handle:vertical:hover {{ background:{COLORS['accent']}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
"""


def primary_button(text: str, height: int = 40, font_size: int = 13,
                   padding: str = "8px 24px") -> AnimButton:
    btn = AnimButton(
        text, fg=COLORS["accent"], fg_hover=COLORS["accent_hover"],
        font_size=font_size, bold=True, padding=padding,
    )
    btn.setMinimumHeight(height)
    return btn


def outline_button(text: str, height: int = 40, font_size: int = 13,
                   bold: bool = True) -> QPushButton:
    btn = QPushButton(text)
    btn.setFont(font(font_size, "bold" if bold else "normal"))
    btn.setMinimumHeight(height)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setStyleSheet(outline_qss())
    return btn


def danger_button(text: str, height: int = 40, font_size: int = 13) -> QPushButton:
    btn = QPushButton(text)
    btn.setFont(font(font_size, "bold"))
    btn.setMinimumHeight(height)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setStyleSheet(danger_qss())
    return btn


def section_header(text: str, color: Optional[str] = None,
                   contained: bool = True) -> QFrame:
    color = color or COLORS["accent"]
    header = QFrame()
    header.setFixedHeight(26)
    header.setStyleSheet("background:transparent;border:none;")
    row = QHBoxLayout(header)
    row.setContentsMargins(2 if contained else 6, 0, 0, 0)
    row.setSpacing(8)
    marker = QFrame()
    marker.setFixedSize(3, 14)
    marker.setStyleSheet(f"background:{color};border:none;border-radius:1px;")
    row.addWidget(marker)
    lbl = QLabel(text.upper())
    lbl.setFont(font(10, "bold"))
    lbl.setStyleSheet(lbl_qss())
    row.addWidget(lbl)
    row.addStretch()
    return header


def divider() -> QFrame:
    d = QFrame()
    d.setFixedHeight(1)
    d.setStyleSheet(f"background:{COLORS['border']};border:none;")
    return d


def body_label(text: str, secondary: bool = True, size: int = 12,
               center: bool = False, bold: bool = False) -> QLabel:
    lbl = QLabel(text)
    lbl.setFont(font(size, "bold" if bold else "normal"))
    lbl.setWordWrap(True)
    lbl.setStyleSheet(lbl_qss("text_secondary" if secondary else "text"))
    if center:
        lbl.setAlignment(Qt.AlignCenter)
    return lbl


def make_panel(name: str, margins: Tuple[int, int, int, int] = (14, 12, 14, 12),
               spacing: int = 8, inset: bool = False) -> Tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName(name)
    frame.setStyleSheet(panel_qss(name, inset=inset))
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(*margins)
    lay.setSpacing(spacing)
    return frame, lay


def make_scroll(inner: QWidget) -> QScrollArea:
    sc = QScrollArea()
    sc.setWidgetResizable(True)
    sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    sc.setStyleSheet(SCROLL_QSS)
    inner.setStyleSheet("background:transparent;")
    sc.setWidget(inner)
    return sc


def make_checkbox(text: str) -> QCheckBox:
    chk = QCheckBox(text)
    chk.setFont(font(11))
    chk.setCursor(Qt.PointingHandCursor)
    chk.setStyleSheet(checkbox_qss())
    return chk


class StatusLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__("", parent)
        self.setFont(font(11))
        self.setWordWrap(True)
        self.setStyleSheet("background:transparent;border:none;")
        self.hide()

    def setText(self, text: str):
        super().setText(text)
        self.setVisible(bool(text))


def icon_badge(emoji: str, color: Optional[str] = None, size: int = 44) -> QLabel:
    color = color or COLORS["accent"]
    lbl = QLabel(emoji)
    lbl.setFixedSize(size, size)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setFont(font(int(size * 0.45)))
    lbl.setStyleSheet(f"""
        QLabel {{
            background:{COLORS['card_bg']};
            border:1px solid {color};
            border-radius:{size // 3}px;
        }}
    """)
    return lbl


class LanguageRow(QFrame):
    selected = Signal(str)

    def __init__(self, code: str, info: dict, is_selected: bool, parent=None):
        super().__init__(parent)
        self.setObjectName("langRow")
        self.lang_code = self.code = code
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(56)
        self._apply(is_selected)

        row = QHBoxLayout(self)
        row.setContentsMargins(14, 8, 14, 8)
        row.setSpacing(12)

        fg  = COLORS["accent_text"] if is_selected else COLORS["text"]
        fg2 = COLORS["accent_text"] if is_selected else COLORS["text_secondary"]

        flag = QLabel(info.get("flag", "🌐"))
        flag.setFont(font(22))
        flag.setStyleSheet("background:transparent;border:none;")
        row.addWidget(flag)

        names = QVBoxLayout()
        names.setSpacing(0)
        native = info.get("native", info.get("name", code))
        n_lbl = QLabel(native)
        n_lbl.setFont(font(13, "bold"))
        n_lbl.setStyleSheet(f"color:{fg};background:transparent;border:none;")
        names.addWidget(n_lbl)
        if info.get("native") and info.get("native") != info.get("name"):
            e_lbl = QLabel(info.get("name", ""))
            e_lbl.setFont(font(10))
            e_lbl.setStyleSheet(f"color:{fg2};background:transparent;border:none;")
            names.addWidget(e_lbl)
        row.addLayout(names, 1)

        if is_selected:
            chk = QLabel("✓")
            chk.setFont(font(16, "bold"))
            chk.setStyleSheet(f"color:{COLORS['accent_text']};background:transparent;border:none;")
            row.addWidget(chk)

    def _apply(self, active: bool):
        if active:
            self.setStyleSheet(f"""
                QFrame#langRow {{
                    background:{COLORS['accent']};
                    border:1px solid {COLORS['accent']};
                    border-radius:8px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QFrame#langRow {{
                    background:{COLORS['frame_bg']};
                    border:1px solid {COLORS['border']};
                    border-radius:8px;
                }}
                QFrame#langRow:hover {{
                    background:{COLORS.get('card_hover', COLORS['card_bg'])};
                    border-color:{COLORS['accent']};
                }}
            """)

    def mousePressEvent(self, _event):
        self.selected.emit(self.lang_code)


class DialogShell(QDialog):

    def __init__(
        self,
        parent: Optional[QWidget],
        title: str,
        width: int = 520,
        height: Optional[int] = None,
        icon: str = "",
        accent: Optional[str] = None,
        subtitle: str = "",
        escape_closes: bool = True,
        body_margins: Tuple[int, int, int, int] = (22, 18, 22, 18),
    ):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Dialog)
        self.setModal(True)
        self._accent        = accent or COLORS["accent"]
        self._escape_closes = escape_closes
        self._fade_done     = False
        self._centered      = False
        self._translucent   = platform_supports_transparency()
        m = SHADOW_MARGIN if self._translucent else 0

        if self._translucent:
            self.setAttribute(Qt.WA_TranslucentBackground)
            self.setStyleSheet("background:transparent;")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(m, m, m, m)
        outer.setSpacing(0)

        self._card = QFrame()
        self._card.setObjectName("dlgCard")
        self._card.setFixedWidth(width)
        self._card.setStyleSheet(f"""
            QFrame#dlgCard {{
                background:{COLORS['frame_bg']};
                border:1px solid {COLORS['border']};
                border-radius:{CARD_RADIUS}px;
            }}
        """)
        outer.addWidget(self._card)

        card_col = QVBoxLayout(self._card)
        card_col.setContentsMargins(0, 0, 0, 0)
        card_col.setSpacing(0)

        card_col.addWidget(self._build_header(title, icon, subtitle))

        body_host = QWidget()
        body_host.setStyleSheet("background:transparent;")
        self.body = QVBoxLayout(body_host)
        self.body.setContentsMargins(*body_margins)
        self.body.setSpacing(14)
        card_col.addWidget(body_host, 1)

        self.footer = QHBoxLayout()
        self.footer.setSpacing(10)
        self._footer_host = body_host

        if height is not None:
            self.setFixedSize(width + 2 * m, height + 2 * m)
        else:
            outer.setSizeConstraint(QLayout.SetFixedSize)

    def _build_header(self, title: str, icon: str, subtitle: str) -> QFrame:
        hdr = QFrame()
        hdr.setObjectName("dlgHeader")
        hdr.setFixedHeight(52)
        hdr.setStyleSheet(f"""
            QFrame#dlgHeader {{
                background:{COLORS.get('topbar_bg', COLORS['card_bg'])};
                border:none;
                border-bottom:1px solid {COLORS['border']};
                border-top-left-radius:{CARD_RADIUS}px;
                border-top-right-radius:{CARD_RADIUS}px;
            }}
        """)
        row = QHBoxLayout(hdr)
        row.setContentsMargins(20, 0, 20, 0)
        row.setSpacing(10)

        marker = QFrame()
        marker.setFixedSize(3, 18)
        marker.setStyleSheet(f"background:{self._accent};border:none;border-radius:1px;")
        row.addWidget(marker)

        self._title_lbl = QLabel((f"{icon}  " if icon else "") + title.upper())
        self._title_lbl.setFont(font(13, "bold"))
        self._title_lbl.setStyleSheet(
            f"color:{self._accent if self._accent != COLORS['accent'] else COLORS['text']};"
            "background:transparent;border:none;"
        )
        row.addWidget(self._title_lbl)
        row.addStretch()

        self._subtitle_lbl = QLabel(subtitle, hdr)
        self._subtitle_lbl.setFont(font(10))
        self._subtitle_lbl.setStyleSheet(
            f"color:{COLORS['accent']};"
            f"background:{COLORS.get('accent_dim', COLORS['card_bg'])};"
            "border:none;border-radius:4px;padding:2px 9px;"
        )
        row.addWidget(self._subtitle_lbl, 0, Qt.AlignVCenter)
        self._subtitle_lbl.setVisible(bool(subtitle))
        return hdr

    def set_title(self, text: str, icon: str = ""):
        self._title_lbl.setText((f"{icon}  " if icon else "") + text.upper())

    def set_subtitle(self, text: str):
        self._subtitle_lbl.setText(text)
        self._subtitle_lbl.setVisible(bool(text))

    def add_footer(self):
        self.body.addWidget(divider())
        self.body.addLayout(self.footer)

    def _center_on_parent(self):
        parent = self.parentWidget()
        if parent is not None:
            pg = parent.window().frameGeometry()
            self.move(pg.x() + (pg.width() - self.width()) // 2,
                      pg.y() + (pg.height() - self.height()) // 2)
        else:
            sg = QApplication.primaryScreen().geometry()
            self.move((sg.width() - self.width()) // 2,
                      (sg.height() - self.height()) // 2)

    def setVisible(self, visible: bool) -> None:
        if visible and not self._centered:
            self._centered = True
            self.ensurePolished()
            lay = self.layout()
            if lay is not None:
                lay.activate()
            self.adjustSize()
            self._center_on_parent()
        super().setVisible(visible)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if self._fade_done:
            return
        self._fade_done = True

        fx = QGraphicsOpacityEffect(self._card)
        fx.setOpacity(0.0)
        self._card.setGraphicsEffect(fx)
        anim = QPropertyAnimation(fx, b"opacity", self._card)
        anim.setDuration(200)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)

        def _done():
            self._card.setGraphicsEffect(None)
            if self._translucent:
                drop_shadow(self._card, 32, (0, 8))

        anim.finished.connect(_done)
        anim.start(QPropertyAnimation.DeleteWhenStopped)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and not self._escape_closes:
            return
        super().keyPressEvent(event)
