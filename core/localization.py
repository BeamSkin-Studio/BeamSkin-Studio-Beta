"""
Localization Manager - Multi-language support for BeamSkin Studio
"""
import os
import json
from typing import Dict, Optional, Any

# Language configuration
LANGUAGES_DIR = "core/localization/languages"
DEFAULT_LANGUAGE = "en_US"

# Available languages will be loaded dynamically from language files
AVAILABLE_LANGUAGES = {}

def _load_available_languages():
    """Dynamically load available languages from the languages directory"""
    global AVAILABLE_LANGUAGES
    AVAILABLE_LANGUAGES = {}
    
    # Get program root directory
    import sys
    if getattr(sys, 'frozen', False):

        program_root = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    else:
        # Try to get the actual program root
        try:
            # This file is in core/localization.py, so go up 2 levels to root
            current_file = os.path.abspath(__file__)
            program_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
        except:
            # Fallback if __file__ doesn't work
            program_root = os.getcwd()
    
    languages_path = os.path.join(program_root, LANGUAGES_DIR)
    
    print(f"[DEBUG] Looking for languages in: {languages_path}")
    
    if not os.path.exists(languages_path):
        print(f"[WARNING] Languages directory not found: {languages_path}")
        # Set default English as fallback
        AVAILABLE_LANGUAGES["en_US"] = {"name": "English", "native": "English", "flag": "US"}
        return
    
    # Scan for .json files in the languages directory
    try:
        files = os.listdir(languages_path)
    except Exception as e:
        print(f"[ERROR] Cannot read languages directory: {e}")
        AVAILABLE_LANGUAGES["en_US"] = {"name": "English", "native": "English", "flag": "US"}
        return
    
    for filename in files:
        if filename.endswith('.json'):
            lang_code = filename[:-5]  # Remove .json extension
            file_path = os.path.join(languages_path, filename)
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                # Check if the file has language metadata
                if 'language_info' in data:
                    info = data['language_info']
                    AVAILABLE_LANGUAGES[lang_code] = {
                        "name": info.get("name", lang_code),
                        "native": info.get("native", lang_code),
                        "flag": info.get("flag", "US")
                    }
                    print(f"[DEBUG] Loaded language: {lang_code} - {info.get('native', lang_code)}")
                else:
                    # Fallback if no language_info in the file
                    AVAILABLE_LANGUAGES[lang_code] = {
                        "name": lang_code,
                        "native": lang_code,
                        "flag": lang_code.split('_')[1] if '_' in lang_code else "US"
                    }
                    print(f"[WARNING] No language_info in {filename}, using defaults")
                    
            except Exception as e:
                print(f"[ERROR] Failed to load language file {filename}: {e}")
    
    # Ensure at least default language exists
    if not AVAILABLE_LANGUAGES:
        print("[WARNING] No languages loaded, using default English")
        AVAILABLE_LANGUAGES["en_US"] = {"name": "English", "native": "English", "flag": "US"}
    elif "en_US" not in AVAILABLE_LANGUAGES and len(AVAILABLE_LANGUAGES) > 0:
        # If we loaded languages but en_US is missing, add it
        print("[WARNING] en_US not found, adding default English")
        AVAILABLE_LANGUAGES["en_US"] = {"name": "English", "native": "English", "flag": "US"}
    
    print(f"[DEBUG] Total languages loaded: {len(AVAILABLE_LANGUAGES)}")

# Load languages on module import
_load_available_languages()

