
from __future__ import annotations
import threading
import os, json
from typing import Optional

from PySide6.QtCore    import Qt, QTimer, Signal, QObject
from PySide6.QtGui     import QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QWidget, QPushButton, QComboBox,
)

from gui.theme   import COLORS, font, drop_shadow, fade_in
from gui.widgets import AnimButton
from gui.icon_helper import set_window_icon

try:
    from core.localization import t, get_current_language
except ImportError as _exc:
    print(f"[DEBUG] _pipe_tmp.py: import failed ({_exc}), using fallback")
    def t(key, **kw):
        return key
    def get_current_language():
        return 'en'

try:
    from deep_translator import GoogleTranslator as _GT
    _TRANSLATE_AVAIL = True
except ImportError as _exc:
    print(f"[DEBUG] _pipe_tmp.py: import failed ({_exc}), using fallback")
    _TRANSLATE_AVAIL = False

_LOCALE_MAP = {
    "en": "en", "fr": "fr", "de": "de", "es": "es", "it": "it",
    "pt": "pt", "nl": "nl", "ru": "ru", "pl": "pl", "cs": "cs",
    "sv": "sv", "no": "no", "da": "da", "fi": "fi", "uk": "uk",
    "zh": "zh-CN", "ja": "ja", "ko": "ko", "ar": "ar",
    "en_US": "en", "en_GB": "en",
}


def _target_lang() -> str:
    try:
        code = get_current_language()
        return _LOCALE_MAP.get(code, code[:2].lower())
    except Exception as _exc:
        print(f"[WARNING] _target_lang: {type(_exc).__name__}: {_exc}")
        return 'en'


def _should_translate() -> bool:
    return _target_lang() not in ("en",)


try:
    from core.settings import get_data_dir
except ImportError as _exc:
    print(f"[DEBUG] _pipe_tmp.py: import failed ({_exc}), using fallback")
    def get_data_dir() -> str:
        return 'data'


def _seen_path() -> str:
    return os.path.join(get_data_dir(), "seen_changelogs.json")


def _load_seen() -> list:
    try:
        if os.path.exists(_seen_path()):
            with open(_seen_path(), encoding="utf-8") as f:
                return json.load(f)
    except Exception as _exc:
        print(f"[WARNING] _load_seen: {type(_exc).__name__}: {_exc}")
    return []


def _mark_seen(version: str):
    seen = _load_seen()
    if version not in seen:
        seen.append(version)
    os.makedirs(os.path.dirname(_seen_path()), exist_ok=True)
    try:
        with open(_seen_path(), "w", encoding="utf-8") as f:
            json.dump(seen, f)
    except Exception as _exc:
        print(f"[WARNING] _mark_seen: {type(_exc).__name__}: {_exc}")


def has_seen_changelog(version: str) -> bool:
    return version in _load_seen()


def _get_remote_changelog_url() -> str:
    import sys
    if sys.platform == "win32":
        return (
            "https://raw.githubusercontent.com/BeamSkin-Studio/"
            "BeamSkin-Studio-Beta/main/core/changelog.py"
        )
    return (
        "https://raw.githubusercontent.com/BeamSkin-Studio/"
        "BeamSkin-Studio-Linux-Beta/main/core/changelog.py"
    )


def _exec_remote_changelog(source: str) -> list | None:
    import builtins as _builtins
    from typing import TypedDict, Literal

    def _title(text):     return {"type": "title",     "text": text}
    def _subtitle(text):  return {"type": "subtitle",  "text": text}
    def _item(text):      return {"type": "item",      "text": text}
    def _note(text):      return {"type": "note",      "text": text}
    def _separator():     return {"type": "separator", "text": ""}

    namespace: dict = {
        "title":        _title,
        "subtitle":     _subtitle,
        "item":         _item,
        "note":         _note,
        "separator":    _separator,
        "TypedDict":    TypedDict,
        "Literal":      Literal,
        "__builtins__": _builtins,
    }
    try:
        exec(compile(source, "<remote_changelog>", "exec"), namespace)
        return namespace.get("CHANGELOGS")
    except Exception as e:
        print(f"[changelog] exec failed: {e}")
        return None


def _normalise_version(v: str) -> str:
    parts = v.strip().split(".")
    return ".".join(p for p in parts[:3] if p.isdigit())


