from __future__ import annotations
from typing import Dict, Callable

from PySide6.QtCore    import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QCheckBox, QComboBox,
    QScrollArea, QVBoxLayout, QHBoxLayout, QMessageBox,
)

from gui.theme   import COLORS, font
from gui.state   import state
from gui.widgets import ToggleSwitch

try:
    from core.localization import t, set_language, get_available_languages, get_current_language
except ImportError as _exc:
    print(f"[DEBUG] _pipe_tmp.py: import failed ({_exc}), using fallback")
    def t(key, **kw):
        return key
    def set_language(lang):
        return False
    def get_available_languages():
        return {}
    def get_current_language():
        return 'en_US'

try:
    from utils.debug import toggle_debug_mode
except ImportError as _exc:
    print(f"[DEBUG] _pipe_tmp.py: import failed ({_exc}), using fallback")
    toggle_debug_mode = None

try:
    from utils.file_logger import start_file_logging, stop_file_logging, is_file_logging_active
    from core.settings import (
        is_file_logging_enabled, set_file_logging_enabled,
        is_file_logging_append, set_file_logging_append,
    )
except ImportError as _exc:
    print(f"[DEBUG] _pipe_tmp.py: import failed ({_exc}), using fallback")
    start_file_logging = stop_file_logging = is_file_logging_active = None
    is_file_logging_enabled = lambda: False
    set_file_logging_enabled = lambda v: None
    is_file_logging_append = lambda: False
    set_file_logging_append = lambda v: None


try:
    from core.model_preview import renderers as _renderers
except Exception as _exc:
    print(f"[WARNING] settings_tab: renderer options unavailable ({type(_exc).__name__}: {_exc})")
    _renderers = None


def _tf(key: str, default: str, **kw) -> str:
    text = t(key, default=default)
    if not isinstance(text, str) or text == key:
        text = default
    try:
        return text.format(**kw)
    except Exception:
        return text


def _muted() -> str:
    return COLORS.get("text_muted", COLORS["text_secondary"])


def _lbl_qss(color_key: str = "text") -> str:
    return (
        f"QLabel {{ color:{COLORS[color_key]}; background:transparent; border:none; }}"
        f"QLabel:disabled {{ color:{_muted()}; }}"
    )


def _panel_qss(name: str, radius: int = 10) -> str:
    return f"""
        QFrame#{name} {{
            background:{COLORS['card_bg']};
            border:1px solid {COLORS['border']};
            border-radius:{radius}px;
        }}
    """


def _row_qss() -> str:
    return f"""
        QFrame#stRow {{
            background:{COLORS['frame_bg']};
            border:1px solid {COLORS['border']};
            border-radius:8px;
        }}
        QFrame#stRow:hover {{ border-color:{COLORS['accent']}; }}
    """


def _btn_primary_qss() -> str:
    hover = COLORS.get('accent_hover', COLORS['accent'])
    return f"""
        QPushButton {{
            background:{COLORS['accent']};
            color:{COLORS['accent_text']};
            border:none; border-radius:8px; padding:4px 18px;
        }}
        QPushButton:hover {{ background:{hover}; }}
        QPushButton:disabled {{
            background:{COLORS['border']};
            color:{_muted()};
        }}
    """


def _btn_outline_qss() -> str:
    return f"""
        QPushButton {{
            background:transparent;
            color:{COLORS['text']};
            border:1px solid {COLORS['border']};
            border-radius:8px; padding:4px 18px;
        }}
        QPushButton:hover {{
            background:{COLORS.get('card_hover', COLORS['card_bg'])};
            border-color:{COLORS['accent']};
        }}
        QPushButton:disabled {{
            color:{_muted()};
        }}
    """


def _chip_qss() -> str:
    return (
        f"QLabel {{ color:{COLORS['accent']};"
        f" background:{COLORS.get('accent_dim', COLORS['frame_bg'])};"
        f" border:none; border-radius:4px; padding:2px 9px; }}"
    )


