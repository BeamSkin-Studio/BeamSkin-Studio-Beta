from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

print("[DEBUG] project_registry: module loading")

### registry file paths resolved relative to this file
_HERE     = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(os.path.dirname(_HERE), "data")
_REGISTRY = os.path.join(_DATA_DIR, "project_registry.json")

print(f"[DEBUG] project_registry: _DATA_DIR={_DATA_DIR}")
print(f"[DEBUG] project_registry: _REGISTRY={_REGISTRY}")


### internal helpers

def _now_iso() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[DEBUG] _now_iso: returning {ts}")
    return ts


def _file_meta(path: str) -> Dict:
    print(f"[DEBUG] _file_meta: reading fs metadata for {path!r}")
    try:
        st        = os.stat(path)
        mtime_iso = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        size_kb   = round(st.st_size / 1024, 1)
        print(f"[DEBUG] _file_meta: mtime={mtime_iso} size_kb={size_kb}")
        return {"last_saved": mtime_iso, "file_size_kb": size_kb}
    except OSError as exc:
        print(f"[DEBUG] _file_meta: OSError reading {path!r}: {exc} — using defaults")
        return {"last_saved": _now_iso(), "file_size_kb": 0.0}


def _count_skins(project_data: Dict) -> int:
    print(f"[DEBUG] _count_skins: counting skins in project_data")
    total = 0
    for car_key, car in project_data.get("cars", {}).items():
        n = len(car.get("skins", []))
        print(f"[DEBUG] _count_skins: car={car_key!r} skins={n}")
        total += n
    print(f"[DEBUG] _count_skins: total={total}")
    return total


def _read() -> List[Dict]:
    print(f"[DEBUG] _read: reading registry from {_REGISTRY!r}")
    if not os.path.exists(_REGISTRY):
        print(f"[DEBUG] _read: registry file does not exist — returning []")
        return []
    try:
        with open(_REGISTRY, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, list):
            print(f"[DEBUG] _read: registry root is not a list (type={type(data)}) — returning []")
            return []
        print(f"[DEBUG] _read: loaded {len(data)} entries")
        return data
    except Exception as exc:
        print(f"[DEBUG] _read: ERROR reading registry: {exc}")
        return []


def _write(entries: List[Dict]) -> None:
    print(f"[DEBUG] _write: writing {len(entries)} entries to {_REGISTRY!r}")
    os.makedirs(_DATA_DIR, exist_ok=True)
    try:
        with open(_REGISTRY, "w", encoding="utf-8") as fh:
            json.dump(entries, fh, indent=2, ensure_ascii=False)
        print(f"[DEBUG] _write: write successful")
    except Exception as exc:
        print(f"[DEBUG] _write: ERROR writing registry: {exc}")


def _normalise_path(path: str) -> str:
    result = os.path.normcase(os.path.abspath(path))
    return result


### public API

def load_registry() -> List[Dict]:
    print(f"[DEBUG] load_registry: called")
    entries = _read()
    entries.sort(key=lambda e: e.get("last_saved", ""), reverse=True)
    print(f"[DEBUG] load_registry: returning {len(entries)} entries sorted newest-first")
    return entries


def add_or_update_entry(path: str, project_data: Dict) -> None:
    print(f"[DEBUG] add_or_update_entry: called with path={path!r}")
    abs_path = os.path.abspath(path)
    print(f"[DEBUG] add_or_update_entry: abs_path={abs_path!r}")

    entries = _read()
    norm    = _normalise_path(abs_path)

    existing = next(
        (e for e in entries if _normalise_path(e.get("path", "")) == norm),
        None,
    )
    print(f"[DEBUG] add_or_update_entry: existing entry found={existing is not None}")

    meta       = _file_meta(abs_path)
    car_count  = len(project_data.get("cars", {}))
    skin_count = _count_skins(project_data)
    mod_name   = project_data.get("mod_name", "") or os.path.splitext(
        os.path.basename(abs_path)
    )[0]
    author     = project_data.get("author", "")

    print(f"[DEBUG] add_or_update_entry: mod_name={mod_name!r} author={author!r} "
          f"cars={car_count} skins={skin_count}")

    entry = {
        "path":         abs_path,
        "mod_name":     mod_name,
        "author":       author,
        "car_count":    car_count,
        "skin_count":   skin_count,
        "last_saved":   meta["last_saved"],
        "file_size_kb": meta["file_size_kb"],
        "added_at":     existing.get("added_at", _now_iso()) if existing else _now_iso(),
    }
    print(f"[DEBUG] add_or_update_entry: built entry={entry}")

    if existing:
        idx = entries.index(existing)
        print(f"[DEBUG] add_or_update_entry: updating existing entry at index {idx}")
        entries[idx] = entry
    else:
        print(f"[DEBUG] add_or_update_entry: appending new entry (total will be {len(entries)+1})")
        entries.append(entry)

    _write(entries)
    print(f"[project_registry] registered: {abs_path}")