def fetch_remote_changelog_for_version(version: str) -> dict | None:
    import requests

    url = _get_remote_changelog_url()
    try:
        resp = requests.get(url, timeout=8)
        resp.raise_for_status()
        source = resp.text
    except Exception as e:
        print(f"[changelog] network fetch failed: {e}")
        return None

    changelogs = _exec_remote_changelog(source)
    if not changelogs:
        return None

    target = _normalise_version(version)
    print(f"[changelog] looking for version '{target}' (raw: '{version}')")
    for entry in changelogs:
        if isinstance(entry, dict):
            entry_ver = _normalise_version(entry.get("version", ""))
            if entry_ver == target:
                print(f"[changelog] found matching entry for {target}")
                return entry

    print(f"[changelog] no exact match for '{target}', falling back to latest entry")
    return changelogs[0] if changelogs else None


class _FetchSignals(QObject):
    done   = Signal(object)
    failed = Signal()


def show_update_changelog(parent: "QWidget", version: str) -> None:
    loading_data = {
        "version": version,
        "date": "",
        "entries": [{"type": "_loading", "text": ""}],
    }
    dlg = ChangelogDialog(parent, loading_data, preview_mode=True)

    signals = _FetchSignals(dlg)

    def _on_done(data: dict):
        dlg._update_remote_data(data)

    def _on_failed():
        dlg._update_remote_data({
            "version": version,
            "date": "",
            "entries": [
                {"type": "title", "text": t("changelog.error_title", default="⚠️  Could Not Load Changelog")},
                {"type": "item",  "text": t("changelog.error_body",  default="Unable to reach GitHub. Please check your internet connection and try again.")},
                {"type": "note",  "text": t("changelog.error_note",  default="You can still download the update — the changelog will appear automatically after installing.")},
            ],
        })

    signals.done.connect(_on_done)
    signals.failed.connect(_on_failed)

    def _worker():
        data = fetch_remote_changelog_for_version(version)
        if data is not None:
            signals.done.emit(data)
        else:
            signals.failed.emit()

    threading.Thread(target=_worker, daemon=True).start()
    dlg.show()


class _TranslationSignals(QObject):
    done = Signal(list)


