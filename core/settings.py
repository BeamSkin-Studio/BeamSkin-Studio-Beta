import os
import sys
import json
import shutil
import platform
from typing import Optional


APP_DIRNAME = "BeamSkinStudio"

_BOOTSTRAP_FILENAME = "data_location.json"

_LEGACY_MODE_FILENAME = "legacy_mode.json"

_cached_data_dir: Optional[str] = None
_cached_legacy_mode: Optional[bool] = None


def get_bundle_path() -> str:
    frozen = getattr(sys, "frozen", False)
    if frozen:
        result = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
        print(f"[DEBUG] get_bundle_path: frozen=True -> {result!r}")
        return result
    result = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    print(f"[DEBUG] get_bundle_path: frozen=False -> {result!r}")
    return result


def get_install_dir() -> str:
    frozen = getattr(sys, "frozen", False)
    if frozen:
        result = os.path.dirname(sys.executable)
        print(f"[DEBUG] get_install_dir: frozen=True -> {result!r}")
        return result
    result = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    print(f"[DEBUG] get_install_dir: frozen=False -> {result!r}")
    return result


def _default_data_dir() -> str:
    system = platform.system()
    print(f"[DEBUG] _default_data_dir: platform.system()={system!r}")
    if system == "Windows":
        base = os.environ.get("APPDATA") or os.path.expanduser(r"~\AppData\Roaming")
    elif system == "Darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    result = os.path.join(base, APP_DIRNAME)
    print(f"[DEBUG] _default_data_dir: base={base!r} -> {result!r}")
    return result


def _bootstrap_path() -> str:
    path = os.path.join(_default_data_dir(), _BOOTSTRAP_FILENAME)
    print(f"[DEBUG] _bootstrap_path: {path!r}")
    return path


def _read_bootstrap() -> Optional[str]:
    path = _bootstrap_path()
    print(f"[DEBUG] _read_bootstrap: reading {path!r}")
    if not os.path.exists(path):
        print("[DEBUG] _read_bootstrap: file does not exist -> None")
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        custom = data.get("data_dir")
        print(f"[DEBUG] _read_bootstrap: data_dir={custom!r}")
        result = custom if custom and os.path.isdir(custom) else None
        print(f"[DEBUG] _read_bootstrap: returning {result!r}")
        return result
    except Exception as e:
        print(f"[WARNING] settings: could not read data-location bootstrap file: {e}")
        return None


def _write_bootstrap(custom_dir: Optional[str]) -> None:
    print(f"[DEBUG] _write_bootstrap: custom_dir={custom_dir!r}")
    default_dir = _default_data_dir()
    os.makedirs(default_dir, exist_ok=True)
    try:
        with open(_bootstrap_path(), "w", encoding="utf-8") as f:
            json.dump({"data_dir": custom_dir}, f, indent=2)
        print(f"[DEBUG] _write_bootstrap: write successful to {_bootstrap_path()!r}")
    except Exception as e:
        print(f"[WARNING] settings: could not write data-location bootstrap file: {e}")


def _legacy_mode_path() -> str:
    path = os.path.join(_default_data_dir(), _LEGACY_MODE_FILENAME)
    print(f"[DEBUG] _legacy_mode_path: {path!r}")
    return path


def _read_legacy_mode() -> bool:
    path = _legacy_mode_path()
    print(f"[DEBUG] _read_legacy_mode: reading {path!r}")
    if not os.path.exists(path):
        print("[DEBUG] _read_legacy_mode: file does not exist -> False")
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        result = bool(data.get("enabled", False))
        print(f"[DEBUG] _read_legacy_mode: enabled={result}")
        return result
    except Exception as e:
        print(f"[WARNING] settings: could not read legacy-mode marker: {e}")
        return False


def _write_legacy_mode(enabled: bool) -> None:
    print(f"[DEBUG] _write_legacy_mode: enabled={enabled}")
    default_dir = _default_data_dir()
    os.makedirs(default_dir, exist_ok=True)
    try:
        with open(_legacy_mode_path(), "w", encoding="utf-8") as f:
            json.dump({"enabled": enabled}, f, indent=2)
        print(f"[DEBUG] _write_legacy_mode: write successful to {_legacy_mode_path()!r}")
    except Exception as e:
        print(f"[WARNING] settings: could not write legacy-mode marker: {e}")


