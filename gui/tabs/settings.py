from __future__ import annotations
import os
import sys
from typing import Dict, Optional, Callable

from PySide6.QtCore    import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QLineEdit,
    QCheckBox, QScrollArea, QVBoxLayout, QHBoxLayout,
    QSizePolicy, QMessageBox,
)

from gui.theme   import COLORS, font, ThemeManager
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



class _ThemeToggle(QWidget):
    """
    A pill-shaped segmented control with two options: 🌙 Dark  /  ☀️ Light.
    Reads the current mode from ``state.theme_mode`` and calls
    ``state.set_theme()`` on click.
    """

    _BTN_W = 100
    _BTN_H = 34

    def __init__(self, parent: QWidget = None):
        print(f"[DEBUG] __init__() called")
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

        # Draw initial state
        self._refresh_styles(state.theme_mode)

    def _select(self, mode: str) -> None:
        print(f"[DEBUG] _select() called")
        if mode == state.theme_mode:
            return
        state.set_theme(mode)
        # ``state.set_theme`` calls ``_refresh_all_ui`` which calls our
        # parent tab's ``refresh_ui``, which re-calls ``_refresh_styles``.
        # Do it here too in case this widget is used standalone.
        self._refresh_styles(mode)

    def _refresh_styles(self, active: str) -> None:
        """Re-paint both buttons to reflect the current active mode."""
        def _active_style(left: bool) -> str:
            r_left  = "8px 0 0 8px"
            r_right = "0 8px 8px 0"
            radius  = r_left if left else r_right
            return f"""
        print(f"[DEBUG] _refresh_styles() called")
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


#  SETTINGS TAB  ─────────────────────────────────────────────────────────── #

class SettingsTab(QWidget):
    """
    Full Settings tab — scrollable page with three card sections.
    The widget tree is built ONCE in __init__ and never rebuilt.
    refresh_ui() updates labels and styles in-place.
    """

    def __init__(
        self,
        parent: QWidget,
        # Accept same kwargs the ctk version accepted:
        main_container=None,
        menu_frame=None,
        menu_buttons: Dict = None,
        switch_view_callback: Callable = None,
        notification_callback: Callable = None,
        **_kwargs,
    ):
        super().__init__(parent)
        print("[DEBUG] SettingsTab __init__ called")
        self.setStyleSheet(f"background:{COLORS['app_bg']};")

        self._notify_cb          = notification_callback
        self._menu_buttons       = menu_buttons or {}
        self._switch_view_cb     = switch_view_callback

        # Ensure the preview toggle state exists on the shared state object
        if not hasattr(state, 'texture_previews_enabled'):
            state.texture_previews_enabled = True

        # Label references updated by refresh_ui()
        self._section_labels: list = []

        self._setup_ui()

    # build (called ONCE)  ───────────────────────────────────────────────── #

    def _setup_ui(self):
        print(f"[DEBUG] _setup_ui() called")
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

        # main title
        self._main_title = QLabel(t("settings.title", default="Settings"))
        self._main_title.setFont(font(20, "bold"))
        self._main_title.setStyleSheet(f"color:{COLORS['text']};background:transparent;border:none;")
        col.addWidget(self._main_title)

        # PATH CONFIGURATION
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

        # APPEARANCE  ────────────────────────────────────────────────────── #
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

        # Texture Previews toggle
        preview_row = QHBoxLayout()
        preview_row.setSpacing(12)
        self._preview_label = QLabel("Texture Previews (.dds / .png):")
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
            "Show image previews when selecting .dds or .png textures. "
            "Disable for faster performance with very large files."
        )
        self._preview_desc.setFont(font(11))
        self._preview_desc.setWordWrap(True)
        self._preview_desc.setStyleSheet(
            f"color:{COLORS['text_secondary']};background:transparent;border:none;"
        )
        a_col.addWidget(self._preview_desc)

        col.addWidget(appearance_card)

        # ADVANCED  ──────────────────────────────────────────────────────── #
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

        # ── Testing Mode ────────────────────────────────────────────────── #
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

        col.addWidget(advanced_card)

        # UPDATES  ───────────────────────────────────────────────────────── #
        updates_card = self._card(page)
        upd_col = updates_card.layout()

        self._updates_title = self._section_title(
            t("settings.updates", default="Updates"), upd_col
        )

        # Current version row
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

        # Check for Updates button
        check_row = QHBoxLayout()
        self._check_update_btn = QPushButton(
            t("settings.check_for_updates", default="🔍  Check for Updates")
        )
        self._check_update_btn.setFont(font(13, "bold"))
        self._check_update_btn.setFixedHeight(40)
        self._check_update_btn.setCursor(Qt.PointingHandCursor)
        self._check_update_btn.setStyleSheet(self._primary_btn_style())
        self._check_update_btn.clicked.connect(self._on_check_for_updates)
        check_row.addWidget(self._check_update_btn)
        check_row.addStretch(1)
        upd_col.addLayout(check_row)

        # Skipped version indicator (hidden unless a version is skipped)
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

        # Embed the row in a plain container so we can hide/show it
        skip_container = QWidget()
        skip_container.setStyleSheet("background:transparent;border:none;")
        skip_container.setLayout(self._skip_row)
        self._skip_container = skip_container
        upd_col.addWidget(skip_container)

        self._refresh_skip_indicator()

        col.addWidget(updates_card)

        col.addStretch(1)

    # stylesheet helpers ─────────────────────────────────────────────────── #

    # updates ────────────────────────────────────────────────────────────── #

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
        """Show or hide the 'Skipped version: X' indicator."""
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
        print(f"[DEBUG] _lang_btn_style() called")
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
        print(f"[DEBUG] _card() called")
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
        print(f"[DEBUG] _section_title() called")
        lbl = QLabel(text)
        lbl.setFont(font(16, "bold"))
        lbl.setStyleSheet(f"color:{COLORS['text']};background:transparent;border:none;")
        layout.addWidget(lbl)
        return lbl

    # debug mode ─────────────────────────────────────────────────────────── #

    def _on_debug_toggled(self, checked: bool):
        print(f"[DEBUG] _on_debug_toggled: debug mode -> {checked}")
        print(f"[DEBUG] _on_debug_toggled: {checked}")
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

    # testing mode ───────────────────────────────────────────────────────── #

    def _on_testing_toggled(self, checked: bool):
        print(f"[DEBUG] _on_testing_toggled: testing mode -> {checked}")
        state.set_testing_mode(checked)

    # texture previews ───────────────────────────────────────────────────── #

    def _on_texture_previews_toggled(self, checked: bool):
        print(f"[DEBUG] _on_texture_previews_toggled: previews enabled -> {checked}")
        state.texture_previews_enabled = checked

    # language selector ──────────────────────────────────────────────────── #

    def _open_language_selector(self):
        print(f"[DEBUG] _open_language_selector: opening language picker dialog")
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

    # notification ───────────────────────────────────────────────────────── #

    def show_notification(self, type: str, message: str):
        print(f"[DEBUG] show_notification: [{type}] {message!r}")
        if self._notify_cb:
            # BeamSkinStudioApp.show_notification expects (message, type) —
            # swap here so the toast displays the real message text and uses
            # the correct colour/icon for the notification type.
            self._notify_cb(message, type)
        else:
            if type == "error":
                QMessageBox.critical(self, t("common.error", default="Error"), message)
            elif type == "warning":
                QMessageBox.warning(self, t("common.warning", default="Warning"), message)
            else:
                QMessageBox.information(self, t("common.info", default="Info"), message)

    # helpers ────────────────────────────────────────────────────────────── #

    def _find_root_app(self):
        print(f"[DEBUG] _find_root_app() called")
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
        print(f"[DEBUG] _refresh_all_ui() called")
        root = self._find_root_app()
        if not root:
            return

        # Prefer delegating to the root window's own implementation so that
        # sidebar._mod_entry / _author_entry are always re-wired to the
        # generator tab after the sidebar teardown-and-rebuild that
        # sidebar.refresh_ui() performs.  This avoids the bug where the
        # generator tab holds stale (deleteLater'd) widget references after
        # a language change.
        if hasattr(root, "_refresh_all_tabs"):
            try:
                root._refresh_all_tabs()
                return
            except Exception as e:
                print(f"[WARNING] _refresh_all_ui delegation failed: {e}")

        # Fallback: replicate the logic manually.
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
                # Re-wire new sidebar entry widgets to the generator tab so
                # that load_project() writes into the live QLineEdits.
                gen = root.tabs.get("generator") if hasattr(root, "tabs") else None
                if gen and hasattr(gen, "set_sidebar_references"):
                    gen.set_sidebar_references(
                        root.sidebar._mod_entry,
                        root.sidebar._author_entry,
                    )
            except Exception:
                pass

    def showEvent(self, event):
        """Reload paths whenever the settings tab becomes visible."""
        super().showEvent(event)
        if hasattr(self, "_path_section") and hasattr(self._path_section, "reload_paths"):
            try:
                self._path_section.reload_paths()
            except Exception as e:
                print(f"[WARNING] path reload on show: {e}")

    # refresh hook ───────────────────────────────────────────────────────── #

    def refresh_ui(self):
        """
        print(f"[DEBUG] showEvent() called")
        Update translatable text and re-apply all stylesheets in-place
        without rebuilding the widget tree.  Called after language changes
        and after theme switches.
        """
        # Re-skin this tab's background
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
        # Re-draw toggle buttons with fresh colours
        self._theme_toggle._refresh_styles(state.theme_mode)

        self._lang_label.setText(t("settings.language", default="Language:"))
        self._lang_label.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;"
        )
        available = get_available_languages()
        current   = get_current_language()
        lang_info = available.get(current, {"native": "English"})

        # Texture previews row
        self._preview_label.setText("Texture Previews (.dds / .png):")
        self._preview_label.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;"
        )
        self._preview_toggle.blockSignals(True)
        self._preview_toggle.setChecked(getattr(state, 'texture_previews_enabled', True))
        self._preview_toggle.blockSignals(False)
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

        # Testing mode checkbox keeps its hardcoded label (dev-only feature)
        self._testing_checkbox.setStyleSheet(
            f"color:{COLORS['text']};background:transparent;border:none;"
        )
        self._testing_checkbox.blockSignals(True)
        self._testing_checkbox.setChecked(state.testing_mode)
        self._testing_checkbox.blockSignals(False)
        self._testing_desc.setStyleSheet(
            f"color:{COLORS['text_secondary']};background:transparent;border:none;padding-left:22px;"
        )

        # Updates card
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


#  LANGUAGE SELECTOR DIALOG  ─────────────────────────────────────────────── #

class _LanguageSelectorDialog:
    """
    Simple language picker built from QDialog.
    Returns after exec() — check .selected_lang.
    """

    def __init__(self, parent: QWidget, available: dict, current: str):
        print(f"[DEBUG] __init__() called")
        from PySide6.QtWidgets import (
            QDialog, QScrollArea, QVBoxLayout,
            QLineEdit, QWidget, QPushButton
        )

        self.selected_lang = current
        self._dialog = QDialog(parent)
        self._dialog.setWindowTitle(t("settings.select_language_title"))
        self._dialog.resize(480, 520)
        self._dialog.setStyleSheet(f"background:{COLORS['app_bg']};color:{COLORS['text']};")

        col = QVBoxLayout(self._dialog)
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
        print(f"[DEBUG] _build_list() called")
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
        print(f"[DEBUG] _select() called")
        self.selected_lang = lang_code
        self._dialog.accept()

    def exec(self) -> bool:
        print(f"[DEBUG] exec() called")
        return bool(self._dialog.exec())


