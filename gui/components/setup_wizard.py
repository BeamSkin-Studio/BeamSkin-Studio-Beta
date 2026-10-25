from __future__ import annotations
import os
import sys
import platform
from typing import Callable

from PySide6.QtCore    import Qt
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QFrame, QWidget, QLineEdit,
    QFileDialog, QApplication, QStackedWidget,
)
from PySide6.QtGui import QPixmap

from gui.theme import COLORS, font
from gui.components.dialog_kit import (
    DialogShell, LanguageRow, StatusLabel, make_panel, make_scroll,
    body_label, primary_button, outline_button, input_qss, lbl_qss, divider,
)

try:
    from core.localization import t, set_language, get_available_languages
except ImportError as _exc:
    print(f"[DEBUG] setup_wizard.py: import failed ({_exc}), using fallback")
    def t(key, **kw):
        return kw.get("default", key)
    def set_language(lang):
        return True
    def get_available_languages():
        return {'en': {'name': 'English', 'native': 'English', 'flag': '🇬🇧'}}

try:
    from core.settings import get_bundle_path, get_data_dir, set_data_dir
except ImportError as _exc:
    print(f"[DEBUG] setup_wizard.py: import failed ({_exc}), using fallback")
    def get_bundle_path():
        return os.getcwd()
    def get_data_dir():
        return os.path.join(os.path.expanduser('~'), 'BeamSkinStudio')
    def set_data_dir(new_dir, migrate=True):
        return True

_LangRow = LanguageRow


