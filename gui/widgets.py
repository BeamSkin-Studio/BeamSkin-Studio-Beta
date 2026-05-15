from __future__ import annotations
from typing import Optional, Callable

from PySide6.QtCore  import (Qt, QTimer, QPropertyAnimation,
                              QEasingCurve, QRect, QPoint, Signal,
                              QSize, Property)
from PySide6.QtGui   import (QColor, QPainter, QPen, QBrush,
                              QLinearGradient, QFont, QFontMetrics,
                              QEnterEvent, QPixmap)
from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QLineEdit, QTextEdit,
    QVBoxLayout, QHBoxLayout, QGridLayout, QScrollArea, QSizePolicy,
    QGraphicsOpacityEffect, QGraphicsDropShadowEffect, QRadioButton,
    QButtonGroup, QApplication, QStackedWidget,
)

from gui.theme import COLORS, font, drop_shadow, fade_in


class ToggleSwitch(QWidget):
    """Animated pill-style toggle switch, drop-in replacement for QCheckBox."""

    stateChanged = Signal(int)   # emits 2 (checked) or 0 (unchecked), matching QCheckBox

    _W, _H = 44, 24             # overall size

    def __init__(self, parent=None):
        print(f"[DEBUG] __init__() called")
        super().__init__(parent)
        self._checked = False
        self._pos     = 0.0     # 0.0 = off, 1.0 = on
        self.setFixedSize(self._W, self._H)
        self.setCursor(Qt.PointingHandCursor)
        self._anim = QPropertyAnimation(self, b"_switch_pos", self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

    def _get_pos(self) -> float:
        return self._pos

    def _set_pos(self, v: float):
        self._pos = v
        self.update()

    _switch_pos = Property(float, _get_pos, _set_pos)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool):
        print(f"[DEBUG] setChecked() called")
        if self._checked == checked:
            return
        self._checked = checked
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()
        self.stateChanged.emit(2 if checked else 0)

    def toggle(self):
        print(f"[DEBUG] toggle() called")
        self.setChecked(not self._checked)

    def mousePressEvent(self, event):
        print(f"[DEBUG] mousePressEvent() called")
        if event.button() == Qt.LeftButton:
            self.toggle()
        super().mousePressEvent(event)

    def paintEvent(self, _event):
        print(f"[DEBUG] paintEvent() called")
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self._W, self._H
        r    = h / 2

        off_c = QColor(COLORS.get("border",  "#555555"))
        on_c  = QColor(COLORS.get("accent",  "#f97316"))
        t     = self._pos
        track = QColor(
            int(off_c.red()   + (on_c.red()   - off_c.red())   * t),
            int(off_c.green() + (on_c.green() - off_c.green()) * t),
            int(off_c.blue()  + (on_c.blue()  - off_c.blue())  * t),
        )
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(track))
        p.drawRoundedRect(0, 0, w, h, r, r)

        margin  = 3
        thumb_d = h - margin * 2
        travel  = w - thumb_d - margin * 2
        x       = int(margin + self._pos * travel)
        p.setBrush(QBrush(QColor("white")))
        p.drawEllipse(QRect(x, margin, thumb_d, thumb_d))

        p.end()

