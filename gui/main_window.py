from __future__ import annotations
import os
from typing import Dict, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QMainWindow, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QApplication

from gui.theme import COLORS, APP_QSS, font
from gui.state   import state
from gui.icon_helper import set_window_icon
from gui.widgets import Toast, FadeStack

from gui.components.navigation import Topbar, Sidebar
from gui.components.preview    import HoverPreviewManager, create_preview_overlay

try:
    from core.localization import t, get_localization
except ImportError as _exc:
    print(f"[DEBUG] _pipe_tmp.py: import failed ({_exc}), using fallback")
    def t(key, **kw):
        return key
    def get_localization():
        return None


class OnlineUnavailableTab(QWidget):
    def __init__(self, parent=None, **_):
        super().__init__(parent)
        self.setStyleSheet(f"background:{COLORS['app_bg']};")
        col = QVBoxLayout(self)
        col.setAlignment(Qt.AlignCenter)
        col.setSpacing(12)

        icon = QLabel("🚧")
        icon.setFont(font(52))
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("background:transparent;border:none;")
        col.addWidget(icon)

        title = QLabel(t("online.unavailable", default="Online Features Unavailable"))
        title.setFont(font(20, "bold"))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"color:{COLORS['text']};background:transparent;")
        col.addWidget(title)

        sub = QLabel(t("online.online_server",
                        default="This feature requires an active server connection."))
        sub.setFont(font(13))
        sub.setAlignment(Qt.AlignCenter)
        sub.setWordWrap(True)
        sub.setStyleSheet(f"color:{COLORS['text_secondary']};background:transparent;")
        col.addWidget(sub)

    def refresh_ui(self):
        pass


