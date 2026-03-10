"""
Localization System for BeamSkin Studio
Provides multi-language support with easy language file management
"""
import os
import json
from typing import Dict, Any, Optional

# Default language
DEFAULT_LANGUAGE = "en"

# Path to language files
LANGUAGES_DIR = os.path.join(os.path.dirname(__file__), "languages")

print(f"[DEBUG] Localization module loaded, languages directory: {LANGUAGES_DIR}")


class Localization:
    """Main localization class"""
    
    def __init__(self):
        self.current_language = DEFAULT_LANGUAGE
        self.translations: Dict[str, Any] = {}
        self.available_languages: Dict[str, Dict[str, str]] = {}
        
        # Ensure languages directory exists
        os.makedirs(LANGUAGES_DIR, exist_ok=True)
        
        # Load available languages
        self._load_available_languages()
        
        # Load default language
        self.load_language(DEFAULT_LANGUAGE)
    
    def _load_available_languages(self):
        """Scan and load available language metadata"""
        self.available_languages = {}
        
        if not os.path.exists(LANGUAGES_DIR):
            print(f"[WARNING] Languages directory not found: {LANGUAGES_DIR}")
            return
        
        for filename in os.listdir(LANGUAGES_DIR):
            if filename.endswith('.json'):
                lang_code = filename.replace('.json', '')
                lang_path = os.path.join(LANGUAGES_DIR, filename)
                
                try:
                    with open(lang_path, 'r', encoding='utf-8') as f:
                        lang_data = json.load(f)
                    
                    # Store metadata
                    if '_meta' in lang_data:
                        self.available_languages[lang_code] = {
                            'name': lang_data['_meta'].get('name', lang_code),
                            'native': lang_data['_meta'].get('native_name', lang_code),
                            'flag': lang_data['_meta'].get('flag', '🌐'),
                            'contributors': lang_data['_meta'].get('contributors', [])
                        }
                        print(f"[DEBUG] Found language: {lang_code} - {lang_data['_meta'].get('name')}")
                    else:
                        print(f"[WARNING] Language file {filename} missing _meta section")
                
                except Exception as e:
                    print(f"[ERROR] Failed to load language metadata for {filename}: {e}")
        
        print(f"[DEBUG] Total languages available: {len(self.available_languages)}")
    
    def load_language(self, lang_code: str) -> bool:
        """Load a language file"""
        lang_path = os.path.join(LANGUAGES_DIR, f"{lang_code}.json")
        
        if not os.path.exists(lang_path):
            print(f"[WARNING] Language file not found: {lang_path}")
            if lang_code != DEFAULT_LANGUAGE:
                print(f"[WARNING] Falling back to default language: {DEFAULT_LANGUAGE}")
                return self.load_language(DEFAULT_LANGUAGE)
            return False
        
        try:
            with open(lang_path, 'r', encoding='utf-8') as f:
                self.translations = json.load(f)
            
            self.current_language = lang_code
            print(f"[DEBUG] Loaded language: {lang_code}")
            return True
        
        except Exception as e:
            print(f"[ERROR] Failed to load language {lang_code}: {e}")
            if lang_code != DEFAULT_LANGUAGE:
                return self.load_language(DEFAULT_LANGUAGE)
            return False
    
    def get(self, key: str, default: Optional[str] = None, **kwargs) -> str:
        """
        Get a translated string by key with optional format arguments
        
        Args:
            key: Translation key in dot notation (e.g., 'menu.file.open')
            default: Default value if key not found
            **kwargs: Format arguments for string formatting
        
        Returns:
            Translated string or default value
        """
        # Split key by dots and navigate through nested dict
        keys = key.split('.')
        value = self.translations
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                # Key not found, return default or key itself
                if default is not None:
                    return default
                print(f"[WARNING] Translation key not found: {key}")
                return key
        
        # If value is still a dict, something went wrong
        if isinstance(value, dict):
            if default is not None:
                return default
            return key
        
        # Format string if kwargs provided
        if kwargs:
            try:
                return value.format(**kwargs)
            except (KeyError, ValueError) as e:
                print(f"[WARNING] Failed to format translation '{key}': {e}")
                return value
        
        return value
    
    def get_available_languages(self) -> Dict[str, Dict[str, str]]:
        """Get all available languages with their metadata"""
        return self.available_languages.copy()
    
    def set_language(self, lang_code: str) -> bool:
        """Set the current language"""
        return self.load_language(lang_code)


# Global localization instance
_localization = Localization()


def get_localization() -> Localization:
    """Get the global localization instance"""
    return _localization


def t(key: str, default: Optional[str] = None, **kwargs) -> str:
    """
    Shorthand function to get a translation
    
    Args:
        key: Translation key in dot notation
        default: Default value if key not found
        **kwargs: Format arguments
    
    Returns:
        Translated string
    """
    return _localization.get(key, default, **kwargs)


def set_language(lang_code: str) -> bool:
    """Set the current language"""
    result = _localization.set_language(lang_code)
    
    # Save to settings
    try:
        from core.settings import app_settings, save_settings
        app_settings["language"] = lang_code
        save_settings()
        print(f"[DEBUG] Language saved to settings: {lang_code}")
    except Exception as e:
        print(f"[WARNING] Failed to save language to settings: {e}")
    
    return result


def get_current_language() -> str:
    """Get the current language code"""
    return _localization.current_language


def get_available_languages() -> Dict[str, Dict[str, str]]:
    """Get all available languages"""
    return _localization.get_available_languages()


# Initialize language from settings
try:
    from core.settings import app_settings
    saved_language = app_settings.get("language", DEFAULT_LANGUAGE)
    if saved_language and saved_language != DEFAULT_LANGUAGE:
        set_language(saved_language)
        print(f"[DEBUG] Loaded language from settings: {saved_language}")
except Exception as e:
    print(f"[WARNING] Could not load language from settings: {e}")