def is_legacy_mode() -> bool:
    global _cached_legacy_mode
    if _cached_legacy_mode is None:
        print("[DEBUG] is_legacy_mode: cache empty, reading from disk")
        _cached_legacy_mode = _read_legacy_mode()
    else:
        print(f"[DEBUG] is_legacy_mode: returning cached value {_cached_legacy_mode}")
    return _cached_legacy_mode


def set_legacy_mode(enabled: bool) -> None:
    print(f"[DEBUG] set_legacy_mode: called with enabled={enabled}")
    global _cached_legacy_mode, _cached_data_dir
    _write_legacy_mode(enabled)
    _cached_legacy_mode = enabled
    print(f"[DEBUG] set_legacy_mode: cache updated to {enabled}, clearing _cached_data_dir "
          f"(was {_cached_data_dir!r})")
    _cached_data_dir = None
    _reload_app_settings()
    _reload_added_vehicles()
    print("[DEBUG] set_legacy_mode: app_settings and added_vehicles reloaded")


def _legacy_root_data_dir() -> str:
    path = os.path.join(get_install_dir(), "data")
    print(f"[DEBUG] _legacy_root_data_dir: {path!r}")
    return path


def _legacy_root_vehicles_dir() -> str:
    path = os.path.join(get_install_dir(), "vehicles")
    print(f"[DEBUG] _legacy_root_vehicles_dir: {path!r}")
    return path


def _legacy_root_vehicle_previews_dir() -> str:
    path = os.path.join(get_install_dir(), "gui", "images", "vehicles")
    print(f"[DEBUG] _legacy_root_vehicle_previews_dir: {path!r}")
    return path


def get_data_dir() -> str:
    global _cached_data_dir
    if _cached_data_dir and os.path.isdir(_cached_data_dir):
        print(f"[DEBUG] get_data_dir: returning cached value {_cached_data_dir!r}")
        return _cached_data_dir

    print("[DEBUG] get_data_dir: cache empty or stale, resolving")

    if is_legacy_mode():
        chosen = _legacy_root_data_dir()
        print(f"[DEBUG] get_data_dir: legacy mode active -> {chosen!r}")
        os.makedirs(chosen, exist_ok=True)
        _cached_data_dir = chosen
        return chosen

    custom = _read_bootstrap()
    chosen = custom or _default_data_dir()
    print(f"[DEBUG] get_data_dir: custom={custom!r} -> chosen={chosen!r}")
    os.makedirs(chosen, exist_ok=True)
    _cached_data_dir = chosen
    return chosen


