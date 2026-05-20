from __future__ import annotations
from typing import Callable, Optional

from PySide6.QtCore    import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QWidget,
    QCheckBox, QPushButton, QScrollArea, QSizePolicy,
)

from gui.theme   import COLORS, font, drop_shadow, fade_in
from gui.widgets import AnimButton, GhostButton, Toast
from gui.icon_helper import set_window_icon

try:
    from core.localization import t
    print("[DEBUG] dialogs.py: localization imported successfully")
except ImportError as e:
    print(f"[DEBUG] dialogs.py: localization import failed ({e}), using fallback")
    def t(key, **kw): return kw.get('default', key)


### Startup sequence

def run_startup_sequence(
    parent: QWidget,
    show_offline_dialog_fn: Optional[Callable] = None,
) -> None:
    print(f"[DEBUG] run_startup_sequence: called, parent={parent}, offline_fn={show_offline_dialog_fn}")

    def _step0_wip():
        print("[DEBUG] run_startup_sequence: _step0_wip starting")
        try:
            show_wip_warning(parent)
            print("[DEBUG] run_startup_sequence: _step0_wip completed")
        except Exception as e:
            print(f"[ERROR] show_wip_warning raised: {e}")
        print("[DEBUG] run_startup_sequence: scheduling _step0b_discord in 100ms")
        QTimer.singleShot(100, _step0b_discord)

    def _step0b_discord():
        print("[DEBUG] run_startup_sequence: _step0b_discord starting")
        try:
            show_discord_notice(parent)
            print("[DEBUG] run_startup_sequence: _step0b_discord completed")
        except Exception as e:
            print(f"[ERROR] show_discord_notice raised: {e}")
        print("[DEBUG] run_startup_sequence: scheduling _step1_update_check in 100ms")
        QTimer.singleShot(100, _step1_update_check)

    def _step1_update_check():
        print("[DEBUG] run_startup_sequence: _step1_update_check starting")
        try:
            from core.updater import check_for_updates
            print("[DEBUG] run_startup_sequence: check_for_updates imported, calling now")
            check_for_updates(on_done=_step2_changelog)
            print("[DEBUG] run_startup_sequence: check_for_updates dispatched")
        except Exception as e:
            print(f"[ERROR] check_for_updates raised: {e}")
            print("[DEBUG] run_startup_sequence: falling through to _step2_changelog after updater error")
            QTimer.singleShot(100, _step2_changelog)

    def _step2_changelog():
        print("[DEBUG] run_startup_sequence: _step2_changelog starting")
        try:
            from gui.components.changelog_dialog import show_changelog_if_needed
            from core.updater import CURRENT_VERSION
            print(f"[DEBUG] run_startup_sequence: CURRENT_VERSION={CURRENT_VERSION}")
            show_changelog_if_needed(parent, CURRENT_VERSION)
            print("[DEBUG] run_startup_sequence: show_changelog_if_needed completed")
        except Exception as e:
            print(f"[ERROR] show_changelog_if_needed raised: {e}")
        print("[DEBUG] run_startup_sequence: scheduling _step3_offline in 100ms")
        QTimer.singleShot(100, _step3_offline)

    def _step3_offline():
        print("[DEBUG] run_startup_sequence: _step3_offline starting")
        try:
            from utils import connection as _conn
            is_online = _conn.is_online
            print(f"[DEBUG] run_startup_sequence: connection.is_online={is_online}")
            if not is_online:
                print("[DEBUG] run_startup_sequence: offline detected, calling show_offline_dialog_fn")
                if show_offline_dialog_fn:
                    show_offline_dialog_fn()
                else:
                    print("[DEBUG] run_startup_sequence: no offline_dialog_fn provided, skipping")
            else:
                print("[DEBUG] run_startup_sequence: online, skipping offline dialog")
        except Exception as e:
            print(f"[DEBUG] run_startup_sequence: offline check skipped: {e}")

    print("[DEBUG] run_startup_sequence: scheduling _step0_wip in 200ms")
    QTimer.singleShot(200, _step0_wip)


### Toast notification shim

