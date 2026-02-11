"""
State Manager
"""
from typing import Dict, List, Tuple, Optional, Any
import customtkinter as ctk
from core.settings import colors, current_theme, app_settings, THEMES, EDITABLE_COLOR_KEYS, COLOR_LABELS
from core.updater import CURRENT_VERSION

import core.settings as settings_module

try:
    from core.config import VEHICLE_IDS
except ImportError:
    print("[WARNING] core/config.py not found, using empty VEHICLE_IDS")
    VEHICLE_IDS = {}

class StateManager:
    """Singleton class to manage application state"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(StateManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self.colors = colors
        self.current_theme = current_theme
        self.app_settings = app_settings
        self.themes = THEMES
        self.editable_color_keys = EDITABLE_COLOR_KEYS
        self.color_labels = COLOR_LABELS

        self.vehicle_ids = VEHICLE_IDS

        self._settings_module = settings_module

        self.current_version = CURRENT_VERSION

        self.project_data: Dict[str, Any] = {
            'mod_name': "My Mod",
            'author_name': "",
            'mod_description': "",
            'mod_version': "1.0",
            'added_cars': []
        }

        self.selected_carid: Optional[str] = None
        self.selected_display_name: Optional[str] = None
        self.expanded_vehicle_carid: Optional[str] = None

        self.sidebar_vehicle_buttons: List[Tuple[ctk.CTkFrame, str, str, ctk.CTkFrame]] = []
        self.carlist_items: List[Tuple[ctk.CTkFrame, str, str]] = []
        self.car_id_list: List[Tuple[str, str]] = []

        self.car_card_frames: List[ctk.CTkFrame] = []

        self.material_settings: Dict[str, Dict[str, Any]] = {}

        self.debug_mode: bool = False

        self.output_icons: Dict[str, Any] = {}

    @property
    def added_vehicles(self):
        """Property that always returns the current added_vehicles from settings module"""
        return self._settings_module.added_vehicles

    def reload_added_vehicles(self):
        """Force reload added_vehicles from disk"""
        import json
        import os

        json_path = "vehicles/added_vehicles.json"
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)

                self._settings_module.added_vehicles.clear()
                self._settings_module.added_vehicles.update(loaded)

                for carid, carname in loaded.items():
                    if carid not in self.vehicle_ids:
                        self.vehicle_ids[carid] = carname

                print(f"[DEBUG] Reloaded {len(loaded)} vehicles from added_vehicles.json")
                return True
            except Exception as e:
                print(f"[ERROR] Failed to reload added_vehicles: {e}")
                return False
        return False

    def get_vehicle_name(self, carid: str) -> str:
        """Get the display name for a vehicle ID"""

        if carid in self.added_vehicles:
            return self.added_vehicles[carid]

        return self.vehicle_ids.get(carid, carid)

    def is_vehicle_in_project(self, carid: str) -> bool:
        """Check if a vehicle is already in the project"""
        return any(car['id'] == carid for car in self.project_data['added_cars'])

    def add_vehicle_to_project(self, carid: str, display_name: str) -> None:
        """Add a vehicle to the project"""
        if not self.is_vehicle_in_project(carid):
            self.project_data['added_cars'].append({
                'id': carid,
                'name': display_name,
                'settings': {}
            })

    def remove_vehicle_from_project(self, carid: str) -> None:
        """Remove a vehicle from the project"""
        self.project_data['added_cars'] = [
            car for car in self.project_data['added_cars']
            if car['id'] != carid
        ]

    def get_project_vehicle_count(self) -> int:
        """Get the number of vehicles in the current project"""
        return len(self.project_data['added_cars'])

    def clear_project(self) -> None:
        """Clear all vehicles from the project"""
        self.project_data['added_cars'] = []

    def update_color(self, key: str, value: str) -> None:
        """Update a theme color"""
        self.colors[key] = value

    def reset_theme_colors(self) -> None:
        """Reset theme colors to defaults"""
        from core.settings import reset_theme_colors
        reset_theme_colors()

state = StateManager()