def set_data_dir(new_dir: str, migrate: bool = True) -> bool:
    print(f"[DEBUG] set_data_dir: called with new_dir={new_dir!r} migrate={migrate}")
    global _cached_data_dir
    new_dir = os.path.abspath(new_dir)
    print(f"[DEBUG] set_data_dir: resolved abs new_dir={new_dir!r}")
    os.makedirs(new_dir, exist_ok=True)

    was_legacy = is_legacy_mode()
    print(f"[DEBUG] set_data_dir: was_legacy={was_legacy}")
    if was_legacy:
        _write_legacy_mode(False)
        global _cached_legacy_mode
        _cached_legacy_mode = False
        print("[DEBUG] set_data_dir: legacy mode turned off")

    ok = True
    if migrate:
        old_dir = os.path.abspath(_legacy_root_data_dir() if was_legacy else get_data_dir())
        print(f"[DEBUG] set_data_dir: old_dir={old_dir!r}")
        if os.path.isdir(old_dir) and old_dir != new_dir:
            print(f"[DEBUG] set_data_dir: migrating contents of {old_dir!r} -> {new_dir!r}")
            copied = 0
            try:
                for name in os.listdir(old_dir):
                    if name == _BOOTSTRAP_FILENAME:
                        print(f"[DEBUG] set_data_dir: skipping bootstrap file {name!r}")
                        continue
                    src = os.path.join(old_dir, name)
                    dst = os.path.join(new_dir, name)
                    if os.path.isdir(src):
                        shutil.copytree(src, dst, dirs_exist_ok=True)
                    else:
                        shutil.copy2(src, dst)
                    copied += 1
                print(f"[DEBUG] set_data_dir: migration copy loop complete, {copied} entries copied")
            except Exception as e:
                print(f"[WARNING] settings: migration to {new_dir} incomplete: {e}")
                ok = False

            if ok and not was_legacy and not new_dir.startswith(old_dir + os.sep):
                print(f"[DEBUG] set_data_dir: removing old data dir {old_dir!r}")
                try:
                    shutil.rmtree(old_dir)
                    print("[DEBUG] set_data_dir: old data dir removed")
                except Exception as e:
                    print(f"[WARNING] settings: could not remove old data dir {old_dir}: {e}")
            else:
                print(f"[DEBUG] set_data_dir: not removing old_dir "
                      f"(ok={ok} was_legacy={was_legacy})")
        else:
            print(f"[DEBUG] set_data_dir: nothing to migrate "
                  f"(isdir={os.path.isdir(old_dir)}, same_dir={old_dir == new_dir})")

    _write_bootstrap(new_dir)
    _cached_data_dir = new_dir
    print(f"[DEBUG] set_data_dir: _cached_data_dir set to {new_dir!r}")
    _reload_app_settings()
    _reload_added_vehicles()
    print(f"[DEBUG] set_data_dir: returning ok={ok}")
    return ok


def get_vehicles_dir() -> str:
    if is_legacy_mode():
        path = _legacy_root_vehicles_dir()
    else:
        path = os.path.join(get_data_dir(), "vehicles")
    print(f"[DEBUG] get_vehicles_dir: {path!r}")
    os.makedirs(path, exist_ok=True)
    return path


def get_vehicle_previews_dir() -> str:
    if is_legacy_mode():
        path = _legacy_root_vehicle_previews_dir()
    else:
        path = os.path.join(get_data_dir(), "vehicle_previews")
    print(f"[DEBUG] get_vehicle_previews_dir: {path!r}")
    os.makedirs(path, exist_ok=True)
    return path


def get_project_registry_path() -> str:
    path = os.path.join(get_data_dir(), "project_registry.json")
    print(f"[DEBUG] get_project_registry_path: {path!r}")
    return path


def get_projects_dir() -> str:
    path = os.path.join(get_data_dir(), "projects")
    print(f"[DEBUG] get_projects_dir: {path!r}")
    os.makedirs(path, exist_ok=True)
    return path


def get_log_path() -> str:
    path = os.path.join(get_data_dir(), "app_log.txt")
    print(f"[DEBUG] get_log_path: {path!r}")
    return path


def get_settings_path() -> str:
    path = os.path.join(get_data_dir(), "app_settings.json")
    print(f"[DEBUG] get_settings_path: {path!r}")
    return path


def get_added_vehicles_path() -> str:
    path = os.path.join(get_vehicles_dir(), "added_vehicles.json")
    print(f"[DEBUG] get_added_vehicles_path: {path!r}")
    return path


def ensure_first_run_seed() -> None:
    bundled_vehicles = os.path.join(get_bundle_path(), "vehicles")
    target = get_vehicles_dir()
    print(f"[DEBUG] ensure_first_run_seed: bundled_vehicles={bundled_vehicles!r} target={target!r}")
    if os.path.isdir(bundled_vehicles) and not os.listdir(target):
        print("[DEBUG] ensure_first_run_seed: target is empty, seeding from bundle")
        try:
            shutil.copytree(bundled_vehicles, target, dirs_exist_ok=True)
            print(f"[DEBUG] settings: seeded built-in vehicle templates into {target}")
        except Exception as e:
            print(f"[WARNING] settings: could not seed vehicle templates: {e}")
    else:
        print(f"[DEBUG] ensure_first_run_seed: skipping seed "
              f"(bundle_exists={os.path.isdir(bundled_vehicles)}, "
              f"target_empty={not os.listdir(target) if os.path.isdir(target) else 'N/A'})")

    get_projects_dir()


