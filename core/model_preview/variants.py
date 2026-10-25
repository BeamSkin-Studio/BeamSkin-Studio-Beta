from __future__ import annotations

import os
import posixpath
import zipfile
from typing import Optional

from .jbeam_reader import decode_bytes, parse_loose_json
from .vehicle_fs import VehicleFS, find_beamng_content


def _registered_vehicle_roots(carid: str) -> list[str]:
    from core.uv_exporter import mod_locations

    roots: list[str] = []
    for location in mod_locations.locations(carid):
        if os.path.isfile(location) and zipfile.is_zipfile(location):
            try:
                with zipfile.ZipFile(location) as archive:
                    if any(
                        name.replace("\\", "/").lower().startswith(
                            (f"vehicles/{carid}/", "vehicles/common/")
                        )
                        for name in archive.namelist()
                    ):
                        roots.append(location)
            except (OSError, zipfile.BadZipFile) as e:
                print(f"[WARNING] model_preview: cannot inspect added mod {location!r}: {e}")
            continue

        directory = location if os.path.isdir(location) else os.path.dirname(location)
        while directory:
            vehicles_dir = os.path.join(directory, "vehicles")
            if os.path.isdir(vehicles_dir):
                if os.path.isdir(os.path.join(vehicles_dir, carid)):
                    roots.append(directory)
                    break
            parent = os.path.dirname(directory)
            if parent == directory:
                break
            directory = parent

    unique: list[str] = []
    seen: set[str] = set()
    for root in roots:
        normalized = os.path.normcase(os.path.abspath(root))
        if normalized not in seen:
            seen.add(normalized)
            unique.append(root)
    return unique


def added_mod_roots(carid: str) -> list[str]:
    return _registered_vehicle_roots(carid)


def default_roots(carid: str, content_dir: str = "", extra_roots=()) -> list[str]:
    roots: list[str] = []
    content_dir = content_dir or find_beamng_content()
    if content_dir:
        vehicles = os.path.join(content_dir, "vehicles")
        roots += [
            os.path.join(vehicles, "common.zip"),
            os.path.join(vehicles, f"{carid}.zip"),
        ]
    roots += [r for r in extra_roots if r]
    return roots


def _squash(text: str) -> str:
    return "".join(c for c in (text or "").lower() if c.isalnum())


def _configs_of(vfs: VehicleFS, carid: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for prefix in (f"vehicles/{carid}/", f"vehicles/common/{carid}/"):
        for vpath in vfs.files(prefix, ".pc", recursive=False):
            out[posixpath.splitext(posixpath.basename(vpath))[0]] = vpath
    return out


def _read_pc(vfs: VehicleFS, vpath: str) -> dict:
    try:
        data = parse_loose_json(decode_bytes(vfs.read(vpath)))
    except (OSError, ValueError, KeyError):
        return {}
    return data if isinstance(data, dict) else {}


def _score(name: str, carid: str, suffix: str) -> Optional[int]:
    n, s, c = _squash(name), _squash(suffix), _squash(carid)
    if not s:
        return None
    if n == s or n == c + s:
        return 0
    if n.endswith(s):
        return 1
    if s in n:
        return 2
    return None


def _pc_hits(pc: dict, suffix: str) -> int:
    s = _squash(suffix)
    parts = pc.get("parts")
    if not s or not isinstance(parts, dict):
        return 0
    return sum(1 for v in parts.values() if isinstance(v, str) and v and s in _squash(v))


def default_chosen_parts(vfs: VehicleFS, carid: str, variant: str) -> Optional[tuple[str, dict]]:
    if not carid or not _squash(variant):
        return None
    ranked = []
    for name, vpath in _configs_of(vfs, carid).items():
        score = _score(name, carid, variant)
        pc = None
        if score is None:
            pc = _read_pc(vfs, vpath)
            if _pc_hits(pc, variant) >= 2:
                score = 3
        if score is not None:
            ranked.append((score, name.lower(), name, vpath, pc))
    for _score_, _low, name, vpath, pc in sorted(ranked, key=lambda r: r[:4]):
        pc = pc if pc is not None else _read_pc(vfs, vpath)
        parts = pc.get("parts")
        if not isinstance(parts, dict):
            continue
        chosen = {
            key.strip().strip("/"): value.strip()
            for key, value in parts.items()
            if isinstance(key, str) and isinstance(value, str) and value.strip()
        }
        main = pc.get("mainPartName")
        if isinstance(main, str) and main.strip():
            chosen["__main"] = main.strip()
        if chosen:
            return name, chosen
    return None
