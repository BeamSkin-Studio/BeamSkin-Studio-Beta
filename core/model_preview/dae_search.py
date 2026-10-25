from __future__ import annotations

import json
import os
import re
import tempfile
from typing import Optional

from .vehicle_fs import VehicleFS

CACHE_DIR = os.path.join(tempfile.gettempdir(), "BeamSkinStudio_preview")

_TAG = re.compile(rb"<(?:node|geometry)\b([^>]*)>")
_ATTR = re.compile(rb'\b(?:name|id)\s*=\s*"([^"]*)"')
_NAME_MEM: dict[str, frozenset] = {}
_NAME_DISK = os.path.join(CACHE_DIR, "dae_names.json")
_disk: Optional[dict] = None


def _disk_cache() -> dict:
    global _disk
    if _disk is None:
        try:
            with open(_NAME_DISK, "r", encoding="utf-8") as f:
                _disk = json.load(f)
            if not isinstance(_disk, dict):
                _disk = {}
        except (OSError, ValueError):
            _disk = {}
    return _disk


def _save_disk_cache():
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        tmp = _NAME_DISK + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_disk or {}, f)
        os.replace(tmp, _NAME_DISK)
    except OSError:
        pass


def dae_names(vfs: VehicleFS, vpath: str) -> frozenset:
    key = "|".join(str(p) for p in vfs.stamp(vpath))
    hit = _NAME_MEM.get(key)
    if hit is not None:
        return hit
    disk = _disk_cache()
    if key in disk:
        names = frozenset(disk[key])
    else:
        data = vfs.read(vpath)
        found = set()
        for m in _TAG.finditer(data):
            for a in _ATTR.finditer(m.group(1)):
                found.add(a.group(1).decode("utf-8", "replace"))
        names = frozenset(found)
        disk[key] = sorted(names)
        _save_disk_cache()
    _NAME_MEM[key] = names
    return names


def _squash(text: str) -> str:
    return "".join(c for c in (text or "").lower() if c.isalnum())


def find_extra_daes(
    vfs: VehicleFS,
    carid: str,
    variant: str,
    wanted: set[str],
    extra_dirs=(),
    shallow_dirs=(),
    mesh_dirs=None,
) -> list[tuple[str, frozenset]]:
    if not wanted:
        return []
    wanted_cf = {name.casefold(): name for name in wanted}

    def hits_of(vpath: str) -> frozenset:
        try:
            names = dae_names(vfs, vpath)
        except (OSError, KeyError):
            return frozenset()
        return frozenset(wanted_cf[n.casefold()] for n in names if n.casefold() in wanted_cf)

    found: dict[str, frozenset] = {}
    scanned: set[str] = set()
    searches = [(f"vehicles/{carid}/", True), (f"vehicles/common/{carid}/", True)]
    searches += [(d, True) for d in extra_dirs] + [(d, False) for d in shallow_dirs]
    for prefix, recursive in searches:
        for vpath in vfs.files(prefix, ".dae", recursive=recursive):
            if vpath.lower() in scanned:
                continue
            scanned.add(vpath.lower())
            hits = hits_of(vpath)
            if hits:
                found[vpath] = hits

    covered = set().union(*found.values()) if found else set()
    uncovered = set(wanted) - covered
    if uncovered:
        key = _squash(variant)
        tokens = {
            _squash(token)
            for name in uncovered
            for token in re.findall(r"[a-z]+", name.lower())
            if len(token) >= 4
        }
        for vpath in vfs.files("vehicles/common/", ".dae"):
            if vpath.lower() in scanned:
                continue
            path = _squash(vpath)
            if not ((key and key in path) or any(token in path for token in tokens)):
                continue
            hits = hits_of(vpath) & uncovered
            if hits:
                found[vpath] = frozenset(hits)

    if mesh_dirs:
        def rank(vpath: str, folder: str) -> int:
            if not folder:
                return 2
            where = vpath.rsplit("/", 1)[0].lower() + "/"
            if where == folder:
                return 0
            return 1 if where.startswith(folder) else 2

        picked: dict[str, set] = {}
        for name in sorted(wanted):
            options = [v for v, hits in found.items() if name in hits]
            if not options:
                continue
            folder = (mesh_dirs.get(name.casefold()) or "").lower()
            best = min(options, key=lambda v: (rank(v, folder), -len(found[v]), v))
            picked.setdefault(best, set()).add(name)
        return sorted(((v, frozenset(names)) for v, names in picked.items()),
                      key=lambda item: (-len(item[1]), item[0]))

    chosen: list[tuple[str, frozenset]] = []
    remaining = set(wanted)
    while remaining and found:
        vpath = max(found, key=lambda v: (len(found[v] & remaining), v))
        gain = found.pop(vpath) & remaining
        if not gain:
            break
        chosen.append((vpath, frozenset(gain)))
        remaining -= gain
    return chosen


def find_variant_daes(vfs: VehicleFS, carid: str, variant: str) -> list[str]:
    key = _squash(variant)
    if not key:
        return []
    car = _squash(carid)
    found: list[str] = []
    for prefix in (f"vehicles/{carid}/", f"vehicles/common/{carid}/", "vehicles/common/"):
        for vpath in vfs.files(prefix, ".dae"):
            if key in _squash(vpath) and vpath not in found:
                found.append(vpath)
    own = [v for v in found if car and car in _squash(v)]
    return own or found
