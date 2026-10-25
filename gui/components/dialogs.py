from __future__ import annotations
from typing import Callable, Optional

from PySide6.QtCore    import Qt, QTimer
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtWidgets import QLabel, QWidget

from gui.theme   import COLORS, font
from gui.widgets import Toast
from gui.components.dialog_kit import (
    DialogShell, make_panel, make_scroll, make_checkbox, primary_button,
    lbl_qss,
)

try:
    from core.localization import t
except ImportError as e:
    print(f"[DEBUG] dialogs.py: localization import failed ({e}), using fallback")
    def t(key, **kw): return kw.get('default', key)


def run_startup_sequence(
    parent: QWidget,
    show_offline_dialog_fn: Optional[Callable] = None,
) -> None:
    def _step0_wip():
        try:
            show_wip_warning(parent)
        except Exception as e:
            print(f"[ERROR] show_wip_warning raised: {e}")
        QTimer.singleShot(100, _step1_update_check)

    def _step1_update_check():
        try:
            from core.updater import check_for_updates
            check_for_updates(on_done=_step2_changelog)
        except Exception as e:
            print(f"[ERROR] check_for_updates raised: {e}")
            QTimer.singleShot(100, _step2_changelog)

    def _step2_changelog():
        try:
            from gui.components.changelog_dialog import show_changelog_if_needed
            from core.updater import CURRENT_VERSION
            show_changelog_if_needed(parent, CURRENT_VERSION)
        except Exception as e:
            print(f"[ERROR] show_changelog_if_needed raised: {e}")
        QTimer.singleShot(100, _step3_offline)

    def _step3_offline():
        try:
            from utils import connection as _conn
            if not _conn.is_online:
                print("[DEBUG] run_startup_sequence: offline detected")
                if show_offline_dialog_fn:
                    show_offline_dialog_fn()
        except Exception as e:
            print(f"[DEBUG] run_startup_sequence: offline check skipped: {e}")

    QTimer.singleShot(200, _step0_wip)


def show_notification(
    parent: QWidget,
    message: str,
    type: str = "info",
    duration: int = 3000,
) -> None:
    cw = (parent.centralWidget() or parent
          if hasattr(parent, "centralWidget") else parent)

    toast = Toast(cw, message, kind=type, duration=duration)

    x = cw.width()  - toast.width()  - 20
    y = cw.height() - toast.height() - 20
    toast.move(x, y)
    toast.show()
    toast.raise_()


def show_wip_warning(parent: QWidget) -> None:
    try:
        from gui.state import state
        first_launch = state.app_settings.get("first_launch", True)
    except Exception as e:
        first_launch = True
        print(f"[DEBUG] show_wip_warning: could not load state ({e}), defaulting first_launch=True")

    if not first_launch:
        return

    dlg = DialogShell(
        parent,
        t("wip.wip_warning_title", default="Work-In-Progress Software"),
        560, icon="⚠️",
        accent=COLORS.get("warning", COLORS["accent"]),
        escape_closes=False,
    )

    panel, p_lay = make_panel("wipPanel", margins=(0, 0, 0, 0), spacing=0)
    inner = QWidget()
    inner_lay = QVBoxLayout(inner)
    inner_lay.setContentsMargins(18, 14, 18, 14)

    msg_text = t("wip.wip_warning_message", default=(
        "Welcome to BeamSkin Studio!\n"
        "This application is currently in active development.\n"
        "While I strive to provide a stable experience, some features may not work.\n\n"
        "Please note:\n"
        "  • Some features may be incomplete\n"
        "  • Occasional bugs or unexpected behaviour may occur\n"
        "  • Updates and improvements are being made regularly\n\n"
        "Your feedback helps improve the software!\n"
        "If you encounter any issues, please report them on the GitHub page.\n"
        "Bug reports and feature suggestions are valuable for making\n"
        "BeamSkin Studio better!\n\n"
        "I appreciate your understanding and support as I continue\n"
        "to enhance BeamSkin Studio."
    ))
    msg_lbl = QLabel(msg_text)
    msg_lbl.setFont(font(12))
    msg_lbl.setWordWrap(True)
    msg_lbl.setAlignment(Qt.AlignLeft | Qt.AlignTop)
    msg_lbl.setStyleSheet(lbl_qss())
    inner_lay.addWidget(msg_lbl)

    scroll = make_scroll(inner)
    scroll.setFixedHeight(280)
    p_lay.addWidget(scroll)
    dlg.body.addWidget(panel)

    chk = make_checkbox(t("wip.wip_dont_show", default="Don't show this message again"))
    dlg.body.addWidget(chk, alignment=Qt.AlignCenter)

    def _on_ok():
        if chk.isChecked():
            try:
                from gui.state import state
                from core.settings import save_settings
                state.app_settings["first_launch"] = False
                save_settings()
            except Exception as e:
                print(f"[DEBUG] show_wip_warning: could not save first_launch setting: {e}")
        dlg.accept()

    ok_btn = primary_button(t("wip.wip_understand", default="I Understand"), height=42, font_size=14)
    ok_btn.clicked.connect(_on_ok)
    dlg.footer.addWidget(ok_btn, 1)
    dlg.add_footer()
    ok_btn.setFocus()

    dlg.exec()
