import os
import json
from typing import Dict, Any, Optional

DEFAULT_LANGUAGE = "en"

LANGUAGES_DIR = os.path.join(os.path.dirname(__file__), "languages")

print(f"[DEBUG] Localization module loaded, languages directory: {LANGUAGES_DIR}")


class Localization:
    
    def __init__(self):
        self.current_language = DEFAULT_LANGUAGE
        self.translations: Dict[str, Any] = {}
        self.available_languages: Dict[str, Dict[str, str]] = {}
        
        os.makedirs(LANGUAGES_DIR, exist_ok=True)
        
        self._load_available_languages()
        
        self.load_language(DEFAULT_LANGUAGE)
    
    def _load_available_languages(self):
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
        keys = key.split('.')
        value = self.translations
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                if default is not None:
                    return default
                print(f"[WARNING] Translation key not found: {key}")
                return key
        
        if isinstance(value, dict):
            if default is not None:
                return default
            return key
        
        if kwargs:
            try:
                return value.format(**kwargs)
            except (KeyError, ValueError) as e:
                print(f"[WARNING] Failed to format translation '{key}': {e}")
                return value
        
        return value
    
    def get_available_languages(self) -> Dict[str, Dict[str, str]]:
        return self.available_languages.copy()
    
    def set_language(self, lang_code: str) -> bool:
        return self.load_language(lang_code)


_localization = Localization()


def get_localization() -> Localization:
    return _localization


def t(key: str, default: Optional[str] = None, **kwargs) -> str:
    return _localization.get(key, default, **kwargs)


def set_language(lang_code: str) -> bool:
    result = _localization.set_language(lang_code)
    
    try:
        from core.settings import app_settings, save_settings
        app_settings["language"] = lang_code
        save_settings()
        print(f"[DEBUG] Language saved to settings: {lang_code}")
    except Exception as e:
        print(f"[WARNING] Failed to save language to settings: {e}")
    
    return result


def get_current_language() -> str:
    return _localization.current_language


def get_available_languages() -> Dict[str, Dict[str, str]]:
    return _localization.get_available_languages()


try:
    from core.settings import app_settings
    saved_language = app_settings.get("language", DEFAULT_LANGUAGE)
    if saved_language and saved_language != DEFAULT_LANGUAGE:
        set_language(saved_language)
        print(f"[DEBUG] Loaded language from settings: {saved_language}")
except Exception as e:
    print(f"[WARNING] Could not load language from settings: {e}")