_DEFAULT_SETTINGS = {
    "first_launch": True,
    "setup_complete": False,
    "beamng_install": "",
    "mods_folder": "",
    "theme_mode": "dark",
    "file_logging_enabled": False,
    "file_logging_append": False,
}

app_settings: dict = dict(_DEFAULT_SETTINGS)


def _reload_app_settings() -> None:
    global app_settings
    path = get_settings_path()
    print(f"[DEBUG] _reload_app_settings: reading {path!r}")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            app_settings = {**_DEFAULT_SETTINGS, **loaded}
            print(f"[DEBUG] _reload_app_settings: loaded keys={list(loaded.keys())}, "
                  f"merged app_settings={app_settings}")
            return
        except Exception as e:
            print(f"[WARNING] settings: could not read {path}: {e}")
    print("[DEBUG] _reload_app_settings: file missing or unreadable, using defaults")
    app_settings = dict(_DEFAULT_SETTINGS)


def save_settings():
    path = get_settings_path()
    print(f"[DEBUG] save_settings: writing to {path!r} app_settings={app_settings}")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(app_settings, f, indent=4)
    print("[DEBUG] save_settings: write successful")


_reload_app_settings()


added_vehicles: dict = {}


def _reload_added_vehicles() -> None:
    global added_vehicles
    path = get_added_vehicles_path()
    print(f"[DEBUG] _reload_added_vehicles: reading {path!r}")
    if not os.path.exists(path):
        print("[DEBUG] _reload_added_vehicles: file does not exist, creating empty one")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({}, f)
        except Exception as e:
            print(f"[WARNING] settings: could not create {path}: {e}")
            added_vehicles = {}
            return
    try:
        with open(path, "r", encoding="utf-8") as f:
            added_vehicles = json.load(f)
        print(f"[DEBUG] _reload_added_vehicles: loaded {len(added_vehicles)} vehicle(s)")
    except Exception as e:
        print(f"[DEBUG] _reload_added_vehicles: ERROR reading {path!r}: {e} — using empty dict")
        added_vehicles = {}


_reload_added_vehicles()


def set_beamng_paths(beamng_install: str = None, mods_folder: str = None):
    print(f"[DEBUG] set_beamng_paths: called with beamng_install={beamng_install!r} "
          f"mods_folder={mods_folder!r}")
    if beamng_install is not None:
        app_settings["beamng_install"] = beamng_install
        print(f"[DEBUG] BeamNG install path set to: {beamng_install}")

    if mods_folder is not None:
        app_settings["mods_folder"] = mods_folder
        print(f"[DEBUG] Mods folder path set to: {mods_folder}")

    save_settings()
    return True

def get_beamng_install_path() -> str:
    value = app_settings.get("beamng_install", "")
    print(f"[DEBUG] get_beamng_install_path: {value!r}")
    return value

def get_mods_folder_path() -> str:
    value = app_settings.get("mods_folder", "")
    print(f"[DEBUG] get_mods_folder_path: {value!r}")
    return value

def is_setup_complete() -> bool:
    value = app_settings.get("setup_complete", False)
    print(f"[DEBUG] is_setup_complete: {value}")
    return value

def mark_setup_complete():
    app_settings["setup_complete"] = True
    save_settings()
    print("[DEBUG] First-time setup marked as complete")

def is_file_logging_enabled() -> bool:
    value = app_settings.get("file_logging_enabled", False)
    print(f"[DEBUG] is_file_logging_enabled: {value}")
    return value

def set_file_logging_enabled(enabled: bool):
    print(f"[DEBUG] set_file_logging_enabled: {bool(enabled)}")
    app_settings["file_logging_enabled"] = bool(enabled)
    save_settings()

def is_file_logging_append() -> bool:
    value = app_settings.get("file_logging_append", False)
    print(f"[DEBUG] is_file_logging_append: {value}")
    return value

def set_file_logging_append(append: bool):
    print(f"[DEBUG] set_file_logging_append: {bool(append)}")
    app_settings["file_logging_append"] = bool(append)
    save_settings()
