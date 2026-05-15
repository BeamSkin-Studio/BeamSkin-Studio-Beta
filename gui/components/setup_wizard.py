from __future__ import annotations
import os
import platform
from typing import Callable, Optional

from PySide6.QtCore    import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QWidget, QLineEdit, QFileDialog, QApplication,
    QStackedWidget, QSizePolicy,
)
from PySide6.QtGui import QPixmap

from gui.theme   import COLORS, font, drop_shadow, fade_in
from gui.widgets import AnimButton, GhostButton, HSeparator, Badge
from gui.icon_helper import set_window_icon

try:
    from core.localization import t, set_language, get_available_languages
except ImportError:
    def t(key, **kw): return key
    def set_language(lang): return True
    def get_available_languages():
        return {"en": {"name": "English", "native": "English", "flag": "🇬🇧"}}

print("[DEBUG] setup_wizard.py loaded (PySide6)")


# LANGUAGE ROW

class _LangRow(QFrame):
    selected = Signal(str)

    def __init__(self, code: str, info: dict, is_selected: bool, parent=None):
        print(f"[DEBUG] __init__() called")
        super().__init__(parent)
        self.code = code
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(60)
        self._apply(is_selected)

        row = QHBoxLayout(self)
        row.setContentsMargins(14, 8, 14, 8)
        row.setSpacing(12)

        flag = QLabel(info.get("flag", "🌐"))
        flag.setFont(font(24))
        flag.setStyleSheet("background:transparent;border:none;")
        row.addWidget(flag)

        names = QVBoxLayout()
        names.setSpacing(1)
        native = QLabel(info.get("native", info.get("name", code)))
        native.setFont(font(14, "bold"))
        tc = COLORS["accent_text"] if is_selected else COLORS["text"]
        native.setStyleSheet(f"color:{tc};background:transparent;border:none;")
        names.addWidget(native)

        if info.get("native") and info.get("native") != info.get("name"):
            eng = QLabel(info.get("name", ""))
            eng.setFont(font(11))
            tc2 = COLORS["accent_text"] if is_selected else COLORS["text_secondary"]
            eng.setStyleSheet(f"color:{tc2};background:transparent;border:none;")
            names.addWidget(eng)

        row.addLayout(names, 1)

        if is_selected:
            chk = QLabel("✓")
            chk.setFont(font(18, "bold"))
            chk.setStyleSheet(
                f"color:{COLORS['accent_text']};background:transparent;border:none;"
            )
            row.addWidget(chk)

    def _apply(self, active: bool):
        print(f"[DEBUG] _apply() called")
        if active:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {COLORS['accent']};
                    border-radius: 10px;
                    border: none;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {COLORS['card_bg']};
                    border-radius: 10px;
                    border: 1px solid {COLORS['border']};
                }}
                QFrame:hover {{
                    background-color: {COLORS['card_hover']};
                    border-color: {COLORS['accent']};
                }}
            """)

    def mousePressEvent(self, _event):
        print(f"[DEBUG] mousePressEvent() called")
        self.selected.emit(self.code)


# SETUP WIZARD DIALOG

class SetupWizard(QDialog):

    def __init__(self, parent: QWidget, colors: dict,
                 on_complete: Callable[[dict], None]):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Dialog)
        set_window_icon(self)
        self.setModal(True)
        self.setFixedSize(860, 760)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background:transparent;")

        self.colors      = colors
        self.on_complete = on_complete
        self.paths       = {"beamng_install": "", "mods_folder": ""}
        self._selected_lang = "en"

        # centre on parent / screen
        if parent:
            pg = parent.frameGeometry()
            self.move(pg.x() + (pg.width() - 860) // 2,
                      pg.y() + (pg.height() - 760) // 2)
        else:
            sg = QApplication.primaryScreen().geometry()
            self.move((sg.width() - 860) // 2, (sg.height() - 760) // 2)

        self._build()
        fade_in(self._card, 220)


    def _build(self):
        print(f"[DEBUG] _build() called")
        self._card = QFrame(self)
        self._card.setObjectName("wizardCard")
        self._card.setGeometry(0, 0, 860, 760)
        self._card.setStyleSheet(f"""
            #wizardCard {{
                background-color: {COLORS['frame_bg']};
                border-radius: 20px;
                border: 1px solid {COLORS['border']};
            }}
        """)
        drop_shadow(self._card, 36, (0, 10))

        root = QVBoxLayout(self._card)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # stacked pages
        self._stack = QStackedWidget()
        root.addWidget(self._stack, 1)

        self._page_lang  = self._build_language_page()
        self._page_paths = self._build_paths_page()
        self._stack.addWidget(self._page_lang)
        self._stack.addWidget(self._page_paths)
        self._stack.setCurrentIndex(0)

    # PAGE 1 — LANGUAGE

    def _build_language_page(self) -> QWidget:
        print(f"[DEBUG] _build_language_page() called")
        page = QWidget()
        page.setStyleSheet("background:transparent;")
        col = QVBoxLayout(page)
        col.setContentsMargins(36, 28, 36, 28)
        col.setSpacing(16)

        # header
        hdr = QVBoxLayout()
        hdr.setSpacing(6)

        logo_path = os.path.join("gui", "Icons", "BeamSkin_Studio_White.png")
        if os.path.exists(logo_path):
            logo_lbl = QLabel()
            px = QPixmap(logo_path).scaled(
                80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            logo_lbl.setPixmap(px)
            logo_lbl.setAlignment(Qt.AlignCenter)
            logo_lbl.setStyleSheet("background:transparent;border:none;")
            hdr.addWidget(logo_lbl)
        else:
            globe = QLabel("🌍")
            globe.setFont(font(48))
            globe.setAlignment(Qt.AlignCenter)
            globe.setStyleSheet("background:transparent;border:none;")
            hdr.addWidget(globe)

        title = QLabel(t("setup_wizard.title"))
        title.setFont(font(22, "bold"))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"color:{COLORS['text']};background:transparent;border:none;")
        hdr.addWidget(title)
        self._welcome_title = title

        sub = QLabel(t("language_selection.selection"))
        sub.setFont(font(13))
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet(
            f"color:{COLORS['text_secondary']};background:transparent;border:none;"
        )
        hdr.addWidget(sub)
        self._welcome_sub = sub
        col.addLayout(hdr)

        # search bar
        self._lang_search = QLineEdit()
        self._lang_search.setPlaceholderText(
            "🔍  " + t("language_selection.search")
        )
        self._lang_search.setMinimumHeight(38)
        self._lang_search.setFont(font(13))
        self._lang_search.setStyleSheet(f"""
            QLineEdit {{
                background:{COLORS['frame_bg']};
                color:{COLORS['text']};
                border:1px solid {COLORS['border']};
                border-radius:8px;
                padding:6px 12px;
                font-size:13px;
            }}
            QLineEdit:focus {{ border-color:{COLORS['border_focus']}; }}
        """)
        self._lang_search.textChanged.connect(self._filter_languages)
        col.addWidget(self._lang_search)

        # language list scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background:transparent; border:none; }}
            QScrollArea > QWidget > QWidget {{ background:transparent; }}
        """)
        self._lang_list_widget = QWidget()
        self._lang_list_widget.setStyleSheet("background:transparent;")
        self._lang_list_layout = QVBoxLayout(self._lang_list_widget)
        self._lang_list_layout.setContentsMargins(2, 2, 2, 2)
        self._lang_list_layout.setSpacing(5)
        scroll.setWidget(self._lang_list_widget)
        col.addWidget(scroll, 1)

        self._populate_languages("")

        # footer button
        col.addWidget(HSeparator())
        next_btn = AnimButton(
            t("language_selection.continue"),
            fg=COLORS["accent"], fg_hover=COLORS["accent_hover"],
            font_size=14, bold=True, padding="12px 32px",
        )
        next_btn.setMinimumHeight(46)
        next_btn.clicked.connect(self._go_to_paths)
        col.addWidget(next_btn)
        self._next_btn = next_btn

        return page

    def _populate_languages(self, query: str):
        print(f"[DEBUG] _populate_languages() called")
        # clear
        while self._lang_list_layout.count():
            item = self._lang_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        langs = get_available_languages()
        q = query.strip().lower()
        for code, info in sorted(langs.items(),
                                  key=lambda x: x[1].get("name", x[0])):
            if q and not any(
                q in s.lower()
                for s in (info.get("native", ""), info.get("name", ""), code)
            ):
                continue
            row = _LangRow(code, info, code == self._selected_lang)
            row.selected.connect(self._on_lang_selected)
            self._lang_list_layout.addWidget(row)

        self._lang_list_layout.addStretch()

    def _filter_languages(self, text: str):
        print(f"[DEBUG] _filter_languages() called")
        self._populate_languages(text)

    def _on_lang_selected(self, code: str):
        print(f"[DEBUG] _on_lang_selected: {code!r}")
        self._selected_lang = code
        set_language(code)
        self._populate_languages(self._lang_search.text())
        self._refresh_texts()

    def _refresh_texts(self):
        """Re-evaluate all t() calls and push updated strings into existing widgets."""
        self._welcome_title.setText(t("setup_wizard.title"))
        self._welcome_sub.setText(t("language_selection.selection"))
        self._lang_search.setPlaceholderText(
            "🔍  " + t("language_selection.search")
        )
        self._next_btn.setText(t("language_selection.continue"))

        self._paths_title_lbl.setText(t("setup_wizard.paths_title"))
        self._paths_sub_lbl.setText(t("setup_wizard.paths_desc"))
        self._back_btn.setText("←  " + t("common.back"))
        self._finish_btn.setText("✓  " + t("common.finish"))

        self._beamng_hdr_lbl.setText(
            f"{self._beamng_number}.  " + t("setup_wizard.beamng_install")
        )
        self._beamng_desc_lbl.setText(t("setup_wizard.beamng_description"))
        self._beamng_entry.setPlaceholderText(t("setup_wizard.no_path_selected"))
        self._beamng_browse_btn.setText(t("common.browse"))

        self._mods_hdr_lbl.setText(
            f"{self._mods_number}.  " + t("setup_wizard.mods_folder")
        )
        self._mods_desc_lbl.setText(t("setup_wizard.mods_description"))
        self._mods_entry.setPlaceholderText(t("setup_wizard.no_path_selected"))
        self._mods_browse_btn.setText(t("common.browse"))

    def _go_to_paths(self):
        set_language(self._selected_lang)
        try:
            from core.settings import app_settings, save_settings
            app_settings["language"] = self._selected_lang
            save_settings()
        except Exception:
            pass
        self._stack.setCurrentIndex(1)
        self._refresh_texts()

    # PAGE 2 — PATHS

    def _build_paths_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background:transparent;")
        col = QVBoxLayout(page)
        col.setContentsMargins(36, 28, 36, 28)
        col.setSpacing(16)

        # header
        hdr_lbl = QLabel(t("setup_wizard.paths_title"))
        hdr_lbl.setFont(font(20, "bold"))
        hdr_lbl.setAlignment(Qt.AlignCenter)
        hdr_lbl.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;"
        )
        col.addWidget(hdr_lbl)
        self._paths_title_lbl = hdr_lbl

        sub_lbl = QLabel(t("setup_wizard.paths_desc"))
        sub_lbl.setFont(font(13))
        sub_lbl.setAlignment(Qt.AlignCenter)
        sub_lbl.setWordWrap(True)
        sub_lbl.setStyleSheet(
            f"color:{COLORS['text_secondary']};background:transparent;border:none;"
        )
        col.addWidget(sub_lbl)
        self._paths_sub_lbl = sub_lbl
        col.addWidget(HSeparator())

        # scroll area for path sections
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background:transparent; border:none; }}
            QScrollArea > QWidget > QWidget {{ background:transparent; }}
        """)
        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        inner_col = QVBoxLayout(inner)
        inner_col.setContentsMargins(0, 0, 0, 0)
        inner_col.setSpacing(14)

        # BeamNG install section
        inner_col.addWidget(self._path_section(
            number="1",
            title=t("setup_wizard.beamng_install"),
            desc=t("setup_wizard.beamng_description"),
            attr="beamng",
            browse_cb=self._browse_beamng,
        ))

        # Mods folder section
        inner_col.addWidget(self._path_section(
            number="2",
            title=t("setup_wizard.mods_folder"),
            desc=t("setup_wizard.mods_description"),
            attr="mods",
            browse_cb=self._browse_mods,
        ))

        inner_col.addStretch()
        scroll.setWidget(inner)
        col.addWidget(scroll, 1)

        # footer buttons
        col.addWidget(HSeparator())
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        back_btn = GhostButton(
            "←  " + t("common.back"),
            font_size=13,
        )
        back_btn.setMinimumHeight(44)
        back_btn.clicked.connect(lambda: self._stack.setCurrentIndex(0))
        btn_row.addWidget(back_btn, 1)
        self._back_btn = back_btn

        finish_btn = AnimButton(
            "✓  " + t("common.finish"),
            fg=COLORS["accent"], fg_hover=COLORS["accent_hover"],
            font_size=13, bold=True, padding="12px 32px",
        )
        finish_btn.setMinimumHeight(44)
        finish_btn.setEnabled(False)
        finish_btn.clicked.connect(self._on_finish)
        btn_row.addWidget(finish_btn, 1)
        self._finish_btn = finish_btn
        col.addLayout(btn_row)

        return page

    def _path_section(
        self,
        number: str,
        title: str,
        desc: str,
        attr: str,
        browse_cb: Callable,
    ) -> QFrame:
        card = QFrame()
        card.setObjectName("pathSectionCard")
        card.setStyleSheet(f"""
            #pathSectionCard {{
                background-color: {COLORS['card_bg']};
                border-radius: 12px;
                border: 1px solid {COLORS['border']};
            }}
        """)
        inner = QVBoxLayout(card)
        inner.setContentsMargins(20, 16, 20, 16)
        inner.setSpacing(8)

        hdr = QLabel(f"{number}.  {title}")
        hdr.setFont(font(14, "bold"))
        hdr.setStyleSheet(f"color:{COLORS['text']};background:transparent;border:none;")
        inner.addWidget(hdr)

        d_lbl = QLabel(desc)
        d_lbl.setFont(font(12))
        d_lbl.setWordWrap(True)
        d_lbl.setStyleSheet(
            f"color:{COLORS['text_secondary']};background:transparent;border:none;"
        )
        inner.addWidget(d_lbl)

        entry_row = QHBoxLayout()
        entry_row.setSpacing(8)

        entry = QLineEdit()
        entry.setReadOnly(True)
        entry.setMinimumHeight(36)
        entry.setFont(font(12))
        entry.setPlaceholderText(t("setup_wizard.no_path_selected"))
        entry.setStyleSheet(f"""
            QLineEdit {{
                background:{COLORS['frame_bg']};
                color:{COLORS['text']};
                border:1px solid {COLORS['border']};
                border-radius:7px;
                padding:4px 10px;
                font-size:12px;
            }}
        """)
        entry_row.addWidget(entry, 1)

        browse_btn = AnimButton(
            t("common.browse"),
            fg=COLORS["accent"], fg_hover=COLORS["accent_hover"],
            font_size=12, bold=True, padding="6px 14px",
        )
        browse_btn.setFixedHeight(36)
        browse_btn.clicked.connect(browse_cb)
        entry_row.addWidget(browse_btn)
        inner.addLayout(entry_row)

        status = QLabel("")
        status.setFont(font(11))
        status.setStyleSheet("background:transparent;border:none;")
        inner.addWidget(status)

        setattr(self, f"_{attr}_entry",      entry)
        setattr(self, f"_{attr}_status",     status)
        setattr(self, f"_{attr}_hdr_lbl",    hdr)
        setattr(self, f"_{attr}_desc_lbl",   d_lbl)
        setattr(self, f"_{attr}_browse_btn", browse_btn)
        setattr(self, f"_{attr}_number",     number)
        return card


    def _browse_beamng(self):
        print(f"[DEBUG] _browse_beamng: opening BeamNG install folder dialog")
        init = self.paths.get("beamng_install") or ""
        if not init or not os.path.exists(init):
            if platform.system() == "Windows":
                init = r"C:\Program Files (x86)\Steam\steamapps\common"
            else:
                init = os.path.expanduser("~")

        path = QFileDialog.getExistingDirectory(
            self, t("setup_wizard.browse_beamng_title"), init
        )
        if not path:
            return

        self._beamng_entry.setText(path)
        if self._validate_beamng(path):
            self.paths["beamng_install"] = path
            self._beamng_status.setText(t("setup_wizard.beamng_valid"))
            self._beamng_status.setStyleSheet(
                f"color:{COLORS['success']};background:transparent;border:none;"
            )
        else:
            self.paths["beamng_install"] = ""
            self._beamng_status.setText(t("setup_wizard.beamng_invalid"))
            self._beamng_status.setStyleSheet(
                f"color:{COLORS['error']};background:transparent;border:none;"
            )
        self._check_finish_ready()

    def _browse_mods(self):
        print(f"[DEBUG] _browse_mods: opening mods folder dialog")
        init = self.paths.get("mods_folder") or ""
        if not init or not os.path.exists(init):
            if platform.system() == "Windows":
                init = os.path.expanduser(
                    r"~\AppData\Local\BeamNG\BeamNG.drive\current\mods"
                )
            else:
                init = os.path.expanduser("~")

        path = QFileDialog.getExistingDirectory(
            self, t("setup_wizard.browse_mods_title"), init
        )
        if not path:
            return

        self._mods_entry.setText(path)
        if os.path.isdir(path) and os.path.basename(path).lower() == "mods":
            self.paths["mods_folder"] = path
            self._mods_status.setText(t("setup_wizard.mods_valid"))
            self._mods_status.setStyleSheet(
                f"color:{COLORS['success']};background:transparent;border:none;"
            )
        else:
            self.paths["mods_folder"] = ""
            self._mods_status.setText(t("setup_wizard.mods_invalid"))
            self._mods_status.setStyleSheet(
                f"color:{COLORS['error']};background:transparent;border:none;"
            )
        self._check_finish_ready()


    def _validate_beamng(self, path: str) -> bool:
        print(f"[DEBUG] _validate_beamng() called")
        if not os.path.exists(path):
            return False
        sys = platform.system()
        if sys == "Windows":
            has_exe = (
                os.path.exists(os.path.join(path, "Bin64", "BeamNG.drive.x64.exe"))
                or os.path.exists(os.path.join(path, "Bin64", "BeamNG.drive.exe"))
            )
        else:
            has_exe = os.path.exists(os.path.join(path, "Bin64", "BeamNG.drive.x64"))
        has_content = os.path.isdir(os.path.join(path, "content"))
        return has_exe and has_content


    def _check_finish_ready(self):
        """Enable the Finish button only when both paths have been confirmed valid."""
        ready = bool(self.paths.get("beamng_install")) and bool(self.paths.get("mods_folder"))
        self._finish_btn.setEnabled(ready)

    def _on_finish(self):
        print(f"[DEBUG] _on_finish: wizard complete, paths={self.paths}")
        self.on_complete(self.paths)
        self.accept()

    def keyPressEvent(self, event):
        print(f"[DEBUG] keyPressEvent() called")
        # prevent Escape from closing without completing
        if event.key() == Qt.Key_Escape:
            return
        super().keyPressEvent(event)

    def show(self):
        print(f"[DEBUG] show() called")
        self.exec()


# PUBLIC HELPER  (same signature as before)

def show_setup_wizard(
    parent: QWidget,
    colors: dict,
    on_complete: Callable[[dict], None],
):
    wizard = SetupWizard(parent, colors, on_complete)
    wizard.show()


