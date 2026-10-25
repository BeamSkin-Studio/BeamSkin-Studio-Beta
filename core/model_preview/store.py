from __future__ import annotations

import json
import os
import threading

try:
    from core.settings import get_settings_path
except Exception:
    def get_settings_path():
        return os.path.join(os.path.expanduser("~"), "BeamSkinStudio", "data", "app_settings.json")

_LOCK = threading.Lock()


def _path() -> str:
    return os.path.join(os.path.dirname(get_settings_path()), "model_preview.json")


def _load() -> dict:
    try:
        with open(_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(data: dict) -> None:
    path = _path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, path)


_OPTIONS_KEY = "_options"


def get_option(name: str, default=None):
    opts = _load().get(_OPTIONS_KEY, {})
    return opts.get(name, default) if isinstance(opts, dict) else default


def set_option(name: str, value) -> None:
    with _LOCK:
        data = _load()
        opts = data.get(_OPTIONS_KEY)
        if not isinstance(opts, dict):
            opts = {}
            data[_OPTIONS_KEY] = opts
        opts[name] = value
        try:
            _save(data)
        except OSError as e:
            print(f"[WARNING] model_preview.store: {e}")


def get_model(carid: str) -> str | None:
    return _load().get(carid, {}).get("model")


def set_model(carid: str, model_key: str) -> None:
    with _LOCK:
        data = _load()
        data.setdefault(carid, {})["model"] = model_key
        try:
            _save(data)
        except OSError as e:
            print(f"[WARNING] model_preview.store: {e}")


def get_selection(carid: str, model_key: str, rules: int | None = None) -> tuple[set[str], set[str]] | None:
    entry = _load().get(carid, {}).get("selections", {}).get(model_key)
    if not isinstance(entry, dict):
        return None
    if rules is not None and entry.get("rules", 0) != rules:
        return None
    return set(entry.get("visible", [])), set(entry.get("hidden", []))


def set_selection(carid: str, model_key: str, visible: list[str], hidden: list[str], rules: int = 0) -> None:
    with _LOCK:
        data = _load()
        sel = data.setdefault(carid, {}).setdefault("selections", {})
        sel[model_key] = {"visible": sorted(visible), "hidden": sorted(hidden), "rules": rules}
        try:
            _save(data)
        except OSError as e:
            print(f"[WARNING] model_preview.store: {e}")


def clear_selection(carid: str, model_key: str) -> None:
    with _LOCK:
        data = _load()
        sel = data.get(carid, {}).get("selections", {})
        if model_key in sel:
            del sel[model_key]
            try:
                _save(data)
            except OSError as e:
                print(f"[WARNING] model_preview.store: {e}")


def _presets(data: dict, carid: str, model_key: str, create: bool = False) -> dict | None:
    car = data.setdefault(carid, {}) if create else data.get(carid)
    if not isinstance(car, dict):
        return None
    allp = car.setdefault("presets", {}) if create else car.get("presets")
    if not isinstance(allp, dict):
        return None
    bucket = allp.setdefault(model_key, {}) if create else allp.get(model_key)
    return bucket if isinstance(bucket, dict) else None


def list_presets(carid: str, model_key: str) -> list[str]:
    bucket = _presets(_load(), carid, model_key) or {}
    return sorted((n for n, v in bucket.items() if isinstance(v, dict)), key=str.lower)


def get_preset(carid: str, model_key: str, name: str) -> tuple[set[str], set[str]] | None:
    entry = (_presets(_load(), carid, model_key) or {}).get(name)
    if not isinstance(entry, dict):
        return None
    return set(entry.get("visible", [])), set(entry.get("hidden", []))


def set_preset(carid: str, model_key: str, name: str, visible: list[str], hidden: list[str]) -> bool:
    with _LOCK:
        data = _load()
        bucket = _presets(data, carid, model_key, create=True)
        if bucket is None:
            data[carid]["presets"] = {model_key: {}}
            bucket = data[carid]["presets"][model_key]
        bucket[name] = {"visible": sorted(visible), "hidden": sorted(hidden)}
        try:
            _save(data)
            return True
        except OSError as e:
            print(f"[WARNING] model_preview.store: {e}")
            return False


def delete_preset(carid: str, model_key: str, name: str) -> None:
    with _LOCK:
        data = _load()
        bucket = _presets(data, carid, model_key)
        if bucket is not None and name in bucket:
            del bucket[name]
            try:
                _save(data)
            except OSError as e:
                print(f"[WARNING] model_preview.store: {e}")