class _ThemeToggle(QWidget):
    _BTN_W = 96
    _BTN_H = 32

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
            btn.setFont(font(12, "bold"))
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
        def _style(left: bool, on: bool) -> str:
            radius = "8px 0 0 8px" if left else "0 8px 8px 0"
            if on:
                return f"""
                    QPushButton {{
                        background-color:{COLORS['accent']};
                        color:{COLORS['accent_text']};
                        border-radius:{radius};
                        border:1px solid {COLORS['accent']};
                        font-size:12px; font-weight:bold;
                    }}
                """
            return f"""
                QPushButton {{
                    background-color:{COLORS['card_bg']};
                    color:{COLORS['text_secondary']};
                    border-radius:{radius};
                    border:1px solid {COLORS['border']};
                    font-size:12px; font-weight:bold;
                }}
                QPushButton:hover {{
                    background-color:{COLORS['card_hover']};
                    color:{COLORS['text']};
                }}
            """

        dark = active == "dark"
        self._dark_btn.setStyleSheet(_style(True, dark))
        self._light_btn.setStyleSheet(_style(False, not dark))


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
        self._cards: list = []
        self._rows: list = []
        self._row_titles: list = []
        self._row_descs: list = []

        self._setup_ui()

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._topbar = QFrame()
        self._topbar.setObjectName("stTopbar")
        self._topbar.setFixedHeight(60)
        top_row = QHBoxLayout(self._topbar)
        top_row.setContentsMargins(20, 0, 20, 0)
        self._main_title = QLabel(t("settings.title", default="Settings"))
        self._main_title.setFont(font(18, "bold"))
        top_row.addWidget(self._main_title)
        top_row.addStretch()
        outer.addWidget(self._topbar)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.addWidget(self._scroll, 1)

        self._page = QWidget()
        col = QVBoxLayout(self._page)
        col.setContentsMargins(20, 20, 20, 20)
        col.setSpacing(12)
        self._scroll.setWidget(self._page)
        page = self._page

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
            stub_lbl.setFont(font(12))
            stub_lbl.setStyleSheet(_lbl_qss("text_secondary"))
            path_stub.layout().addWidget(stub_lbl)
            col.addWidget(path_stub)

        appearance_card = self._card(page)
        a_col = appearance_card.layout()
        self._appearance_title = self._section_title(
            t("settings.appearance", default="Appearance"), a_col
        )

        self._theme_toggle = _ThemeToggle(appearance_card)
        row, self._theme_label, _ = self._setting_row(
            t("settings.theme", default="Theme:"), None, self._theme_toggle)
        a_col.addWidget(row)

        available = get_available_languages()
        current   = get_current_language()
        lang_info = available.get(current, {"native": "English"})
        self._lang_btn = QPushButton(lang_info.get("native", "English"))
        self._lang_btn.setFont(font(12))
        self._lang_btn.setFixedSize(200, 32)
        self._lang_btn.setCursor(Qt.PointingHandCursor)
        self._lang_btn.setStyleSheet(self._lang_btn_style())
        self._lang_btn.clicked.connect(self._open_language_selector)
        row, self._lang_label, _ = self._setting_row(
            t("settings.language", default="Language:"), None, self._lang_btn)
        a_col.addWidget(row)

        self._preview_toggle = ToggleSwitch()
        self._preview_toggle.setChecked(getattr(state, 'texture_previews_enabled', True))
        self._preview_toggle.stateChanged.connect(self._on_texture_previews_toggled)
        row, self._preview_label, self._preview_desc = self._setting_row(
            t("settings.texture_previews", default="Texture Previews (.dds / .png):"),
            t("settings.texture_previews_desc",
              default="Show image previews when selecting .dds or .png textures. "
                      "Disable for faster performance with very large files."),
            self._preview_toggle)
        a_col.addWidget(row)

        col.addWidget(appearance_card)

        advanced_card = self._card(page)
        adv_col = advanced_card.layout()
        self._advanced_title = self._section_title(
            t("settings.advanced", default="Advanced"), adv_col
        )

        self._debug_checkbox = ToggleSwitch()
        self._debug_checkbox.stateChanged.connect(self._on_debug_toggled)
        row, self._debug_title, self._debug_desc = self._setting_row(
            t("settings.debug_mode", default="Debug Mode"),
            t("settings.debug_mode_desc",
              default="Opens a debug console window showing application logs."),
            self._debug_checkbox)
        adv_col.addWidget(row)

        self._file_log_checkbox = ToggleSwitch()
        self._file_log_checkbox.setChecked(is_file_logging_enabled())
        self._file_log_checkbox.stateChanged.connect(self._on_file_logging_toggled)
        row, self._file_log_title, self._file_log_desc = self._setting_row(
            t("settings.file_logging", default="Log to File"),
            t("settings.file_logging_desc",
              default="Writes all application logs to data/app_log.txt on disk."),
            self._file_log_checkbox)
        adv_col.addWidget(row)

        self._file_log_append_checkbox = ToggleSwitch()
        self._file_log_append_checkbox.setChecked(is_file_logging_append())
        self._file_log_append_checkbox.setEnabled(is_file_logging_enabled())
        self._file_log_append_checkbox.stateChanged.connect(self._on_file_logging_append_toggled)
        row, self._file_log_append_title, self._file_log_append_desc = self._setting_row(
            t("settings.file_logging_append", default="Append to Existing Log"),
            t("settings.file_logging_append_desc",
              default="On: new logs are dated and added on top of the existing file. "
                      "Off: each launch overwrites the log file with a fresh one."),
            self._file_log_append_checkbox)
        adv_col.addWidget(row)

        self._testing_checkbox = ToggleSwitch()
        self._testing_checkbox.setChecked(state.testing_mode)
        self._testing_checkbox.stateChanged.connect(self._on_testing_toggled)
        row, self._testing_title, self._testing_desc = self._setting_row(
            "🧪  Developer Testing Mode",
            "Adds an 'Add All Vehicles' button to the sidebar vehicle list, and "
            "broadcasts any skin added in the Generator to every vehicle currently "
            "in the project.  For developer use only.",
            self._testing_checkbox)
        adv_col.addWidget(row)

        self._confirm_save_checkbox = ToggleSwitch()
        self._confirm_save_checkbox.setChecked(state.confirm_on_save)
        self._confirm_save_checkbox.stateChanged.connect(self._on_confirm_save_toggled)
        row, self._confirm_save_title, self._confirm_save_desc = self._setting_row(
            t("settings.confirm_on_save", default="💾  Confirm Before Saving"),
            t("settings.confirm_on_save_desc", default=(
                "Shows a confirmation dialog every time you save a project, naming "
                "the file that will be overwritten. Turn this off if you'd rather "
                "save without being asked each time."
            )),
            self._confirm_save_checkbox)
        adv_col.addWidget(row)

        if _renderers is not None:
            self._renderer_combo = QComboBox()
            self._renderer_combo.setFixedSize(270, 32)
            self._renderer_combo.setFont(font(12))
            self._renderer_combo.setCursor(Qt.PointingHandCursor)
            self._renderer_combo.setStyleSheet(self._combo_style())
            self._populate_renderer_combo()
            self._renderer_combo.currentIndexChanged.connect(self._on_renderer_changed)
            row, self._renderer_title, self._renderer_desc = self._setting_row(
                t("settings.preview_renderer", default="🖥️  3D Preview Renderer"),
                t("settings.preview_renderer_desc", default=(
                    "Automatic picks the best working renderer and switches by itself if one "
                    "fails. Choose a specific one to force it, for example if Automatic picked "
                    "something slower than your system can do.")),
                self._renderer_combo)
            adv_col.addWidget(row)

            self._renderer_status = QLabel("")
            self._renderer_status.setFont(font(11))
            self._renderer_status.setWordWrap(True)
            self._renderer_status.setContentsMargins(14, 0, 14, 4)
            self._row_descs.append(self._renderer_status)
            adv_col.addWidget(self._renderer_status)
            self._refresh_renderer_status()

        col.addWidget(advanced_card)

        updates_card = self._card(page)
        upd_col = updates_card.layout()
        self._updates_title = self._section_title(
            t("settings.updates", default="Updates"), upd_col
        )

        try:
            from core.updater import CURRENT_VERSION as _cv
        except Exception as _exc:
            print(f"[WARNING] _setup_ui: {type(_exc).__name__}: {_exc}")
            _cv = 'unknown'
        self._ver_value = QLabel(_cv)
        self._ver_value.setFont(font(11, "bold"))
        self._ver_value.setAlignment(Qt.AlignCenter)
        row, self._ver_label, _ = self._setting_row(
            t("settings.current_version", default="Current version:"), None, self._ver_value)
        upd_col.addWidget(row)

        check_row = QHBoxLayout()
        check_row.setContentsMargins(0, 4, 0, 0)
        check_row.setSpacing(8)
        self._check_update_btn = QPushButton(
            t("settings.check_for_updates", default="🔍  Check for Updates")
        )
        self._check_update_btn.setFont(font(12, "bold"))
        self._check_update_btn.setFixedHeight(38)
        self._check_update_btn.setCursor(Qt.PointingHandCursor)
        self._check_update_btn.setStyleSheet(self._primary_btn_style())
        self._check_update_btn.clicked.connect(self._on_check_for_updates)
        check_row.addWidget(self._check_update_btn)

        self._changelog_btn = QPushButton(
            t("settings.view_changelog", default="📜  Changelog History")
        )
        self._changelog_btn.setFont(font(12, "bold"))
        self._changelog_btn.setFixedHeight(38)
        self._changelog_btn.setCursor(Qt.PointingHandCursor)
        self._changelog_btn.setStyleSheet(self._secondary_btn_style())
        self._changelog_btn.clicked.connect(self._on_view_changelog)
        check_row.addWidget(self._changelog_btn)

        check_row.addStretch(1)
        upd_col.addLayout(check_row)

        self._skip_row = QHBoxLayout()
        self._skip_row.setContentsMargins(0, 0, 0, 0)
        self._skip_row.setSpacing(8)
        self._skip_lbl = QLabel("")
        self._skip_lbl.setFont(font(11))
        self._skip_clear_btn = QPushButton(
            t("settings.clear_skipped", default="Clear")
        )
        self._skip_clear_btn.setFont(font(11))
        self._skip_clear_btn.setCursor(Qt.PointingHandCursor)
        self._skip_clear_btn.setFlat(True)
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

        self._restyle()

    def _restyle(self):
        self.setStyleSheet(f"background:{COLORS['app_bg']};")
        self._topbar.setStyleSheet(f"""
            QFrame#stTopbar {{
                background-color:{COLORS.get('topbar_bg', COLORS['frame_bg'])};
                border-bottom:1px solid {COLORS['border']};
            }}
        """)
        self._main_title.setStyleSheet(_lbl_qss())
        self._scroll.setStyleSheet(f"""
            QScrollArea {{ background:{COLORS['app_bg']}; border:none; }}
        """)
        self._page.setStyleSheet(f"background:{COLORS['app_bg']};")

        for card in self._cards:
            card.setStyleSheet(_panel_qss("stCard"))
        for row in self._rows:
            row.setStyleSheet(_row_qss())
        for lbl in self._row_titles:
            lbl.setStyleSheet(_lbl_qss())
        for lbl in self._row_descs:
            lbl.setStyleSheet(_lbl_qss("text_secondary"))
        for lbl in self._section_labels:
            lbl.setStyleSheet(_lbl_qss())

        if hasattr(self, "_renderer_combo"):
            self._renderer_combo.setStyleSheet(self._combo_style())
        self._ver_value.setStyleSheet(_chip_qss())
        self._lang_btn.setStyleSheet(self._lang_btn_style())
        self._check_update_btn.setStyleSheet(self._primary_btn_style())
        self._changelog_btn.setStyleSheet(self._secondary_btn_style())
        self._skip_lbl.setStyleSheet(_lbl_qss("text_secondary"))
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
        for m in self.findChildren(QFrame, "stMarker"):
            m.setStyleSheet(
                f"background:{COLORS['accent']};border:none;border-radius:1px;"
            )
        self._theme_toggle._refresh_styles(state.theme_mode)

    def _setting_row(self, title: str, desc, control: QWidget):
        row = QFrame()
        row.setObjectName("stRow")
        h = QHBoxLayout(row)
        h.setContentsMargins(14, 10, 14, 10)
        h.setSpacing(14)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        title_lbl = QLabel(title)
        title_lbl.setFont(font(12, "bold"))
        text_col.addWidget(title_lbl)
        self._row_titles.append(title_lbl)

        desc_lbl = None
        if desc:
            desc_lbl = QLabel(desc)
            desc_lbl.setFont(font(11))
            desc_lbl.setWordWrap(True)
            text_col.addWidget(desc_lbl)
            self._row_descs.append(desc_lbl)

        h.addLayout(text_col, 1)
        h.addWidget(control, 0, Qt.AlignVCenter)
        self._rows.append(row)
        return row, title_lbl, desc_lbl

    def _primary_btn_style(self) -> str:
        return _btn_primary_qss()

    def _secondary_btn_style(self) -> str:
        return _btn_outline_qss()

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
            QPushButton:hover {{
                background:{COLORS.get('card_hover', COLORS['card_bg'])};
                border-color:{COLORS['accent']};
            }}
        """

    def _combo_style(self) -> str:
        return f"""
            QComboBox {{
                background:{COLORS['card_bg']};
                color:{COLORS['text']};
                border:1px solid {COLORS['border']};
                border-radius:8px;
                padding:4px 10px;
            }}
            QComboBox:hover {{ border-color:{COLORS['accent']}; }}
            QComboBox QAbstractItemView {{
                background:{COLORS['card_bg']};
                color:{COLORS['text']};
                selection-background-color:{COLORS['accent']};
                selection-color:{COLORS.get('accent_text', COLORS['text'])};
                border:1px solid {COLORS['border']};
            }}
        """

    def _populate_renderer_combo(self):
        combo = self._renderer_combo
        combo.blockSignals(True)
        combo.clear()
        for opt in _renderers.list_options():
            label = opt.label if opt.available else f"{opt.label}  (unavailable)"
            combo.addItem(label, opt.id)
            i = combo.count() - 1
            tip = opt.description if opt.available else f"{opt.description}\n{opt.reason}"
            combo.setItemData(i, tip, Qt.ToolTipRole)
            if not opt.available:
                item = combo.model().item(i)
                if item is not None:
                    item.setEnabled(False)
        idx = combo.findData(_renderers.get_preference())
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        combo.blockSignals(False)

    def _refresh_renderer_status(self):
        if _renderers is None or not hasattr(self, "_renderer_status"):
            return
        pref = _renderers.get_preference()
        active = _renderers.get_active()
        lines = []
        lines.append(
            _tf("settings.preview_renderer_active", "In use: {name}", name=active)
            if active else
            _tf("settings.preview_renderer_idle",
                "In use: not detected yet, open the 3D preview to see it."))
        if pref == _renderers.AUTO:
            lines.append(_tf("settings.preview_renderer_auto_note",
                             "Automatic mode: falls back to another renderer if one fails."))
        else:
            lines.append(_tf("settings.preview_renderer_forced_note",
                             "Forced: {name}. No automatic fallback, switch back to "
                             "Automatic if the preview stays blank.",
                             name=_renderers.label_for(pref)))
        if _renderers.restart_required(pref):
            lines.append(_tf("settings.preview_renderer_restart",
                             "Restart BeamSkin Studio to apply the OpenGL mode change."))
        if not _renderers.wgpu_installed():
            lines.append(_tf("settings.preview_renderer_wgpu",
                             "Direct3D 12 / Vulkan / Metal need the optional package: pip install wgpu"))
        self._renderer_status.setText("\n".join(lines))

    def _on_renderer_changed(self, index: int):
        rid = self._renderer_combo.itemData(index)
        if not rid or _renderers is None:
            return
        print(f"[DEBUG] _on_renderer_changed: 3D preview renderer -> {rid}")
        restart = _renderers.set_preference(rid)
        label = _renderers.label_for(rid)
        if restart:
            self.show_notification(
                "warning",
                _tf("settings.preview_renderer_saved_restart",
                    "{name} saved. Restart BeamSkin Studio to apply it.", name=label))
        else:
            self.show_notification(
                "success",
                _tf("settings.preview_renderer_saved",
                    "3D preview renderer set to {name}.", name=label))
        self._refresh_renderer_status()
        QTimer.singleShot(800, self._refresh_renderer_status)

    def _card(self, parent: QWidget) -> QFrame:
        f = QFrame(parent)
        f.setObjectName("stCard")
        f.setStyleSheet(_panel_qss("stCard"))
        lay = QVBoxLayout(f)
        lay.setContentsMargins(10, 10, 10, 12)
        lay.setSpacing(8)
        self._cards.append(f)
        return f

    def _section_title(self, text: str, layout: QVBoxLayout) -> QLabel:
        header = QFrame()
        header.setFixedHeight(30)
        header.setStyleSheet("background:transparent;border:none;")
        row = QHBoxLayout(header)
        row.setContentsMargins(6, 0, 6, 0)
        row.setSpacing(6)

        marker = QFrame()
        marker.setFixedSize(3, 14)
        marker.setStyleSheet(
            f"background:{COLORS['accent']};border:none;border-radius:1px;"
        )
        marker.setObjectName("stMarker")
        row.addWidget(marker)

        lbl = QLabel(text.upper())
        lbl.setFont(font(10, "bold"))
        row.addWidget(lbl)
        row.addStretch()
        layout.addWidget(header)
        self._section_labels.append(lbl)
        return lbl

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
        from PySide6.QtWidgets import QToolTip
        from PySide6.QtCore import QTimer
        QToolTip.hideText()
        QTimer.singleShot(50, self._open_changelog_browser)

    def _open_changelog_browser(self):
        try:
            from gui.components.changelog_dialog import show_changelog_browser
            show_changelog_browser(self.window())
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
        except Exception as _exc:
            print(f"[WARNING] _refresh_skip_indicator: {type(_exc).__name__}: {_exc}")
            skipped = ''
        if skipped:
            self._skip_lbl.setText(
                t("settings.skipped_version", skipped=skipped,
                  default=f"Skipped version: {skipped}")
            )
            self._skip_container.show()
        else:
            self._skip_container.hide()

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
        state.set_texture_previews_enabled(checked)


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
            except Exception as _exc:
                print(f"[WARNING] _refresh_all_ui: {type(_exc).__name__}: {_exc}")
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
            except Exception as _exc:
                print(f"[WARNING] _refresh_all_ui: {type(_exc).__name__}: {_exc}")

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh_renderer_status()
        if hasattr(self, "_path_section") and hasattr(self._path_section, "reload_paths"):
            try:
                self._path_section.reload_paths()
            except Exception as e:
                print(f"[WARNING] path reload on show: {e}")


    def refresh_ui(self):
        self._restyle()

        self._main_title.setText(t("settings.title", default="Settings"))
        self._appearance_title.setText(t("settings.appearance", default="Appearance").upper())
        self._theme_label.setText(t("settings.theme", default="Theme:"))
        self._lang_label.setText(t("settings.language", default="Language:"))
        available = get_available_languages()
        current   = get_current_language()
        lang_info = available.get(current, {"native": "English"})
        self._lang_btn.setText(lang_info.get("native", "English"))

        self._preview_label.setText(t("settings.texture_previews", default="Texture Previews (.dds / .png):"))
        self._preview_toggle.blockSignals(True)
        self._preview_toggle.setChecked(getattr(state, 'texture_previews_enabled', True))
        self._preview_toggle.blockSignals(False)
        self._preview_desc.setText(
            t("settings.texture_previews_desc",
              default="Show image previews when selecting .dds or .png textures. "
                      "Disable for faster performance with very large files.")
        )

        if hasattr(self, "_path_section") and hasattr(self._path_section, "refresh_ui"):
            try:
                self._path_section.refresh_ui()
            except Exception as e:
                print(f"[WARNING] PathConfigurationSection.refresh_ui: {e}")

        self._advanced_title.setText(t("settings.advanced", default="Advanced").upper())
        self._debug_title.setText(t("settings.debug_mode", default="Debug Mode"))
        self._debug_desc.setText(
            t("settings.debug_mode_desc",
              default="Opens a debug console window showing application logs.")
        )
        self._file_log_title.setText(t("settings.file_logging", default="Log to File"))
        self._file_log_desc.setText(
            t("settings.file_logging_desc",
              default="Writes all application logs to data/app_log.txt on disk.")
        )
        self._file_log_append_title.setText(
            t("settings.file_logging_append", default="Append to Existing Log")
        )
        self._file_log_append_desc.setText(
            t("settings.file_logging_append_desc",
              default="On: new logs are dated and added on top of the existing file. "
                      "Off: each launch overwrites the log file with a fresh one.")
        )

        self._testing_checkbox.blockSignals(True)
        self._testing_checkbox.setChecked(state.testing_mode)
        self._testing_checkbox.blockSignals(False)

        self._confirm_save_title.setText(
            t("settings.confirm_on_save", default="💾  Confirm Before Saving")
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

        if _renderers is not None and hasattr(self, "_renderer_combo"):
            self._renderer_title.setText(t("settings.preview_renderer", default="🖥️  3D Preview Renderer"))
            self._populate_renderer_combo()
            self._refresh_renderer_status()

        self._updates_title.setText(t("settings.updates", default="Updates").upper())
        self._ver_label.setText(t("settings.current_version", default="Current version:"))
        if self._check_update_btn.isEnabled():
            self._check_update_btn.setText(
                t("settings.check_for_updates", default="🔍  Check for Updates")
            )
        self._changelog_btn.setText(
            t("settings.view_changelog", default="📜  Changelog History")
        )
        self._skip_clear_btn.setText(t("settings.clear_skipped", default="Clear"))
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
                border-radius:12px;
            }}
        """)
        wrapper = QVBoxLayout(self._dialog)
        wrapper.setContentsMargins(0, 0, 0, 0)
        wrapper.addWidget(frame)

        col = QVBoxLayout(frame)
        col.setContentsMargins(16, 16, 16, 16)
        col.setSpacing(10)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(4, 0, 4, 0)
        title_row.setSpacing(8)
        marker = QFrame()
        marker.setFixedSize(3, 18)
        marker.setStyleSheet(
            f"background:{COLORS['accent']};border:none;border-radius:1px;"
        )
        title_row.addWidget(marker)
        title = QLabel(t("settings.select_language_title"))
        title.setFont(font(16, "bold"))
        title.setStyleSheet(_lbl_qss())
        title_row.addWidget(title)
        title_row.addStretch()
        col.addLayout(title_row)

        search = QLineEdit()
        search.setPlaceholderText("Search languages…")
        search.setFixedHeight(36)
        search.setFont(font(12))
        search.setStyleSheet(f"""
            QLineEdit {{
                background:{COLORS['frame_bg']};
                color:{COLORS['text']};
                border:1px solid {COLORS['border']};
                border-radius:8px;
                padding:4px 10px;
                selection-background-color:{COLORS['accent']};
            }}
            QLineEdit:focus {{ border-color:{COLORS.get('border_focus', COLORS['accent'])}; }}
        """)
        col.addWidget(search)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet(
            "QScrollArea { background:transparent; border:none; }"
        )
        scroll_content = QWidget()
        scroll_content.setStyleSheet(f"background:{COLORS['app_bg']};")
        self._list_col = QVBoxLayout(scroll_content)
        self._list_col.setContentsMargins(0, 0, 0, 0)
        self._list_col.setSpacing(6)
        scroll_area.setWidget(scroll_content)
        col.addWidget(scroll_area, 1)

        self._available = available
        self._current   = current
        self._build_list("")
        search.textChanged.connect(self._build_list)

        cancel_btn = QPushButton(t("common.cancel"))
        cancel_btn.setFont(font(12, "bold"))
        cancel_btn.setFixedHeight(36)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet(_btn_outline_qss())
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
            btn.setFont(font(13, "bold" if is_current else "normal"))
            btn.setFixedHeight(44)
            btn.setCursor(Qt.PointingHandCursor)
            bg     = COLORS['accent'] if is_current else COLORS['frame_bg']
            hover  = COLORS['accent_hover'] if is_current else COLORS.get('card_hover', COLORS['card_bg'])
            fg     = COLORS['accent_text'] if is_current else COLORS['text']
            border = COLORS['accent'] if is_current else COLORS['border']
            btn.setStyleSheet(f"""
                QPushButton {{
                    background:{bg};
                    color:{fg};
                    border-radius:8px;
                    border:1px solid {border};
                    text-align:left;
                    padding:0 12px;
                }}
                QPushButton:hover {{
                    background:{hover};
                    border-color:{COLORS['accent']};
                }}
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