def show_notification(
    parent: QWidget,
    message: str,
    type: str = "info",
    duration: int = 3000,
) -> None:
    print(f"[DEBUG] show_notification: message={message!r}, type={type}, duration={duration}")
    print(f"[DEBUG] show_notification: parent={parent}, has centralWidget={hasattr(parent, 'centralWidget')}")

    cw = (parent.centralWidget() or parent
          if hasattr(parent, "centralWidget") else parent)
    print(f"[DEBUG] show_notification: resolved container widget={cw}")

    toast = Toast(cw, message, kind=type, duration=duration)
    print(f"[DEBUG] show_notification: Toast created, size={toast.width()}x{toast.height()}")

    x = cw.width()  - toast.width()  - 20
    y = cw.height() - toast.height() - 20
    print(f"[DEBUG] show_notification: positioning toast at ({x}, {y}), container size={cw.width()}x{cw.height()}")
    toast.move(x, y)
    toast.show()
    toast.raise_()
    print("[DEBUG] show_notification: toast shown and raised")


### WIP warning dialog

def show_wip_warning(parent: QWidget) -> None:
    print("\n[DEBUG] ========== WIP WARNING CHECK ==========")

    try:
        from gui.state import state
        first_launch = state.app_settings.get("first_launch", True)
        print(f"[DEBUG] show_wip_warning: app_settings loaded, first_launch={first_launch}")
    except Exception as e:
        first_launch = True
        print(f"[DEBUG] show_wip_warning: could not load state ({e}), defaulting first_launch=True")

    if not first_launch:
        print("[DEBUG] show_wip_warning: not first launch — skipping")
        print("[DEBUG] ========== WIP WARNING SKIPPED ==========\n")
        return

    print("[DEBUG] show_wip_warning: first launch confirmed — building dialog")

    ### Dialog shell
    dlg = QDialog(parent)
    dlg.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
    dlg.setModal(True)
    dlg.setFixedWidth(560)
    dlg.setStyleSheet(f"""
        QDialog {{
            background: {COLORS['frame_bg']};
            border: 1px solid {COLORS['border']};
            border-radius: 14px;
        }}
    """)
    print(f"[DEBUG] show_wip_warning: dialog created, width=560, modal=True, frameless")

    root = QVBoxLayout(dlg)
    root.setContentsMargins(24, 24, 24, 24)
    root.setSpacing(16)

    ### Icon + title
    icon_lbl = QLabel("⚠️")
    icon_lbl.setFont(font(42))
    icon_lbl.setAlignment(Qt.AlignCenter)
    icon_lbl.setStyleSheet("background: transparent; border: none;")
    root.addWidget(icon_lbl)

    title_text = t("wip.wip_warning_title", default="Work-In-Progress Software")
    print(f"[DEBUG] show_wip_warning: title text={title_text!r}")
    title_lbl = QLabel(title_text)
    title_lbl.setFont(font(18, "bold"))
    title_lbl.setAlignment(Qt.AlignCenter)
    title_lbl.setStyleSheet(f"color: {COLORS['text']}; background: transparent; border: none;")
    root.addWidget(title_lbl)

    ### Scrollable message card
    card = QFrame()
    card.setStyleSheet(f"""
        QFrame {{
            background: {COLORS['card_bg']};
            border-radius: 12px;
            border: 1px solid {COLORS['border']};
        }}
    """)
    card_lay = QVBoxLayout(card)
    card_lay.setContentsMargins(20, 16, 20, 16)

    scroll = QScrollArea()
    scroll.setWidget(card)
    scroll.setWidgetResizable(True)
    scroll.setFixedHeight(300)
    scroll.setStyleSheet("""
        QScrollArea { border: none; background: transparent; }
        QScrollBar:vertical {
            background: transparent; width: 6px; margin: 0;
        }
        QScrollBar::handle:vertical {
            background: rgba(255,255,255,0.15); border-radius: 3px; min-height: 20px;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
    """)

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
    print(f"[DEBUG] show_wip_warning: message text length={len(msg_text)} chars")
    msg_lbl = QLabel(msg_text)
    msg_lbl.setFont(font(13))
    msg_lbl.setWordWrap(True)
    msg_lbl.setAlignment(Qt.AlignLeft | Qt.AlignTop)
    msg_lbl.setStyleSheet(
        f"color: {COLORS['text']}; background: transparent; border: none; line-height: 1.5;"
    )
    card_lay.addWidget(msg_lbl)
    root.addWidget(scroll)

    ### Don't show again checkbox
    chk_text = t("wip.wip_dont_show", default="Don't show this message again")
    print(f"[DEBUG] show_wip_warning: checkbox label={chk_text!r}")
    chk = QCheckBox(chk_text)
    chk.setFont(font(12))
    chk.setStyleSheet(f"""
        QCheckBox {{
            color: {COLORS['text_secondary']};
            background: transparent;
            spacing: 8px;
        }}
        QCheckBox::indicator {{
            width: 16px; height: 16px;
            border: 1px solid {COLORS['border']};
            border-radius: 4px;
            background: {COLORS['frame_bg']};
        }}
        QCheckBox::indicator:checked {{
            background: {COLORS['accent']};
            border-color: {COLORS['accent']};
        }}
    """)
    root.addWidget(chk, alignment=Qt.AlignCenter)

    ### I Understand button
    ok_btn = QPushButton(t("wip.wip_understand", default="I Understand"))
    ok_btn.setFont(font(13, "bold"))
    ok_btn.setFixedHeight(44)
    ok_btn.setFixedWidth(200)
    ok_btn.setCursor(Qt.PointingHandCursor)
    ok_btn.setStyleSheet(f"""
        QPushButton {{
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 {COLORS['accent']},
                stop:1 {COLORS.get('accent_hover', COLORS['accent'])});
            color: white;
            border: none;
            border-radius: 10px;
        }}
        QPushButton:hover {{
            background: {COLORS.get('accent_hover', COLORS['accent'])};
        }}
        QPushButton:pressed {{
            background: {COLORS.get('accent_dim', COLORS['accent'])};
        }}
    """)

    def _on_ok():
        print("[DEBUG] show_wip_warning: user clicked 'I Understand'")
        print(f"[DEBUG] show_wip_warning: dont_show_again checked={chk.isChecked()}")
        if chk.isChecked():
            try:
                from gui.state import state
                from core.settings import save_settings
                print("[DEBUG] show_wip_warning: saving first_launch=False to settings")
                state.app_settings["first_launch"] = False
                save_settings()
                print("[DEBUG] show_wip_warning: first_launch=False saved successfully")
            except Exception as e:
                print(f"[DEBUG] show_wip_warning: could not save setting: {e}")
        else:
            print("[DEBUG] show_wip_warning: dont_show_again not checked, first_launch unchanged")
        print("[DEBUG] show_wip_warning: accepting dialog")
        dlg.accept()

    ok_btn.clicked.connect(_on_ok)
    root.addWidget(ok_btn, alignment=Qt.AlignCenter)

    # Block Escape — the button is the only way to dismiss this dialog.
    dlg.keyPressEvent = lambda e: None

    dlg.adjustSize()
    set_window_icon(dlg)
    print(f"[DEBUG] show_wip_warning: dialog adjusted size={dlg.width()}x{dlg.height()}")

    ### Centre on parent
    if parent and parent.isVisible():
        pg = parent.geometry()
        x = pg.x() + (pg.width()  - dlg.width())  // 2
        y = pg.y() + (pg.height() - dlg.height()) // 2
        print(f"[DEBUG] show_wip_warning: centering on parent geometry={pg}, dialog pos=({x},{y})")
        dlg.move(x, y)
    else:
        print(f"[DEBUG] show_wip_warning: parent not visible or None, skipping centering")

    print("[DEBUG] show_wip_warning: executing dialog — blocking until user responds")
    result = dlg.exec()
    print(f"[DEBUG] show_wip_warning: dialog closed, result={result}")
    print("[DEBUG] ========== WIP WARNING COMPLETE ==========\n")