class Card(QFrame):

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        bg: str = None,
        radius: int = 12,
        shadow: bool = True,
        border: bool = True,
    ):
        super().__init__(parent)
        self._bg     = bg or COLORS["card_bg"]
        self._radius = radius
        self._border = border
        self._apply_style()
        if shadow:
            drop_shadow(self, blur=16, offset=(0, 4))

    def _apply_style(self):
        b = f"1px solid {COLORS['border']}" if self._border else "none"
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {self._bg};
                border-radius: {self._radius}px;
                border: {b};
            }}
        """)

    def set_bg(self, color: str):
        print(f"[DEBUG] set_bg() called")
        self._bg = color
        self._apply_style()

class AnimButton(QPushButton):

    def __init__(
        self,
        text: str = "",
        parent: Optional[QWidget] = None,
        fg: str = None,
        fg_hover: str = None,
        text_color: str = None,
        radius: int = 8,
        font_size: int = 13,
        bold: bool = True,
        icon_text: str = "",
        padding: str = "8px 18px",
    ):
        super().__init__(text, parent)
        self._fg       = fg       or COLORS["accent"]
        self._fg_hover = fg_hover or COLORS["accent_hover"]
        self._tc       = text_color or COLORS["accent_text"]
        self._radius   = radius
        self._fs       = font_size
        self._bold     = bold
        self._padding  = padding
        self._hovered  = False

        f = QFont("Segoe UI", font_size)
        if bold:
            f.setBold(True)
        self.setFont(f)

        if icon_text:
            self.setText(f"{icon_text}  {text}")

        self._apply(hover=False)
        self.setCursor(Qt.PointingHandCursor)

    def _apply(self, hover: bool):
        print(f"[DEBUG] _apply() called")
        bg = self._fg_hover if hover else self._fg
        w  = "bold" if self._bold else "normal"
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: {self._tc};
                border-radius: {self._radius}px;
                border: none;
                padding: {self._padding};
                font-size: {self._fs}px;
                font-weight: {w};
            }}
            QPushButton:pressed {{
                background-color: {COLORS['accent_dim']};
            }}
            QPushButton:disabled {{
                background-color: {COLORS['border']};
                color: {COLORS['text_muted']};
            }}
        """)

    def enterEvent(self, event: QEnterEvent):
        print(f"[DEBUG] enterEvent() called")
        self._hovered = True
        self._apply(hover=True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        print(f"[DEBUG] leaveEvent() called")
        self._hovered = False
        self._apply(hover=False)
        super().leaveEvent(event)

class GhostButton(QPushButton):

    def __init__(
        self,
        text: str = "",
        parent: Optional[QWidget] = None,
        font_size: int = 13,
        radius: int = 8,
        bold: bool = False,
    ):
        super().__init__(text, parent)
        self._fs     = font_size
        self._radius = radius
        self._bold   = bold
        f = QFont("Segoe UI", font_size)
        if bold:
            f.setBold(True)
        self.setFont(f)
        self.setCursor(Qt.PointingHandCursor)
        self._apply_normal()

    def _apply_normal(self):
        w = "bold" if self._bold else "normal"
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {COLORS['text_secondary']};
                border-radius: {self._radius}px;
                border: 1px solid {COLORS['border']};
                padding: 8px 16px;
                font-size: {self._fs}px;
                font-weight: {w};
            }}
            QPushButton:hover {{
                background-color: {COLORS['card_hover']};
                color: {COLORS['text']};
                border-color: {COLORS['accent']};
            }}
            QPushButton:pressed {{
                background-color: {COLORS['card_bg']};
            }}
        """)

class LabelledEntry(QWidget):

    textChanged = Signal(str)

    def __init__(
        self,
        label: str = "",
        placeholder: str = "",
        parent: Optional[QWidget] = None,
        read_only: bool = False,
    ):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        if label:
            lbl = QLabel(label, self)
            lbl.setFont(font(11, "bold"))
            lbl.setStyleSheet(f"color:{COLORS['text']};background:transparent;")
            layout.addWidget(lbl)

        self.entry = QLineEdit(self)
        self.entry.setPlaceholderText(placeholder)
        self.entry.setReadOnly(read_only)
        self.entry.setFont(font(13))
        self.entry.setMinimumHeight(36)
        self.entry.setStyleSheet(f"""
            QLineEdit {{
                background-color: {COLORS['frame_bg']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 6px 10px;
                font-size: 13px;
                selection-background-color: {COLORS['accent']};
            }}
            QLineEdit:focus {{
                border-color: {COLORS['border_focus']};
            }}
            QLineEdit:read-only {{
                color: {COLORS['text_secondary']};
            }}
        """)
        self.entry.textChanged.connect(self.textChanged)
        layout.addWidget(self.entry)

    def text(self) -> str:
        return self.entry.text()

    def set_text(self, t: str):
        print(f"[DEBUG] set_text() called")
        self.entry.setText(t)

    def clear(self):
        print(f"[DEBUG] clear() called")
        self.entry.clear()

class HSeparator(QFrame):
    def __init__(self, parent=None):
        print(f"[DEBUG] __init__() called")
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setFixedHeight(1)
        self.setStyleSheet(f"background:{COLORS['separator']};border:none;")

_TYPE_COLORS = {
    "success": COLORS["success"],
    "warning": COLORS["warning"],
    "error":   COLORS["error"],
    "info":    COLORS["accent"],
}

_TYPE_ICONS = {

}

class Toast(QFrame):

    def __init__(
        self,
        parent: QWidget,
        message: str,
        kind: str = "info",
        duration: int = 3000,
    ):
        super().__init__(parent)

        self._duration = duration
        accent = _TYPE_COLORS.get(kind, COLORS["accent"])
        icon   = _TYPE_ICONS.get(kind, "ℹ️")

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['card_bg']};
                border-radius: 10px;
                border: 1px solid {accent};
                border-left: 4px solid {accent};
            }}
        """)

        row = QHBoxLayout(self)
        row.setContentsMargins(16, 12, 16, 12)
        row.setSpacing(12)

        icon_lbl = QLabel(icon)
        icon_lbl.setFont(font(18))
        icon_lbl.setStyleSheet("background:transparent;border:none;")
        row.addWidget(icon_lbl)

        msg_lbl = QLabel(message)
        msg_lbl.setFont(font(13))
        msg_lbl.setStyleSheet(f"color:{COLORS['text']};background:transparent;border:none;")
        msg_lbl.setWordWrap(True)
        row.addWidget(msg_lbl, 1)

        self.setFixedWidth(360)
        self.adjustSize()
        self._reposition()
        fade_in(self, 200)
        QTimer.singleShot(duration, self._dismiss)

    def _reposition(self):
        print(f"[DEBUG] _reposition() called")
        p = self.parent()
        if p:
            pg = p.rect()
            self.move(pg.right() - self.width() - 20,
                      pg.bottom() - self.height() - 20)

    def _dismiss(self):
        print(f"[DEBUG] _dismiss() called")
        fx = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(fx)
        anim = QPropertyAnimation(fx, b"opacity", self)
        anim.setDuration(300)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.finished.connect(self.deleteLater)
        anim.start(QPropertyAnimation.DeleteWhenStopped)

