"""Theme and settings management"""
import os
import json

# -----------------------
# Theme System
# -----------------------

SETTINGS_FILE = "data/app_settings.json"

# Default settings
app_settings = {
    "theme": "dark",  # "dark" or "light"
    "first_launch": True,  # Show WIP warning on first launch
    "setup_complete": False,  # Track if first-time setup is complete
    "beamng_install": "",  # BeamNG.drive installation path
    "mods_folder": ""  # BeamNG mods folder path
}

# Ensure data directory exists
os.makedirs("data", exist_ok=True)

# Load settings
if os.path.exists(SETTINGS_FILE):
    try:
        with open(SETTINGS_FILE, "r") as f:
            app_settings = json.load(f)
    except:
        pass

def save_settings():
    """Save app settings to file"""
    os.makedirs("data", exist_ok=True)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(app_settings, f, indent=4)

DEFAULT_THEMES = {
    "dark": {
        "app_bg": "#0a0a0a",
        "frame_bg": "#141414",
        "card_bg": "#1e1e1e",
        "card_hover": "#282828",
        "text": "#f5f5f5",
        "text_secondary": "#999999",
        "accent": "#39E09B",
        "accent_hover": "#2fc97f",
        "accent_text": "#0a0a0a",
        "tab_selected": "#1e1e1e",
        "tab_selected_hover": "#282828",
        "tab_unselected": "#141414",
        "tab_unselected_hover": "#1e1e1e",
        "border": "#2a2a2a",
        "error": "#ff4444",
        "error_hover": "#cc3636",
        "success": "#39E09B",
        "warning": "#ffa726",
        "topbar_bg": "#181818",
        "sidebar_bg": "#121212"
    },
    "light": {
        "app_bg": "#fafafa",
        "frame_bg": "#f0f0f0",
        "card_bg": "#ffffff",
        "card_hover": "#f5f5f5",
        "text": "#1a1a1a",
        "text_secondary": "#888888",
        "accent": "#39E09B",
        "accent_hover": "#2fc97f",
        "accent_text": "#0a0a0a",
        "tab_selected": "#ffffff",
        "tab_selected_hover": "#f5f5f5",
        "tab_unselected": "#f0f0f0",
        "tab_unselected_hover": "#ffffff",
        "border": "#e0e0e0",
        "error": "#ff4444",
        "error_hover": "#cc3636",
        "success": "#39E09B",
        "warning": "#ffa726",
        "topbar_bg": "#f5f5f5",
        "sidebar_bg": "#eeeeee"
    }
}

EDITABLE_COLOR_KEYS = [
    "app_bg", "frame_bg", "card_bg", "card_hover",
    "text", "text_secondary", "accent", "accent_hover", "accent_text",
    "tab_selected", "tab_selected_hover", "tab_unselected", "tab_unselected_hover",
    "border", "topbar_bg", "sidebar_bg"
]

COLOR_LABELS = {
    "app_bg": "App Background",
    "frame_bg": "Frame Background",
    "card_bg": "Card Background",
    "card_hover": "Card Hover",
    "text": "Text",
    "text_secondary": "Secondary Text",
    "accent": "Accent Color",
    "accent_hover": "Accent Hover",
    "accent_text": "Accent Text",
    "tab_selected": "Tab Selected",
    "tab_selected_hover": "Tab Selected Hover",
    "tab_unselected": "Tab Unselected",
    "tab_unselected_hover": "Tab Unselected Hover",
    "border": "Border",
    "topbar_bg": "Top Bar Background",
    "sidebar_bg": "Sidebar Background"
}

# Theme color definitions
THEMES = {
    "dark": {
        "app_bg": "#0a0a0a",
        "frame_bg": "#141414",
        "card_bg": "#1e1e1e",
        "card_hover": "#282828",
        "text": "#f5f5f5",
        "text_secondary": "#999999",
        "accent": "#39E09B",
        "accent_hover": "#2fc97f",
        "accent_text": "#0a0a0a",
        "tab_selected": "#1e1e1e",
        "tab_selected_hover": "#282828",
        "tab_unselected": "#141414",
        "tab_unselected_hover": "#1e1e1e",
        "border": "#2a2a2a",
        "error": "#ff4444",
        "error_hover": "#cc3636",
        "success": "#39E09B",
        "warning": "#ffa726",
        "topbar_bg": "#181818",
        "sidebar_bg": "#121212"
    },
    "light": {
        "app_bg": "#fafafa",
        "frame_bg": "#f0f0f0",
        "card_bg": "#ffffff",
        "card_hover": "#f5f5f5",
        "text": "#1a1a1a",
        "text_secondary": "#888888",
        "accent": "#39E09B",
        "accent_hover": "#2fc97f",
        "accent_text": "#0a0a0a",
        "tab_selected": "#ffffff",
        "tab_selected_hover": "#f5f5f5",
        "tab_unselected": "#f0f0f0",
        "tab_unselected_hover": "#ffffff",
        "border": "#e0e0e0",
        "error": "#ff4444",
        "error_hover": "#cc3636",
        "success": "#39E09B",
        "warning": "#ffa726",
        "topbar_bg": "#f5f5f5",
        "sidebar_bg": "#eeeeee"
    }
}

