import os
import json
from typing import Dict, Any

LANGUAGES_DIR = "core/localization/languages"
DEFAULT_LANGUAGE = "en_US"

AVAILABLE_LANGUAGES = {}

def _bundled_languages_dir() -> str:
    try:
        from core.settings import get_bundle_path
        return os.path.join(get_bundle_path(), LANGUAGES_DIR)
    except ImportError as _exc:
        print(f"[WARNING] _bundled_languages_dir: {type(_exc).__name__}: {_exc}")
        import sys
        if getattr(sys, 'frozen', False):
            program_root = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
        else:
            program_root = os.getcwd()
        return os.path.join(program_root, LANGUAGES_DIR)


def _writable_languages_dir() -> str:
    try:
        from core.settings import get_data_dir
        path = os.path.join(get_data_dir(), "languages")
        os.makedirs(path, exist_ok=True)
        return path
    except ImportError as _exc:
        print(f"[WARNING] _writable_languages_dir: {type(_exc).__name__}: {_exc}")
        path = _bundled_languages_dir()
        os.makedirs(path, exist_ok=True)
        return path


def _load_available_languages():
    global AVAILABLE_LANGUAGES
    AVAILABLE_LANGUAGES = {}

    search_dirs = [_writable_languages_dir(), _bundled_languages_dir()]

    print(f"[DEBUG] Looking for languages in: {search_dirs}")

    files_by_dir = {}
    for languages_path in search_dirs:
        if not os.path.exists(languages_path):
            print(f"[WARNING] Languages directory not found: {languages_path}")
            continue
        try:
            files_by_dir[languages_path] = os.listdir(languages_path)
        except Exception as e:
            print(f"[ERROR] Cannot read languages directory {languages_path}: {e}")

    if not files_by_dir:
        AVAILABLE_LANGUAGES["en_US"] = {"name": "English", "native": "English", "flag": "US"}
        return

    flattened = [
        (languages_path, filename)
        for languages_path in reversed(search_dirs)
        for filename in files_by_dir.get(languages_path, [])
    ]
    files = flattened
    
    for languages_path, filename in files:
        if filename.endswith('.json'):
            lang_code = filename[:-5]
            file_path = os.path.join(languages_path, filename)
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                if 'language_info' in data:
                    info = data['language_info']
                    AVAILABLE_LANGUAGES[lang_code] = {
                        "name": info.get("name", lang_code),
                        "native": info.get("native", lang_code),
                        "flag": info.get("flag", "US")
                    }
                    print(f"[DEBUG] Loaded language: {lang_code} - {info.get('native', lang_code)}")
                else:
                    AVAILABLE_LANGUAGES[lang_code] = {
                        "name": lang_code,
                        "native": lang_code,
                        "flag": lang_code.split('_')[1] if '_' in lang_code else "US"
                    }
                    print(f"[WARNING] No language_info in {filename}, using defaults")
                    
            except Exception as e:
                print(f"[ERROR] Failed to load language file {filename}: {e}")
    
    if not AVAILABLE_LANGUAGES:
        print("[WARNING] No languages loaded, using default English")
        AVAILABLE_LANGUAGES["en_US"] = {"name": "English", "native": "English", "flag": "US"}
    elif "en_US" not in AVAILABLE_LANGUAGES and len(AVAILABLE_LANGUAGES) > 0:
        print("[WARNING] en_US not found, adding default English")
        AVAILABLE_LANGUAGES["en_US"] = {"name": "English", "native": "English", "flag": "US"}
    
    print(f"[DEBUG] Total languages loaded: {len(AVAILABLE_LANGUAGES)}")

_load_available_languages()

class LocalizationManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LocalizationManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        self.current_language = DEFAULT_LANGUAGE
        self.translations: Dict[str, Any] = {}
        self.fallback_translations: Dict[str, Any] = {}
        
        self.languages_dir = _bundled_languages_dir()

        self.writable_languages_dir = _writable_languages_dir()

        print(f"[DEBUG] LocalizationManager bundled languages directory: {self.languages_dir}")
        print(f"[DEBUG] LocalizationManager writable languages directory: {self.writable_languages_dir}")

        self._load_language(DEFAULT_LANGUAGE, fallback=True)
        
        from core.settings import app_settings
        saved_language = app_settings.get("language", DEFAULT_LANGUAGE)
        self.set_language(saved_language)
    
    def _load_language(self, language_code: str, fallback: bool = False) -> bool:
        bundled_path  = os.path.join(self.languages_dir, f"{language_code}.json")
        writable_path = os.path.join(self.writable_languages_dir, f"{language_code}.json")

        for file_path in (bundled_path, writable_path):
            if not os.path.exists(file_path):
                continue
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    translations = json.load(f)

                if fallback:
                    self.fallback_translations = translations
                else:
                    self.translations = translations

                print(f"[DEBUG] Loaded language file: {language_code} (from {file_path})")
                return True
            except Exception as e:
                print(f"[ERROR] Failed to load language {language_code} from {file_path}: {e}")
                continue

        print(f"[WARNING] Language file not found in bundle or data dir: {language_code}")

        if language_code == DEFAULT_LANGUAGE:
            self._create_default_language_file()
            return self._load_language(language_code, fallback)

        return False
    
    def set_language(self, language_code: str) -> bool:
        if language_code not in AVAILABLE_LANGUAGES:
            print(f"[WARNING] Language {language_code} not available, using default")
            language_code = DEFAULT_LANGUAGE
        
        if self._load_language(language_code):
            self.current_language = language_code
            
            from core.settings import app_settings, save_settings
            app_settings["language"] = language_code
            save_settings()
            
            print(f"[DEBUG] Language changed to: {language_code}")
            return True
        
        return False
    
    def get(self, key: str, **kwargs) -> str:
        keys = key.split('.')
        value = self.translations

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                value = self.fallback_translations
                for k in keys:
                    if isinstance(value, dict) and k in value:
                        value = value[k]
                    else:
                        return f"[{key}]"
                break

        if not isinstance(value, str):
            return f"[{key}]"

        if kwargs:
            try:
                return value.format(**kwargs)
            except KeyError as e:
                print(f"[WARNING] Missing format key {e} for translation: {key}")
                return value

        return value
    
    def get_current_language_info(self) -> Dict[str, str]:
        return AVAILABLE_LANGUAGES.get(self.current_language, AVAILABLE_LANGUAGES[DEFAULT_LANGUAGE])
    
    def get_available_languages(self) -> Dict[str, Dict[str, str]]:
        return AVAILABLE_LANGUAGES
    
    def _create_default_language_file(self):
        default_translations = self._get_default_translations()

        os.makedirs(self.writable_languages_dir, exist_ok=True)
        file_path = os.path.join(self.writable_languages_dir, f"{DEFAULT_LANGUAGE}.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(default_translations, f, indent=2, ensure_ascii=False)

        print(f"[DEBUG] Created default language file: {file_path}")
    
    def _get_default_translations(self) -> Dict[str, Any]:
        return {
            "language_info": {
                "name": "English",
                "native": "English",
                "flag": "US"
            },
            
            "common": {
                "yes": "Yes",
                "no": "No",
                "ok": "OK",
                "cancel": "Cancel",
                "save": "Save",
                "close": "Close",
                "delete": "Delete",
                "edit": "Edit",
                "add": "Add",
                "remove": "Remove",
                "browse": "Browse",
                "search": "Search",
                "loading": "Loading...",
                "success": "Success",
                "error": "Error",
                "warning": "Warning",
                "info": "Information",
                "confirm": "Confirm",
                "apply": "Apply",
                "reset": "Reset"
            },
            
            "window": {
                "title": "BeamSkin Studio",
                "closing": "Shutting down BeamSkin Studio..."
            },
            
            "menu": {
                "generator": "Generator",
                "carlist": "Car List",
                "howto": "How To Use",
                "add_vehicles": "Add Vehicles",
                "settings": "Settings",
                "about": "About",
                "generate": "Generate Mod"
            },
            
            "sidebar": {
                "mod_info": "Mod Information",
                "mod_name": "Mod Name:",
                "mod_name_placeholder": "Enter mod name...",
                "author": "Author:",
                "author_placeholder": "Enter author name...",
                "output_location": "Output Location",
                "output_mode": "Output Mode:",
                "steam_workshop": "Steam Workshop",
                "custom_location": "Custom Location",
                "custom_path": "Custom Path:",
                "custom_path_placeholder": "Select output folder...",
                "select_folder": "Select Folder",
                "vehicle_library": "Vehicle Library",
                "search_vehicles": "Search vehicles...",
                "add_to_project": "Add to Project",
                "in_project": "In Project"
            },
            
            "generator": {
                "title": "Mod Generator",
                "project": "Current Project",
                "no_vehicles": "No vehicles added yet",
                "add_vehicles_prompt": "Add vehicles from the sidebar to get started",
                "vehicle_count": "{count} Vehicle(s)",
                "remove_vehicle": "Remove from Project",
                "clear_project": "Clear Project",
                "clear_confirm_title": "Clear Entire Project?",
                "clear_confirm_message": "Are you sure you want to remove all vehicles from this project?\n\nThis action cannot be undone.",
                "material_settings": "Material Settings",
                "skin_name": "Skin Name:",
                "skin_name_placeholder": "Enter skin name...",
                "config_type": "Configuration:",
                "texture_mode": "Texture Mode:",
                "dds_texture": "DDS Texture",
                "colorable_png": "Colorable (PNG)",
                "dds_file": "DDS File:",
                "no_file_selected": "No file selected",
                "browse_dds": "Browse DDS",
                "data_map": "Data Map (PNG):",
                "browse_data_map": "Browse Data Map",
                "color_palette": "Color Palette Map (PNG):",
                "browse_color_palette": "Browse Color Palette",
                "generating": "Generating...",
                "generate_success": "Mod generated successfully!",
                "generate_error": "Failed to generate mod"
            },
            
            "carlist": {
                "title": "Vehicle Library",
                "search_placeholder": "Search by name or ID...",
                "showing": "Showing {count} of {total} vehicles",
                "no_results": "No vehicles found",
                "try_different_search": "Try a different search term",
                "stock_vehicles": "Stock Vehicles",
                "custom_vehicles": "Custom Vehicles"
            },
            
            "howto": {
                "title": "How To Use",
                "welcome": "Welcome to BeamSkin Studio",
                "intro": "A powerful tool for creating vehicle skin mods for BeamNG.drive",
                "step1_title": "1. Add Vehicles",
                "step1_text": "Browse the vehicle library and add vehicles to your project",
                "step2_title": "2. Configure Materials",
                "step2_text": "Set up skin names, textures, and configurations for each vehicle",
                "step3_title": "3. Generate Mod",
                "step3_text": "Click 'Generate Mod' to create your mod package",
                "tips_title": "Tips & Tricks",
                "tip1": "Use the search bar to quickly find vehicles",
                "tip2": "Hover over vehicles to see preview images",
                "tip3": "Save custom output locations for quick access",
                "support_title": "Need Help?",
                "support_text": "Visit the GitHub page for documentation and support"
            },
            
            "add_vehicles": {
                "title": "Add Custom Vehicles",
                "description": "Add your own custom vehicles to BeamSkin Studio",
                "vehicle_info": "Vehicle Information",
                "vehicle_id": "Vehicle ID:",
                "vehicle_id_placeholder": "e.g., my_custom_car",
                "vehicle_name": "Vehicle Name:",
                "vehicle_name_placeholder": "e.g., My Custom Car",
                "required_files": "Required Files",
                "json_file": "Material JSON File:",
                "jbeam_file": "JBeam File:",
                "preview_image": "Preview Image (Optional):",
                "browse_json": "Browse JSON",
                "browse_jbeam": "Browse JBeam",
                "browse_image": "Browse Image",
                "add_vehicle_button": "Add Vehicle",
                "adding": "Adding vehicle...",
                "success_title": "Vehicle Added",
                "success_message": "Custom vehicle '{name}' has been added successfully!",
                "error_title": "Failed to Add Vehicle",
                "error_message": "Could not add vehicle. Please check the files and try again.",
                "validation_error": "Please fill in all required fields"
            },
            
            "settings": {
                "title": "Settings",
                "appearance": "Appearance",
                "theme": "Theme:",
                "dark_theme": "Dark Theme",
                "light_theme": "Light Theme",
                "language": "Language:",
                "select_language": "Select Language",
                "paths": "Paths & Locations",
                "beamng_install": "BeamNG.drive Installation:",
                "mods_folder": "Mods Folder:",
                "browse_beamng": "Browse BeamNG Install",
                "browse_mods": "Browse Mods Folder",
                "advanced": "Advanced",
                "debug_mode": "Debug Mode",
                "enable_debug": "Enable Debug Console",
                "config_types": "Configuration Types",
                "config_types_desc": "Manage available configuration types",
                "theme_customization": "Theme Customization",
                "customize_colors": "Customize Theme Colors",
                "reset_theme": "Reset to Default",
                "about_app": "About",
                "version": "Version:",
                "check_updates": "Check for Updates"
            },
            
            "about": {
                "title": "About BeamSkin Studio",
                "subtitle": "Professional Skin Modding Tool",
                "credits": "Credits:",
                "developer": "Developer:",
                "linktree": "Linktree",
                "donate": "Donate via PayPal",
                "version": "Version: {version}"
            },
            
            "dialogs": {
                "update_available": "Update Available!",
                "current_version": "Current Version: {version}",
                "new_version": "New Version: {version}",
                "update_prompt": "Would you like to open the GitHub page to download it?",
                "download_update": "Download Update",
                "maybe_later": "Maybe Later",
                
                "wip_warning_title": "Work-In-Progress Software",
                "wip_warning_message": "Welcome to BeamSkin Studio!\n\nThis application is currently in active development.\nWhile I strive to provide a stable experience, some features may not work\n\nPlease note:\n• Some features may be incomplete\n• Occasional bugs or unexpected behavior may occur\n• Updates and improvements are being made\n\nYour feedback helps me improve the software!\nIf you encounter any issues, please report them on my GitHub page.\n\nI appreciate your understanding and support!",
                "dont_show_again": "Don't show this message again",
                "i_understand": "I Understand",
                
                "setup_wizard_title": "First-Time Setup",
                "setup_welcome": "Welcome to BeamSkin Studio",
                "setup_description": "Let's get you started by configuring some basic settings",
                "setup_complete": "Setup Complete",
                "setup_skip": "Skip for Now"
            },
            
            "language_dialog": {
                "title": "Select Your Language",
                "description": "Choose your preferred language for BeamSkin Studio",
                "continue": "Continue"
            },
            
            "notifications": {
                "mod_generated": "Mod generated successfully!",
                "vehicle_added": "Vehicle added to project",
                "vehicle_removed": "Vehicle removed from project",
                "project_cleared": "Project cleared",
                "settings_saved": "Settings saved",
                "language_changed": "Language changed to {language}",
                "theme_changed": "Theme changed",
                "paths_saved": "Paths saved successfully",
                "custom_vehicle_added": "Custom vehicle added",
                "file_copied": "File copied to clipboard",
                "restart_required": "Restart required for changes to take effect"
            },
            
            "errors": {
                "no_vehicles": "No vehicles in project",
                "invalid_path": "Invalid path",
                "file_not_found": "File not found",
                "permission_denied": "Permission denied",
                "generation_failed": "Mod generation failed",
                "invalid_file_type": "Invalid file type",
                "missing_required_field": "Missing required field",
                "duplicate_vehicle": "Vehicle already in project"
            }
        }

_localization = None

def get_localization() -> LocalizationManager:
    global _localization
    if _localization is None:
        _localization = LocalizationManager()
    return _localization

def t(key: str, **kwargs) -> str:
    return get_localization().get(key, **kwargs)

def set_language(language_code: str) -> bool:
    return get_localization().set_language(language_code)

def get_current_language() -> str:
    return get_localization().current_language

def get_available_languages() -> Dict[str, Dict[str, str]]:
    return get_localization().get_available_languages()