def register_existing(path: str) -> Optional[Dict]:
    print(f"[DEBUG] register_existing: called with path={path!r}")
    abs_path = os.path.abspath(path)
    print(f"[DEBUG] register_existing: abs_path={abs_path!r}")

    if not os.path.isfile(abs_path):
        print(f"[DEBUG] register_existing: file not found at {abs_path!r} — returning None")
        return None

    entries  = _read()
    norm     = _normalise_path(abs_path)
    existing = next(
        (e for e in entries if _normalise_path(e.get("path", "")) == norm),
        None,
    )

    if existing:
        print(f"[DEBUG] register_existing: already registered — refreshing fs metadata")
        meta = _file_meta(abs_path)
        existing.update(meta)
        print(f"[DEBUG] register_existing: updated meta={meta}")
        _write(entries)
        return existing

    ### new entry — read the project file for metadata
    print(f"[DEBUG] register_existing: new entry — reading project file for metadata")
    try:
        with open(abs_path, "r", encoding="utf-8") as fh:
            project_data = json.load(fh)
        print(f"[DEBUG] register_existing: project file read OK "
              f"keys={list(project_data.keys())}")
    except Exception as exc:
        print(f"[DEBUG] register_existing: ERROR reading project file: {exc} — using empty dict")
        project_data = {}

    add_or_update_entry(abs_path, project_data)

    entries = _read()
    result  = next(
        (e for e in entries if _normalise_path(e.get("path", "")) == norm),
        None,
    )
    print(f"[DEBUG] register_existing: returning entry found={result is not None}")
    return result


def remove_entry(path: str) -> bool:
    print(f"[DEBUG] remove_entry: called with path={path!r}")
    abs_path = os.path.abspath(path)
    norm     = _normalise_path(abs_path)
    entries  = _read()
    before   = len(entries)
    print(f"[DEBUG] remove_entry: {before} entries before removal")

    entries = [e for e in entries if _normalise_path(e.get("path", "")) != norm]
    after   = len(entries)
    print(f"[DEBUG] remove_entry: {after} entries after removal")

    if after < before:
        _write(entries)
        print(f"[project_registry] removed: {abs_path}")
        return True

    print(f"[DEBUG] remove_entry: path was not in registry — nothing removed")
    return False


def validate_entries() -> Tuple[List[Dict], List[Dict]]:
    print(f"[DEBUG] validate_entries: called")
    entries = _read()
    print(f"[DEBUG] validate_entries: checking {len(entries)} entries")

    valid:   List[Dict] = []
    missing: List[Dict] = []

    for entry in entries:
        p      = entry.get("path", "")
        exists = os.path.isfile(p)
        print(f"[DEBUG] validate_entries: path={p!r} exists={exists}")
        if exists:
            valid.append(entry)
        else:
            missing.append(entry)

    print(f"[DEBUG] validate_entries: valid={len(valid)} missing={len(missing)}")

    if missing:
        print(f"[DEBUG] validate_entries: pruning {len(missing)} missing entries from registry")
        _write(valid)
        print(f"[project_registry] pruned {len(missing)} missing entries")

    return valid, missing


def get_registry_path() -> str:
    print(f"[DEBUG] get_registry_path: returning {_REGISTRY!r}")
    return _REGISTRY
