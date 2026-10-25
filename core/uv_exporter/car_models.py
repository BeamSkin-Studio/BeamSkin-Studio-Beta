
from __future__ import annotations

import os
import tempfile
import zipfile
from dataclasses import dataclass


@dataclass
class CarModelSource:
    label: str
    kind: str
    path: str
    member: str = ""
    size: int = 0
    carid: str = ""


def _fmt_size(n: int) -> str:
    if n >= 1 << 20:
        return f"{n / (1 << 20):.1f} MB"
    return f"{max(1, n // 1024)} KB"


def _scan_folder(root: str, carid: str, out: list[CarModelSource]) -> None:
    if not os.path.isdir(root):
        return
    for dirpath, _dirs, files in os.walk(root):
        for fn in files:
            if not fn.lower().endswith(".dae"):
                continue
            full = os.path.join(dirpath, fn)
            try:
                size = os.path.getsize(full)
            except OSError:
                size = 0
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            out.append(CarModelSource(
                label=f"{rel}  ({_fmt_size(size)})",
                kind="file", path=full, size=size, carid=carid,
            ))


def find_car_dae_sources(carid: str) -> list[CarModelSource]:
    found: list[CarModelSource] = []

    try:
        from core.settings import get_vehicles_dir
        _scan_folder(os.path.join(get_vehicles_dir(), carid), carid, found)
    except Exception as exc:
        print(f"[WARNING] uv_exporter: local vehicle scan failed: {exc}")

    install = None
    try:
        from core.settings import get_beamng_install_path
        install = get_beamng_install_path()
    except Exception as exc:
        print(f"[WARNING] uv_exporter: BeamNG path lookup failed: {exc}")

    if install:
        vehicles = os.path.join(install, "content", "vehicles")
        _scan_folder(os.path.join(vehicles, carid), carid, found)

        zip_path = os.path.join(vehicles, f"{carid}.zip")
        if os.path.isfile(zip_path):
            prefix = f"vehicles/{carid}/"
            try:
                with zipfile.ZipFile(zip_path, "r") as z:
                    for info in z.infolist():
                        name = info.filename
                        if name.startswith(prefix) and name.lower().endswith(".dae"):
                            rel = name[len(prefix):]
                            found.append(CarModelSource(
                                label=f"{rel}  ({_fmt_size(info.file_size)})",
                                kind="zip", path=zip_path, member=name,
                                size=info.file_size, carid=carid,
                            ))
            except zipfile.BadZipFile as exc:
                print(f"[WARNING] uv_exporter: bad zip {zip_path}: {exc}")

    found.sort(key=lambda s: s.size, reverse=True)
    return found


def _cache_root() -> str:
    return os.path.join(tempfile.gettempdir(), "BeamSkinStudio", "uv_exporter_cache")


def resolve_path(source: CarModelSource) -> str:
    if source.kind == "file":
        return source.path
    root = os.path.join(_cache_root(), source.carid or "_")
    target = os.path.normpath(os.path.join(root, *source.member.split("/")))
    if not target.startswith(os.path.normpath(root) + os.sep):
        raise ValueError(f"Refusing unsafe zip member path: {source.member!r}")
    return target


def materialize(source: CarModelSource) -> str:
    target = resolve_path(source)
    if source.kind == "file":
        return target
    if os.path.isfile(target) and os.path.getsize(target) == source.size:
        return target
    os.makedirs(os.path.dirname(target), exist_ok=True)
    tmp = target + ".part"
    with zipfile.ZipFile(source.path, "r") as z, z.open(source.member) as src, open(tmp, "wb") as dst:
        while True:
            chunk = src.read(1 << 20)
            if not chunk:
                break
            dst.write(chunk)
    os.replace(tmp, target)
    return target
