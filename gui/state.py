from __future__ import annotations
from typing import Dict, List, Tuple, Optional, Any

from gui.theme import COLORS, ThemeManager

try:
    from core.settings import app_settings
    import core.settings as _settings_module
except ImportError:
    app_settings     = {}
    _settings_module = None  # type: ignore

try:
    from core.config import VEHICLE_IDS
except ImportError:
    VEHICLE_IDS: dict = {}

try:
    from core.updater import CURRENT_VERSION
except ImportError:
    CURRENT_VERSION = "1.0.0"


class StateManager:
    """Singleton application state."""

    _instance: Optional["StateManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        print(f"[DEBUG] __init__() called")
        if self._initialized:
            return
        self._initialized = True

        # ``self.colors`` IS the same live dict as ``theme.COLORS``.
        # ThemeManager mutates COLORS in-place so both references stay in sync.
        self.colors: Dict[str, str] = COLORS

        self.app_settings        = app_settings
        self.vehicle_ids         = dict(VEHICLE_IDS)
        self._settings_module    = _settings_module
        self.current_version     = CURRENT_VERSION

        self.theme_mode: str = self._load_theme_preference()
        self.testing_mode: bool = self._load_testing_mode_preference()

        self._local_added_vehicles: Dict[str, str] = {}
        if self._settings_module is not None:
            if not hasattr(self._settings_module, "added_vehicles"):
                self._settings_module.added_vehicles = self._local_added_vehicles

        # project
        self.project_data: Dict[str, Any] = {
            "mod_name":        "My Mod",
            "author_name":     "",
            "mod_description": "",
            "mod_version":     "1.0",
            "added_cars":      [],
        }

        self.selected_carid:          Optional[str] = None
        self.selected_display_name:   Optional[str] = None
        self.expanded_vehicle_carid:  Optional[str] = None

        self.sidebar_vehicle_buttons: list = []
        self.carlist_items:           list = []
        self.car_id_list:             list = []
        self.car_card_frames:         list = []
        self.material_settings:       Dict[str, Dict[str, Any]] = {}
        self.debug_mode:              bool = False
        self.output_icons:            Dict[str, Any] = {}

        # Apply persisted theme on startup (before any window is shown).
        ThemeManager.instance().set_mode(self.theme_mode)


    def _load_theme_preference(self) -> str:
        print(f"[DEBUG] _load_theme_preference() called")
        # app_settings is loaded from data/app_settings.json at import time,
        # so reading it here gives the persisted value straight away.
        if self._settings_module is not None:
            return getattr(self._settings_module, "app_settings", {}).get(
                "theme_mode", "dark"
            )
        if isinstance(self.app_settings, dict):
            return self.app_settings.get("theme_mode", "dark")
        return "dark"

    def _load_testing_mode_preference(self) -> bool:
        print(f"[DEBUG] _load_testing_mode_preference() called")
        if self._settings_module is not None:
            return bool(getattr(self._settings_module, "app_settings", {}).get(
                "testing_mode", False
            ))
        if isinstance(self.app_settings, dict):
            return bool(self.app_settings.get("testing_mode", False))
        return False

    def set_testing_mode(self, enabled: bool) -> None:
        """Enable or disable developer testing mode and persist the preference."""
        print(f"[DEBUG] set_testing_mode() called: enabled={enabled}")
        self.testing_mode = enabled
        if self._settings_module is not None:
            try:
                self._settings_module.app_settings["testing_mode"] = enabled
                self._settings_module.save_settings()
            except Exception as e:
                print(f"[WARNING] Could not persist testing_mode: {e}")
        elif isinstance(self.app_settings, dict):
            self.app_settings["testing_mode"] = enabled
        # Directly toggle the sidebar button — no full UI rebuild needed.
        from PySide6.QtWidgets import QApplication
        for top in QApplication.topLevelWidgets():
            if hasattr(top, "sidebar"):
                try:
                    top.sidebar._add_all_btn.setVisible(enabled)
                except Exception:
                    pass

    def set_theme(self, mode: str) -> None:
        """
        Switch the application theme.

        Flow:
          1. ``ThemeManager.set_mode()`` — mutates COLORS, re-applies app QSS,
             patches every live widget's stylesheet via single-pass regex.
          2. Persist the preference.
          3. ``_refresh_all_ui()`` — rebuilds topbar/sidebar (they regenerate
             their stylesheets from current COLORS) and calls refresh_ui() on
             each tab (updates translated text + any remaining custom styles).

        _refresh_all_ui is deferred via QTimer so that the current event
        (e.g. a button click that triggered the theme switch) finishes
        before sidebar.refresh_ui() tears down and deleteLater()s widgets.
        Doing it synchronously risks accessing widgets scheduled for deletion
        inside the same call stack as the originating click handler.
        """
        print(f"[DEBUG] set_theme() called")
        if mode not in ("dark", "light"):
            raise ValueError(f"Unknown theme mode: {mode!r}")
        self.theme_mode = mode
        ThemeManager.instance().set_mode(mode)
        self._save_theme_preference(mode)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self._refresh_all_ui)

    def _save_theme_preference(self, mode: str) -> None:
        print(f"[DEBUG] _save_theme_preference() called")
        if self._settings_module is not None:
            try:
                # Write into the live dict so in-process reads are correct too.
                self._settings_module.app_settings["theme_mode"] = mode
                # save_settings() is the function that flushes to
                # data/app_settings.json — NOT .save() (which doesn't exist).
                self._settings_module.save_settings()
            except Exception as e:
                print(f"[WARNING] Could not persist theme preference: {e}")
        elif isinstance(self.app_settings, dict):
            self.app_settings["theme_mode"] = mode

    def _refresh_all_ui(self) -> None:
        """Rebuild chrome widgets and call refresh_ui() on all tabs."""
        from PySide6.QtWidgets import QApplication
        for top in QApplication.topLevelWidgets():
            # Prefer the root window's own _refresh_all_tabs() so that
            # sidebar._mod_entry / _author_entry are re-wired to the
            # generator tab after the sidebar teardown-and-rebuild that
            # sidebar.refresh_ui() performs.
            if hasattr(top, "_refresh_all_tabs"):
                try:
                    top._refresh_all_tabs()
                    continue
                except Exception as e:
                    print(f"[WARNING] _refresh_all_tabs delegation failed: {e}")

            # Fallback path (e.g. during tests or alternative host windows).
            if hasattr(top, "tabs"):
                for name, tab in top.tabs.items():
                    if hasattr(tab, "refresh_ui"):
                        try:
                            tab.refresh_ui()
                        except Exception as e:
                            print(f"[WARNING] refresh_ui {name}: {e}")
            if hasattr(top, "topbar") and hasattr(top.topbar, "refresh_ui"):
                try:
                    top.topbar.refresh_ui()
                except Exception:
                    pass
            if hasattr(top, "sidebar") and hasattr(top.sidebar, "refresh_ui"):
                try:
                    top.sidebar.refresh_ui(
                        getattr(top, "_add_vehicle_from_sidebar", None)
                    )
                    # Re-wire new sidebar entry widgets to the generator tab.
                    gen = top.tabs.get("generator") if hasattr(top, "tabs") else None
                    if gen and hasattr(gen, "set_sidebar_references"):
                        gen.set_sidebar_references(
                            top.sidebar._mod_entry,
                            top.sidebar._author_entry,
                        )
                except Exception:
                    pass


    @property
    def added_vehicles(self) -> Dict[str, str]:
        if self._settings_module is not None:
            return self._settings_module.added_vehicles  # type: ignore[attr-defined]
        return self._local_added_vehicles


    def reload_added_vehicles(self) -> bool:
        import json, os
        # Resolve relative to this file rather than the process working
        # directory, which varies depending on how the app is launched.
        _base = os.path.dirname(os.path.abspath(__file__))
        path  = os.path.join(_base, "vehicles", "added_vehicles.json")
        if not os.path.exists(path):
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            self.added_vehicles.clear()
            self.added_vehicles.update(loaded)
            for cid, name in loaded.items():
                if cid not in self.vehicle_ids:
                    self.vehicle_ids[cid] = name
            return True
        except Exception as e:
            print(f"[ERROR] reload_added_vehicles: {e}")
            return False


    def get_vehicle_name(self, carid: str) -> str:
        if carid in self.added_vehicles:
            return self.added_vehicles[carid]
        return self.vehicle_ids.get(carid, carid)

    def is_vehicle_in_project(self, carid: str) -> bool:
        return any(c["id"] == carid for c in self.project_data["added_cars"])

    def add_vehicle_to_project(self, carid: str, display_name: str):
        if not self.is_vehicle_in_project(carid):
            self.project_data["added_cars"].append(
                {"id": carid, "name": display_name, "settings": {}}
            )

    def remove_vehicle_from_project(self, carid: str):
        self.project_data["added_cars"] = [
            c for c in self.project_data["added_cars"] if c["id"] != carid
        ]

    def get_project_vehicle_count(self) -> int:
        return len(self.project_data["added_cars"])

    def clear_project(self):
        self.project_data["added_cars"] = []

    def update_color(self, key: str, value: str):
        self.colors[key] = value


state = StateManager()
