from __future__ import annotations
from typing import Optional

from PySide6.QtCore    import Qt, QPropertyAnimation, QEasingCurve, QRect
from PySide6.QtGui     import QFont, QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QWidget, QApplication,
    QGraphicsDropShadowEffect,
)

from gui.theme   import COLORS, font, drop_shadow, fade_in
from gui.widgets import AnimButton, GhostButton, Card, HSeparator
from gui.icon_helper import set_window_icon

try:
    from core.localization import t
except ImportError:
    def t(key, **kw): return key


# BASE  DIALOG

class _BaseDialog(QDialog):
    """Common boilerplate: dark background, centred, animated entrance."""

    def __init__(self, parent: QWidget, title: str, width: int = 520, height: int = 320):
        print(f"[DEBUG] __init__() called")
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Dialog)
        set_window_icon(self)
        self.setModal(True)
        self.setFixedSize(width, height)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent;")

        # centre relative to parent
        if parent:
            pg = parent.frameGeometry()
            self.move(
                pg.x() + (pg.width()  - width)  // 2,
                pg.y() + (pg.height() - height) // 2,
            )
        else:
            screen = QApplication.primaryScreen().geometry()
            self.move(
                (screen.width()  - width)  // 2,
                (screen.height() - height) // 2,
            )

        # outer card
        self._card = QFrame(self)
        self._card.setGeometry(0, 0, width, height)
        self._card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['frame_bg']};
                border-radius: 16px;
                border: 1px solid {COLORS['border']};
            }}
        """)
        drop_shadow(self._card, blur=32, offset=(0, 8), color="#00000088")

        self._root = QVBoxLayout(self._card)
        self._root.setContentsMargins(28, 24, 28, 24)
        self._root.setSpacing(16)

        self._build_content(title)

    def _build_content(self, title: str):
        print(f"[DEBUG] _build_content() called")
        raise NotImplementedError

    def showEvent(self, event):
        print(f"[DEBUG] showEvent() called")
        fade_in(self._card, 220)
        super().showEvent(event)


# DANGER  CONFIRMATION  DIALOG
# Used for destructive actions like Clear Project.

class DangerConfirmationDialog(QDialog):
    """
    Purpose-built dialog for destructive / irreversible actions.

    Visual language:
      • Red glowing outer border + thin red accent strip at top
      • Centered icon, title (red), and optional "irreversible" subtitle
      • Message card with subtle red-tinted border
      • Ghost cancel on the left, solid red confirm on the right
    """

    def __init__(
        self,
        parent:       QWidget,
        title:        str,
        message:      str,
        colors:       dict,
        confirm_text: Optional[str] = None,
        cancel_text:  Optional[str] = None,
        icon:         str  = "🗑️",
        irreversible: bool = True,
    ):
        if confirm_text is None:
            confirm_text = t("dialog.yes", default="Yes")
        if cancel_text is None:
            cancel_text = t("dialog.no", default="No")

        super().__init__(parent, Qt.FramelessWindowHint | Qt.Dialog)
        set_window_icon(self)
        self.setModal(True)

        W, H = 480, 310
        self.setFixedSize(W, H)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent;")
        self.result = False

        # centre on parent
        if parent:
            pg = parent.frameGeometry()
            self.move(
                pg.x() + (pg.width()  - W) // 2,
                pg.y() + (pg.height() - H) // 2,
            )
        else:
            sg = QApplication.primaryScreen().geometry()
            self.move((sg.width() - W) // 2, (sg.height() - H) // 2)

        err     = COLORS["error"]
        err_h   = COLORS["error_hover"]
        err_dim = "#7a1c1c"

        # Outer card
        self._card = QFrame(self)
        self._card.setGeometry(0, 0, W, H)
        self._card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['frame_bg']};
                border-radius: 16px;
                border: 1.5px solid {err};
            }}
        """)

        # Red drop-shadow glow
        glow = QGraphicsDropShadowEffect(self._card)
        glow.setBlurRadius(40)
        glow.setOffset(0, 0)
        glow.setColor(QColor(err + "77"))
        self._card.setGraphicsEffect(glow)

        root = QVBoxLayout(self._card)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Thin red accent strip at top (matches card's border-radius)
        accent_strip = QFrame()
        accent_strip.setFixedHeight(4)
        accent_strip.setStyleSheet(f"""
            QFrame {{
                background-color: {err};
                border-top-left-radius: 14px;
                border-top-right-radius: 14px;
                border-bottom-left-radius: 0;
                border-bottom-right-radius: 0;
                border: none;
            }}
        """)
        root.addWidget(accent_strip)

        # Main content — uniform padding, centred layout to match other dialogs
        content = QVBoxLayout()
        content.setContentsMargins(28, 18, 28, 24)
        content.setSpacing(10)

        # Icon (centred, same scale as InfoDialog)
        icon_lbl = QLabel(icon)
        icon_lbl.setFont(font(38))
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("background:transparent;border:none;")
        content.addWidget(icon_lbl)

        # Title in danger colour, centred
        title_lbl = QLabel(title)
        title_lbl.setFont(font(18, "bold"))
        title_lbl.setAlignment(Qt.AlignCenter)
        title_lbl.setStyleSheet(f"color:{err};background:transparent;border:none;")
        content.addWidget(title_lbl)

        # Optional "cannot be undone" subtitle
        if irreversible:
            irrev_lbl = QLabel(t("dialog.irreversible", default="This action cannot be undone"))
            irrev_lbl.setFont(font(11))
            irrev_lbl.setAlignment(Qt.AlignCenter)
            irrev_lbl.setStyleSheet(
                f"color:{COLORS['text_secondary']};background:transparent;border:none;"
            )
            content.addWidget(irrev_lbl)

        content.addSpacing(4)

        # Message card — subtle red-tinted border so it still reads as danger
        msg_card = QFrame()
        msg_card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['card_bg']};
                border-radius: 10px;
                border: 1px solid {err}44;
            }}
        """)
        msg_inner = QVBoxLayout(msg_card)
        msg_inner.setContentsMargins(18, 12, 18, 12)

        msg_lbl = QLabel(message)
        msg_lbl.setFont(font(13))
        msg_lbl.setAlignment(Qt.AlignCenter)
        msg_lbl.setWordWrap(True)
        msg_lbl.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;"
        )
        msg_inner.addWidget(msg_lbl)
        content.addWidget(msg_card)

        content.addSpacing(2)

        # Button row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        cancel_btn = GhostButton(cancel_text, font_size=14)
        cancel_btn.setMinimumHeight(42)
        cancel_btn.clicked.connect(self._on_cancel)

        # Solid red confirm — explicit stylesheet so :pressed stays dark-red,
        # not the global accent_dim (orange).
        confirm_btn = QPushButton(confirm_text)
        confirm_btn.setFont(font(14, "bold"))
        confirm_btn.setMinimumHeight(42)
        confirm_btn.setCursor(Qt.PointingHandCursor)
        confirm_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {err};
                color: #ffffff;
                border-radius: 8px;
                border: none;
                padding: 8px 24px;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {err_h};
            }}
            QPushButton:pressed {{
                background-color: {err_dim};
            }}
            QPushButton:disabled {{
                background-color: {COLORS['border']};
                color: {COLORS['text_muted']};
            }}
        """)
        confirm_btn.clicked.connect(self._on_confirm)

        btn_row.addWidget(cancel_btn, 1)
        btn_row.addWidget(confirm_btn, 1)
        content.addLayout(btn_row)

        root.addLayout(content)

        # default focus → cancel (safe default for destructive actions)
        cancel_btn.setFocus()


    def _on_confirm(self):
        print(f"[DEBUG] _on_confirm() called")
        self.result = True
        self.accept()

    def _on_cancel(self):
        print(f"[DEBUG] _on_cancel() called")
        self.result = False
        self.reject()

    def keyPressEvent(self, event):
        print(f"[DEBUG] keyPressEvent() called")
        if event.key() == Qt.Key_Escape:
            self._on_cancel()
        super().keyPressEvent(event)

    def showEvent(self, event):
        print(f"[DEBUG] showEvent() called")
        # _card carries a QGraphicsDropShadowEffect for the red glow, so
        # fade_in() would detect it and return early (no animation).
        # Animate the window-level opacity instead — this coexists with any
        # QGraphicsEffect already applied to child widgets.
        self.setWindowOpacity(0.0)
        anim = QPropertyAnimation(self, b"windowOpacity", self)
        anim.setDuration(220)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start(QPropertyAnimation.DeleteWhenStopped)
        super().showEvent(event)

    def show_and_get(self) -> bool:
        print(f"[DEBUG] show_and_get() called")
        self.exec()
        return self.result


