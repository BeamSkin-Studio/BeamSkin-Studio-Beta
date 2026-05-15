from __future__ import annotations
import json
import os
import threading
import time
import webbrowser
from typing import Optional

from PySide6.QtCore    import Qt, Signal, QTimer
from PySide6.QtGui     import QPixmap
from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QScrollArea, QSizePolicy,
)

from gui.theme   import COLORS, font, drop_shadow, fade_in
from gui.state   import state

try:
    from core.localization import t
except ImportError:
    def t(key, **kw): return key


_LOCALES_DIR = os.path.join("core", "localization", "languages")


def _scan_translators() -> str:
    if not os.path.isdir(_LOCALES_DIR):
        return t("about.no_translators", default="—")
    current_lang_names: dict = {}
    try:
        lp = _get_current_locale_path()
        if lp and os.path.isfile(lp):
            with open(lp, "r", encoding="utf-8") as f:
                current_lang_names = json.load(f).get("language_names", {})
    except Exception:
        pass

    entries: list = []
    seen: set = set()
    for filename in sorted(os.listdir(_LOCALES_DIR)):
        if not filename.lower().endswith(".json"):
            continue
        try:
            with open(os.path.join(_LOCALES_DIR, filename), "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        meta         = data.get("_meta", {})
        contributors = meta.get("contributors", [])
        flag         = meta.get("flag", "")
        if flag and flag in current_lang_names:
            lang_display = current_lang_names[flag]
        elif meta.get("name"):
            lang_display = meta["name"]
        elif meta.get("native_name"):
            lang_display = meta["native_name"]
        else:
            lang_display = filename.replace(".json", "")
        for c in contributors:
            line = f"{c} - {lang_display}"
            if line not in seen:
                seen.add(line)
                entries.append(line)
    return "\n".join(entries) if entries else t("about.no_translators", default="—")


def _get_current_locale_path() -> Optional[str]:
    for attr in ("locale_path", "language_path", "current_locale_path"):
        p = getattr(state, attr, None)
        if p and os.path.isfile(p):
            return p
    if not os.path.isdir(_LOCALES_DIR):
        return None
    for attr in ("language", "current_language", "locale", "lang_code"):
        code = getattr(state, attr, None)
        if code:
            for fn in os.listdir(_LOCALES_DIR):
                if not fn.lower().endswith(".json"):
                    continue
                stem = os.path.splitext(fn)[0].lower()
                if (stem == code.lower() or
                        stem.replace("_", "").replace("-", "") ==
                        code.lower().replace("_", "").replace("-", "")):
                    return os.path.join(_LOCALES_DIR, fn)
    return None


#  ABOUT TAB

class AboutTab(QWidget):
    """
    About tab showing logo, credits, translators, and donation options.

    FIX — blank on return: the widget tree is built once and persisted.
    """

    def __init__(self, parent: QWidget):
        print(f"[DEBUG] __init__() called")
        super().__init__(parent)
        print("[DEBUG] AboutTab __init__ called")
        self.setStyleSheet(f"background:{COLORS['app_bg']};")

        self._payment_overlay: Optional[QWidget] = None
        self._logo_lbl:        Optional[QLabel] = None   # kept for theme-switch updates
        self._translators_lbl: Optional[QLabel] = None
        self._version_lbl:     Optional[QLabel] = None
        self._credits_lbl:     Optional[QLabel] = None
        self._dev_lbl:         Optional[QLabel] = None
        self._trans_hdr:       Optional[QLabel] = None
        self._donate_btn                        = None
        self._discord_btn:     Optional[QPushButton] = None

        self._setup_ui()


    def _setup_ui(self):
        print(f"[DEBUG] _setup_ui() called")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ background:{COLORS['app_bg']};border:none; }}")
        outer.addWidget(scroll)

        content_widget = QWidget()
        content_widget.setStyleSheet(f"background:{COLORS['frame_bg']};")
        scroll.setWidget(content_widget)

        col = QVBoxLayout(content_widget)
        col.setContentsMargins(40, 30, 40, 30)
        col.setSpacing(10)
        col.setAlignment(Qt.AlignHCenter)

        logo_px = self._load_logo_pixmap()
        if logo_px:
            self._logo_lbl = QLabel()
            self._logo_lbl.setPixmap(logo_px)
            self._logo_lbl.setAlignment(Qt.AlignCenter)
            self._logo_lbl.setStyleSheet("background:transparent;border:none;")
            col.addWidget(self._logo_lbl)
        else:
            self._logo_lbl = None
            title_lbl = QLabel(t("about.title", default="BeamSkin Studio"))
            title_lbl.setFont(font(26, "bold"))
            title_lbl.setAlignment(Qt.AlignCenter)
            title_lbl.setStyleSheet(f"color:{COLORS['text']};background:transparent;border:none;")
            col.addWidget(title_lbl)

        col.addSpacing(30)

        self._credits_lbl = QLabel(t("about.credits", default="Credits"))
        self._credits_lbl.setFont(font(22, "bold"))
        self._credits_lbl.setAlignment(Qt.AlignCenter)
        self._credits_lbl.setStyleSheet(f"color:{COLORS['text']};background:transparent;border:none;")
        col.addWidget(self._credits_lbl)

        self._dev_lbl = QLabel(t("about.developer", default="Developer"))
        self._dev_lbl.setFont(font(19, "bold"))
        self._dev_lbl.setAlignment(Qt.AlignCenter)
        self._dev_lbl.setStyleSheet(f"color:{COLORS['text']};background:transparent;border:none;")
        col.addWidget(self._dev_lbl)

        dev_btn = self._card_button("@Burzt_YT", 140, font_size=17)
        dev_btn.clicked.connect(lambda: webbrowser.open("https://linktr.ee/burzt_yt"))
        col.addWidget(dev_btn, alignment=Qt.AlignCenter)

        col.addSpacing(16)

        self._trans_hdr = QLabel(t("about.translators", default="Translators"))
        self._trans_hdr.setFont(font(19, "bold"))
        self._trans_hdr.setAlignment(Qt.AlignCenter)
        self._trans_hdr.setStyleSheet(f"color:{COLORS['text']};background:transparent;border:none;")
        col.addWidget(self._trans_hdr)

        self._translators_lbl = QLabel(_scan_translators())
        self._translators_lbl.setFont(font(16, "bold"))
        self._translators_lbl.setAlignment(Qt.AlignCenter)
        self._translators_lbl.setStyleSheet(f"color:{COLORS['text']};background:transparent;border:none;")
        col.addWidget(self._translators_lbl)

        col.addStretch(1)

        self._donate_btn = QPushButton(t("about.donate", default="💙 Donate"))
        self._donate_btn.setFont(font(22, "bold"))
        self._donate_btn.setFixedSize(200, 50)
        self._donate_btn.setCursor(Qt.PointingHandCursor)
        self._donate_btn.setStyleSheet("""
            QPushButton {
                background:#0070BA;
                color:white;
                border-radius:10px;
                border:none;
            }
            QPushButton:hover { background:#005EA6; }
        """)
        self._donate_btn.clicked.connect(self._show_payment_options)
        col.addWidget(self._donate_btn, alignment=Qt.AlignCenter)

        self._discord_btn = QPushButton("  Join our Discord")
        self._discord_btn.setFont(font(16, "bold"))
        self._discord_btn.setFixedSize(220, 46)
        self._discord_btn.setCursor(Qt.PointingHandCursor)
        self._discord_btn.setStyleSheet("""
            QPushButton {
                background: #5865F2;
                color: white;
                border-radius: 10px;
                border: none;
                padding-left: 8px;
            }
            QPushButton:hover { background: #4752C4; }
        """)
        # Discord icon sits inside the button to the left of the text
        discord_icon = QLabel("", self._discord_btn)
        discord_icon.setPixmap(self._load_discord_icon())
        discord_icon.setFixedSize(24, 24)
        discord_icon.setStyleSheet("background:transparent;border:none;")
        discord_icon.setAttribute(Qt.WA_TransparentForMouseEvents)
        discord_icon.move(14, 11)
        self._discord_btn.clicked.connect(self._open_discord)
        col.addWidget(self._discord_btn, alignment=Qt.AlignCenter)

        col.addSpacing(10)

        version_str = getattr(state, "current_version", "")
        self._version_lbl = QLabel(
            t("about.version", version=version_str, default=f"Version {version_str}")
        )
        self._version_lbl.setFont(font(14))
        self._version_lbl.setAlignment(Qt.AlignCenter)
        self._version_lbl.setStyleSheet(f"color:{COLORS['text']};background:transparent;border:none;")
        col.addWidget(self._version_lbl)


    def _load_logo_pixmap(self) -> Optional[QPixmap]:
        print(f"[DEBUG] _load_logo_pixmap() called")
        icon_dir = os.path.join("gui", "Icons")
        suffix   = "White" if state.theme_mode == "dark" else "Black"
        path     = os.path.join(icon_dir, f"BeamSkin_Studio_{suffix}.png")
        if os.path.exists(path):
            # Logo is 2:1 (width × height). Scale to a 400×200 bounding box so
            # the rendered pixmap is 400×200 rather than the old undersized 200×100.
            return QPixmap(path).scaled(400, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return None


    def _accent_button(self, text: str, width: int = 120) -> QPushButton:
        print(f"[DEBUG] _accent_button() called")
        btn = QPushButton(text)
        btn.setFont(font(15))
        btn.setFixedHeight(40)
        btn.setFixedWidth(width)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background:{COLORS['accent']};
                color:{COLORS['accent_text']};
                border-radius:8px;
                border:none;
            }}
            QPushButton:hover {{ background:{COLORS['accent_hover']}; }}
        """)
        return btn

    def _card_button(self, text: str, width: int = 140, font_size: int = 13) -> QPushButton:
        print(f"[DEBUG] _card_button() called")
        btn = QPushButton(text)
        btn.setFont(font(font_size, "bold"))
        btn.setFixedHeight(40)
        btn.setFixedWidth(width)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background:{COLORS['card_bg']};
                color:{COLORS['text']};
                border-radius:8px;
                border:1px solid {COLORS['border']};
            }}
            QPushButton:hover {{ background:{COLORS.get('card_hover', COLORS['card_bg'])}; }}
        """)
        return btn


    def _show_payment_options(self):
        print(f"[DEBUG] _show_payment_options: showing donation overlay")
        if self._payment_overlay is not None:
            return

        overlay = QWidget(self)
        overlay.setStyleSheet(
            f"background:rgba(13,15,20,0.85);"
        )
        overlay.setAttribute(Qt.WA_StyledBackground, True)
        overlay.setGeometry(self.rect())
        overlay.raise_()
        overlay.show()
        self._payment_overlay = overlay

        # Center dialog
        dialog = QFrame(overlay)
        dialog.setStyleSheet(f"""
            QFrame {{
                background:{COLORS['frame_bg']};
                border-radius:14px;
                border:2px solid {COLORS['accent']};
            }}
        """)
        d_col = QVBoxLayout(dialog)
        d_col.setContentsMargins(40, 24, 40, 24)
        d_col.setSpacing(10)

        ttl = QLabel(t("about.select_payment_method", default="Choose a payment method"))
        ttl.setFont(font(18, "bold"))
        ttl.setAlignment(Qt.AlignCenter)
        ttl.setStyleSheet(f"color:{COLORS['text']};background:transparent;border:none;")
        d_col.addWidget(ttl)

        def _pay_btn(text, bg, hover_bg, callback):
            b = QPushButton(text)
            b.setFont(font(15, "bold"))
            b.setFixedSize(200, 45)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(f"""
                QPushButton {{ background:{bg};color:white;border-radius:8px;border:none; }}
                QPushButton:hover {{ background:{hover_bg}; }}
            """)
            b.clicked.connect(callback)
            d_col.addWidget(b, alignment=Qt.AlignCenter)

        _pay_btn("💳 PayPal",  "#0070BA", "#005EA6", self._open_paypal)
        _pay_btn("💚 Swish",   "#7BDC3D", "#6BC935", self._open_swish)

        monthly_lbl = QLabel(t("about.monthly", default="Monthly support:"))
        monthly_lbl.setFont(font(12))
        monthly_lbl.setAlignment(Qt.AlignCenter)
        monthly_lbl.setStyleSheet(f"color:{COLORS['text']};background:transparent;border:none;")
        d_col.addWidget(monthly_lbl)

        _pay_btn("🎨 Patreon", "#F96854", "#E05A48", self._open_patreon)

        cancel_btn = self._card_button(t("about.cancel", default="Cancel"), width=200)
        cancel_btn.clicked.connect(self._close_payment_options)
        d_col.addWidget(cancel_btn, alignment=Qt.AlignCenter)

        dialog.show()
        dialog.adjustSize()
        dialog.move(
            (overlay.width()  - dialog.width())  // 2,
            (overlay.height() - dialog.height()) // 2,
        )

        # close when clicking the dim overlay (but not the dialog)
        def _maybe_close(event):
            if not dialog.geometry().contains(event.pos()):
                self._close_payment_options()
        overlay.mousePressEvent = _maybe_close

    def _close_payment_options(self):
        print(f"[DEBUG] _close_payment_options: closing donation overlay")
        if self._payment_overlay:
            self._payment_overlay.deleteLater()
            self._payment_overlay = None

    def resizeEvent(self, event):
        print(f"[DEBUG] resizeEvent() called")
        super().resizeEvent(event)
        if self._payment_overlay:
            self._payment_overlay.setGeometry(self.rect())

    def _load_discord_icon(self) -> QPixmap:
        """Return the Discord logo from the Icons folder."""
        path = os.path.join("gui", "Icons", "discord_logo_white.png")
        if os.path.exists(path):
            return QPixmap(path).scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return QPixmap()  # empty fallback — no icon rather than a fake 'D'

    def _open_discord(self):
        webbrowser.open("https://discord.gg/mbr3YxZzrr")

    def _open_paypal(self):
        webbrowser.open("https://www.paypal.com/paypalme/thedriveryt")
        self._close_payment_options()

    def _open_swish(self):
        webbrowser.open("https://imgur.com/a/lI2y6tj")
        self._close_payment_options()

    def _open_patreon(self):
        webbrowser.open("https://www.patreon.com/BURZT_YT")
        self._close_payment_options()


    def refresh_ui(self):
        """Update translatable strings without rebuilding the widget tree."""
        print(f"[DEBUG] _load_discord_icon() called")
        if self._logo_lbl is not None:
            new_px = self._load_logo_pixmap()
            if new_px:
                self._logo_lbl.setPixmap(new_px)
        if self._credits_lbl:
            self._credits_lbl.setText(t("about.credits", default="Credits"))
        if self._dev_lbl:
            self._dev_lbl.setText(t("about.developer", default="Developer"))
        if self._trans_hdr:
            self._trans_hdr.setText(t("about.translators", default="Translators"))
        if self._translators_lbl:
            self._translators_lbl.setText(_scan_translators())
        if self._donate_btn:
            self._donate_btn.setText(t("about.donate", default="💙 Donate"))
        if self._version_lbl:
            version_str = getattr(state, "current_version", "")
            self._version_lbl.setText(
                t("about.version", version=version_str, default=f"Version {version_str}")
            )