class ChangelogDialog(QDialog):
    def __init__(self, parent: QWidget, changelog_data: dict,
                 *, preview_mode: bool = False, browsable: bool = False):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Dialog)
        set_window_icon(self)
        self.setModal(True)
        self.setFixedSize(620, 720)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background:transparent;")

        self._data         = changelog_data
        self._entries      = list(changelog_data.get("entries", []))
        self._version      = changelog_data.get("version", "?")
        self._date         = changelog_data.get("date", "")
        self._translating  = False
        self._preview_mode = preview_mode
        self._sub_lbl: Optional[QLabel] = None
        self._signals      = _TranslationSignals(self)
        self._signals.done.connect(self._apply_translation)

        self._browsable     = browsable
        self._all_versions: list[str] = []
        self._version_index = 0
        self._prev_btn: Optional[QPushButton] = None
        self._next_btn: Optional[QPushButton] = None
        self._version_combo: Optional[QComboBox] = None
        if browsable:
            self._all_versions = self._load_all_versions()
            try:
                self._version_index = self._all_versions.index(self._version)
            except ValueError as _exc:
                print(f"[WARNING] __init__: {type(_exc).__name__}: {_exc}")
                self._version_index = 0

        if parent:
            top = parent.window()
            pg = top.frameGeometry()
            self.move(pg.x() + (pg.width()  - 620) // 2,
                      pg.y() + (pg.height() - 720) // 2)

        self._build()
        drop_shadow(self._card, 36, (0, 10))
        fade_in(self._card, 220)


    def _load_all_versions(self) -> list:
        try:
            from core.changelog import get_all_versions
            return get_all_versions()
        except Exception as e:
            print(f"[changelog] could not load version list: {e}")
            return [self._version] if self._version else []

    def _go_to_version(self, index: int):
        if not self._all_versions:
            return
        index = index % len(self._all_versions)
        version = self._all_versions[index]
        try:
            from core.changelog import get_changelog_for_version
            data = get_changelog_for_version(version)
        except Exception as e:
            print(f"[changelog] could not load version {version!r}: {e}")
            data = None
        if data is None:
            return
        self._version_index = index
        self._update_remote_data(data)
        self._refresh_nav_buttons()

    def _refresh_nav_buttons(self):
        if not self._browsable or self._prev_btn is None:
            return
        self._prev_btn.setEnabled(True)
        self._next_btn.setEnabled(True)
        if self._version_combo is not None:
            self._version_combo.blockSignals(True)
            self._version_combo.setCurrentIndex(self._version_index)
            self._version_combo.blockSignals(False)


    def _build(self):
        self._loading_timer: Optional[QTimer] = None

        self._card = QFrame(self)
        self._card.setObjectName("mainCard")
        self._card.setGeometry(0, 0, 620, 720)
        self._card.setStyleSheet(f"""
            QFrame#mainCard {{
                background-color: {COLORS['app_bg']};
                border-radius: 18px;
                border: none;
            }}
        """)

        root = QVBoxLayout(self._card)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        hdr = QFrame()
        hdr.setObjectName("dlgHeader")
        hdr.setFixedHeight(100)
        hdr.setStyleSheet(f"""
            QFrame#dlgHeader {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 {COLORS['card_bg']},
                    stop:1 {COLORS['frame_bg']});
                border-top-left-radius: 18px;
                border-top-right-radius: 18px;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
                border: none;
                border-bottom: 1px solid {COLORS['border']};
            }}
        """)


        hdr_row = QHBoxLayout(hdr)
        hdr_row.setContentsMargins(24, 8, 24, 0)
        hdr_row.setSpacing(16)

        badge = QFrame()
        badge.setFixedSize(50, 50)
        badge.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 {COLORS['accent']},
                    stop:1 {COLORS.get('accent_dim', COLORS['accent'])});
                border-radius: 14px;
                border: none;
            }}
        """)
        b_lay = QVBoxLayout(badge)
        b_lay.setContentsMargins(0, 0, 0, 0)
        b_icon = QLabel("✦")
        b_icon.setFont(font(20, "bold"))
        b_icon.setAlignment(Qt.AlignCenter)
        b_icon.setStyleSheet("color:white;background:transparent;border:none;")
        b_lay.addWidget(b_icon)
        hdr_row.addWidget(badge)

        txt_col = QVBoxLayout()
        txt_col.setSpacing(5)

        wn_lbl = QLabel(t("changelog.title", default="What's New"))
        wn_lbl.setFont(font(17, "bold"))
        wn_lbl.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;"
        )
        txt_col.addWidget(wn_lbl)

        sub_text = f"Version {self._version}"
        if self._date:
            sub_text += f"  ·  {self._date}"
        sub_lbl = QLabel(sub_text)
        sub_lbl.setFont(font(11))
        sub_lbl.setStyleSheet(
            f"color:{COLORS['text_secondary']};background:transparent;border:none;"
        )
        txt_col.addWidget(sub_lbl)
        hdr_row.addLayout(txt_col, 1)
        self._sub_lbl = sub_lbl

        if self._browsable:
            nav_row = QHBoxLayout()
            nav_row.setSpacing(4)

            def _nav_btn(arrow: str) -> QPushButton:
                b = QPushButton(arrow)
                b.setFixedSize(30, 30)
                b.setFont(font(13, "bold"))
                b.setCursor(Qt.PointingHandCursor)
                b.setStyleSheet(f"""
                    QPushButton {{
                        background:{COLORS['card_bg']};
                        color:{COLORS['text']};
                        border:1px solid {COLORS['border']};
                        border-radius:8px;
                    }}
                    QPushButton:hover:enabled {{
                        background:{COLORS.get('card_hover', COLORS['card_bg'])};
                        border-color:{COLORS['accent']};
                    }}
                    QPushButton:disabled {{
                        color:{COLORS['text_secondary']};
                    }}
                """)
                return b

            self._prev_btn = _nav_btn("‹")
            self._prev_btn.setToolTip(t("changelog.older", default="Older version"))
            self._prev_btn.clicked.connect(
                lambda: self._go_to_version(self._version_index + 1)
            )
            nav_row.addWidget(self._prev_btn)

            self._version_combo = QComboBox()
            self._version_combo.addItems(self._all_versions)
            self._version_combo.setCurrentIndex(self._version_index)
            self._version_combo.setFixedHeight(30)
            self._version_combo.setFont(font(11))
            self._version_combo.setCursor(Qt.PointingHandCursor)
            self._version_combo.setStyleSheet(f"""
                QComboBox {{
                    background:{COLORS['card_bg']};
                    color:{COLORS['text']};
                    border:1px solid {COLORS['border']};
                    border-radius:8px;
                    padding:0 8px;
                    min-width:110px;
                }}
                QComboBox:hover {{
                    border-color:{COLORS['accent']};
                }}
                QComboBox::drop-down {{
                    border:none;
                    width:18px;
                }}
                QComboBox::down-arrow {{
                    width:10px;
                    height:10px;
                }}
                QComboBox QAbstractItemView {{
                    background:{COLORS['card_bg']};
                    color:{COLORS['text']};
                    border:1px solid {COLORS['border']};
                    border-radius:8px;
                    selection-background-color:{COLORS['accent']};
                    selection-color:{COLORS.get('accent_text','white')};
                    padding:4px;
                }}
            """)
            self._version_combo.currentIndexChanged.connect(self._go_to_version)
            nav_row.addWidget(self._version_combo)

            self._next_btn = _nav_btn("›")
            self._next_btn.setToolTip(t("changelog.newer", default="Newer version"))
            self._next_btn.clicked.connect(
                lambda: self._go_to_version(self._version_index - 1)
            )
            nav_row.addWidget(self._next_btn)

            hdr_row.addLayout(nav_row)
            self._refresh_nav_buttons()

        if _TRANSLATE_AVAIL and _should_translate():
            self._translate_btn = AnimButton(
                t("changelog.translate", default="Translate"),
                icon_text="🌐",
                fg=COLORS["accent"], fg_hover=COLORS["accent_hover"],
                font_size=12, bold=True, padding="6px 14px",
            )
            self._translate_btn.setFixedHeight(34)
            self._translate_btn.clicked.connect(self._on_translate)
            hdr_row.addWidget(self._translate_btn)
        else:
            self._translate_btn = None

        root.addWidget(hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background:transparent; border:none; }}
            QScrollArea > QWidget > QWidget {{ background:{COLORS['app_bg']}; }}
            QScrollBar:vertical {{
                background: transparent;
                width: 4px;
                margin: 6px 2px;
            }}
            QScrollBar::handle:vertical {{
                background: {COLORS['border']};
                border-radius: 2px;
                min-height: 28px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {COLORS['text_secondary']};
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{ height: 0; }}
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {{ background: transparent; }}
        """)
        self._content_w = QWidget()
        self._content_w.setStyleSheet(f"background:{COLORS['app_bg']};")
        self._content_layout = QVBoxLayout(self._content_w)
        self._content_layout.setContentsMargins(20, 20, 20, 16)
        self._content_layout.setSpacing(0)
        scroll.setWidget(self._content_w)
        root.addWidget(scroll, 1)

        ftr = QFrame()
        ftr.setObjectName("dlgFooter")
        ftr.setFixedHeight(68)
        ftr.setStyleSheet(f"""
            QFrame#dlgFooter {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 {COLORS['card_bg']},
                    stop:1 {COLORS['frame_bg']});
                border: none;
                border-top: 1px solid {COLORS['border']};
                border-top-left-radius: 0px;
                border-top-right-radius: 0px;
                border-bottom-left-radius: 18px;
                border-bottom-right-radius: 18px;
            }}
        """)
        ftr_row = QHBoxLayout(ftr)
        ftr_row.setContentsMargins(24, 0, 24, 0)
        close_label = (
            t("changelog.close_preview", default="Close")
            if self._preview_mode
            else t("changelog.close", default="Got it!")
        )
        ok_btn = AnimButton(
            close_label,
            fg=COLORS["accent"], fg_hover=COLORS["accent_hover"],
            font_size=13, bold=True, padding="8px 36px",
        )
        ok_btn.setFixedHeight(40)
        ok_btn.clicked.connect(self._on_close)
        ftr_row.addStretch()
        ftr_row.addWidget(ok_btn)
        ftr_row.addStretch()
        root.addWidget(ftr)

        self._render_entries(self._entries)


    def _clear_content(self):
        if self._loading_timer is not None:
            self._loading_timer.stop()
            self._loading_timer = None
        while self._content_layout.count():
            child = self._content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def _render_entries(self, entries: list):
        self._clear_content()

        preamble: list = []
        sections: list = []
        current: dict | None = None

        for entry in entries:
            etype = entry.get("type", "item")
            if etype == "title":
                if current is not None:
                    sections.append(current)
                current = {"title": entry, "children": []}
            elif etype == "separator":
                if current is not None:
                    sections.append(current)
                    current = None
                sections.append({"separator": True})
            elif current is None:
                preamble.append(entry)
            else:
                current["children"].append(entry)

        if current is not None:
            sections.append(current)

        for entry in preamble:
            self._render_preamble_entry(entry)

        for section in sections:
            if section.get("separator"):
                self._content_layout.addSpacing(8)
            else:
                self._render_section_card(section)

        self._content_layout.addStretch()


    def _render_preamble_entry(self, entry: dict):
        etype = entry.get("type", "item")
        if etype == "_loading":
            self._content_layout.addSpacing(56)
            wrap = QWidget()
            wrap.setStyleSheet("background:transparent;border:none;")
            wl = QVBoxLayout(wrap)
            wl.setAlignment(Qt.AlignCenter)
            wl.setSpacing(14)

            ic = QLabel("✦")
            ic.setFont(font(26))
            ic.setAlignment(Qt.AlignCenter)
            ic.setStyleSheet(
                f"color:{COLORS['accent']};background:transparent;border:none;"
            )
            wl.addWidget(ic)

            self._loading_lbl = QLabel(t("changelog.fetching", default="Fetching changelog"))
            self._loading_lbl.setFont(font(12))
            self._loading_lbl.setAlignment(Qt.AlignCenter)
            self._loading_lbl.setStyleSheet(
                f"color:{COLORS['text_secondary']};background:transparent;border:none;"
            )
            wl.addWidget(self._loading_lbl)
            self._content_layout.addWidget(wrap)

            self._loading_dots = 0
            self._loading_timer = QTimer(self)
            def _tick():
                self._loading_dots = (self._loading_dots + 1) % 4
                self._loading_lbl.setText(
                    t("changelog.fetching", default="Fetching changelog") + "." * self._loading_dots
                )
            self._loading_timer.timeout.connect(_tick)
            self._loading_timer.start(420)


    def _render_section_card(self, section: dict):
        self._content_layout.addSpacing(12)

        accent_c = QColor(COLORS['accent'])
        glow_color = f"rgba({accent_c.red()},{accent_c.green()},{accent_c.blue()},55)"
        glow_wrap = QFrame()
        glow_wrap.setObjectName("glowWrap")
        glow_wrap.setStyleSheet(f"""
            QFrame#glowWrap {{
                background-color: {glow_color};
                border-radius: 15px;
                border: none;
            }}
        """)
        glow_lay = QVBoxLayout(glow_wrap)
        glow_lay.setContentsMargins(5, 5, 5, 5)
        glow_lay.setSpacing(0)

        card = QFrame()
        card.setStyleSheet(f"""
            QFrame#sectionCard {{
                background-color: {COLORS['card_bg']};
                border-radius: 12px;
                border: 1px solid {COLORS['border']};
            }}
        """)
        card.setObjectName("sectionCard")
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(0, 0, 0, 0)
        card_lay.setSpacing(0)

        title_row = QFrame()
        title_row.setObjectName("titleRow")
        title_row.setStyleSheet(f"""
            QFrame#titleRow {{
                background: transparent;
                border: none;
                border-bottom: 1px solid {COLORS['border']};
            }}
        """)
        tr_lay = QHBoxLayout(title_row)
        tr_lay.setContentsMargins(16, 11, 16, 11)
        title_lbl = QLabel(section["title"]["text"])
        title_lbl.setFont(font(14, "bold"))
        title_lbl.setWordWrap(True)
        title_lbl.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;"
        )
        tr_lay.addWidget(title_lbl)
        card_lay.addWidget(title_row)

        if section["children"]:
            body = QWidget()
            body.setStyleSheet("background:transparent;border:none;")
            body_lay = QVBoxLayout(body)
            body_lay.setContentsMargins(12, 10, 12, 12)
            body_lay.setSpacing(6)

            for child in section["children"]:
                ctype = child.get("type", "item")
                ctext = child.get("text", "")

                if ctype == "subtitle":
                    lbl = QLabel(ctext.upper())
                    lbl.setFont(font(9, "bold"))
                    lbl.setWordWrap(True)
                    lbl.setStyleSheet(f"""
                        color: {COLORS['accent']};
                        background: transparent;
                        border: none;
                        letter-spacing: 1.5px;
                        padding-left: 2px;
                        padding-top: 2px;
                    """)
                    body_lay.addWidget(lbl)

                elif ctype == "item":
                    row = QFrame()
                    row.setStyleSheet(
                        f"background:{COLORS['frame_bg']};border-radius:7px;border:none;"
                    )
                    rl = QHBoxLayout(row)
                    rl.setContentsMargins(10, 7, 12, 7)
                    rl.setSpacing(8)

                    arrow = QLabel("›")
                    arrow.setFont(font(15, "bold"))
                    arrow.setStyleSheet(
                        f"color:{COLORS['accent']};background:transparent;border:none;"
                    )
                    arrow.setFixedWidth(10)
                    arrow.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
                    rl.addWidget(arrow)

                    item_lbl = QLabel(ctext)
                    item_lbl.setFont(font(12))
                    item_lbl.setWordWrap(True)
                    item_lbl.setStyleSheet(
                        f"color:{COLORS['text']};background:transparent;border:none;"
                    )
                    rl.addWidget(item_lbl, 1)
                    body_lay.addWidget(row)

                elif ctype == "note":
                    note_card = QFrame()
                    note_card.setStyleSheet(f"""
                        QFrame {{
                            background-color: {COLORS['frame_bg']};
                            border-radius: 7px;
                            border: none;
                        }}
                    """)
                    nl = QHBoxLayout(note_card)
                    nl.setContentsMargins(10, 8, 12, 8)
                    note_lbl = QLabel(f"💡  {ctext}")
                    note_lbl.setFont(font(11))
                    note_lbl.setWordWrap(True)
                    note_lbl.setStyleSheet(
                        f"color:{COLORS['text_secondary']};background:transparent;border:none;"
                    )
                    nl.addWidget(note_lbl)
                    body_lay.addWidget(note_card)

            card_lay.addWidget(body)

        glow_lay.addWidget(card)
        self._content_layout.addWidget(glow_wrap)


    def _update_remote_data(self, data: dict):
        self._version = data.get("version", self._version)
        self._date    = data.get("date", "")
        self._entries = list(data.get("entries", []))

        if self._sub_lbl is not None:
            sub_text = f"Version {self._version}"
            if self._date:
                sub_text += f"  ·  {self._date}"
            self._sub_lbl.setText(sub_text)

        self._translating = False
        if self._translate_btn:
            self._translate_btn.setText(
                "🌐  " + t("changelog.translate", default="Translate")
            )
            self._translate_btn.setEnabled(True)

        self._render_entries(self._entries)


    def _on_translate(self):
        if self._translating:
            return
        self._translating = True
        if self._translate_btn:
            self._translate_btn.setText(
                "⏳  " + t("changelog.translating", default="Translating…")
            )
            self._translate_btn.setEnabled(False)

        def _worker():
            target = _target_lang()
            out = []
            for entry in self._entries:
                if entry.get("type") == "separator" or not entry.get("text", "").strip():
                    out.append(entry)
                    continue
                try:
                    translated = _GT(source="en", target=target).translate(entry["text"])
                    out.append({**entry, "text": translated or entry["text"]})
                except Exception as _exc:
                    print(f"[WARNING] _worker: {type(_exc).__name__}: {_exc}")
                    out.append(entry)
            self._signals.done.emit(out)

        threading.Thread(target=_worker, daemon=True).start()

    def _apply_translation(self, entries: list):
        self._render_entries(entries)
        self._translating = False
        if self._translate_btn:
            self._translate_btn.setText(
                "✓  " + t("changelog.translated", default="Translated")
            )
            self._translate_btn.setEnabled(False)


    def _on_close(self):
        if not self._preview_mode:
            _mark_seen(self._version)
        self.accept()

    def show(self):
        self.exec()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._on_close()
        super().keyPressEvent(event)


def show_changelog_if_needed(
    parent: QWidget, version: str, *, force: bool = False
) -> bool:
    from core.changelog import get_changelog_for_version
    if not force and has_seen_changelog(version):
        return False
    data = get_changelog_for_version(version)
    if data is None:
        _mark_seen(version)
        return False
    ChangelogDialog(parent, data).show()
    return True


def show_changelog_browser(parent: QWidget, version: Optional[str] = None) -> None:
    from core.changelog import get_latest_changelog, get_changelog_for_version

    data = get_changelog_for_version(version) if version else None
    if data is None:
        data = get_latest_changelog()
    if data is None:
        print("[changelog] show_changelog_browser: no changelog entries available")
        return

    ChangelogDialog(parent, data, preview_mode=True, browsable=True).show()
