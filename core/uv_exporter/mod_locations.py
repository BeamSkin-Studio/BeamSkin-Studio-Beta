from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
import zipfile
from dataclasses import dataclass
from typing import Optional

try:
    from core.settings import get_settings_path
except Exception:
    def get_settings_path():
        return os.path.join(os.path.expanduser("~"), "BeamSkinStudio", "data", "app_settings.json")

_LOCK = threading.Lock()


def _store_path() -> str:
    return os.path.join(os.path.dirname(get_settings_path()), "mod_locations.json")


def _norm(p: str) -> str:
    return os.path.normcase(os.path.abspath(p))


def _load() -> dict:
    try:
        with open(_store_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(data: dict) -> None:
    path = _store_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def register(carid: str, mod_path: str) -> None:
    if not carid or not mod_path:
        return
    mod_path = os.path.abspath(mod_path)
    with _LOCK:
        data = _load()
        existing = [p for p in data.get(carid, []) if _norm(p) != _norm(mod_path)]
        data[carid] = [mod_path] + existing
        try:
            _save(data)
        except OSError as e:
            print(f"[WARNING] mod_locations.register: {e}")


def forget(carid: str, mod_path: Optional[str] = None) -> None:
    with _LOCK:
        data = _load()
        if carid not in data:
            return
        if mod_path is None:
            del data[carid]
        else:
            data[carid] = [p for p in data[carid] if _norm(p) != _norm(mod_path)]
            if not data[carid]:
                del data[carid]
        try:
            _save(data)
        except OSError as e:
            print(f"[WARNING] mod_locations.forget: {e}")


def locations(carid: str) -> list[str]:
    return list(_load().get(carid, []))


def missing_locations(carid: str) -> list[str]:
    return [p for p in locations(carid) if not os.path.exists(p)]


@dataclass
class ModDaeSource:
    carid: str
    mod_path: str
    member: Optional[str]
    size: int
    label: str

    def key(self) -> str:
        return f"{_norm(self.mod_path)}|{self.member or ''}"


def _is_car_segment(parts: list[str], carid: str) -> bool:
    cid = carid.lower()
    for i, seg in enumerate(parts[:-1]):
        if seg == "vehicles" and i + 1 < len(parts) - 1 and parts[i + 1] == cid:
            return True
    return False


def _scan_location(carid: str, path: str) -> list[ModDaeSource]:
    out: list[ModDaeSource] = []
    name = os.path.basename(path.rstrip("\\/"))
    if os.path.isfile(path):
        if path.lower().endswith(".dae"):
            out.append(ModDaeSource(carid, path, None, os.path.getsize(path), f"{name} (mod)"))
        elif zipfile.is_zipfile(path):
            try:
                with zipfile.ZipFile(path) as z:
                    for info in z.infolist():
                        if info.is_dir() or not info.filename.lower().endswith(".dae"):
                            continue
                        out.append(ModDaeSource(
                            carid, path, info.filename, info.file_size,
                            f"{name} › {info.filename}"))
            except (OSError, zipfile.BadZipFile) as e:
                print(f"[WARNING] mod_locations: cannot read {path!r}: {e}")
    elif os.path.isdir(path):
        for dirpath, _dirs, files in os.walk(path):
            for fn in files:
                if not fn.lower().endswith(".dae"):
                    continue
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, path)
                try:
                    size = os.path.getsize(full)
                except OSError:
                    continue
                out.append(ModDaeSource(carid, full, None, size, f"{name} › {rel}"))
    return out


def _squash(text: str) -> str:
    return "".join(c for c in text.lower() if c.isalnum())


def _rank(carid: str, src: ModDaeSource):
    name = src.member if src.member is not None else src.mod_path
    norm = name.replace("\\", "/")
    stem = _squash(os.path.splitext(os.path.basename(norm))[0])
    cid = _squash(carid)
    if stem == cid:
        name_rank = 0
    elif cid and cid in stem:
        name_rank = 1
    else:
        name_rank = 2
    in_car_dir = 0 if _is_car_segment(norm.lower().split("/"), carid) else 1
    return (name_rank, in_car_dir, -src.size)


def _sorted(carid: str, sources: list[ModDaeSource]) -> list[ModDaeSource]:
    return sorted(sources, key=lambda s: _rank(carid, s))


def find_dae_sources(carid: str) -> list[ModDaeSource]:
    results: list[ModDaeSource] = []
    seen: set[str] = set()
    for loc in locations(carid):
        if not os.path.exists(loc):
            continue
        for s in _scan_location(carid, loc):
            if s.key() not in seen:
                seen.add(s.key())
                results.append(s)
    return _sorted(carid, results)


def probe(carid: str, path: str) -> list[ModDaeSource]:
    return _sorted(carid, _scan_location(carid, path))


def _cache_path(src: ModDaeSource) -> str:
    if src.member is None:
        return src.mod_path
    try:
        mtime = int(os.path.getmtime(src.mod_path))
    except OSError:
        mtime = 0
    h = hashlib.sha1(f"{src.key()}|{mtime}".encode("utf-8")).hexdigest()[:16]
    return os.path.join(tempfile.gettempdir(), "bss_uv_cache", h, os.path.basename(src.member))


def materialize(src: ModDaeSource) -> str:
    dest = _cache_path(src)
    if src.member is None:
        if not os.path.isfile(dest):
            raise ValueError(f"Model file no longer exists: {dest}")
        return dest
    if os.path.isfile(dest) and os.path.getsize(dest) == src.size:
        return dest
    if not os.path.isfile(src.mod_path):
        raise ValueError(f"Mod archive no longer exists: {src.mod_path}")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with zipfile.ZipFile(src.mod_path) as z, z.open(src.member) as fin, open(dest, "wb") as fout:
        while True:
            chunk = fin.read(1 << 20)
            if not chunk:
                break
            fout.write(chunk)
    return dest
