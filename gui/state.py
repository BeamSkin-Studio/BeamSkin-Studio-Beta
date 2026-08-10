from __future__ import annotations
from typing import Dict, Optional, Any

from gui.theme import COLORS, ThemeManager

try:
    from core.settings import app_settings
    import core.settings as _settings_module
except ImportError as _exc:
    print(f"[DEBUG] _pipe_tmp.py: import failed ({_exc}), using fallback")
    app_settings = {}
    _settings_module = None

try:
    from core.config import VEHICLE_IDS
except ImportError as _exc:
    print(f"[DEBUG] _pipe_tmp.py: import failed ({_exc}), using fallback")
    VEHICLE_IDS: dict = {}

try:
    from core.updater import CURRENT_VERSION
except ImportError as _exc:
    print(f"[DEBUG] _pipe_tmp.py: import failed ({_exc}), using fallback")
    CURRENT_VERSION = '1.0.0'


class StateManager:
    _instance: Optional["StateManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self.colors: Dict[str, str] = COLORS

        self.app_settings        = app_settings
        self.vehicle_ids         = dict(VEHICLE_IDS)
        self._settings_module    = _settings_module
        self.current_version     = CURRENT_VERSION

        self.theme_mode: str = self._load_theme_preference()
        self.testing_mode: bool = self._load_testing_mode_preference()
        self.confirm_on_save: bool = self._load_confirm_on_save_preference()

        self._local_added_vehicles: Dict[str, str] = {}
        if self._settings_module is not None:
            if not hasattr(self._settings_module, "added_vehicles"):
                self._settings_module.added_vehicles = self._local_added_vehicles

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

        ThemeManager.instance().set_mode(self.theme_mode)


    def _load_theme_preference(self) -> str:
        if self._settings_module is not None:
            return getattr(self._settings_module, "app_settings", {}).get(
                "theme_mode", "dark"
            )
        if isinstance(self.app_settings, dict):
            return self.app_settings.get("theme_mode", "dark")
        return "dark"

    def _load_testing_mode_preference(self) -> bool:
        if self._settings_module is not None:
            return bool(getattr(self._settings_module, "app_settings", {}).get(
                "testing_mode", False
            ))
        if isinstance(self.app_settings, dict):
            return bool(self.app_settings.get("testing_mode", False))
        return False

    def _load_confirm_on_save_preference(self) -> bool:
        if self._settings_module is not None:
            return bool(getattr(self._settings_module, "app_settings", {}).get(
                "confirm_on_save", True
            ))
        if isinstance(self.app_settings, dict):
            return bool(self.app_settings.get("confirm_on_save", True))
        return True

    def set_confirm_on_save(self, enabled: bool) -> None:
        print(f"[DEBUG] set_confirm_on_save: enabled={enabled}")
        self.confirm_on_save = enabled
        if self._settings_module is not None:
            try:
                self._settings_module.app_settings["confirm_on_save"] = enabled
                self._settings_module.save_settings()
            except Exception as e:
                print(f"[WARNING] Could not persist confirm_on_save: {e}")
        elif isinstance(self.app_settings, dict):
            self.app_settings["confirm_on_save"] = enabled

    def set_testing_mode(self, enabled: bool) -> None:
        print(f"[DEBUG] set_testing_mode: enabled={enabled}")
        self.testing_mode = enabled
        if self._settings_module is not None:
            try:
                self._settings_module.app_settings["testing_mode"] = enabled
                self._settings_module.save_settings()
            except Exception as e:
                print(f"[WARNING] Could not persist testing_mode: {e}")
        elif isinstance(self.app_settings, dict):
            self.app_settings["testing_mode"] = enabled
        from PySide6.QtWidgets import QApplication
        for top in QApplication.topLevelWidgets():
            if hasattr(top, "sidebar"):
                try:
                    top.sidebar._add_all_btn.setVisible(enabled)
                except Exception as _exc:
                    print(f"[WARNING] set_testing_mode: {type(_exc).__name__}: {_exc}")

    def set_theme(self, mode: str) -> None:
        if mode not in ("dark", "light"):
            raise ValueError(f"Unknown theme mode: {mode!r}")
        self.theme_mode = mode
        ThemeManager.instance().set_mode(mode)
        self._save_theme_preference(mode)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self._refresh_all_ui)

    def _save_theme_preference(self, mode: str) -> None:
        if self._settings_module is not None:
            try:
                self._settings_module.app_settings["theme_mode"] = mode
                self._settings_module.save_settings()
            except Exception as e:
                print(f"[WARNING] Could not persist theme preference: {e}")
        elif isinstance(self.app_settings, dict):
            self.app_settings["theme_mode"] = mode

    def _refresh_all_ui(self) -> None:
        from PySide6.QtWidgets import QApplication
        for top in QApplication.topLevelWidgets():
            if hasattr(top, "_refresh_all_tabs"):
                try:
                    top._refresh_all_tabs()
                    continue
                except Exception as e:
                    print(f"[WARNING] _refresh_all_tabs delegation failed: {e}")

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
                except Exception as _exc:
                    print(f"[WARNING] _refresh_all_ui: {type(_exc).__name__}: {_exc}")
            if hasattr(top, "sidebar") and hasattr(top.sidebar, "refresh_ui"):
                try:
                    top.sidebar.refresh_ui(
                        getattr(top, "_add_vehicle_from_sidebar", None)
                    )
                    gen = top.tabs.get("generator") if hasattr(top, "tabs") else None
                    if gen and hasattr(gen, "set_sidebar_references"):
                        gen.set_sidebar_references(
                            top.sidebar._mod_entry,
                            top.sidebar._author_entry,
                        )
                except Exception as _exc:
                    print(f"[WARNING] _refresh_all_ui: {type(_exc).__name__}: {_exc}")


    @property
    def added_vehicles(self) -> Dict[str, str]:
        if self._settings_module is not None:
            return self._settings_module.added_vehicles
        return self._local_added_vehicles


    def reload_added_vehicles(self) -> bool:
        import json, os
        try:
            from core.settings import get_vehicles_dir
            path = os.path.join(get_vehicles_dir(), "added_vehicles.json")
        except ImportError as _exc:
            print(f"[WARNING] reload_added_vehicles: {type(_exc).__name__}: {_exc}")
            _base = os.path.dirname(os.path.abspath(__file__))
            path = os.path.join(_base, 'vehicles', 'added_vehicles.json')
        if not os.path.exists(path):
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            target = self.added_vehicles
            target.clear()
            target.update(loaded)
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
