from __future__ import annotations

import glob
import json
import os
import shutil
import sys
import zipfile

MOD_NAME = "beamskin_studio_exporter_mod"
SETTING_KEY = "exporter_mod_source"

MISSING = "missing"
OUTDATED = "outdated"
INSTALLED = "installed"

_SUBDIRS = ("", "resources", "assets", "data", "mods", "_internal", "_internal/resources", "_internal/assets")


def _search_roots() -> list[str]:
    roots: list[str] = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            roots.append(meipass)
        roots.append(os.path.dirname(sys.executable))
    path = os.path.dirname(os.path.abspath(__file__))
    for _ in range(5):
        roots.append(path)
        path = os.path.dirname(path)
    roots.append(os.getcwd())
    return roots


def _saved_source() -> str:
    try:
        from core import settings as _s
        return str(_s.app_settings.get(SETTING_KEY, "") or "")
    except Exception:
        return ""


def remember_source(path: str) -> None:
    try:
        from core import settings as _s
        _s.app_settings[SETTING_KEY] = path
        _s.save_settings()
    except Exception as e:
        print(f"[WARNING] exporter_mod: could not save source: {type(e).__name__}: {e}")


def bundled_source() -> str:
    saved = _saved_source()
    if saved and os.path.exists(saved):
        return saved
    seen: set[str] = set()
    for root in _search_roots():
        for sub in _SUBDIRS:
            base = os.path.normpath(os.path.join(root, sub, MOD_NAME))
            for candidate in (base, base + ".zip"):
                if candidate in seen:
                    continue
                seen.add(candidate)
                if os.path.exists(candidate):
                    return candidate
    return ""


def valid_source(path: str) -> bool:
    if os.path.isdir(path):
        return os.path.isdir(os.path.join(path, "ui")) or os.path.isdir(os.path.join(path, "lua"))
    if os.path.isfile(path) and path.lower().endswith(".zip"):
        try:
            with zipfile.ZipFile(path) as z:
                return any(n.startswith(("ui/", "lua/")) for n in z.namelist())
        except (OSError, zipfile.BadZipFile):
            return False
    return False


def unpacked_dir(mods_folder: str) -> str:
    return os.path.join(mods_folder, "unpacked")


def installed_path(mods_folder: str) -> str:
    if not mods_folder:
        return ""
    folder = os.path.join(unpacked_dir(mods_folder), MOD_NAME)
    if os.path.isdir(folder):
        return folder
    for zip_path in glob.glob(os.path.join(mods_folder, "*exporter*.zip")) + glob.glob(os.path.join(mods_folder, MOD_NAME + "*.zip")):
        if "beamskin" in os.path.basename(zip_path).lower():
            return zip_path
    return ""


def _manifest(folder: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for dirpath, _dirs, files in os.walk(folder):
        for name in files:
            full = os.path.join(dirpath, name)
            out[os.path.relpath(full, folder).replace("\\", "/")] = os.path.getsize(full)
    return out


def status(mods_folder: str) -> str:
    target = installed_path(mods_folder)
    if not target:
        return MISSING
    source = bundled_source()
    if os.path.isdir(target) and source and os.path.isdir(source):
        try:
            have = _manifest(target)
            want = _manifest(source)
        except OSError:
            return INSTALLED
        if any(have.get(k) != v for k, v in want.items()):
            return OUTDATED
    return INSTALLED


def install(mods_folder: str, source: str = "") -> str:
    source = source or bundled_source()
    if not source:
        raise FileNotFoundError("The exporter mod was not found next to the app.")
    target = os.path.join(unpacked_dir(mods_folder), MOD_NAME)
    os.makedirs(unpacked_dir(mods_folder), exist_ok=True)
    if os.path.isdir(target):
        shutil.rmtree(target)
    if os.path.isdir(source):
        shutil.copytree(source, target)
    else:
        with zipfile.ZipFile(source) as z:
            z.extractall(target)
    return target


def app_name(folder: str = "") -> str:
    for base in (folder, bundled_source()):
        if base and os.path.isdir(base):
            for manifest in glob.glob(os.path.join(base, "**", "app.json"), recursive=True):
                try:
                    with open(manifest, "r", encoding="utf-8") as f:
                        name = json.load(f).get("name")
                    if name:
                        return str(name)
                except (OSError, ValueError):
                    continue
    return "BeamSkin Studio - Vehicle Parts Exporter"


def export_folder(mods_folder: str, carid: str) -> str:
    if not mods_folder:
        return ""
    return os.path.join(os.path.dirname(os.path.normpath(mods_folder)), "settings", "beamskin_studio", carid)


def has_export(folder: str) -> bool:
    try:
        return bool(folder) and os.path.isdir(folder) and any(n.lower().endswith(".json") for n in os.listdir(folder))
    except OSError:
        return False


def howto_text(carid: str, name: str, folder: str) -> str:
    where = folder or "…/BeamNG.drive/current/settings/beamskin_studio/<vehicle>"
    return (
        f"1. Start BeamNG.drive (restart it if it was already open) and spawn {carid or 'the vehicle'} "
        "with the parts you want to preview.\n"
        f"2. Open the UI apps menu (Vehicle Info category), add \"{name}\" to your layout, "
        "pick a preset name and press \"Export current vehicle parts\".\n"
        f"3. Come back here and click Load BeamNG parts, then pick the preset's .json from:\n{where}"
    )