# STANDARD  CONFIRMATION  DIALOG  (non-danger)

class ConfirmationDialog(_BaseDialog):

    def __init__(
        self,
        parent: QWidget,
        title: str,
        message: str,
        colors: dict,
        confirm_text: Optional[str] = None,
        cancel_text:  Optional[str] = None,
        icon: str = "❓",
        danger: bool = False,
    ):
        # Route destructive requests to the purpose-built danger dialog.
        # We store the result on self so show_and_get() can return it.
        if confirm_text is None:
            confirm_text = t("dialog.yes", default="Yes")
        if cancel_text is None:
            cancel_text = t("dialog.no", default="No")

        if danger:
            self._delegate = DangerConfirmationDialog(
                parent, title, message, colors,
                confirm_text=confirm_text,
                cancel_text=cancel_text,
                icon=icon,
            )
            # Skip _BaseDialog.__init__ — we never show this shell.
            self.result = False
            return

        self._delegate    = None
        self._message      = message
        self._confirm_text = confirm_text
        self._cancel_text  = cancel_text
        self._icon         = icon
        self._danger       = False
        self.result        = False
        super().__init__(parent, title, 520, 320)

    def _build_content(self, title: str):
        print(f"[DEBUG] _build_content() called")
        # icon
        icon_lbl = QLabel(self._icon)
        icon_lbl.setFont(font(44))
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("background:transparent;border:none;")
        self._root.addWidget(icon_lbl)

        # title
        title_lbl = QLabel(title)
        title_lbl.setFont(font(20, "bold"))
        title_lbl.setAlignment(Qt.AlignCenter)
        title_lbl.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;"
        )
        self._root.addWidget(title_lbl)

        # message card
        msg_card = QFrame()
        msg_card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['card_bg']};
                border-radius: 10px;
                border: 1px solid {COLORS['border']};
            }}
        """)
        msg_inner = QVBoxLayout(msg_card)
        msg_inner.setContentsMargins(20, 16, 20, 16)
        msg_lbl = QLabel(self._message)
        msg_lbl.setFont(font(13))
        msg_lbl.setAlignment(Qt.AlignCenter)
        msg_lbl.setWordWrap(True)
        msg_lbl.setStyleSheet(f"color:{COLORS['text']};background:transparent;")
        msg_inner.addWidget(msg_lbl)
        self._root.addWidget(msg_card)

        # buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        cancel_btn = GhostButton(self._cancel_text, font_size=14)
        cancel_btn.setMinimumHeight(42)
        cancel_btn.clicked.connect(self._on_cancel)

        confirm_btn = AnimButton(
            self._confirm_text,
            fg=COLORS["accent"], fg_hover=COLORS["accent_hover"],
            font_size=14, bold=True, padding="8px 24px",
        )
        confirm_btn.setMinimumHeight(42)
        confirm_btn.clicked.connect(self._on_confirm)

        btn_row.addWidget(cancel_btn, 1)
        btn_row.addWidget(confirm_btn, 1)
        self._root.addLayout(btn_row)

        confirm_btn.setFocus()

    def _on_confirm(self):
        print(f"[DEBUG] _on_confirm() called")
        self.result = True
        self.accept()

    def _on_cancel(self):
        print(f"[DEBUG] _on_cancel() called")
        self.result = False
        self.reject()

    def keyPressEvent(self, event):
        print(f"[DEBUG] keyPressEvent() called")
        if event.key() == Qt.Key_Escape:
            self._on_cancel()
        super().keyPressEvent(event)

    def show_and_get(self) -> bool:
        print(f"[DEBUG] show_and_get() called")
        # If we delegated to DangerConfirmationDialog, run that instead.
        if self._delegate is not None:
            return self._delegate.show_and_get()
        self.exec()
        return self.result


# INFO  DIALOG  (OK only)

class InfoDialog(_BaseDialog):

    def __init__(
        self,
        parent: QWidget,
        title: str,
        message: str,
        colors: dict,
        button_text: Optional[str] = None,
        icon: str = "ℹ️",
        type: str = "info",
    ):
        self._message     = message
        self._button_text = button_text if button_text is not None else t("dialog.ok", default="OK")
        self._icon        = icon
        self._type        = type
        super().__init__(parent, title, 520, 300)

    def _build_content(self, title: str):
        print(f"[DEBUG] _build_content() called")
        type_color_map = {
            "error":   COLORS["error"],
            "warning": COLORS["warning"],
            "success": COLORS["success"],
            "info":    COLORS["text"],
        }
        title_color = type_color_map.get(self._type, COLORS["text"])

        icon_lbl = QLabel(self._icon)
        icon_lbl.setFont(font(44))
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("background:transparent;border:none;")
        self._root.addWidget(icon_lbl)

        title_lbl = QLabel(title)
        title_lbl.setFont(font(20, "bold"))
        title_lbl.setAlignment(Qt.AlignCenter)
        title_lbl.setStyleSheet(f"color:{title_color};background:transparent;border:none;")
        self._root.addWidget(title_lbl)

        msg_card = QFrame()
        msg_card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['card_bg']};
                border-radius: 10px;
                border: 1px solid {COLORS['border']};
            }}
        """)
        msg_inner = QVBoxLayout(msg_card)
        msg_inner.setContentsMargins(20, 14, 20, 14)
        msg_lbl = QLabel(self._message)
        msg_lbl.setFont(font(13))
        msg_lbl.setAlignment(Qt.AlignCenter)
        msg_lbl.setWordWrap(True)
        msg_lbl.setStyleSheet(f"color:{COLORS['text']};background:transparent;")
        msg_inner.addWidget(msg_lbl)
        self._root.addWidget(msg_card)

        ok_btn = AnimButton(
            self._button_text,
            fg=COLORS["accent"], fg_hover=COLORS["accent_hover"],
            font_size=14, bold=True,
        )
        ok_btn.setMinimumHeight(42)
        ok_btn.clicked.connect(self.accept)
        self._root.addWidget(ok_btn)
        ok_btn.setFocus()

    def keyPressEvent(self, event):
        print(f"[DEBUG] keyPressEvent() called")
        if event.key() in (Qt.Key_Escape, Qt.Key_Return):
            self.accept()
        super().keyPressEvent(event)