class BeamSkinStudioApp(QMainWindow):
    def __init__(self):
        super().__init__()
        QApplication.instance().setStyleSheet(APP_QSS)

        self.setWindowTitle("BeamSkin Studio")
        set_window_icon(self)
        self.resize(1460, 1000)
        self.setMinimumSize(1300, 700)

        central = QWidget()
        self.setCentralWidget(central)
        self._root_layout = QVBoxLayout(central)
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(0)

        self.tabs: Dict[str, QWidget] = {}
        self.current_tab = "generator"

        self._setup_ui()
        self._post_init()


    def _setup_ui(self):
        logo_px = self._load_logo_pixmap()
        self.topbar = Topbar(self, logo_pixmap=logo_px)
        self.topbar.view_changed.connect(self.switch_view)
        self.topbar.generate_clicked.connect(self._generate_mod)
        self._root_layout.addWidget(self.topbar)

        content_row = QHBoxLayout()
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(0)

        self.sidebar = Sidebar(self)
        self.sidebar.add_vehicle_requested.connect(
            self._add_vehicle_from_sidebar
        )
        content_row.addWidget(self.sidebar)

        self._stack = FadeStack()
        self._stack.setStyleSheet(f"background:{COLORS['app_bg']};")
        content_row.addWidget(self._stack, 1)

        wrapper = QWidget()
        wrapper.setLayout(content_row)
        self._root_layout.addWidget(wrapper, 1)

        _central = self.centralWidget()
        self._preview_overlay = create_preview_overlay(_central)
        self.preview_manager  = HoverPreviewManager(_central, self._preview_overlay)

        self._build_tabs()

    def _build_tabs(self):
        print("[DEBUG] _build_tabs: building all tab widgets")
        from gui.tabs.generator    import GeneratorTab
        from gui.tabs.howto        import HowToTab
        from gui.tabs.car_list     import CarListTab
        from gui.tabs.add_vehicles import AddVehiclesTab
        from gui.tabs.settings     import SettingsTab
        from gui.tabs.about        import AboutTab

        try:
            from gui.tabs.online_tab import OnlineTab as _OnlineTab
            _online_cls    = _OnlineTab
            _online_kwargs = {"notification_callback": self.show_notification}
        except Exception as e:
            print(f"[WARN] Could not import OnlineTab: {e}")
            _online_cls    = OnlineUnavailableTab
            _online_kwargs = {}

        tab_classes = {
            "generator":    (GeneratorTab,   {"preview_manager": self.preview_manager,
                                               "notification_callback": self.show_notification}),
            "howto":        (HowToTab,       {}),
            "carlist":      (CarListTab,     {}),
            "add_vehicles": (AddVehiclesTab, {"notification_callback": self.show_notification,
                                               "refresh_vehicle_list_callback": self._refresh_vehicle_list}),
            "settings":     (SettingsTab,    {"notification_callback": self.show_notification}),
            "about":        (AboutTab,       {}),
            "online_tab":   (_online_cls,    _online_kwargs),
        }

        for name, (cls, kwargs) in tab_classes.items():
            try:
                tab = cls(self, **kwargs)
            except TypeError:
                try:
                    tab = cls(self)
                except Exception as e:
                    print(f"[ERROR] Could not create tab '{name}': {e}")
                    tab = OnlineUnavailableTab(self)
            except Exception as e:
                print(f"[ERROR] Could not create tab '{name}': {e}")
                import traceback; traceback.print_exc()
                tab = OnlineUnavailableTab(self)

            self.tabs[name] = tab
            self._stack.addWidget(tab)

        gen = self.tabs.get("generator")
        if gen and hasattr(gen, "add_car_to_project"):
            self.sidebar.populate_vehicles(self._add_vehicle_from_sidebar)
        self.switch_view("generator")

        if gen and hasattr(gen, "set_sidebar_references"):
            gen.set_sidebar_references(
                self.sidebar._mod_entry,
                self.sidebar._author_entry,
            )


    def switch_view(self, view_name: str):
        print(f"[DEBUG] switch_view: switching to {view_name!r}")
        if view_name not in self.tabs:
            print(f"[DEBUG] Tab '{view_name}' not found")
            return

        self.topbar.set_active(view_name)
        self.sidebar.setVisible(view_name == "generator")

        idx = self._stack.indexOf(self.tabs[view_name])
        self._stack.setCurrentIndex(idx)
        self.current_tab = view_name


    def _generate_mod(self):
        print("[DEBUG] _generate_mod: triggering mod generation")
        gen = self.tabs.get("generator")
        if gen and hasattr(gen, "generate_mod"):
            gen.generate_mod(
                self.topbar.generate_button,
                self.sidebar.get_output_mode(),
                self.sidebar.get_custom_output(),
                self.sidebar.get_unpacked(),
            )


    def _add_vehicle_from_sidebar(self, carid: str, display_name: str, variant: str = ""):
        gen = self.tabs.get("generator")
        if gen and hasattr(gen, "add_car_to_project"):
            gen.add_car_to_project(carid, display_name, variant)
            if hasattr(self, "preview_manager"):
                self.preview_manager.hide_hover_preview(force=True)
            self.show_notification(
                f"Added {display_name} to project", type="success"
            )


    def _refresh_vehicle_list(self):
        try:
            from utils.file_ops import load_added_vehicles_json
            vehicles = load_added_vehicles_json()
            state.added_vehicles.clear()
            state.added_vehicles.update(vehicles)
        except Exception as e:
            print(f"[WARNING] _refresh_vehicle_list: could not reload vehicles: {e}")

        if hasattr(self, "sidebar"):
            self.sidebar.populate_vehicles(self._add_vehicle_from_sidebar)

        gen = self.tabs.get("generator")
        if gen and hasattr(gen, "refresh_vehicle_list"):
            try:
                gen.refresh_vehicle_list()
            except Exception as e:
                print(f"[WARNING] _refresh_vehicle_list: gen.refresh_vehicle_list failed: {e}")

        carlist = self.tabs.get("carlist")
        if carlist and hasattr(carlist, "refresh_vehicle_list"):
            try:
                carlist.refresh_vehicle_list()
            except Exception as e:
                print(f"[WARNING] _refresh_vehicle_list: carlist.refresh_vehicle_list failed: {e}")

    def show_notification(
        self, message: str, type: str = "info", duration: int = 3000
    ):
        cw = self.centralWidget() or self
        toast = Toast(cw, message, kind=type, duration=duration)
        toast.move(
            cw.width()  - toast.width()  - 20,
            cw.height() - toast.height() - 20,
        )
        toast.show()
        toast.raise_()


    def _load_logo_pixmap(self) -> Optional[QPixmap]:
        icon_dir = os.path.join("gui", "Icons")
        path = os.path.join(icon_dir, "BeamSkin_Studio_White.png")
        if os.path.exists(path):
            return QPixmap(path)
        return None


    def _post_init(self):
        QTimer.singleShot(150, self._apply_startup_language)

    def _apply_startup_language(self):
        try:
            from core.localization import set_language
            from core.settings import app_settings
            lang = app_settings.get("language", "en_US")
            set_language(lang)
            self._refresh_all_tabs()
        except Exception as e:
            print(f"[ERROR] _apply_startup_language: {e}")

    def _refresh_all_tabs(self):
        print("[DEBUG] _refresh_all_tabs: refreshing all tab UIs")
        for name, tab in self.tabs.items():
            if hasattr(tab, "refresh_ui"):
                try:
                    tab.refresh_ui()
                except Exception as e:
                    print(f"[ERROR] refresh_ui for {name}: {e}")
        if hasattr(self, "topbar"):
            try:
                self.topbar.refresh_ui()
            except Exception as e:
                print(f"[ERROR] topbar.refresh_ui: {e}")
        if hasattr(self, "sidebar"):
            try:
                self.sidebar.refresh_ui(
                    getattr(self, "_add_vehicle_from_sidebar", None)
                )
                gen = self.tabs.get("generator")
                if gen and hasattr(gen, "set_sidebar_references"):
                    gen.set_sidebar_references(
                        self.sidebar._mod_entry,
                        self.sidebar._author_entry,
                    )
            except Exception as e:
                print(f"[ERROR] sidebar.refresh_ui: {e}")


    def show_legacy_migration_prompt(self, then: callable):
        try:
            from gui.components.legacy_migration_dialog import (
                show_legacy_migration_dialog_if_needed,
            )
        except Exception as e:
            print(f"[WARNING] show_legacy_migration_prompt: could not import dialog: {e}")
            then()
            return

        shown = show_legacy_migration_dialog_if_needed(self, then)
        if not shown:
            then()

    def show_setup_wizard(self):
        from gui.components.setup_wizard import show_setup_wizard
        from core.settings import set_beamng_paths, mark_setup_complete

        def _done(paths: dict):
            set_beamng_paths(
                beamng_install=paths.get("beamng_install"),
                mods_folder=paths.get("mods_folder"),
            )
            mark_setup_complete()
            try:
                from core.localization import set_language as _set_lang
                from core.settings import app_settings
                _set_lang(app_settings.get("language", "en_US"))
            except Exception as e:
                print(f"[WARNING] _done: could not apply wizard language: {e}")
            self._refresh_all_tabs()
            if paths.get("beamng_install") or paths.get("mods_folder"):
                self.show_notification("Setup complete! Paths saved.", type="success")
            QTimer.singleShot(400, self.show_startup_warning)

        show_setup_wizard(self, state.colors, _done)

    def show_startup_warning(self):
        from gui.components.dialogs import show_wip_warning
        show_wip_warning(self)
        QTimer.singleShot(200, self._maybe_show_changelog)

    def _maybe_show_changelog(self):
        from gui.components.changelog_dialog import show_changelog_if_needed
        from core.updater import CURRENT_VERSION
        show_changelog_if_needed(self, CURRENT_VERSION)

    def prompt_update(self, new_version: str):
        from gui.components.dialogs import show_update_dialog
        show_update_dialog(self, new_version)


    def show_startup_sequence(self):
        if not self.isVisible():
            self.show()
        self.raise_()
        self.activateWindow()

        def _after_legacy_check():
            try:
                from core.settings import is_setup_complete
                if not is_setup_complete():
                    QTimer.singleShot(100, self.show_setup_wizard)
                    return
            except ImportError as _exc:
                print(f"[WARNING] _after_legacy_check: {type(_exc).__name__}: {_exc}")
            QTimer.singleShot(100, self.show_startup_warning)

        QTimer.singleShot(100, lambda: self.show_legacy_migration_prompt(_after_legacy_check))


    def closeEvent(self, event):
        print("[DEBUG] closeEvent: application closing")

        gen = self.tabs.get("generator")
        if gen is not None and getattr(gen, "_project_dirty", False):
            print("[DEBUG] closeEvent: unsaved project changes detected, confirming with user")
            proceed = gen._confirm_discard_if_dirty(
                "project.unsaved.close_message",
                "project.unsaved.close_title",
            )
            if not proceed:
                print("[DEBUG] closeEvent: user cancelled close due to unsaved changes")
                event.ignore()
                return

        print("[DEBUG] Shutting down BeamSkin Studio...")
        event.accept()


def main():
    import sys
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore    import Qt

    try:
        from gui.tabs.add_vehicles import load_added_vehicles_at_startup
        load_added_vehicles_at_startup()
    except Exception as _exc:
        print(f"[WARNING] main: {type(_exc).__name__}: {_exc}")

    app = QApplication.instance() or QApplication(sys.argv)
    app.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    window = BeamSkinStudioApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