if "custom_themes" in app_settings:
    THEMES = app_settings["custom_themes"]
else:
    import copy
    THEMES = copy.deepcopy(DEFAULT_THEMES)
    app_settings["custom_themes"] = THEMES
    save_settings()

current_theme = app_settings["theme"]
colors = THEMES[current_theme]


ADDED_VEHICLES_FILE = "vehicles/added_vehicles.json"
added_vehicles = {}  # carid -> carname

os.makedirs("vehicles", exist_ok=True)


if not os.path.exists(ADDED_VEHICLES_FILE):
    with open(ADDED_VEHICLES_FILE, "w") as f:
        json.dump({}, f)


with open(ADDED_VEHICLES_FILE, "r") as f:
    try:
        added_vehicles = json.load(f)
    except:
        added_vehicles = {}


def show_wip_warning(app=None, force=False):
    """Show WIP warning on first launch using CustomTkinter
    
    Args:
        app: The main CTk app instance
        force: If True, show the dialog even if not first launch (for testing)
    """
    print(f"[DEBUG] show_wip_warning called with app={app}, force={force}")
    print(f"[DEBUG] first_launch setting: {app_settings.get('first_launch', True)}")
    
    if force or app_settings.get("first_launch", True):
        print(f"[DEBUG] Showing WIP warning dialog...")
        
       
        import customtkinter as ctk
        
        if app is None:
            print("[ERROR] No app instance provided to show_wip_warning!")
            return
        
        dialog = ctk.CTkToplevel(app)
        dialog.title("Work in Progress")
        dialog.geometry("600x650")
        dialog.resizable(False, False)
 
        dialog.transient(app)
        dialog.grab_set()
        
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (600 // 2)
        y = (dialog.winfo_screenheight() // 2) - (650 // 2)
        dialog.geometry(f"600x650+{x}+{y}")
        
        dialog.lift()
        dialog.focus_force()
        dialog.attributes('-topmost', True)
        dialog.after(100, lambda: dialog.attributes('-topmost', False))
        
        main_frame = ctk.CTkFrame(dialog, fg_color=colors["frame_bg"])
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        icon_label = ctk.CTkLabel(
            main_frame,
            text="🚧",
            font=ctk.CTkFont(size=32)
        )
        icon_label.pack(pady=(10, 5))

        title_label = ctk.CTkLabel(
            main_frame,
            text="Work in Progress",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=colors["warning"]
        )
        title_label.pack(pady=(0, 15))

        message_frame = ctk.CTkFrame(main_frame, fg_color=colors["card_bg"], corner_radius=10)
        message_frame.pack(fill="both", expand=True, padx=10, pady=10)

        message_label = ctk.CTkLabel(
            message_frame,
            text="BeamSkin Studio is currently in active development.\n\n"
                 "Please be aware that:\n"
                 "• Bugs and errors should be expected\n"
                 "• Some features may not work as intended\n"
                 "• Data loss or unexpected behavior may occur\n"
                 "• Regular updates and changes are being made\n\n"
                 "Known Limitations:\n"
                 "• Car variations are NOT supported yet\n"
                 "  (e.g., Ambulance, Box Truck, Sedan, Wagon)\n"
                 "• Modded cars added via Developer tab\n"
                 "  won't work properly\n\n"
                 "Thank you for your patience and understanding!",
            font=ctk.CTkFont(size=20),
            text_color=colors["text"],
            justify="left"
        )
        message_label.pack(pady=20, padx=20)
        
        def close_dialog():
            print(f"[DEBUG] WIP warning dialog closed by user")
            if not force: 
                app_settings["first_launch"] = False
                save_settings()
                print(f"[DEBUG] Settings saved, first_launch set to False")
            dialog.destroy()
        
        ok_button = ctk.CTkButton(
            main_frame,
            text="Got it!",
            command=close_dialog,
            fg_color=colors["accent"],
            hover_color=colors["accent_hover"],
            text_color=colors["accent_text"],
            height=40,
            corner_radius=8,
            font=ctk.CTkFont(size=14, weight="bold")
        )
        ok_button.pack(pady=(0, 10), padx=40, fill="x")
        
        print(f"[DEBUG] WIP warning dialog created and shown")
    else:
        print(f"[DEBUG] Skipping WIP warning (not first launch)")


def reset_theme_colors(theme_name):
    """Reset a theme to default colors"""
    import copy
    if theme_name in DEFAULT_THEMES:
        THEMES[theme_name] = copy.deepcopy(DEFAULT_THEMES[theme_name])
        app_settings["custom_themes"] = THEMES
        save_settings()
        print(f"[DEBUG] Reset {theme_name} theme to default colors")
        return True
    return False


def update_theme_color(theme_name, color_key, color_value):
    """Update a single color in a theme
    
    Args:
        theme_name: Name of the theme ("dark" or "light")
        color_key: Key of the color to update
        color_value: New color value (hex string)
    
    Returns:
        True if successful, False otherwise
    """
    # Ensure THEMES exists in app_settings
    if "custom_themes" not in app_settings:
        import copy
        app_settings["custom_themes"] = copy.deepcopy(THEMES)
    
    # Check if theme and color key exist
    if theme_name not in THEMES:
        print(f"[ERROR] Theme '{theme_name}' not found")
        return False
    
    if color_key not in THEMES[theme_name]:
        print(f"[ERROR] Color key '{color_key}' not found in theme '{theme_name}'")
        return False
    
    # Update the color
    THEMES[theme_name][color_key] = color_value
    app_settings["custom_themes"][theme_name][color_key] = color_value
    
    # Save settings
    save_settings()
    
    print(f"[DEBUG] Updated {theme_name}.{color_key} to {color_value}")
    return True


def get_theme_color(theme_name, color_key):
    """Get a color value from a theme"""
    if theme_name in THEMES and color_key in THEMES[theme_name]:
        return THEMES[theme_name][color_key]
    return None


def toggle_theme(app_instance=None):
    """
    Toggle between dark and light themes
    
    Args:
        app_instance: Optional reference to the main app for live UI updates
    
    Returns:
        The new theme name ("dark" or "light")
    """
    global current_theme, colors
    
    # Toggle theme
    new_theme = "light" if current_theme == "dark" else "dark"
    
    # Update global variables
    current_theme = new_theme
    colors = THEMES[current_theme]
    
    # Save to settings
    app_settings["theme"] = new_theme
    save_settings()
    
    print(f"[DEBUG] Theme toggled to: {new_theme}")
    
    # If app instance provided, update its state
    if app_instance:
        try:
            from gui.state import state
            state.current_theme = new_theme
            state.colors = colors
            print(f"[DEBUG] Updated app state with new theme")
        except Exception as e:
            print(f"[DEBUG] Could not update app state: {e}")
    
    return new_theme


def set_theme(theme_name, app_instance=None):
    """
    Set a specific theme
    
    Args:
        theme_name: "dark" or "light"
        app_instance: Optional reference to the main app for live UI updates
    
    Returns:
        True if successful, False if theme doesn't exist
    """
    global current_theme, colors
    
    if theme_name not in THEMES:
        print(f"[ERROR] Theme '{theme_name}' does not exist")
        return False
    
    # Update global variables
    current_theme = theme_name
    colors = THEMES[current_theme]
    
    # Save to settings
    app_settings["theme"] = theme_name
    save_settings()
    
    print(f"[DEBUG] Theme set to: {theme_name}")
    
    # If app instance provided, update its state
    if app_instance:
        try:
            from gui.state import state
            state.current_theme = theme_name
            state.colors = colors
            print(f"[DEBUG] Updated app state with new theme")
        except Exception as e:
            print(f"[DEBUG] Could not update app state: {e}")
    
    return True


def set_beamng_paths(beamng_install: str = None, mods_folder: str = None):
    """
    Set BeamNG.drive installation and/or mods folder paths
    
    Args:
        beamng_install: Path to BeamNG.drive installation (optional)
        mods_folder: Path to mods folder (optional)
    
    Returns:
        True if successful
    """
    if beamng_install is not None:
        app_settings["beamng_install"] = beamng_install
        print(f"[DEBUG] BeamNG install path set to: {beamng_install}")
    
    if mods_folder is not None:
        app_settings["mods_folder"] = mods_folder
        print(f"[DEBUG] Mods folder path set to: {mods_folder}")
    
    save_settings()
    return True


def get_beamng_install_path() -> str:
    """Get the BeamNG.drive installation path"""
    return app_settings.get("beamng_install", "")


def get_mods_folder_path() -> str:
    """Get the BeamNG mods folder path"""
    return app_settings.get("mods_folder", "")


def is_setup_complete() -> bool:
    """Check if first-time setup has been completed"""
    return app_settings.get("setup_complete", False)


def mark_setup_complete():
    """Mark first-time setup as complete"""
    app_settings["setup_complete"] = True
    save_settings()
    print("[DEBUG] First-time setup marked as complete")