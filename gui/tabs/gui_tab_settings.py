from __future__ import annotations
from typing import Dict, Callable

from PySide6.QtCore    import Qt
from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QCheckBox,
    QScrollArea, QVBoxLayout, QHBoxLayout, QMessageBox,
)

from gui.theme   import COLORS, font
from gui.state   import state
from gui.widgets import ToggleSwitch

try:
    from core.localization import t, set_language, get_available_languages, get_current_language
except ImportError:
    def t(key, **kw): return key
    def set_language(lang): return False
    def get_available_languages(): return {}
    def get_current_language(): return "en_US"

try:
    from utils.debug import toggle_debug_mode
except ImportError:
    toggle_debug_mode = None

try:
    from utils.file_logger import start_file_logging, stop_file_logging, is_file_logging_active
    from core.settings import (
        is_file_logging_enabled, set_file_logging_enabled,
        is_file_logging_append, set_file_logging_append,
    )
except ImportError:
    start_file_logging = stop_file_logging = is_file_logging_active = None
    is_file_logging_enabled = lambda: False
    set_file_logging_enabled = lambda v: None
    is_file_logging_append = lambda: False
    set_file_logging_append = lambda v: None


class _ThemeToggle(QWidget):
    _BTN_W = 100
    _BTN_H = 34

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setFixedHeight(self._BTN_H)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        self._dark_btn  = QPushButton("🌙  Dark")
        self._light_btn = QPushButton("☀️  Light")

        for btn in (self._dark_btn, self._light_btn):
            btn.setFixedSize(self._BTN_W, self._BTN_H)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFont(font(13, "bold"))
            row.addWidget(btn)

        self._dark_btn.clicked.connect(lambda: self._select("dark"))
        self._light_btn.clicked.connect(lambda: self._select("light"))

        self._refresh_styles(state.theme_mode)

    def _select(self, mode: str) -> None:
        if mode == state.theme_mode:
            return
        state.set_theme(mode)
        self._refresh_styles(mode)

    def _refresh_styles(self, active: str) -> None:
        def _active_style(left: bool) -> str:
            r_left  = "8px 0 0 8px"
            r_right = "0 8px 8px 0"
            radius  = r_left if left else r_right
            return f"""
                QPushButton {{
                    background-color: {COLORS['accent']};
                    color: {COLORS['accent_text']};
                    border-radius: {radius};
                    border: 1px solid {COLORS['accent']};
                    font-size: 13px;
                    font-weight: bold;
                }}
            """

        def _inactive_style(left: bool) -> str:
            r_left  = "8px 0 0 8px"
            r_right = "0 8px 8px 0"
            radius  = r_left if left else r_right
            return f"""
                QPushButton {{
                    background-color: {COLORS['card_bg']};
                    color: {COLORS['text_secondary']};
                    border-radius: {radius};
                    border: 1px solid {COLORS['border']};
                    font-size: 13px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: {COLORS['card_hover']};
                    color: {COLORS['text']};
                }}
            """

        if active == "dark":
            self._dark_btn.setStyleSheet(_active_style(left=True))
            self._light_btn.setStyleSheet(_inactive_style(left=False))
        else:
            self._dark_btn.setStyleSheet(_inactive_style(left=True))
            self._light_btn.setStyleSheet(_active_style(left=False))


