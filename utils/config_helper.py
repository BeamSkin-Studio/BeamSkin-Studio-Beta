import os
import sys
import platform

def load_config_types(config_file=None):
    print(f"[DEBUG] load_config_types called")
    """
    Load config types from carconfigs.txt file in vehicles folder.
    Returns a list of config types.

    Args:
        config_file: Optional custom path to the config types file

    Returns:
        List of config type strings
    """
    config_types = ["Factory", "Custom", "Police"]

    if config_file is None:
        config_file = os.path.join("vehicles", "carconfigs.txt")

    try:
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                loaded_types = [line.strip() for line in f if line.strip()]
                if loaded_types:
                    config_types = loaded_types
                    print(f"[DEBUG] Loaded {len(config_types)} config types from {config_file}")
                else:
                    print(f"[DEBUG] Config file empty, using defaults")
        else:
            print(f"[DEBUG] Config file not found at {config_file}, using default config types")
            os.makedirs("vehicles", exist_ok=True)
            with open(config_file, 'w', encoding='utf-8') as f:
                f.write("Factory\nCustom\nPolice\n")
            print(f"[DEBUG] Created default {config_file}")
    except Exception as e:
        print(f"[DEBUG] Error loading config types: {e}, using defaults")

    return config_types

def get_beamng_vehicles_path():
    print(f"[DEBUG] get_beamng_vehicles_path called")
    """
    Get the path to BeamNG.drive vehicles folder.
    Cross-platform implementation.

    Returns:
        Path to BeamNG vehicles folder based on OS
    """
    system = platform.system()

    if system == "Windows":

        import getpass
        username = getpass.getuser()
        return os.path.join(
            "C:\\Users",
            username,
            "AppData",
            "Local",
            "BeamNG",
            "BeamNG.drive",
            "current",
            "vehicles"
        )

    elif system == "Linux":

        home = os.path.expanduser("~")
        return os.path.join(
            home,
            ".local",
            "share",
            "BeamNG.drive",
            "current",
            "vehicles"
        )

    elif system == "Darwin":

        home = os.path.expanduser("~")
        return os.path.join(
            home,
            "Library",
            "Application Support",
            "BeamNG.drive",
            "current",
            "vehicles"
        )

    else:

        print(f"[WARNING] Unknown platform: {system}")
        home = os.path.expanduser("~")
        return os.path.join(home, ".beamng", "current", "vehicles")

def get_beamng_default_install_paths():
    """
    Get list of common BeamNG.drive installation paths based on OS.
    Used for the file browser initial directory.

    Returns:
        List of potential installation paths
    """
    system = platform.system()
    paths = []

    if system == "Windows":

        drives = ['C:', 'D:', 'E:']
        for drive in drives:

            paths.append(os.path.join(drive, "Program Files (x86)", "Steam", "steamapps", "common", "BeamNG.drive"))
            paths.append(os.path.join(drive, "Program Files", "Steam", "steamapps", "common", "BeamNG.drive"))

            paths.append(os.path.join(drive, "Program Files", "Epic Games", "BeamNG.drive"))

            paths.append(os.path.join(drive, "BeamNG.drive"))

    elif system == "Linux":
        home = os.path.expanduser("~")

        paths.extend([
            os.path.join(home, ".steam", "steam", "steamapps", "common", "BeamNG.drive"),
            os.path.join(home, ".local", "share", "Steam", "steamapps", "common", "BeamNG.drive"),

            os.path.join(home, ".var", "app", "com.valvesoftware.Steam", ".steam", "steam", "steamapps", "common", "BeamNG.drive"),

            "/opt/BeamNG.drive",
            os.path.join(home, "BeamNG.drive"),
            os.path.join(home, "Games", "BeamNG.drive")
        ])

    elif system == "Darwin":
        home = os.path.expanduser("~")

        paths.extend([
            os.path.join(home, "Library", "Application Support", "Steam", "steamapps", "common", "BeamNG.drive"),
            "/Applications/BeamNG.drive.app",
            os.path.join(home, "Applications", "BeamNG.drive.app")
        ])

    existing_paths = [p for p in paths if os.path.exists(p)]

    if not existing_paths and paths:
        return [paths[0]]

    return existing_paths if existing_paths else [os.path.expanduser("~")]

def get_beamng_mods_default_paths():
    """
    Get list of common BeamNG.drive mods folder paths based on OS.

    Returns:
        List of potential mods folder paths
    """
    system = platform.system()
    home = os.path.expanduser("~")
    paths = []

    if system == "Windows":
        import getpass
        username = getpass.getuser()
        paths.extend([
            # Version-specific paths (newer structure)
            os.path.join("C:\\Users", username, "AppData", "Local", "BeamNG.drive", "0.33", "mods"),
            os.path.join("C:\\Users", username, "AppData", "Local", "BeamNG.drive", "mods"),
            # Current/mods path (alternative structure)
            os.path.join("C:\\Users", username, "AppData", "Local", "BeamNG", "BeamNG.drive", "current", "mods"),
            os.path.join("C:\\Users", username, "AppData", "Local", "BeamNG.drive", "current", "mods"),
            # Documents location
            os.path.join("C:\\Users", username, "Documents", "BeamNG.drive", "mods")
        ])

    elif system == "Linux":
        paths.extend([
            os.path.join(home, ".local", "share", "BeamNG.drive", "0.33", "mods"),
            os.path.join(home, ".local", "share", "BeamNG.drive", "mods"),
            # Current/mods path
            os.path.join(home, ".local", "share", "BeamNG", "BeamNG.drive", "current", "mods"),
            os.path.join(home, ".local", "share", "BeamNG.drive", "current", "mods"),
            os.path.join(home, "Documents", "BeamNG.drive", "mods"),

            os.path.join(home, ".var", "app", "com.beamng.drive", "data", "BeamNG.drive", "mods")
        ])

    elif system == "Darwin":
        paths.extend([
            os.path.join(home, "Library", "Application Support", "BeamNG.drive", "0.33", "mods"),
            os.path.join(home, "Library", "Application Support", "BeamNG.drive", "mods"),
            # Current/mods path
            os.path.join(home, "Library", "Application Support", "BeamNG", "BeamNG.drive", "current", "mods"),
            os.path.join(home, "Library", "Application Support", "BeamNG.drive", "current", "mods"),
            os.path.join(home, "Documents", "BeamNG.drive", "mods")
        ])

    existing_paths = [p for p in paths if os.path.exists(p)]

    if not existing_paths and paths:
        return [paths[0]]

    return existing_paths if existing_paths else [os.path.join(home, "Documents")]