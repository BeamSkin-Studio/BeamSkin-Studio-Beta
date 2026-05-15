"""Settings management"""
import os
import json

SETTINGS_FILE = "data/app_settings.json"

app_settings = {
    "first_launch": True,
    "setup_complete": False,
    "beamng_install": "",
    "mods_folder": "",
    "theme_mode": "dark",
}

os.makedirs("data", exist_ok=True)

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

ADDED_VEHICLES_FILE = "vehicles/added_vehicles.json"
added_vehicles = {}

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

        main_frame = ctk.CTkFrame(dialog)
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
        )
        title_label.pack(pady=(0, 15))

        message_frame = ctk.CTkFrame(main_frame, corner_radius=10)
        message_frame.pack(fill="both", expand=True, padx=10, pady=10)

        message_label = ctk.CTkLabel(
            message_frame,
            text="BeamSkin Studio is in active development.\n\n"
                 "Please be aware that:\n"
                 "• Bugs and errors should be expected\n"
                 "• Some features may not work as intended\n"
                 "• Data loss or unexpected behavior may occur\n"
                 "• Regular updates and changes are being made\n\n"
                 "Thank you for your patience and understanding!",
            font=ctk.CTkFont(size=20),
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
            height=40,
            corner_radius=8,
            font=ctk.CTkFont(size=14, weight="bold")
        )
        ok_button.pack(pady=(0, 10), padx=40, fill="x")

        print(f"[DEBUG] WIP warning dialog created and shown")
    else:
        print(f"[DEBUG] Skipping WIP warning (not first launch)")

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
