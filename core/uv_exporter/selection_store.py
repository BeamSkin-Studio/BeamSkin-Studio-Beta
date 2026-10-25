
import json
import os

_STORE_FILENAME = "uv_exporter_selections.json"


def _store_path() -> str:
    try:
        from core.settings import get_settings_path
        base = os.path.dirname(get_settings_path())
    except Exception:
        base = os.path.join(os.path.expanduser("~"), "BeamSkinStudio", "data")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, _STORE_FILENAME)


def _load_all() -> dict:
    path = _store_path()
    if not os.path.isfile(path):
        return {"by_path": {}, "by_name": {}}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"by_path": {}, "by_name": {}}
    data.setdefault("by_path", {})
    data.setdefault("by_name", {})
    return data


def _save_all(data: dict) -> None:
    path = _store_path()
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, path)
    except OSError:
        pass


def save_selection(file_path: str, selection: dict) -> None:
    data = _load_all()
    data["by_path"][os.path.abspath(file_path)] = selection
    data["by_name"][os.path.basename(file_path)] = selection
    _save_all(data)


def load_selection(file_path: str) -> dict | None:
    data = _load_all()
    abs_path = os.path.abspath(file_path)
    if abs_path in data["by_path"]:
        return data["by_path"][abs_path]
    return data["by_name"].get(os.path.basename(file_path))


def clear_selection(file_path: str) -> None:
    data = _load_all()
    data["by_path"].pop(os.path.abspath(file_path), None)
    data["by_name"].pop(os.path.basename(file_path), None)
    _save_all(data)