### Discord notice dialog

DISCORD_URL = "https://discord.gg/mbr3YxZzrr"
_OK_DELAY_MS = 15_000   # 15 seconds before OK becomes clickable


def show_discord_notice(parent: QWidget) -> None:

    import webbrowser

    print("\n[DEBUG] ========== DISCORD NOTICE CHECK ==========")

    try:
        from gui.state import state
        already_shown = state.app_settings.get("discord_notice_shown", False)
        print(f"[DEBUG] show_discord_notice: discord_notice_shown={already_shown}")
    except Exception as e:
        already_shown = False
        print(f"[DEBUG] show_discord_notice: could not load state ({e}), defaulting to show")

    if already_shown:
        print("[DEBUG] show_discord_notice: already shown — skipping")
        print("[DEBUG] ========== DISCORD NOTICE SKIPPED ==========\n")
        return

    print("[DEBUG] show_discord_notice: first time — building dialog")

    # ── Dialog shell ──────────────────────────────────────────────────────────
    dlg = QDialog(parent)
    dlg.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
    dlg.setModal(True)
    dlg.setFixedWidth(580)
    dlg.setStyleSheet(f"""
        QDialog {{
            background: {COLORS['frame_bg']};
            border: 1px solid {COLORS['border']};
            border-radius: 14px;
        }}
    """)

    root = QVBoxLayout(dlg)
    root.setContentsMargins(28, 28, 28, 28)
    root.setSpacing(18)

    # ── Icon + title row ──────────────────────────────────────────────────────
    icon_lbl = QLabel("📢")
    icon_lbl.setFont(font(44))
    icon_lbl.setAlignment(Qt.AlignCenter)
    icon_lbl.setStyleSheet("background: transparent; border: none;")
    root.addWidget(icon_lbl)

    title_lbl = QLabel("Important Notice from the Developer")
    title_lbl.setFont(font(17, "bold"))
    title_lbl.setAlignment(Qt.AlignCenter)
    title_lbl.setWordWrap(True)
    title_lbl.setStyleSheet(
        f"color: {COLORS['text']}; background: transparent; border: none;"
    )
    root.addWidget(title_lbl)

    # ── Message card ──────────────────────────────────────────────────────────
    card = QFrame()
    card.setStyleSheet(f"""
        QFrame {{
            background: {COLORS['card_bg']};
            border-radius: 12px;
            border: 1px solid {COLORS['border']};
        }}
    """)
    card_lay = QVBoxLayout(card)
    card_lay.setContentsMargins(20, 18, 20, 18)
    card_lay.setSpacing(10)

    msg_text = (
        "I have been wrongfully banned and removed from the official "
        "BeamNG.Drive Discord server.\n\n"
        "Because of this, I am no longer able to provide support, share "
        "development updates, or stay in contact with the community through "
        "that server.\n\n"
        "If you want to:\n"
        "  •  Stay up to date with BeamSkin Studio development\n"
        "  •  Get help with issues or questions\n"
        "  •  Give feedback or report bugs\n"
        "  •  Connect directly with me\n\n"
        "Please join the official BeamSkin Studio Discord server using the "
        "button below. It is the only place where I can guarantee support "
        "and direct communication going forward.\n\n"
        "Thank you for your understanding and continued support! ❤️\n"
        "— Burzt"
    )

    msg_lbl = QLabel(msg_text)
    msg_lbl.setFont(font(13))
    msg_lbl.setWordWrap(True)
    msg_lbl.setAlignment(Qt.AlignLeft | Qt.AlignTop)
    msg_lbl.setStyleSheet(
        f"color: {COLORS['text']}; background: transparent; border: none;"
    )
    card_lay.addWidget(msg_lbl)

    scroll = QScrollArea()
    scroll.setWidget(card)
    scroll.setWidgetResizable(True)
    scroll.setFixedHeight(280)
    scroll.setStyleSheet("""
        QScrollArea { border: none; background: transparent; }
        QScrollBar:vertical {
            background: transparent; width: 6px; margin: 0;
        }
        QScrollBar::handle:vertical {
            background: rgba(255,255,255,0.15); border-radius: 3px; min-height: 20px;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
    """)
    root.addWidget(scroll)

    # ── Button row ────────────────────────────────────────────────────────────
    btn_row = QHBoxLayout()
    btn_row.setSpacing(12)

    # "Join Discord" — always clickable
    join_btn = QPushButton("Join the BeamSkin Studio Discord Server")
    join_btn.setFont(font(13, "bold"))
    join_btn.setFixedHeight(44)
    join_btn.setCursor(Qt.PointingHandCursor)
    join_btn.setStyleSheet(f"""
        QPushButton {{
            background: #5865F2;
            color: white;
            border: none;
            border-radius: 10px;
            padding: 0 18px;
        }}
        QPushButton:hover  {{ background: #4752C4; }}
        QPushButton:pressed {{ background: #3C45A5; }}
    """)
    join_btn.clicked.connect(lambda: webbrowser.open(DISCORD_URL))
    btn_row.addWidget(join_btn)

    # "OK" — locked for _OK_DELAY_MS milliseconds
    ok_btn = QPushButton("OK  (15)")
    ok_btn.setFont(font(13, "bold"))
    ok_btn.setFixedHeight(44)
    ok_btn.setFixedWidth(110)
    ok_btn.setEnabled(False)
    ok_btn.setCursor(Qt.ForbiddenCursor)

    _locked_style = f"""
        QPushButton {{
            background: {COLORS.get('card_bg', '#2a2a2a')};
            color: {COLORS.get('text_secondary', '#888888')};
            border: 1px solid {COLORS['border']};
            border-radius: 10px;
        }}
    """
    _unlocked_style = f"""
        QPushButton {{
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 {COLORS['accent']},
                stop:1 {COLORS.get('accent_hover', COLORS['accent'])});
            color: white;
            border: none;
            border-radius: 10px;
        }}
        QPushButton:hover  {{ background: {COLORS.get('accent_hover', COLORS['accent'])}; }}
        QPushButton:pressed {{ background: {COLORS.get('accent_dim',   COLORS['accent'])}; }}
    """
    ok_btn.setStyleSheet(_locked_style)
    btn_row.addWidget(ok_btn)

    root.addLayout(btn_row)

    # ── Countdown timer ───────────────────────────────────────────────────────
    _remaining = [_OK_DELAY_MS // 1000]   # mutable cell for the closure

    def _tick():
        _remaining[0] -= 1
        if _remaining[0] > 0:
            ok_btn.setText(f"OK  ({_remaining[0]})")
        else:
            ok_btn.setText("OK")
            ok_btn.setEnabled(True)
            ok_btn.setCursor(Qt.PointingHandCursor)
            ok_btn.setStyleSheet(_unlocked_style)
            _countdown.stop()

    _countdown = QTimer(dlg)
    _countdown.setInterval(1000)
    _countdown.timeout.connect(_tick)
    _countdown.start()

    # ── OK handler ────────────────────────────────────────────────────────────
    def _on_ok():
        print("[DEBUG] show_discord_notice: user clicked OK")
        _countdown.stop()
        try:
            from gui.state import state
            from core.settings import save_settings
            state.app_settings["discord_notice_shown"] = True
            save_settings()
            print("[DEBUG] show_discord_notice: discord_notice_shown=True saved")
        except Exception as e:
            print(f"[DEBUG] show_discord_notice: could not save setting: {e}")
        dlg.accept()

    ok_btn.clicked.connect(_on_ok)

    # If the user closes via the X button, still mark as shown so we don't
    # spam them on every launch.
    def _on_rejected():
        print("[DEBUG] show_discord_notice: dialog closed via X")
        _countdown.stop()
        try:
            from gui.state import state
            from core.settings import save_settings
            state.app_settings["discord_notice_shown"] = True
            save_settings()
        except Exception:
            pass

    # Escape key fires the rejected signal — _on_rejected handles it.
    dlg.rejected.connect(_on_rejected)

    # ── Layout & positioning ──────────────────────────────────────────────────
    dlg.adjustSize()
    set_window_icon(dlg)
    print(f"[DEBUG] show_discord_notice: dialog size={dlg.width()}x{dlg.height()}")

    if parent and parent.isVisible():
        pg = parent.geometry()
        dlg.move(
            pg.x() + (pg.width()  - dlg.width())  // 2,
            pg.y() + (pg.height() - dlg.height()) // 2,
        )

    print("[DEBUG] show_discord_notice: executing dialog")
    result = dlg.exec()
    print(f"[DEBUG] show_discord_notice: dialog closed, result={result}")
    print("[DEBUG] ========== DISCORD NOTICE COMPLETE ==========\n")