# PUBLIC  HELPER  FUNCTIONS  (same signatures as ctk originals)

def askyesno(parent, title: str, message: str, colors: dict,
             icon: str = "❓", danger: bool = False) -> bool:
    yes = t("dialog.yes", default="Yes")
    no  = t("dialog.no",  default="No")
    if danger:
        d = DangerConfirmationDialog(parent, title, message, colors,
                                     confirm_text=yes, cancel_text=no,
                                     icon=icon)
    else:
        d = ConfirmationDialog(parent, title, message, colors,
                               confirm_text=yes, cancel_text=no,
                               icon=icon, danger=False)
    return d.show_and_get()


def askokcancel(parent, title: str, message: str, colors: dict,
                icon: str = "❓", danger: bool = False) -> bool:
    ok     = t("dialog.ok",     default="OK")
    cancel = t("dialog.cancel", default="Cancel")
    if danger:
        d = DangerConfirmationDialog(parent, title, message, colors,
                                     confirm_text=ok, cancel_text=cancel,
                                     icon=icon)
    else:
        d = ConfirmationDialog(parent, title, message, colors,
                               confirm_text=ok, cancel_text=cancel,
                               icon=icon, danger=False)
    return d.show_and_get()


def showinfo(parent, title: str, message: str, colors: dict, icon: str = "ℹ️"):
    InfoDialog(parent, title, message, colors, icon=icon, type="info").exec()


def showwarning(parent, title: str, message: str, colors: dict, icon: str = "⚠️"):
    InfoDialog(parent, title, message, colors, icon=icon, type="warning").exec()


def showerror(parent, title: str, message: str, colors: dict, icon: str = "❌"):
    InfoDialog(parent, title, message, colors, icon=icon, type="error").exec()


def showsuccess(parent, title: str, message: str, colors: dict, icon: str = "✅"):
    InfoDialog(parent, title, message, colors, icon=icon, type="success").exec()


