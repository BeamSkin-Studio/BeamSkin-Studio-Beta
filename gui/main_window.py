from __future__ import annotations
import os
from typing import Dict, Optional

from PySide6.QtCore    import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui     import QPixmap, QIcon, QColor
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QFrame, QLabel, QVBoxLayout,
    QHBoxLayout, QStackedWidget, QApplication, QSizePolicy,
)

from gui.theme   import COLORS, APP_QSS, font, drop_shadow, fade_in
from gui.state   import state
from gui.icon_helper import set_window_icon
from gui.widgets import Toast, FadeStack, Spinner

from gui.components.navigation import Topbar, Sidebar
from gui.components.preview    import HoverPreviewManager, create_preview_overlay

try:
    from core.localization import t, get_localization
except ImportError:
    def t(key, **kw): return key
    def get_localization(): return None


# OFFLINE PLACEHOLDER

class OnlineUnavailableTab(QWidget):
    def __init__(self, parent=None, **_):
        print(f"[DEBUG] __init__() called")
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
        print(f"[DEBUG] refresh_ui() called")
        pass


# MAIN  WINDOW

class BeamSkinStudioApp(QMainWindow):

    def __init__(self):
        print(f"[DEBUG] __init__() called")
        super().__init__()
        QApplication.instance().setStyleSheet(APP_QSS)

        self.setWindowTitle("BeamSkin Studio")
        set_window_icon(self)
        self.resize(1600, 1000)
        self.setMinimumSize(1000, 700)

        central = QWidget()
        self.setCentralWidget(central)
        self._root_layout = QVBoxLayout(central)
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(0)

        self.tabs: Dict[str, QWidget] = {}
        self.current_tab = "generator"

        self._setup_ui()
        self.show()
        self._post_init()


    def _setup_ui(self):
        print(f"[DEBUG] _setup_ui() called")
        logo_px = self._load_logo_pixmap()
        self.topbar = Topbar(self, logo_pixmap=logo_px)
        self.topbar.view_changed.connect(self.switch_view)
        self.topbar.generate_clicked.connect(self._generate_mod)
        self._root_layout.addWidget(self.topbar)

        content_row = QHBoxLayout()
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(0)

        self.sidebar = Sidebar(self)
        # Sidebar now emits (carid, display_name, variant_suffix).
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
        print(f"[DEBUG] _build_tabs: building all tab widgets")
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
        print(f"[DEBUG] _generate_mod: triggering mod generation")
        gen = self.tabs.get("generator")
        if gen and hasattr(gen, "generate_mod"):
            gen.generate_mod(
                self.topbar.generate_button,
                self.sidebar.get_output_mode(),
                self.sidebar.get_custom_output(),
                self.sidebar.get_unpacked(),
            )


    def _add_vehicle_from_sidebar(self, carid: str, display_name: str, variant: str = ""):
        """
        Callback wired to sidebar.add_vehicle_requested.

        Parameters
        ----------
        carid        : Vehicle ID (e.g. "pickup")
        display_name : Human-readable name including variant if applicable
                       (e.g. "Pickup (Ambulance)").  This is already formatted
                       by VehicleVariantExpander before the signal is emitted.
        variant      : Body-variant suffix, e.g. "" (normal), "ambulance", "box".
        """
        print(f"[DEBUG] _add_vehicle_from_sidebar() called")
        gen = self.tabs.get("generator")
        if gen and hasattr(gen, "add_car_to_project"):
            gen.add_car_to_project(carid, display_name, variant)
            # The sidebar widget is removed on add, so Qt never fires leaveEvent
            # on it — force-hide the preview here so it doesn't get stuck.
            if hasattr(self, "preview_manager"):
                self.preview_manager.hide_hover_preview(force=True)
            self.show_notification(
                f"Added {display_name} to project", type="success"
            )


    def _refresh_vehicle_list(self):
        """
        Called by AddVehiclesTab after a vehicle/variant is added or deleted.

        Mirrors generator._build_car_id_list(): uses load_added_vehicles_json()
        (the same source of truth used at startup) to sync state.added_vehicles,
        then repopulates the sidebar, the generator's car list, and the CarListTab.
        """
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

        # Keep CarListTab in sync — without this, added/deleted vehicles only
        # appear there after a full app restart.
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
        print(f"[DEBUG] _load_logo_pixmap() called")
        icon_dir = os.path.join("gui", "Icons")
        path = os.path.join(icon_dir, "BeamSkin_Studio_White.png")
        if os.path.exists(path):
            return QPixmap(path)
        return None


    def _post_init(self):
        print(f"[DEBUG] _post_init() called")
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
        print(f"[DEBUG] _refresh_all_tabs: refreshing all tab UIs")
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


    def show_setup_wizard(self):
        print(f"[DEBUG] show_setup_wizard() called")
        from gui.components.setup_wizard import show_setup_wizard
        from core.settings import set_beamng_paths, mark_setup_complete

        def _done(paths: dict):
            set_beamng_paths(**paths)
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
        print(f"[DEBUG] show_startup_warning() called")
        from gui.components.dialogs import show_wip_warning
        show_wip_warning(self)
        QTimer.singleShot(200, self._maybe_show_changelog)

    def _maybe_show_changelog(self):
        print(f"[DEBUG] _maybe_show_changelog() called")
        from gui.components.changelog_dialog import show_changelog_if_needed
        from core.updater import CURRENT_VERSION
        show_changelog_if_needed(self, CURRENT_VERSION)

    def prompt_update(self, new_version: str):
        print(f"[DEBUG] prompt_update() called")
        from gui.components.dialogs import show_update_dialog
        show_update_dialog(self, new_version)


    def show_startup_sequence(self):
        print(f"[DEBUG] show_startup_sequence() called")
        if not self.isVisible():
            self.show()
        self.raise_()
        self.activateWindow()
        try:
            from core.settings import is_setup_complete
            if not is_setup_complete():
                QTimer.singleShot(100, self.show_setup_wizard)
                return
        except ImportError:
            pass
        QTimer.singleShot(100, self.show_startup_warning)


    def closeEvent(self, event):
        print(f"[DEBUG] closeEvent: application closing")
        print("[DEBUG] Shutting down BeamSkin Studio...")
        event.accept()


# ENTRY POINT

def main():
    import sys
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore    import Qt

    try:
        from gui.tabs.add_vehicles import load_added_vehicles_at_startup
        load_added_vehicles_at_startup()
    except Exception:
        pass

    app = QApplication.instance() or QApplication(sys.argv)
    app.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    window = BeamSkinStudioApp()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()