class SettingsTab(QWidget):
    def __init__(
        self,
        parent: QWidget,
        main_container=None,
        menu_frame=None,
        menu_buttons: Dict = None,
        switch_view_callback: Callable = None,
        notification_callback: Callable = None,
        **_kwargs,
    ):
        super().__init__(parent)
        self.setStyleSheet(f"background:{COLORS['app_bg']};")

        self._notify_cb          = notification_callback
        self._menu_buttons       = menu_buttons or {}
        self._switch_view_cb     = switch_view_callback

        if not hasattr(state, 'texture_previews_enabled'):
            state.texture_previews_enabled = True

        self._section_labels: list = []

        self._setup_ui()


    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ background:{COLORS['app_bg']};border:none; }}")
        outer.addWidget(scroll)

        page = QWidget()
        page.setStyleSheet(f"background:{COLORS['app_bg']};")
        col = QVBoxLayout(page)
        col.setContentsMargins(20, 20, 20, 20)
        col.setSpacing(20)
        scroll.setWidget(page)

        self._main_title = QLabel(t("settings.title", default="Settings"))
        self._main_title.setFont(font(20, "bold"))
        self._main_title.setStyleSheet(f"color:{COLORS['text']};background:transparent;border:none;")
        col.addWidget(self._main_title)

        try:
            from gui.components.path_configuration import PathConfigurationSection
            self._path_section = PathConfigurationSection(
                page, notification_callback=self.show_notification
            )
            self._path_section.setObjectName("pathConfigSection")
            self._path_section.setStyleSheet(
                self._path_section.styleSheet() +
                "\n#pathConfigSection { border: none; }"
            )
            col.addWidget(self._path_section)
        except Exception as e:
            print(f"[WARNING] PathConfigurationSection unavailable: {e}")
            path_stub = self._card(page)
            stub_lbl  = QLabel("📁  Path configuration — unavailable in this build")
            stub_lbl.setFont(font(13))
            stub_lbl.setStyleSheet(f"color:{COLORS['text_secondary']};background:transparent;border:none;")
            path_stub.layout().addWidget(stub_lbl)
            col.addWidget(path_stub)

        appearance_card = self._card(page)
        a_col = appearance_card.layout()

        self._appearance_title = self._section_title(
            t("settings.appearance", default="Appearance"), a_col
        )

        theme_row = QHBoxLayout()
        theme_row.setSpacing(12)

        self._theme_label = QLabel(t("settings.theme", default="Theme:"))
        self._theme_label.setFont(font(13, "bold"))
        self._theme_label.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;"
        )
        theme_row.addWidget(self._theme_label)

        self._theme_toggle = _ThemeToggle(appearance_card)
        theme_row.addWidget(self._theme_toggle)
        theme_row.addStretch(1)
        a_col.addLayout(theme_row)

        lang_row = QHBoxLayout()
        self._lang_label = QLabel(t("settings.language", default="Language:"))
        self._lang_label.setFont(font(13, "bold"))
        self._lang_label.setStyleSheet(f"color:{COLORS['text']};background:transparent;border:none;")
        lang_row.addWidget(self._lang_label)

        available = get_available_languages()
        current   = get_current_language()
        lang_info = available.get(current, {"native": "English"})
        self._lang_btn = QPushButton(lang_info.get("native", "English"))
        self._lang_btn.setFont(font(13))
        self._lang_btn.setFixedSize(200, 34)
        self._lang_btn.setCursor(Qt.PointingHandCursor)
        self._lang_btn.setStyleSheet(self._lang_btn_style())
        self._lang_btn.clicked.connect(self._open_language_selector)
        lang_row.addWidget(self._lang_btn)
        lang_row.addStretch(1)
        a_col.addLayout(lang_row)

        preview_row = QHBoxLayout()
        preview_row.setSpacing(12)
        self._preview_label = QLabel(t("settings.texture_previews", default="Texture Previews (.dds / .png):"))
        self._preview_label.setFont(font(13, "bold"))
        self._preview_label.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;"
        )
        preview_row.addWidget(self._preview_label)
        self._preview_toggle = ToggleSwitch()
        self._preview_toggle.setChecked(getattr(state, 'texture_previews_enabled', True))
        self._preview_toggle.stateChanged.connect(self._on_texture_previews_toggled)
        preview_row.addWidget(self._preview_toggle)
        preview_row.addStretch(1)
        a_col.addLayout(preview_row)

        self._preview_desc = QLabel(
            t("settings.texture_previews_desc",
              default="Show image previews when selecting .dds or .png textures. "
                      "Disable for faster performance with very large files.")
        )
        self._preview_desc.setFont(font(11))
        self._preview_desc.setWordWrap(True)
        self._preview_desc.setStyleSheet(
            f"color:{COLORS['text_secondary']};background:transparent;border:none;"
        )
        a_col.addWidget(self._preview_desc)

        col.addWidget(appearance_card)

        advanced_card = self._card(page)
        adv_col = advanced_card.layout()

        self._advanced_title = self._section_title(
            t("settings.advanced", default="Advanced"), adv_col
        )

        self._debug_checkbox = QCheckBox(t("settings.debug_mode", default="Debug Mode"))
        self._debug_checkbox.setFont(font(13, "bold"))
        self._debug_checkbox.setStyleSheet(f"color:{COLORS['text']};background:transparent;border:none;")
        self._debug_checkbox.toggled.connect(self._on_debug_toggled)
        adv_col.addWidget(self._debug_checkbox)

        self._debug_desc = QLabel(
            t("settings.debug_mode_desc",
              default="Opens a debug console window showing application logs.")
        )
        self._debug_desc.setFont(font(13))
        self._debug_desc.setWordWrap(True)
        self._debug_desc.setStyleSheet(
            f"color:{COLORS['text_secondary']};background:transparent;border:none;padding-left:22px;"
        )
        adv_col.addWidget(self._debug_desc)

        self._file_log_checkbox = QCheckBox(
            t("settings.file_logging", default="Log to File")
        )
        self._file_log_checkbox.setFont(font(13, "bold"))
        self._file_log_checkbox.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;"
        )
        self._file_log_checkbox.setChecked(is_file_logging_enabled())
        self._file_log_checkbox.toggled.connect(self._on_file_logging_toggled)
        adv_col.addWidget(self._file_log_checkbox)

        self._file_log_desc = QLabel(
            t("settings.file_logging_desc",
              default="Writes all application logs to data/app_log.txt on disk.")
        )
        self._file_log_desc.setFont(font(13))
        self._file_log_desc.setWordWrap(True)
        self._file_log_desc.setStyleSheet(
            f"color:{COLORS['text_secondary']};background:transparent;border:none;padding-left:22px;"
        )
        adv_col.addWidget(self._file_log_desc)

        self._file_log_append_checkbox = QCheckBox(
            t("settings.file_logging_append", default="Append to Existing Log")
        )
        self._file_log_append_checkbox.setFont(font(13))
        self._file_log_append_checkbox.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;padding-left:22px;"
        )
        self._file_log_append_checkbox.setChecked(is_file_logging_append())
        self._file_log_append_checkbox.setEnabled(is_file_logging_enabled())
        self._file_log_append_checkbox.toggled.connect(self._on_file_logging_append_toggled)
        adv_col.addWidget(self._file_log_append_checkbox)

        self._file_log_append_desc = QLabel(
            t("settings.file_logging_append_desc",
              default="On: new logs are dated and added on top of the existing file. "
                      "Off: each launch overwrites the log file with a fresh one.")
        )
        self._file_log_append_desc.setFont(font(13))
        self._file_log_append_desc.setWordWrap(True)
        self._file_log_append_desc.setStyleSheet(
            f"color:{COLORS['text_secondary']};background:transparent;border:none;padding-left:22px;"
        )
        adv_col.addWidget(self._file_log_append_desc)

        self._testing_checkbox = QCheckBox("🧪  Developer Testing Mode")
        self._testing_checkbox.setFont(font(13, "bold"))
        self._testing_checkbox.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;"
        )
        self._testing_checkbox.setChecked(state.testing_mode)
        self._testing_checkbox.toggled.connect(self._on_testing_toggled)
        adv_col.addWidget(self._testing_checkbox)

        self._testing_desc = QLabel(
            "Adds an 'Add All Vehicles' button to the sidebar vehicle list, and "
            "broadcasts any skin added in the Generator to every vehicle currently "
            "in the project.  For developer use only."
        )
        self._testing_desc.setFont(font(13))
        self._testing_desc.setWordWrap(True)
        self._testing_desc.setStyleSheet(
            f"color:{COLORS['text_secondary']};background:transparent;border:none;padding-left:22px;"
        )
        adv_col.addWidget(self._testing_desc)

        self._confirm_save_checkbox = QCheckBox(
            t("settings.confirm_on_save", default="💾  Confirm Before Saving")
        )
        self._confirm_save_checkbox.setFont(font(13, "bold"))
        self._confirm_save_checkbox.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;"
        )
        self._confirm_save_checkbox.setChecked(state.confirm_on_save)
        self._confirm_save_checkbox.toggled.connect(self._on_confirm_save_toggled)
        adv_col.addWidget(self._confirm_save_checkbox)

        self._confirm_save_desc = QLabel(
            t("settings.confirm_on_save_desc", default=(
                "Shows a confirmation dialog every time you save a project, naming "
                "the file that will be overwritten. Turn this off if you'd rather "
                "save without being asked each time."
            ))
        )
        self._confirm_save_desc.setFont(font(13))
        self._confirm_save_desc.setWordWrap(True)
        self._confirm_save_desc.setStyleSheet(
            f"color:{COLORS['text_secondary']};background:transparent;border:none;padding-left:22px;"
        )
        adv_col.addWidget(self._confirm_save_desc)

        col.addWidget(advanced_card)

        updates_card = self._card(page)
        upd_col = updates_card.layout()

        self._updates_title = self._section_title(
            t("settings.updates", default="Updates"), upd_col
        )

        ver_row = QHBoxLayout()
        self._ver_label = QLabel(t("settings.current_version", default="Current version:"))
        self._ver_label.setFont(font(13, "bold"))
        self._ver_label.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;"
        )
        ver_row.addWidget(self._ver_label)

        try:
            from core.updater import CURRENT_VERSION as _cv
        except Exception:
            _cv = "unknown"
        self._ver_value = QLabel(_cv)
        self._ver_value.setFont(font(13))
        self._ver_value.setStyleSheet(
            f"color:{COLORS['text_secondary']};background:transparent;border:none;"
        )
        ver_row.addWidget(self._ver_value)
        ver_row.addStretch(1)
        upd_col.addLayout(ver_row)

        check_row = QHBoxLayout()
        check_row.setSpacing(10)
        self._check_update_btn = QPushButton(
            t("settings.check_for_updates", default="🔍  Check for Updates")
        )
        self._check_update_btn.setFont(font(13, "bold"))
        self._check_update_btn.setFixedHeight(40)
        self._check_update_btn.setCursor(Qt.PointingHandCursor)
        self._check_update_btn.setStyleSheet(self._primary_btn_style())
        self._check_update_btn.clicked.connect(self._on_check_for_updates)
        check_row.addWidget(self._check_update_btn)

        self._changelog_btn = QPushButton(
            t("settings.view_changelog", default="📜  Changelog History")
        )
        self._changelog_btn.setFont(font(13, "bold"))
        self._changelog_btn.setFixedHeight(40)
        self._changelog_btn.setCursor(Qt.PointingHandCursor)
        self._changelog_btn.setStyleSheet(self._secondary_btn_style())
        self._changelog_btn.clicked.connect(self._on_view_changelog)
        check_row.addWidget(self._changelog_btn)

        check_row.addStretch(1)
        upd_col.addLayout(check_row)

        self._skip_row = QHBoxLayout()
        self._skip_row.setSpacing(8)
        self._skip_lbl = QLabel("")
        self._skip_lbl.setFont(font(12))
        self._skip_lbl.setStyleSheet(
            f"color:{COLORS['text_secondary']};background:transparent;border:none;"
        )
        self._skip_clear_btn = QPushButton(
            t("settings.clear_skipped", default="Clear")
        )
        self._skip_clear_btn.setFont(font(11))
        self._skip_clear_btn.setCursor(Qt.PointingHandCursor)
        self._skip_clear_btn.setFlat(True)
        self._skip_clear_btn.setStyleSheet(f"""
            QPushButton {{
                color:{COLORS['accent']};
                background:transparent;
                border:none;
                text-decoration:underline;
                padding:0;
            }}
            QPushButton:hover {{ color:{COLORS.get('accent_hover', COLORS['accent'])}; }}
        """)
        self._skip_clear_btn.clicked.connect(self._on_clear_skipped_version)
        self._skip_row.addWidget(self._skip_lbl)
        self._skip_row.addWidget(self._skip_clear_btn)
        self._skip_row.addStretch(1)

        skip_container = QWidget()
        skip_container.setStyleSheet("background:transparent;border:none;")
        skip_container.setLayout(self._skip_row)
        self._skip_container = skip_container
        upd_col.addWidget(skip_container)

        self._refresh_skip_indicator()

        col.addWidget(updates_card)

        col.addStretch(1)


    def _primary_btn_style(self) -> str:
        return f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {COLORS['accent']},
                    stop:1 {COLORS.get('accent_hover', COLORS['accent'])});
                color: white;
                border: none;
                border-radius: 10px;
                padding: 0 20px;
            }}
            QPushButton:hover {{
                background: {COLORS.get('accent_hover', COLORS['accent'])};
            }}
            QPushButton:pressed {{
                background: {COLORS.get('accent_dim', COLORS['accent'])};
            }}
            QPushButton:disabled {{
                background: {COLORS['border']};
                color: {COLORS['text_secondary']};
            }}
        """

    def _secondary_btn_style(self) -> str:
        return f"""
            QPushButton {{
                background:{COLORS['card_bg']};
                color:{COLORS['text']};
                border:1px solid {COLORS['border']};
                border-radius:10px;
                padding:0 20px;
            }}
            QPushButton:hover {{
                background:{COLORS.get('card_hover', COLORS['card_bg'])};
                border-color:{COLORS['accent']};
                color:{COLORS['accent']};
            }}
        """

    def _on_check_for_updates(self):
        print("[DEBUG] SettingsTab._on_check_for_updates: triggered by user")
        self._check_update_btn.setEnabled(False)
        self._check_update_btn.setText(
            t("settings.checking_updates", default="⏳  Checking…")
        )

        def _done():
            self._check_update_btn.setEnabled(True)
            self._check_update_btn.setText(
                t("settings.check_for_updates", default="🔍  Check for Updates")
            )
            self._refresh_skip_indicator()

        try:
            from core.updater import check_for_updates_manual
            check_for_updates_manual(on_done=_done)
        except Exception as e:
            print(f"[WARNING] check_for_updates_manual unavailable: {e}")
            self.show_notification("error", f"Update check failed: {e}")
            _done()

    def _on_view_changelog(self):
        print("[DEBUG] SettingsTab._on_view_changelog: opening changelog history")
        try:
            from gui.components.changelog_dialog import show_changelog_browser
            show_changelog_browser(self)
        except Exception as e:
            print(f"[WARNING] show_changelog_browser unavailable: {e}")
            self.show_notification("error", f"Could not open changelog: {e}")

    def _on_clear_skipped_version(self):
        print("[DEBUG] SettingsTab._on_clear_skipped_version: clearing skipped version")
        try:
            from core.updater import set_skipped_version
            set_skipped_version("")
        except Exception as e:
            print(f"[WARNING] set_skipped_version unavailable: {e}")
        self._refresh_skip_indicator()
        self.show_notification(
            "success",
            t("settings.skipped_cleared", default="Skipped version cleared — updates will be shown again.")
        )

    def _refresh_skip_indicator(self):
        try:
            from core.updater import get_skipped_version
            skipped = get_skipped_version()
        except Exception:
            skipped = ""
        if skipped:
            self._skip_lbl.setText(
                t("settings.skipped_version", skipped=skipped,
                  default=f"Skipped version: {skipped}")
            )
            self._skip_container.show()
        else:
            self._skip_container.hide()

    def _lang_btn_style(self) -> str:
        return f"""
            QPushButton {{
                background:{COLORS['card_bg']};
                color:{COLORS['text']};
                border:1px solid {COLORS['border']};
                border-radius:8px;
                padding:4px 10px;
                text-align:left;
            }}
            QPushButton:hover {{ background:{COLORS.get('card_hover', COLORS['card_bg'])}; }}
        """

    def _card(self, parent: QWidget) -> QFrame:
        f = QFrame(parent)
        f.setObjectName("settingsCard")
        f.setStyleSheet(f"""
            QFrame#settingsCard {{
                background:{COLORS['card_bg']};
                border-radius:12px;
                border:1px solid {COLORS['border']};
            }}
        """)
        lay = QVBoxLayout(f)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(12)
        return f

    def _section_title(self, text: str, layout: QVBoxLayout) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(font(16, "bold"))
        lbl.setStyleSheet(f"color:{COLORS['text']};background:transparent;border:none;")
        layout.addWidget(lbl)
        return lbl


    def _on_debug_toggled(self, checked: bool):
        print(f"[DEBUG] _on_debug_toggled: debug mode -> {checked}")
        if toggle_debug_mode is None:
            return
        root_app = self._find_root_app()
        if root_app:
            toggle_debug_mode(
                root_app, state.colors,
                on_close=lambda: (
                self._debug_checkbox.blockSignals(True),
                self._debug_checkbox.setChecked(False),
                self._debug_checkbox.blockSignals(False),
            ))


    def _on_file_logging_toggled(self, checked: bool):
        print(f"[DEBUG] _on_file_logging_toggled: file logging -> {checked}")
        set_file_logging_enabled(checked)
        self._file_log_append_checkbox.setEnabled(checked)

        if start_file_logging is None:
            return

        if checked:
            ok = start_file_logging(append=is_file_logging_append())
            if not ok:
                self.show_notification(
                    "error",
                    t("settings.file_logging_start_failed",
                      default="Could not start file logging. Check folder permissions.")
                )
                self._file_log_checkbox.blockSignals(True)
                self._file_log_checkbox.setChecked(False)
                self._file_log_checkbox.blockSignals(False)
                set_file_logging_enabled(False)
                self._file_log_append_checkbox.setEnabled(False)
        else:
            stop_file_logging()

    def _on_file_logging_append_toggled(self, checked: bool):
        print(f"[DEBUG] _on_file_logging_append_toggled: append -> {checked}")
        set_file_logging_append(checked)
        if is_file_logging_active and is_file_logging_active():
            stop_file_logging()
            start_file_logging(append=checked)


    def _on_testing_toggled(self, checked: bool):
        print(f"[DEBUG] _on_testing_toggled: testing mode -> {checked}")
        state.set_testing_mode(checked)


    def _on_confirm_save_toggled(self, checked: bool):
        print(f"[DEBUG] _on_confirm_save_toggled: confirm_on_save -> {checked}")
        state.set_confirm_on_save(checked)


    def _on_texture_previews_toggled(self, checked: bool):
        print(f"[DEBUG] _on_texture_previews_toggled: previews enabled -> {checked}")
        state.texture_previews_enabled = checked


    def _open_language_selector(self):
        print("[DEBUG] _open_language_selector: opening language picker dialog")
        available = get_available_languages()
        current   = get_current_language()
        dlg = _LanguageSelectorDialog(self, available, current)
        if dlg.exec():
            new_lang = dlg.selected_lang
            if new_lang != current:
                ok = set_language(new_lang)
                if ok:
                    lang_info = available.get(new_lang, {"native": new_lang})
                    self._lang_btn.setText(lang_info.get("native", new_lang))
                    self._refresh_all_ui()
                    self.show_notification(
                        "success",
                        f"Language changed to {lang_info.get('native', new_lang)}"
                    )
                else:
                    self.show_notification("error", f"Failed to set language: {new_lang}")


    def show_notification(self, type: str, message: str):
        print(f"[DEBUG] show_notification: [{type}] {message!r}")
        if self._notify_cb:
            self._notify_cb(message, type)
        else:
            if type == "error":
                QMessageBox.critical(self, t("common.error", default="Error"), message)
            elif type == "warning":
                QMessageBox.warning(self, t("common.warning", default="Warning"), message)
            else:
                QMessageBox.information(self, t("common.info", default="Info"), message)


    def _find_root_app(self):
        from PySide6.QtWidgets import QApplication
        for w in QApplication.topLevelWidgets():
            if hasattr(w, "tabs"):
                return w
        widget = self.parent()
        for _ in range(15):
            if widget is None:
                break
            if hasattr(widget, "tabs"):
                return widget
            widget = widget.parent()
        return None

    def _refresh_all_ui(self):
        root = self._find_root_app()
        if not root:
            return

        if hasattr(root, "_refresh_all_tabs"):
            try:
                root._refresh_all_tabs()
                return
            except Exception as e:
                print(f"[WARNING] _refresh_all_ui delegation failed: {e}")

        if hasattr(root, "tabs"):
            for name, tab in root.tabs.items():
                if hasattr(tab, "refresh_ui"):
                    try:
                        tab.refresh_ui()
                    except Exception as e:
                        print(f"[ERROR] refresh_ui {name}: {e}")
        if hasattr(root, "topbar"):
            try:
                root.topbar.refresh_ui()
            except Exception:
                pass
        if hasattr(root, "sidebar"):
            try:
                root.sidebar.refresh_ui(
                    getattr(root, "_add_vehicle_from_sidebar", None)
                )
                gen = root.tabs.get("generator") if hasattr(root, "tabs") else None
                if gen and hasattr(gen, "set_sidebar_references"):
                    gen.set_sidebar_references(
                        root.sidebar._mod_entry,
                        root.sidebar._author_entry,
                    )
            except Exception:
                pass

    def showEvent(self, event):
        super().showEvent(event)
        if hasattr(self, "_path_section") and hasattr(self._path_section, "reload_paths"):
            try:
                self._path_section.reload_paths()
            except Exception as e:
                print(f"[WARNING] path reload on show: {e}")


    def refresh_ui(self):
        self.setStyleSheet(f"background:{COLORS['app_bg']};")

        self._main_title.setText(t("settings.title", default="Settings"))
        self._main_title.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;"
        )

        self._appearance_title.setText(t("settings.appearance", default="Appearance"))
        self._appearance_title.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;"
        )

        self._theme_label.setText(t("settings.theme", default="Theme:"))
        self._theme_label.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;"
        )
        self._theme_toggle._refresh_styles(state.theme_mode)

        self._lang_label.setText(t("settings.language", default="Language:"))
        self._lang_label.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;"
        )
        available = get_available_languages()
        current   = get_current_language()
        lang_info = available.get(current, {"native": "English"})

        self._preview_label.setText(t("settings.texture_previews", default="Texture Previews (.dds / .png):"))
        self._preview_label.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;"
        )
        self._preview_toggle.blockSignals(True)
        self._preview_toggle.setChecked(getattr(state, 'texture_previews_enabled', True))
        self._preview_toggle.blockSignals(False)
        self._preview_desc.setText(
            t("settings.texture_previews_desc",
              default="Show image previews when selecting .dds or .png textures. "
                      "Disable for faster performance with very large files.")
        )
        self._preview_desc.setStyleSheet(
            f"color:{COLORS['text_secondary']};background:transparent;border:none;"
        )
        self._lang_btn.setText(lang_info.get("native", "English"))
        self._lang_btn.setStyleSheet(self._lang_btn_style())

        if hasattr(self, "_path_section") and hasattr(self._path_section, "refresh_ui"):
            try:
                self._path_section.refresh_ui()
            except Exception as e:
                print(f"[WARNING] PathConfigurationSection.refresh_ui: {e}")

        self._advanced_title.setText(t("settings.advanced", default="Advanced"))
        self._advanced_title.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;"
        )
        self._debug_checkbox.setText(t("settings.debug_mode", default="Debug Mode"))
        self._debug_checkbox.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;"
        )
        self._debug_desc.setText(
            t("settings.debug_mode_desc",
              default="Opens a debug console window showing application logs.")
        )
        self._debug_desc.setStyleSheet(
            f"color:{COLORS['text_secondary']};background:transparent;border:none;padding-left:22px;"
        )

        self._file_log_checkbox.setText(t("settings.file_logging", default="Log to File"))
        self._file_log_checkbox.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;"
        )
        self._file_log_desc.setText(
            t("settings.file_logging_desc",
              default="Writes all application logs to data/app_log.txt on disk.")
        )
        self._file_log_desc.setStyleSheet(
            f"color:{COLORS['text_secondary']};background:transparent;border:none;padding-left:22px;"
        )
        self._file_log_append_checkbox.setText(
            t("settings.file_logging_append", default="Append to Existing Log")
        )
        self._file_log_append_checkbox.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;padding-left:22px;"
        )
        self._file_log_append_desc.setText(
            t("settings.file_logging_append_desc",
              default="On: new logs are dated and added on top of the existing file. "
                      "Off: each launch overwrites the log file with a fresh one.")
        )
        self._file_log_append_desc.setStyleSheet(
            f"color:{COLORS['text_secondary']};background:transparent;border:none;padding-left:22px;"
        )

        self._testing_checkbox.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;"
        )
        self._testing_checkbox.blockSignals(True)
        self._testing_checkbox.setChecked(state.testing_mode)
        self._testing_checkbox.blockSignals(False)
        self._testing_desc.setStyleSheet(
            f"color:{COLORS['text_secondary']};background:transparent;border:none;padding-left:22px;"
        )

        self._confirm_save_checkbox.setText(
            t("settings.confirm_on_save", default="💾  Confirm Before Saving")
        )
        self._confirm_save_checkbox.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;"
        )
        self._confirm_save_checkbox.blockSignals(True)
        self._confirm_save_checkbox.setChecked(state.confirm_on_save)
        self._confirm_save_checkbox.blockSignals(False)
        self._confirm_save_desc.setText(
            t("settings.confirm_on_save_desc", default=(
                "Shows a confirmation dialog every time you save a project, naming "
                "the file that will be overwritten. Turn this off if you'd rather "
                "save without being asked each time."
            ))
        )
        self._confirm_save_desc.setStyleSheet(
            f"color:{COLORS['text_secondary']};background:transparent;border:none;padding-left:22px;"
        )

        self._updates_title.setText(t("settings.updates", default="Updates"))
        self._updates_title.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;"
        )
        self._ver_label.setText(t("settings.current_version", default="Current version:"))
        self._ver_label.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;"
        )
        self._ver_value.setStyleSheet(
            f"color:{COLORS['text_secondary']};background:transparent;border:none;"
        )
        if self._check_update_btn.isEnabled():
            self._check_update_btn.setText(
                t("settings.check_for_updates", default="🔍  Check for Updates")
            )
        self._check_update_btn.setStyleSheet(self._primary_btn_style())
        self._changelog_btn.setText(
            t("settings.view_changelog", default="📜  Changelog History")
        )
        self._changelog_btn.setStyleSheet(self._secondary_btn_style())
        self._skip_clear_btn.setText(t("settings.clear_skipped", default="Clear"))
        self._skip_clear_btn.setStyleSheet(f"""
            QPushButton {{
                color:{COLORS['accent']};
                background:transparent;
                border:none;
                text-decoration:underline;
                padding:0;
            }}
            QPushButton:hover {{ color:{COLORS.get('accent_hover', COLORS['accent'])}; }}
        """)
        self._refresh_skip_indicator()


class _LanguageSelectorDialog:
    def __init__(self, parent: QWidget, available: dict, current: str):
        from PySide6.QtWidgets import (
            QDialog, QScrollArea, QVBoxLayout,
            QLineEdit, QWidget, QPushButton
        )

        self.selected_lang = current
        self._dialog = QDialog(parent, Qt.Dialog | Qt.FramelessWindowHint)
        self._dialog.setWindowTitle(t("settings.select_language_title"))
        self._dialog.setModal(True)
        self._dialog.resize(480, 520)
        self._dialog.setAttribute(Qt.WA_TranslucentBackground)
        self._dialog.setStyleSheet("")

        frame = QFrame(self._dialog)
        frame.setObjectName("langFrame")
        frame.setStyleSheet(f"""
            QFrame#langFrame {{
                background:{COLORS['app_bg']};
                color:{COLORS['text']};
                border:1px solid {COLORS['border']};
                border-radius:14px;
            }}
        """)
        wrapper = QVBoxLayout(self._dialog)
        wrapper.setContentsMargins(0, 0, 0, 0)
        wrapper.addWidget(frame)

        col = QVBoxLayout(frame)
        col.setContentsMargins(20, 20, 20, 20)
        col.setSpacing(12)

        title = QLabel(t("settings.select_language_title"))
        title.setFont(font(20, "bold"))
        title.setStyleSheet(f"color:{COLORS['text']};background:transparent;border:none;")
        col.addWidget(title)

        search = QLineEdit()
        search.setPlaceholderText("Search languages…")
        search.setFixedHeight(38)
        search.setFont(font(13))
        search.setStyleSheet(f"""
            QLineEdit {{
                background:{COLORS['card_bg']};
                color:{COLORS['text']};
                border:1px solid {COLORS['border']};
                border-radius:8px;
                padding:4px 10px;
            }}
        """)
        col.addWidget(search)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet(
            f"QScrollArea {{ background:{COLORS['app_bg']};border:none; }}"
        )
        scroll_content = QWidget()
        scroll_content.setStyleSheet(f"background:{COLORS['app_bg']};")
        self._list_col = QVBoxLayout(scroll_content)
        self._list_col.setContentsMargins(0, 0, 0, 0)
        self._list_col.setSpacing(4)
        scroll_area.setWidget(scroll_content)
        col.addWidget(scroll_area, 1)

        self._available = available
        self._current   = current
        self._build_list("")
        search.textChanged.connect(self._build_list)

        cancel_btn = QPushButton(t("common.cancel"))
        cancel_btn.setFont(font(13))
        cancel_btn.setFixedHeight(38)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background:{COLORS['card_bg']};
                color:{COLORS['text']};
                border:1px solid {COLORS['border']};
                border-radius:8px;
            }}
            QPushButton:hover {{ background:{COLORS.get('card_hover', COLORS['card_bg'])}; }}
        """)
        cancel_btn.clicked.connect(self._dialog.reject)
        col.addWidget(cancel_btn)

    def _build_list(self, filter_text: str = ""):
        while self._list_col.count():
            item = self._list_col.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        ft = filter_text.lower()
        sorted_langs = sorted(
            self._available.items(),
            key=lambda x: x[1].get("native", "")
        )
        for lang_code, lang_info in sorted_langs:
            native = lang_info.get("native", lang_code)
            name   = lang_info.get("name", "")
            if ft and ft not in native.lower() and ft not in name.lower():
                continue
            is_current = (lang_code == self._current)
            btn = QPushButton(
                f"  {native}" + (f"  ({name})" if name and name != native else "")
                + ("  ✓" if is_current else "")
            )
            btn.setFont(font(14, "bold" if is_current else "normal"))
            btn.setFixedHeight(50)
            btn.setCursor(Qt.PointingHandCursor)
            bg    = COLORS['accent'] if is_current else COLORS['card_bg']
            hover = COLORS['accent_hover'] if is_current else COLORS.get('card_hover', COLORS['card_bg'])
            fg    = COLORS['accent_text'] if is_current else COLORS['text']
            btn.setStyleSheet(f"""
                QPushButton {{
                    background:{bg};
                    color:{fg};
                    border-radius:8px;
                    border:1px solid {COLORS['border']};
                    text-align:left;
                    padding:0 12px;
                }}
                QPushButton:hover {{ background:{hover}; }}
            """)
            _lc = lang_code
            btn.clicked.connect(lambda checked=False, lc=_lc: self._select(lc))
            self._list_col.addWidget(btn)

        if self._list_col.count() == 0:
            empty = QLabel(t("settings.no_languages"))
            empty.setFont(font(13))
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet(
                f"color:{COLORS['text_secondary']};background:transparent;padding:20px;"
            )
            self._list_col.addWidget(empty)

        self._list_col.addStretch(1)

    def _select(self, lang_code: str):
        self.selected_lang = lang_code
        self._dialog.accept()

    def exec(self) -> bool:
        return bool(self._dialog.exec())
