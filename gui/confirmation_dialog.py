from __future__ import annotations
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QWidget

from gui.theme import COLORS
from gui.components.dialog_kit import (
    DialogShell, make_panel, body_label, primary_button, outline_button,
    danger_button, icon_badge,
)

try:
    from core.localization import t
except ImportError as _exc:
    print(f"[DEBUG] confirmation_dialog.py: import failed ({_exc}), using fallback")
    def t(key, **kw):
        return kw.get("default", key)


class _MessageDialog(DialogShell):

    def __init__(self, parent: QWidget, title: str, message: str, icon: str,
                 accent: str | None = None, subtitle: str = "",
                 width: int = 480):
        super().__init__(parent, title, width, icon="", accent=accent, subtitle=subtitle)
        self.result = False

        panel, lay = make_panel("msgPanel", margins=(16, 14, 16, 14), spacing=0)
        row = QHBoxLayout()
        row.setSpacing(14)
        row.addWidget(icon_badge(icon, accent), 0, Qt.AlignTop)
        msg = body_label(message, secondary=False, size=13)
        row.addWidget(msg, 1)
        lay.addLayout(row)
        self.body.addWidget(panel)

    def _on_confirm(self):
        self.result = True
        self.accept()

    def _on_cancel(self):
        self.result = False
        self.reject()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._on_cancel()
            return
        super().keyPressEvent(event)

    def show_and_get(self) -> bool:
        self.exec()
        return self.result


class DangerConfirmationDialog(_MessageDialog):
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
        confirm_text = confirm_text or t("dialog.yes", default="Yes")
        cancel_text  = cancel_text  or t("dialog.no",  default="No")
        super().__init__(
            parent, title, message, icon, accent=COLORS["error"],
            subtitle=t("dialog.irreversible", default="This action cannot be undone")
            if irreversible else "",
        )
        cancel_btn  = outline_button(cancel_text)
        confirm_btn = danger_button(confirm_text)
        cancel_btn.clicked.connect(self._on_cancel)
        confirm_btn.clicked.connect(self._on_confirm)
        self.footer.addWidget(cancel_btn, 1)
        self.footer.addWidget(confirm_btn, 1)
        self.add_footer()
        cancel_btn.setFocus()


class ConfirmationDialog(_MessageDialog):
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
        confirm_text = confirm_text or t("dialog.yes", default="Yes")
        cancel_text  = cancel_text  or t("dialog.no",  default="No")
        self._danger = danger
        accent = COLORS["error"] if danger else None
        super().__init__(parent, title, message, icon, accent=accent)

        cancel_btn  = outline_button(cancel_text)
        confirm_btn = danger_button(confirm_text) if danger else primary_button(confirm_text)
        cancel_btn.clicked.connect(self._on_cancel)
        confirm_btn.clicked.connect(self._on_confirm)
        self.footer.addWidget(cancel_btn, 1)
        self.footer.addWidget(confirm_btn, 1)
        self.add_footer()
        (cancel_btn if danger else confirm_btn).setFocus()


class InfoDialog(_MessageDialog):
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
        accent = {
            "error":   COLORS["error"],
            "warning": COLORS["warning"],
            "success": COLORS["success"],
        }.get(type)
        super().__init__(parent, title, message, icon, accent=accent)
        self._type = type

        ok_btn = primary_button(button_text or t("dialog.ok", default="OK"))
        ok_btn.clicked.connect(self.accept)
        self.footer.addStretch(1)
        self.footer.addWidget(ok_btn, 2)
        self.footer.addStretch(1)
        self.add_footer()
        ok_btn.setFocus()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Escape, Qt.Key_Return, Qt.Key_Enter):
            self.accept()
            return
        super().keyPressEvent(event)


def askyesno(parent, title: str, message: str, colors: dict,
             icon: str = "❓", danger: bool = False) -> bool:
    yes = t("dialog.yes", default="Yes")
    no  = t("dialog.no",  default="No")
    if danger:
        d = DangerConfirmationDialog(parent, title, message, colors,
                                     confirm_text=yes, cancel_text=no, icon=icon)
    else:
        d = ConfirmationDialog(parent, title, message, colors,
                               confirm_text=yes, cancel_text=no, icon=icon)
    return d.show_and_get()


def askokcancel(parent, title: str, message: str, colors: dict,
                icon: str = "❓", danger: bool = False) -> bool:
    ok     = t("dialog.ok",     default="OK")
    cancel = t("dialog.cancel", default="Cancel")
    if danger:
        d = DangerConfirmationDialog(parent, title, message, colors,
                                     confirm_text=ok, cancel_text=cancel, icon=icon)
    else:
        d = ConfirmationDialog(parent, title, message, colors,
                               confirm_text=ok, cancel_text=cancel, icon=icon)
    return d.show_and_get()


def showinfo(parent, title: str, message: str, colors: dict, icon: str = "ℹ️"):
    InfoDialog(parent, title, message, colors, icon=icon, type="info").exec()


def showwarning(parent, title: str, message: str, colors: dict, icon: str = "⚠️"):
    InfoDialog(parent, title, message, colors, icon=icon, type="warning").exec()


def showerror(parent, title: str, message: str, colors: dict, icon: str = "❌"):
    InfoDialog(parent, title, message, colors, icon=icon, type="error").exec()


def showsuccess(parent, title: str, message: str, colors: dict, icon: str = "✅"):
    InfoDialog(parent, title, message, colors, icon=icon, type="success").exec()
