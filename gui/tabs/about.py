from __future__ import annotations
import json
import os
import webbrowser
from typing import Optional

from PySide6.QtCore    import Qt, QSize
from PySide6.QtGui     import QPixmap, QIcon
from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QScrollArea, QSizePolicy,
)

from gui.theme   import COLORS, font
from gui.state   import state

try:
    from core.localization import t
except ImportError as _exc:
    print(f"[DEBUG] _pipe_tmp.py: import failed ({_exc}), using fallback")
    def t(key, **kw):
        return key

try:
    from core.settings import get_bundle_path
except ImportError as _exc:
    print(f"[DEBUG] _pipe_tmp.py: import failed ({_exc}), using fallback")
    def get_bundle_path():
        return os.getcwd()


_LOCALES_DIR = os.path.join(get_bundle_path(), "core", "localization", "languages")


def _scan_translators() -> str:
    if not os.path.isdir(_LOCALES_DIR):
        return t("about.no_translators", default="—")
    current_lang_names: dict = {}
    try:
        lp = _get_current_locale_path()
        if lp and os.path.isfile(lp):
            with open(lp, "r", encoding="utf-8") as f:
                current_lang_names = json.load(f).get("language_names", {})
    except Exception as _exc:
        print(f"[WARNING] _scan_translators: {type(_exc).__name__}: {_exc}")

    entries: list = []
    seen: set = set()
    for filename in sorted(os.listdir(_LOCALES_DIR)):
        if not filename.lower().endswith(".json"):
            continue
        try:
            with open(os.path.join(_LOCALES_DIR, filename), "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as _exc:
            print(f"[WARNING] _scan_translators: {type(_exc).__name__}: {_exc}")
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


_CONTENT_MAX_WIDTH = 760


def _scrollbar_qss() -> str:
    return f"""
        QScrollBar:vertical {{
            background:transparent; width:10px; margin:2px;
        }}
        QScrollBar::handle:vertical {{
            background:{COLORS['card_hover']}; border-radius:4px; min-height:30px;
        }}
        QScrollBar::handle:vertical:hover {{ background:{COLORS['accent']}; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background:transparent; }}
    """


class AboutTab(QWidget):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setStyleSheet(f"background:{COLORS['app_bg']};")

        self._payment_overlay: Optional[QWidget] = None
        self._logo_lbl:        Optional[QLabel] = None
        self._translators_box: Optional[QVBoxLayout] = None
        self._version_lbl:     Optional[QLabel] = None
        self._credits_lbl:     Optional[QLabel] = None
        self._dev_lbl:         Optional[QLabel] = None
        self._trans_hdr:       Optional[QLabel] = None
        self._support_hdr:     Optional[QLabel] = None
        self._donate_btn                        = None
        self._discord_btn:     Optional[QPushButton] = None

        self._setup_ui()


    def _card(self, name: str) -> QFrame:
        card = QFrame()
        card.setObjectName(name)
        card.setStyleSheet(f"""
            QFrame#{name} {{
                background:{COLORS['card_bg']};
                border:1px solid {COLORS['border']};
                border-radius:10px;
            }}
        """)
        return card

    def _section_header(self, text: str):
        header = QFrame()
        header.setFixedHeight(30)
        header.setStyleSheet("background:transparent;border:none;")
        row = QHBoxLayout(header)
        row.setContentsMargins(6, 0, 10, 0)
        row.setSpacing(6)

        marker = QFrame()
        marker.setFixedSize(3, 14)
        marker.setStyleSheet(
            f"background:{COLORS['accent']};border:none;border-radius:1px;"
        )
        row.addWidget(marker)

        label = QLabel(text.upper())
        label.setFont(font(10, "bold"))
        label.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;"
        )
        row.addWidget(label)
        row.addStretch()
        return header, label

    def _row_frame(self, height: int = 48) -> QFrame:
        row = QFrame()
        row.setMinimumHeight(height)
        row.setStyleSheet(f"""
            QFrame {{
                background:{COLORS['frame_bg']};
                border:1px solid {COLORS['border']};
                border-radius:8px;
            }}
        """)
        return row

    def _chip(self, text: str) -> QLabel:
        chip = QLabel(text)
        chip.setFont(font(11))
        chip.setStyleSheet(f"""
            QLabel {{
                background:{COLORS['card_hover']};
                color:{COLORS['text_secondary']};
                border:none;
                border-radius:9px;
                padding:3px 10px;
            }}
        """)
        return chip

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            f"QScrollArea {{ background:{COLORS['app_bg']};border:none; }}"
            + _scrollbar_qss()
        )
        outer.addWidget(scroll)

        page = QWidget()
        page.setStyleSheet(f"background:{COLORS['app_bg']};")
        scroll.setWidget(page)

        page_row = QHBoxLayout(page)
        page_row.setContentsMargins(14, 14, 14, 14)
        page_row.setSpacing(0)
        page_row.addStretch(1)

        column = QWidget()
        column.setMaximumWidth(_CONTENT_MAX_WIDTH)
        column.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        column.setStyleSheet("background:transparent;")
        page_row.addWidget(column, 100)
        page_row.addStretch(1)

        col = QVBoxLayout(column)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(12)

        col.addWidget(self._build_hero())
        col.addWidget(self._build_credits())
        col.addWidget(self._build_translators())
        col.addWidget(self._build_support())
        col.addStretch(1)

    def _build_hero(self) -> QFrame:
        card = self._card("aboutHero")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(20, 24, 20, 20)
        lay.setSpacing(12)
        lay.setAlignment(Qt.AlignHCenter)

        logo_px = self._load_logo_pixmap()
        if logo_px:
            self._logo_lbl = QLabel()
            self._logo_lbl.setPixmap(logo_px)
            self._logo_lbl.setAlignment(Qt.AlignCenter)
            self._logo_lbl.setStyleSheet("background:transparent;border:none;")
            lay.addWidget(self._logo_lbl, alignment=Qt.AlignHCenter)
        else:
            self._logo_lbl = None
            title_lbl = QLabel(t("about.title", default="BeamSkin Studio"))
            title_lbl.setFont(font(26, "bold"))
            title_lbl.setAlignment(Qt.AlignCenter)
            title_lbl.setStyleSheet(
                f"color:{COLORS['text']};background:transparent;border:none;"
            )
            lay.addWidget(title_lbl)

        version_str = getattr(state, "current_version", "")
        self._version_lbl = self._chip(
            t("about.version", version=version_str, default=f"Version {version_str}")
        )
        self._version_lbl.setFont(font(12, "bold"))
        lay.addWidget(self._version_lbl, alignment=Qt.AlignHCenter)
        return card

    def _build_credits(self) -> QFrame:
        card = self._card("aboutCredits")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        hdr, self._credits_lbl = self._section_header(
            t("about.credits", default="Credits")
        )
        lay.addWidget(hdr)

        row = self._row_frame(52)
        row_lay = QHBoxLayout(row)
        row_lay.setContentsMargins(14, 6, 8, 6)
        row_lay.setSpacing(10)

        self._dev_lbl = QLabel(t("about.developer", default="Developer"))
        self._dev_lbl.setFont(font(13, "bold"))
        self._dev_lbl.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;"
        )
        row_lay.addWidget(self._dev_lbl)
        row_lay.addStretch(1)

        dev_btn = self._card_button("@Burzt_YT", 150, font_size=13)
        dev_btn.clicked.connect(lambda: webbrowser.open("https://linktr.ee/burzt_yt"))
        row_lay.addWidget(dev_btn)
        lay.addWidget(row)
        return card

    def _build_translators(self) -> QFrame:
        card = self._card("aboutTranslators")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        hdr, self._trans_hdr = self._section_header(
            t("about.translators", default="Translators")
        )
        lay.addWidget(hdr)

        holder = QWidget()
        holder.setStyleSheet("background:transparent;")
        self._translators_box = QVBoxLayout(holder)
        self._translators_box.setContentsMargins(0, 0, 0, 0)
        self._translators_box.setSpacing(6)
        lay.addWidget(holder)

        self._populate_translators()
        return card

    def _populate_translators(self):
        box = self._translators_box
        if box is None:
            return
        while box.count():
            item = box.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

        raw = _scan_translators()
        for line in raw.split("\n"):
            line = line.strip()
            if not line:
                continue
            row = self._row_frame(42)
            row_lay = QHBoxLayout(row)
            row_lay.setContentsMargins(14, 4, 10, 4)
            row_lay.setSpacing(10)

            if " - " in line:
                name, lang = line.rsplit(" - ", 1)
            else:
                name, lang = line, ""

            name_lbl = QLabel(name.strip())
            name_lbl.setFont(font(13, "bold"))
            name_lbl.setStyleSheet(
                f"color:{COLORS['text']};background:transparent;border:none;"
            )
            row_lay.addWidget(name_lbl)
            row_lay.addStretch(1)
            if lang:
                row_lay.addWidget(self._chip(lang.strip()))
            box.addWidget(row)

    def _build_support(self) -> QFrame:
        card = self._card("aboutSupport")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(8, 8, 8, 10)
        lay.setSpacing(8)

        hdr, self._support_hdr = self._section_header(
            t("about.support", default="Support & Community")
        )
        lay.addWidget(hdr)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(4, 0, 4, 0)
        btn_row.setSpacing(10)

        self._donate_btn = QPushButton(t("about.donate", default="💙 Donate"))
        self._donate_btn.setFont(font(14, "bold"))
        self._donate_btn.setMinimumHeight(46)
        self._donate_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._donate_btn.setCursor(Qt.PointingHandCursor)
        self._donate_btn.setFocusPolicy(Qt.NoFocus)
        self._donate_btn.setStyleSheet("""
            QPushButton {
                background:#0070BA;
                color:white;
                border-radius:8px;
                border:none;
                padding:6px 16px;
            }
            QPushButton:hover { background:#005EA6; }
        """)
        self._donate_btn.clicked.connect(self._show_payment_options)
        btn_row.addWidget(self._donate_btn)

        self._discord_btn = QPushButton(
            t("about.discord", default="Join our Discord")
        )
        self._discord_btn.setFont(font(14, "bold"))
        self._discord_btn.setMinimumHeight(46)
        self._discord_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._discord_btn.setCursor(Qt.PointingHandCursor)
        self._discord_btn.setFocusPolicy(Qt.NoFocus)
        icon_px = self._load_discord_icon()
        if not icon_px.isNull():
            self._discord_btn.setIcon(QIcon(icon_px))
            self._discord_btn.setIconSize(QSize(22, 22))
        self._discord_btn.setStyleSheet("""
            QPushButton {
                background:#5865F2;
                color:white;
                border-radius:8px;
                border:none;
                padding:6px 16px;
            }
            QPushButton:hover { background:#4752C4; }
        """)
        self._discord_btn.clicked.connect(self._open_discord)
        btn_row.addWidget(self._discord_btn)

        lay.addLayout(btn_row)
        return card


    def _load_logo_pixmap(self) -> Optional[QPixmap]:
        icon_dir = os.path.join(get_bundle_path(), "gui", "Icons")
        suffix   = "White" if state.theme_mode == "dark" else "Black"
        path     = os.path.join(icon_dir, f"BeamSkin_Studio_{suffix}.png")
        if os.path.exists(path):
            return QPixmap(path).scaled(360, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return None


    def _accent_button(self, text: str, width: int = 120) -> QPushButton:
        btn = QPushButton(text)
        btn.setFont(font(13, "bold"))
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
        btn = QPushButton(text)
        btn.setFont(font(font_size, "bold"))
        btn.setFixedHeight(38)
        btn.setFixedWidth(width)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFocusPolicy(Qt.NoFocus)
        btn.setStyleSheet(f"""
            QPushButton {{
                background:{COLORS['card_hover']};
                color:{COLORS['text']};
                border-radius:8px;
                border:none;
            }}
            QPushButton:hover {{
                background:{COLORS['accent']};
                color:{COLORS['accent_text']};
            }}
        """)
        return btn


    def _show_payment_options(self):
        print("[DEBUG] _show_payment_options: showing donation overlay")
        if self._payment_overlay is not None:
            return

        overlay = QWidget(self)
        overlay.setStyleSheet("background:rgba(13,15,20,0.85);")
        overlay.setAttribute(Qt.WA_StyledBackground, True)
        overlay.setGeometry(self.rect())
        overlay.raise_()
        overlay.show()
        self._payment_overlay = overlay

        dialog = QFrame(overlay)
        dialog.setObjectName("paymentDialog")
        dialog.setFixedWidth(320)
        dialog.setStyleSheet(f"""
            QFrame#paymentDialog {{
                background:{COLORS['card_bg']};
                border:1px solid {COLORS['border']};
                border-radius:10px;
            }}
        """)
        d_col = QVBoxLayout(dialog)
        d_col.setContentsMargins(16, 14, 16, 16)
        d_col.setSpacing(8)

        hdr, _ = self._section_header(
            t("about.select_payment_method", default="Choose a payment method")
        )
        d_col.addWidget(hdr)

        def _pay_btn(text, bg, hover_bg, callback, fg="white"):
            b = QPushButton(text)
            b.setFont(font(13, "bold"))
            b.setMinimumHeight(44)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            b.setCursor(Qt.PointingHandCursor)
            b.setFocusPolicy(Qt.NoFocus)
            b.setStyleSheet(f"""
                QPushButton {{ background:{bg};color:{fg};border-radius:8px;border:none; }}
                QPushButton:hover {{ background:{hover_bg}; }}
            """)
            b.clicked.connect(callback)
            d_col.addWidget(b)

        _pay_btn("💳  PayPal", "#0070BA", "#005EA6", self._open_paypal)
        _pay_btn("💚  Swish",  "#7BDC3D", "#6BC935", self._open_swish, fg="#10230a")

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{COLORS['border']};border:none;")
        d_col.addSpacing(4)
        d_col.addWidget(sep)
        d_col.addSpacing(2)

        monthly_lbl = QLabel(t("about.monthly", default="Monthly support").rstrip(":"))
        monthly_lbl.setFont(font(11))
        monthly_lbl.setStyleSheet(
            f"color:{COLORS['text_secondary']};background:transparent;border:none;padding-left:4px;"
        )
        d_col.addWidget(monthly_lbl)

        _pay_btn("🎨  Patreon", "#F96854", "#E05A48", self._open_patreon)

        cancel_btn = QPushButton(t("about.cancel", default="Cancel"))
        cancel_btn.setFont(font(13))
        cancel_btn.setMinimumHeight(40)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setFocusPolicy(Qt.NoFocus)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background:{COLORS['card_hover']};color:{COLORS['text']};
                border-radius:8px;border:none;
            }}
            QPushButton:hover {{ background:{COLORS['frame_bg']}; }}
        """)
        cancel_btn.clicked.connect(self._close_payment_options)
        d_col.addSpacing(4)
        d_col.addWidget(cancel_btn)

        dialog.show()
        dialog.adjustSize()
        dialog.move(
            (overlay.width()  - dialog.width())  // 2,
            (overlay.height() - dialog.height()) // 2,
        )

        def _maybe_close(event):
            if not dialog.geometry().contains(event.pos()):
                self._close_payment_options()
        overlay.mousePressEvent = _maybe_close

    def _close_payment_options(self):
        print("[DEBUG] _close_payment_options: closing donation overlay")
        if self._payment_overlay:
            self._payment_overlay.deleteLater()
            self._payment_overlay = None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._payment_overlay:
            self._payment_overlay.setGeometry(self.rect())
            dlg = self._payment_overlay.findChild(QFrame, "paymentDialog")
            if dlg is not None:
                dlg.move(
                    (self._payment_overlay.width()  - dlg.width())  // 2,
                    (self._payment_overlay.height() - dlg.height()) // 2,
                )

    def _load_discord_icon(self) -> QPixmap:
        path = os.path.join(get_bundle_path(), "gui", "Icons", "discord_logo_white.png")
        if os.path.exists(path):
            return QPixmap(path).scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return QPixmap()

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
        if self._logo_lbl is not None:
            new_px = self._load_logo_pixmap()
            if new_px:
                self._logo_lbl.setPixmap(new_px)
        if self._credits_lbl:
            self._credits_lbl.setText(t("about.credits", default="Credits").upper())
        if self._dev_lbl:
            self._dev_lbl.setText(t("about.developer", default="Developer"))
        if self._trans_hdr:
            self._trans_hdr.setText(t("about.translators", default="Translators").upper())
        if self._support_hdr:
            self._support_hdr.setText(
                t("about.support", default="Support & Community").upper()
            )
        self._populate_translators()
        if self._donate_btn:
            self._donate_btn.setText(t("about.donate", default="💙 Donate"))
        if self._discord_btn:
            self._discord_btn.setText(t("about.discord", default="Join our Discord"))
        if self._version_lbl:
            version_str = getattr(state, "current_version", "")
            self._version_lbl.setText(
                t("about.version", version=version_str, default=f"Version {version_str}")
            )