class LocalizationManager:
    """Manages application translations and language switching"""
    
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
        
        # Get program root directory
        import sys
        if getattr(sys, 'frozen', False):

            program_root = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
        else:
            # Try to get the actual program root
            try:
                # This file is in core/localization.py, so go up 2 levels to root
                current_file = os.path.abspath(__file__)
                program_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
            except:
                # Fallback if __file__ doesn't work
                program_root = os.getcwd()
        
        self.languages_dir = os.path.join(program_root, LANGUAGES_DIR)
        
        print(f"[DEBUG] LocalizationManager languages directory: {self.languages_dir}")

        import sys as _sys
        if not getattr(_sys, 'frozen', False):
            try:
                os.makedirs(self.languages_dir, exist_ok=True)
            except OSError:
                pass  # non-fatal — we'll just work with whatever is there
        
        # Load default English translations (fallback)
        self._load_language(DEFAULT_LANGUAGE, fallback=True)
        
        # Load user's language from settings
        from core.settings import app_settings
        saved_language = app_settings.get("language", DEFAULT_LANGUAGE)
        self.set_language(saved_language)
    
    def _load_language(self, language_code: str, fallback: bool = False) -> bool:
        """Load translation file for a specific language"""
        file_path = os.path.join(self.languages_dir, f"{language_code}.json")
        
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    translations = json.load(f)
                    
                if fallback:
                    self.fallback_translations = translations
                else:
                    self.translations = translations
                    
                print(f"[DEBUG] Loaded language file: {language_code}")
                return True
            else:
                print(f"[WARNING] Language file not found: {file_path}")
                
                # Create default English file if it doesn't exist
                if language_code == DEFAULT_LANGUAGE:
                    self._create_default_language_file()
                    return self._load_language(language_code, fallback)
                    
                return False
        except Exception as e:
            print(f"[ERROR] Failed to load language {language_code}: {e}")
            return False
    
    def set_language(self, language_code: str) -> bool:
        """Change the current language"""
        if language_code not in AVAILABLE_LANGUAGES:
            print(f"[WARNING] Language {language_code} not available, using default")
            language_code = DEFAULT_LANGUAGE
        
        if self._load_language(language_code):
            self.current_language = language_code
            
            # Save to settings
            from core.settings import app_settings, save_settings
            app_settings["language"] = language_code
            save_settings()
            
            print(f"[DEBUG] Language changed to: {language_code}")
            return True
        
        return False
    
    def get(self, key: str, **kwargs) -> str:

        # Navigate nested dictionary using dot notation
        keys = key.split('.')
        value = self.translations
        
        # Try to get value from current language
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                # Fallback to English
                value = self.fallback_translations
                for k in keys:
                    if isinstance(value, dict) and k in value:
                        value = value[k]
                    else:
                        # Return key if not found
                        return f"[{key}]"
                break
        
        # If value is not a string, return key
        if not isinstance(value, str):
            return f"[{key}]"
        
        # Format string with kwargs if provided
        if kwargs:
            try:
                return value.format(**kwargs)
            except KeyError as e:
                print(f"[WARNING] Missing format key {e} for translation: {key}")
                return value
        
        return value
    
    def get_current_language_info(self) -> Dict[str, str]:
        """Get information about the current language"""
        return AVAILABLE_LANGUAGES.get(self.current_language, AVAILABLE_LANGUAGES[DEFAULT_LANGUAGE])
    
    def get_available_languages(self) -> Dict[str, Dict[str, str]]:
        """Get all available languages"""
        return AVAILABLE_LANGUAGES
    
    def _create_default_language_file(self):
        """Create the default English translation file"""
        default_translations = self._get_default_translations()
        
        file_path = os.path.join(self.languages_dir, f"{DEFAULT_LANGUAGE}.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(default_translations, f, indent=2, ensure_ascii=False)
        
        print(f"[DEBUG] Created default language file: {file_path}")
    
    def _get_default_translations(self) -> Dict[str, Any]:
        """Get the default English translations"""
        return {
            # Language metadata
            "language_info": {
                "name": "English",
                "native": "English",
                "flag": "US"
            },
            
            # Common
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
            
            # Main Window
            "window": {
                "title": "BeamSkin Studio",
                "closing": "Shutting down BeamSkin Studio..."
            },
            
            # Top Menu Bar
            "menu": {
                "generator": "Generator",
                "carlist": "Car List",
                "howto": "How To Use",
                "add_vehicles": "Add Vehicles",
                "settings": "Settings",
                "about": "About",
                "generate": "Generate Mod"
            },
            
            # Sidebar
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
            
            # Generator Tab
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
            
            # Car List Tab
            "carlist": {
                "title": "Vehicle Library",
                "search_placeholder": "Search by name or ID...",
                "showing": "Showing {count} of {total} vehicles",
                "no_results": "No vehicles found",
                "try_different_search": "Try a different search term",
                "stock_vehicles": "Stock Vehicles",
                "custom_vehicles": "Custom Vehicles"
            },
            
            # How To Tab
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
            
            # Add Vehicles Tab
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
            
            # Settings Tab
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
            
            # About Tab
            "about": {
                "title": "About BeamSkin Studio",
                "subtitle": "Professional Skin Modding Tool",
                "credits": "Credits:",
                "developer": "Developer:",
                "linktree": "Linktree",
                "donate": "Donate via PayPal",
                "version": "Version: {version}"
            },
            
            # Dialogs
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
            
            # Language Selection Dialog
            "language_dialog": {
                "title": "Select Your Language",
                "description": "Choose your preferred language for BeamSkin Studio",
                "continue": "Continue"
            },
            
            # Notifications
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
            
            # Errors
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

# Global localization manager instance
_localization = None

def get_localization() -> LocalizationManager:
    """Get the global localization manager instance"""
    global _localization
    if _localization is None:
        _localization = LocalizationManager()
    return _localization

def t(key: str, **kwargs) -> str:

    return get_localization().get(key, **kwargs)

def set_language(language_code: str) -> bool:
    """Change the application language"""
    return get_localization().set_language(language_code)

def get_current_language() -> str:
    """Get the current language code"""
    return get_localization().current_language

def get_available_languages() -> Dict[str, Dict[str, str]]:
    """Get all available languages"""
    return get_localization().get_available_languages()