class SetupWizard(DialogShell):
    def __init__(self, parent: QWidget, colors: dict,
                 on_complete: Callable[[dict], None]):
        super().__init__(
            parent,
            t("setup_wizard.title", default="Welcome to BeamSkin Studio"),
            780, 720,
            subtitle="1 / 2",
            escape_closes=False,
            body_margins=(0, 0, 0, 0),
        )
        self.colors      = colors
        self.on_complete = on_complete
        self.paths       = {
            "beamng_install": "",
            "mods_folder":    "",
            "data_folder":    get_data_dir(),
        }
        self._selected_lang  = "en"
        self._setup_finished = False

        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background:transparent;")
        self._page_lang  = self._build_language_page()
        self._page_paths = self._build_paths_page()
        self._stack.addWidget(self._page_lang)
        self._stack.addWidget(self._page_paths)
        self._stack.setCurrentIndex(0)
        self.body.addWidget(self._stack, 1)

    def _page_shell(self):
        page = QWidget()
        page.setStyleSheet("background:transparent;")
        col = QVBoxLayout(page)
        col.setContentsMargins(26, 20, 26, 22)
        col.setSpacing(14)
        return page, col

    def _build_language_page(self) -> QWidget:
        page, col = self._page_shell()

        hdr = QHBoxLayout()
        hdr.setSpacing(14)
        logo_path = os.path.join(get_bundle_path(), "gui", "Icons", "BeamSkin_Studio_White.png")
        if os.path.exists(logo_path):
            logo_lbl = QLabel()
            logo_lbl.setPixmap(QPixmap(logo_path).scaled(
                56, 56, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            logo_lbl.setStyleSheet("background:transparent;border:none;")
            hdr.addWidget(logo_lbl)
        txt = QVBoxLayout()
        txt.setSpacing(2)
        self._welcome_title = QLabel(t("setup_wizard.title"))
        self._welcome_title.setFont(font(18, "bold"))
        self._welcome_title.setStyleSheet(lbl_qss())
        txt.addWidget(self._welcome_title)
        self._welcome_sub = body_label(t("language_selection.selection"), size=12)
        txt.addWidget(self._welcome_sub)
        hdr.addLayout(txt, 1)
        col.addLayout(hdr)

        self._lang_search = QLineEdit()
        self._lang_search.setPlaceholderText("🔍  " + t("language_selection.search"))
        self._lang_search.setMinimumHeight(38)
        self._lang_search.setFont(font(12))
        self._lang_search.setClearButtonEnabled(True)
        self._lang_search.setStyleSheet(input_qss())
        self._lang_search.textChanged.connect(self._filter_languages)
        col.addWidget(self._lang_search)

        self._lang_list_widget = QWidget()
        self._lang_list_layout = QVBoxLayout(self._lang_list_widget)
        self._lang_list_layout.setContentsMargins(0, 0, 4, 0)
        self._lang_list_layout.setSpacing(6)
        col.addWidget(make_scroll(self._lang_list_widget), 1)
        self._populate_languages("")

        col.addWidget(divider())
        self._next_btn = primary_button(t("language_selection.continue"), height=44, font_size=14)
        self._next_btn.clicked.connect(self._go_to_paths)
        col.addWidget(self._next_btn)
        return page

    def _populate_languages(self, query: str):
        while self._lang_list_layout.count():
            item = self._lang_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        q = query.strip().lower()
        for code, info in sorted(get_available_languages().items(),
                                 key=lambda x: x[1].get("name", x[0])):
            if q and not any(q in s.lower()
                             for s in (info.get("native", ""), info.get("name", ""), code)):
                continue
            row = LanguageRow(code, info, code == self._selected_lang)
            row.selected.connect(self._on_lang_selected)
            self._lang_list_layout.addWidget(row)
        self._lang_list_layout.addStretch()

    def _filter_languages(self, text: str):
        self._populate_languages(text)

    def _on_lang_selected(self, code: str):
        print(f"[DEBUG] _on_lang_selected: {code!r}")
        self._selected_lang = code
        set_language(code)
        self._populate_languages(self._lang_search.text())
        self._refresh_texts()

    def _refresh_texts(self):
        self.set_title(t("setup_wizard.title"))
        self._welcome_title.setText(t("setup_wizard.title"))
        self._welcome_sub.setText(t("language_selection.selection"))
        self._lang_search.setPlaceholderText("🔍  " + t("language_selection.search"))
        self._next_btn.setText(t("language_selection.continue"))

        self._paths_title_lbl.setText(t("setup_wizard.paths_title"))
        self._paths_sub_lbl.setText(t("setup_wizard.paths_desc"))
        self._back_btn.setText("←  " + t("common.back"))
        self._finish_btn.setText("✓  " + t("common.finish"))

        self._beamng_hdr_lbl.setText(t("setup_wizard.beamng_install"))
        self._beamng_desc_lbl.setText(t("setup_wizard.beamng_description"))
        self._beamng_entry.setPlaceholderText(t("setup_wizard.no_path_selected"))
        self._beamng_browse_btn.setText(t("common.browse"))

        self._mods_hdr_lbl.setText(t("setup_wizard.mods_folder"))
        self._mods_desc_lbl.setText(t("setup_wizard.mods_description"))
        self._mods_entry.setPlaceholderText(t("setup_wizard.no_path_selected"))
        self._mods_browse_btn.setText(t("common.browse"))

    def _go_to_paths(self):
        set_language(self._selected_lang)
        try:
            from core.settings import app_settings, save_settings
            app_settings["language"] = self._selected_lang
            save_settings()
        except Exception as _exc:
            print(f"[WARNING] _go_to_paths: {type(_exc).__name__}: {_exc}")
        self._goto(1)
        self._refresh_texts()

    def _goto(self, index: int):
        self._stack.setCurrentIndex(index)
        self.set_subtitle(f"{index + 1} / 2")

    def _build_paths_page(self) -> QWidget:
        page, col = self._page_shell()

        self._paths_title_lbl = QLabel(t("setup_wizard.paths_title"))
        self._paths_title_lbl.setFont(font(18, "bold"))
        self._paths_title_lbl.setStyleSheet(lbl_qss())
        col.addWidget(self._paths_title_lbl)

        self._paths_sub_lbl = body_label(t("setup_wizard.paths_desc"), size=12)
        col.addWidget(self._paths_sub_lbl)

        inner = QWidget()
        inner_col = QVBoxLayout(inner)
        inner_col.setContentsMargins(0, 0, 4, 0)
        inner_col.setSpacing(12)

        inner_col.addWidget(self._path_section(
            number="1", title=t("setup_wizard.beamng_install"),
            desc=t("setup_wizard.beamng_description"),
            attr="beamng", browse_cb=self._browse_beamng,
        ))
        inner_col.addWidget(self._path_section(
            number="2", title=t("setup_wizard.mods_folder"),
            desc=t("setup_wizard.mods_description"),
            attr="mods", browse_cb=self._browse_mods,
        ))
        data_section = self._path_section(
            number="3",
            title=t("setup_wizard.data_folder", default="BeamSkin Studio Data Folder"),
            desc=t(
                "setup_wizard.data_folder_desc",
                default="Where your added vehicles, projects, and settings are stored. "
                        "The default location works for most people — only change this "
                        "if you want your data on a different drive.",
            ),
            attr="data", browse_cb=self._browse_data,
        )
        self._data_entry.setReadOnly(False)
        self._data_entry.setText(self.paths["data_folder"])
        inner_col.addWidget(data_section)
        inner_col.addStretch()
        col.addWidget(make_scroll(inner), 1)

        col.addWidget(divider())
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self._back_btn = outline_button("←  " + t("common.back"), height=44)
        self._back_btn.clicked.connect(lambda: self._goto(0))
        btn_row.addWidget(self._back_btn, 1)

        self._finish_btn = primary_button("✓  " + t("common.finish"), height=44, font_size=14)
        self._finish_btn.setEnabled(False)
        self._finish_btn.clicked.connect(self._on_finish)
        btn_row.addWidget(self._finish_btn, 2)
        col.addLayout(btn_row)
        return page

    def _path_section(self, number: str, title: str, desc: str, attr: str,
                      browse_cb: Callable) -> QFrame:
        card, inner = make_panel(f"pathSection_{attr}", margins=(16, 14, 16, 14), spacing=8)

        top = QHBoxLayout()
        top.setSpacing(10)
        step = QLabel(number)
        step.setFixedSize(22, 22)
        step.setAlignment(Qt.AlignCenter)
        step.setFont(font(10, "bold"))
        step.setStyleSheet(f"""
            QLabel {{
                background:{COLORS['accent']}; color:{COLORS['accent_text']};
                border:none; border-radius:6px;
            }}
        """)
        top.addWidget(step)
        hdr = QLabel(title)
        hdr.setFont(font(13, "bold"))
        hdr.setStyleSheet(lbl_qss())
        top.addWidget(hdr, 1)
        inner.addLayout(top)

        d_lbl = body_label(desc, size=11)
        inner.addWidget(d_lbl)

        entry_row = QHBoxLayout()
        entry_row.setSpacing(8)
        entry = QLineEdit()
        entry.setReadOnly(True)
        entry.setMinimumHeight(36)
        entry.setFont(font(12))
        entry.setPlaceholderText(t("setup_wizard.no_path_selected"))
        entry.setStyleSheet(input_qss())
        entry_row.addWidget(entry, 1)

        browse_btn = outline_button(t("common.browse"), height=36, font_size=12)
        browse_btn.clicked.connect(browse_cb)
        entry_row.addWidget(browse_btn)
        inner.addLayout(entry_row)

        status = StatusLabel()
        inner.addWidget(status)

        setattr(self, f"_{attr}_entry",      entry)
        setattr(self, f"_{attr}_status",     status)
        setattr(self, f"_{attr}_hdr_lbl",    hdr)
        setattr(self, f"_{attr}_desc_lbl",   d_lbl)
        setattr(self, f"_{attr}_browse_btn", browse_btn)
        setattr(self, f"_{attr}_number",     number)
        return card

    def _browse_beamng(self):
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


    def _browse_data(self):
        init = self.paths.get("data_folder") or get_data_dir()
        if not os.path.exists(init):
            init = os.path.expanduser("~")

        path = QFileDialog.getExistingDirectory(
            self, t("setup_wizard.browse_data_title", default="Choose Data Folder"), init
        )
        if not path:
            return

        self._data_entry.setText(path)
        if os.path.isdir(path) and os.access(path, os.W_OK):
            self.paths["data_folder"] = path
            self._data_status.setText(
                t("setup_wizard.data_valid", default="✓ Folder is writable")
            )
            self._data_status.setStyleSheet(
                f"color:{COLORS['success']};background:transparent;border:none;"
            )
        else:
            self.paths["data_folder"] = get_data_dir()
            self._data_entry.setText(self.paths["data_folder"])
            self._data_status.setText(
                t("setup_wizard.data_invalid", default="✗ Folder is not writable — reverted to default")
            )
            self._data_status.setStyleSheet(
                f"color:{COLORS['error']};background:transparent;border:none;"
            )
        self._check_finish_ready()


    def _validate_beamng(self, path: str) -> bool:
        if not os.path.exists(path):
            return False
        sys = platform.system()
        if sys == "Windows":
            has_exe = (
                os.path.exists(os.path.join(path, "Bin64", "BeamNG.drive.x64.exe"))
                or os.path.exists(os.path.join(path, "Bin64", "BeamNG.drive.exe"))
            )
        elif sys == "Darwin":
            has_exe = path.endswith(".app") or os.path.exists(os.path.join(path, "BeamNG.drive"))
        else:
            has_exe = any(
                os.path.exists(os.path.join(path, p))
                for p in ["BeamNG.drive.x64", "Bin64/BeamNG.drive.x64", "BeamNG"]
            )
        has_content = os.path.isdir(os.path.join(path, "content"))
        return has_exe and has_content


    def _check_finish_ready(self):
        ready = bool(self.paths.get("beamng_install")) and bool(self.paths.get("mods_folder"))
        self._finish_btn.setEnabled(ready)

    def _on_finish(self):
        print(f"[DEBUG] _on_finish: wizard complete, paths={self.paths}")

        chosen_data_dir = self.paths.get("data_folder") or get_data_dir()
        try:
            set_data_dir(chosen_data_dir, migrate=True)
        except Exception as e:
            print(f"[WARNING] setup_wizard: could not apply data folder: {e}")

        self._setup_finished = True
        self.on_complete(self.paths)
        self.accept()

    def closeEvent(self, event):
        if self._setup_finished:
            event.accept()
            return

        print("[DEBUG] closeEvent: setup wizard closed before completion — quitting application")
        event.accept()
        app = QApplication.instance()
        if app is not None:
            app.quit()
        else:
            sys.exit(1)

    def show(self):
        self.exec()


def show_setup_wizard(
    parent: QWidget,
    colors: dict,
    on_complete: Callable[[dict], None],
) -> bool:
    wizard = SetupWizard(parent, colors, on_complete)
    wizard.show()
    return wizard._setup_finished