class SectionHeader(QWidget):

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        parent: Optional[QWidget] = None,
        icon: str = "",
    ):
        super().__init__(parent)
        self.setStyleSheet("background:transparent;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        t_text = f"{icon}  {title}" if icon else title
        title_lbl = QLabel(t_text)
        title_lbl.setFont(font(20, "bold"))
        title_lbl.setStyleSheet(f"color:{COLORS['text']};background:transparent;")
        layout.addWidget(title_lbl)

        if subtitle:
            sub_lbl = QLabel(subtitle)
            sub_lbl.setFont(font(12))
            sub_lbl.setStyleSheet(
                f"color:{COLORS['text_secondary']};background:transparent;"
            )
            layout.addWidget(sub_lbl)

class FadeStack(QStackedWidget):

    def setCurrentIndex(self, index: int):
        print(f"[DEBUG] setCurrentIndex() called")
        prev = self.currentIndex()
        super().setCurrentIndex(index)
        w = self.currentWidget()
        if w and index != prev:
            fade_in(w, duration=200)

class VehicleCard(QFrame):
    """
    Clickable sidebar card for single-body vehicles.
    A single click immediately emits add_requested — no expand/collapse step.
    """

    add_requested = Signal(str, str)

    def __init__(
        self,
        carid: str,
        display_name: str,
        parent: Optional[QWidget] = None,
        is_custom: bool = False,
        **_kwargs,          # absorb legacy show_add kwarg without error
    ):
        super().__init__(parent)
        self.carid        = carid
        self.display_name = display_name

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['card_bg']};
                border-radius: 8px;
                border: 1px solid {COLORS['border']};
            }}
            QFrame:hover {{
                border-color: {COLORS['accent']};
                background-color: {COLORS['card_hover']};
            }}
        """)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(38)

        row = QHBoxLayout(self)
        row.setContentsMargins(10, 0, 10, 0)
        row.setSpacing(8)

        name_lbl = QLabel(display_name)
        name_lbl.setFont(font(13, "bold"))
        name_lbl.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;"
        )
        row.addWidget(name_lbl, 1)

        if is_custom:
            mod_badge = QLabel("mod")
            mod_badge.setFont(font(8))
            mod_badge.setStyleSheet(f"""
                QLabel {{
                    color: {COLORS['text_secondary']};
                    background: transparent;
                    border: 1px solid {COLORS['border']};
                    border-radius: 3px;
                    padding: 0px 4px;
                }}
            """)
            row.addWidget(mod_badge)

    def mousePressEvent(self, event):
        print(f"[DEBUG] mousePressEvent() called")
        if event.button() == Qt.LeftButton:
            self.add_requested.emit(self.carid, self.display_name)
        super().mousePressEvent(event)

class Badge(QLabel):
    def __init__(
        self,
        text: str,
        color: str = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(text, parent)
        c = color or COLORS["accent"]
        self.setFont(font(10, "bold"))
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {c};
                color: white;
                border-radius: 8px;
                padding: 2px 8px;
            }}
        """)
        self.setAlignment(Qt.AlignCenter)

class Spinner(QLabel):
    _FRAMES = ["◐", "◓", "◑", "◒"]

    def __init__(self, parent=None, size: int = 18):
        print(f"[DEBUG] __init__() called")
        super().__init__(self._FRAMES[0], parent)
        self.setFont(font(size))
        self.setStyleSheet(
            f"color:{COLORS['accent']};background:transparent;border:none;"
        )
        self.setAlignment(Qt.AlignCenter)
        self._idx = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(120)

    def _tick(self):
        print(f"[DEBUG] _tick() called")
        self._idx = (self._idx + 1) % len(self._FRAMES)
        self.setText(self._FRAMES[self._idx])

    def stop(self):
        print(f"[DEBUG] stop() called")
        self._timer.stop()


