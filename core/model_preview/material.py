from __future__ import annotations

import os
import posixpath
from dataclasses import dataclass, replace
from typing import Callable, Optional

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

DETAIL_CAP = 1024
SURFACE_CAP = 4096

MAP_KEYS = (
    "baseColorMap", "opacityMap", "opacityDetailMap",
    "roughnessDetailMap", "metallicDetailMap", "colorPaletteMap",
    "roughnessMap", "metallicMap", "normalMap",
)

DEFAULT_PAINTS = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


@dataclass
class PreviewMaterial:
    albedo: Optional[QImage] = None
    detail: Optional[QImage] = None
    palette: Optional[QImage] = None
    surface: Optional[QImage] = None
    under: Optional[QImage] = None
    mask: Optional[QImage] = None
    mask_uv0: bool = False
    surface_uv0: bool = False
    under_uv0: bool = False
    detail_uv0: bool = False
    detail_scale: tuple = (1.0, 1.0)
    roughness: float = 1.0
    metallic: float = 0.0
    clearcoat: float = 0.0
    clearcoat_roughness: float = 0.0
    retroreflectivity: float = 0.0

    @property
    def has_detail(self) -> bool:
        return self.detail is not None


@dataclass
class PreviewMaterialSet:
    base: PreviewMaterial
    variant: Optional[PreviewMaterial] = None


def _to_array(img: QImage) -> np.ndarray:
    img = img.convertToFormat(QImage.Format_RGBA8888)
    w, h, bpl = img.width(), img.height(), img.bytesPerLine()
    raw = np.frombuffer(img.constBits(), dtype=np.uint8, count=h * bpl)
    return raw.reshape(h, bpl)[:, : w * 4].reshape(h, w, 4).copy()


def _to_image(arr: np.ndarray) -> QImage:
    arr = np.ascontiguousarray(arr, dtype=np.uint8)
    h, w = arr.shape[:2]
    return QImage(arr.data, w, h, w * 4, QImage.Format_RGBA8888).copy()


def _resized(img: QImage, w: int, h: int) -> QImage:
    if (img.width(), img.height()) == (w, h):
        return img
    return img.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)


def _channel_r(img: QImage, w: int, h: int) -> np.ndarray:
    return _to_array(_resized(img, w, h))[:, :, 0]


def _number(stage: dict, key: str, default: float) -> float:
    try:
        value = stage.get(key, default)
        return float(default if value is None else value)
    except (TypeError, ValueError):
        return float(default)


DEFAULT_DETAIL_SCALE = (1500.0, 750.0)


def _scale(stage: dict) -> tuple:
    value = stage.get("detailScale")
    try:
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            sx, sy = float(value[0]), float(value[1])
        elif isinstance(value, (list, tuple)) and len(value) == 1:
            sx = sy = float(value[0])
        elif value is not None:
            sx = sy = float(value)
        else:
            has_detail = any(stage.get(k) for k in
                             ("opacityDetailMap", "roughnessDetailMap", "metallicDetailMap"))
            return DEFAULT_DETAIL_SCALE if has_detail else (1.0, 1.0)
    except (TypeError, ValueError):
        return (1.0, 1.0)
    return (sx if sx > 0 else 1.0, sy if sy > 0 else 1.0)


_COLOUR_UV_KEYS = ("diffuseMapUseUV", "baseColorMapUseUV")


def _per_map_uv(stage: dict) -> bool:
    return any(stage.get(k) is not None for k in _COLOUR_UV_KEYS)


def _on_uv0(stage: dict, *keys: str) -> bool:
    for key in keys:
        value = stage.get(key)
        if value is None:
            continue
        try:
            return not int(value)
        except (TypeError, ValueError):
            continue
    return True


def _colour_on_uv1(stage: dict) -> bool:
    for key in _COLOUR_UV_KEYS:
        value = stage.get(key)
        if value is None:
            continue
        try:
            return bool(int(value))
        except (TypeError, ValueError):
            continue
    return False


def _explicit_uv0(stage: dict, *keys: str) -> bool:
    if not _colour_on_uv1(stage):
        return False
    for key in keys:
        value = stage.get(key)
        if value is None:
            continue
        try:
            return not int(value)
        except (TypeError, ValueError):
            continue
    return False


def stage_files(stage: dict, resolve: Callable[[str], Optional[str]]) -> dict:
    out = {}
    for key in MAP_KEYS:
        value = stage.get(key)
        if not value or not isinstance(value, str):
            continue
        path = resolve(value)
        if path and os.path.isfile(path):
            out[key] = path
    for i, layer in enumerate(stage.get("_under") or []):
        if isinstance(layer, dict):
            for key, path in stage_files(layer, resolve).items():
                out[f"under{i}:{key}"] = path
    variant = stage.get("_variant")
    if isinstance(variant, dict):
        for key, path in stage_files(variant, resolve).items():
            out[f"variant:{key}"] = path
    return out


def stage_stamp(files: dict) -> tuple:
    parts = []
    for key in sorted(files):
        try:
            st = os.stat(files[key])
            parts.append((key, files[key], st.st_mtime, st.st_size))
        except OSError:
            parts.append((key, files[key], 0, 0))
    return tuple(parts)


UNDER_CAP = 2048
UNDER_CAP_FULL = 16384
_STRIP_ROWS = 512


def _strip(img: QImage, sw: int, sh: int, y0: int, y1: int) -> np.ndarray:
    iw, ih = img.width(), img.height()
    if (iw, ih) == (sw, sh):
        return _to_array(img.copy(0, y0, iw, y1 - y0))
    s0 = max(0, min(ih - 1, (y0 * ih) // sh))
    s1 = max(s0 + 1, min(ih, -(-(y1 * ih) // sh)))
    band = img.copy(0, s0, iw, s1 - s0)
    return _to_array(_resized(band, sw, y1 - y0))


def _build_under(layers: list, resolve, load, size: tuple, full: bool = False) -> Optional[QImage]:
    bw, bh = size
    cap = UNDER_CAP_FULL if full else UNDER_CAP
    scale = min(1.0, cap / max(bw, bh, 1))
    sw, sh = max(1, int(bw * scale)), max(1, int(bh * scale))

    memo: dict = {}

    def get(path):
        if path not in memo:
            memo[path] = load(path)
        img = memo[path]
        return img if img is not None and not img.isNull() else None

    prepared = []
    for layer in layers:
        files = stage_files(layer, resolve)
        if "baseColorMap" not in files or "colorPaletteMap" in files:
            continue
        base = get(files["baseColorMap"])
        if base is None:
            continue
        op = get(files["opacityMap"]) if "opacityMap" in files else None
        det_mean = 1.0
        if "opacityDetailMap" in files:
            det = get(files["opacityDetailMap"])
            if det is not None:
                det_mean = float(_channel_r(det, 64, 64).mean()) / 255.0
        prepared.append((base, op, bool(layer.get("_alphaOpacity")), det_mean))
    if not prepared:
        return None

    out = QImage(sw, sh, QImage.Format_RGBA8888)
    bpl = out.bytesPerLine()
    view = np.frombuffer(out.bits(), dtype=np.uint8, count=sh * bpl).reshape(sh, bpl)[:, : sw * 4].reshape(sh, sw, 4)

    for y0 in range(0, sh, _STRIP_ROWS):
        y1 = min(sh, y0 + _STRIP_ROWS)
        prem = np.zeros((y1 - y0, sw, 3), dtype=np.float32)
        alpha = np.zeros((y1 - y0, sw), dtype=np.float32)
        for base, op, alpha_opacity, det_mean in prepared:
            rgba = _strip(base, sw, sh, y0, y1)
            rgb = rgba[:, :, :3].astype(np.float32) / 255.0
            if op is not None:
                cov = _strip(op, sw, sh, y0, y1)[:, :, 0].astype(np.float32) / 255.0
            elif alpha_opacity:
                cov = rgba[:, :, 3].astype(np.float32) / 255.0
            else:
                cov = np.ones((y1 - y0, sw), dtype=np.float32)
            cov = cov * det_mean
            c3 = cov[:, :, None]
            prem = rgb * c3 + prem * (1.0 - c3)
            alpha = cov + alpha * (1.0 - cov)
        view[y0:y1, :, :3] = np.clip(prem / np.maximum(alpha, 1e-4)[:, :, None] * 255.0, 0, 255).astype(np.uint8)
        view[y0:y1, :, 3] = np.clip(alpha * 255.0, 0, 255).astype(np.uint8)
    return out


def apply_factors(material: PreviewMaterial, stage: dict) -> PreviewMaterial:
    return replace(
        material,
        detail_scale=_scale(stage),
        roughness=min(1.0, max(0.0, _number(stage, "roughnessFactor", 1.0))),
        metallic=min(1.0, max(0.0, _number(stage, "metallicFactor", 0.0))),
        clearcoat=min(1.0, max(0.0, _number(stage, "clearCoatFactor", 0.0))),
        clearcoat_roughness=min(1.0, max(0.0, _number(stage, "clearCoatRoughnessFactor", 0.0))),
        retroreflectivity=min(1.0, max(0.0, _number(stage, "retroreflectivity", 0.0))),
    )


def build_material(stage: dict,
                   resolve: Callable[[str], Optional[str]],
                   load: Callable[[str], Optional[QImage]],
                   full: bool = False) -> Optional[PreviewMaterial]:
    files = stage_files(stage, resolve)
    base = load(files["baseColorMap"]) if "baseColorMap" in files else None
    if base is None or base.isNull():
        return None

    bw, bh = base.width(), base.height()
    arr = _to_array(base)
    arr[:, :, 3] = 255

    per_map_uv = _per_map_uv(stage)
    mask = None
    mask_uv0 = False
    if "opacityMap" in files:
        op = load(files["opacityMap"])
        if op is not None and not op.isNull():
            if _explicit_uv0(stage, "opacityMapUseUV"):
                m = _to_array(op)
                m[:, :, 1] = m[:, :, 0]
                m[:, :, 2] = m[:, :, 0]
                m[:, :, 3] = 255
                mask = _to_image(m)
                mask_uv0 = True
            else:
                arr[:, :, 3] = _channel_r(op, bw, bh)

    detail = None
    detail_maps = [k for k in ("opacityDetailMap", "roughnessDetailMap", "metallicDetailMap")
                   if k in files]
    if detail_maps:
        loaded = {}
        for key in detail_maps:
            img = load(files[key])
            if img is not None and not img.isNull():
                loaded[key] = img
        if loaded:
            size = max(max(i.width(), i.height()) for i in loaded.values())
            size = max(2, min(DETAIL_CAP, 1 << max(0, (size - 1).bit_length())))
            packed = np.full((size, size, 4), 255, dtype=np.uint8)
            for chan, key in enumerate(("opacityDetailMap", "roughnessDetailMap", "metallicDetailMap")):
                if key in loaded:
                    packed[:, :, chan] = _channel_r(loaded[key], size, size)
            detail = _to_image(packed)

    palette = None
    if "colorPaletteMap" in files:
        pal = load(files["colorPaletteMap"])
        if pal is not None and not pal.isNull():
            palette = pal

    surface = None
    surface_maps = [k for k in ("normalMap", "roughnessMap", "metallicMap") if k in files]
    if surface_maps:
        scale = min(1.0, SURFACE_CAP / max(bw, bh))
        sw, sh = max(1, int(bw * scale)), max(1, int(bh * scale))
        packed = np.empty((sh, sw, 4), dtype=np.uint8)
        packed[:, :, 0] = 128
        packed[:, :, 1] = 128
        packed[:, :, 2] = 255
        packed[:, :, 3] = 255
        found = False
        for key in surface_maps:
            img = load(files[key])
            if img is None or img.isNull():
                continue
            found = True
            rgba = _to_array(_resized(img, sw, sh))
            if key == "normalMap":
                packed[:, :, 0:2] = rgba[:, :, 0:2]
            elif key == "roughnessMap":
                packed[:, :, 2] = rgba[:, :, 0]
            else:
                packed[:, :, 3] = rgba[:, :, 0]
        if found:
            surface = _to_image(packed)

    under_layers = [l for l in (stage.get("_under") or []) if isinstance(l, dict)]
    under = _build_under(under_layers, resolve, load, (bw, bh), full) if under_layers else None

    under_uv0 = bool(per_map_uv and under_layers
                     and _on_uv0(under_layers[-1], *_COLOUR_UV_KEYS))
    detail_uv0 = bool(detail is not None
                      and _explicit_uv0(stage, "opacityDetailMapUseUV", "opacityMapUseUV"))
    surface_uv0 = bool(surface is not None
                       and _explicit_uv0(stage, "normalMapUseUV", "roughnessMapUseUV", "metallicMapUseUV"))
    return PreviewMaterial(
        albedo=_to_image(arr),
        under=under,
        mask=mask,
        mask_uv0=mask_uv0,
        surface_uv0=surface_uv0,
        under_uv0=under_uv0,
        detail_uv0=detail_uv0,
        detail=detail,
        palette=palette,
        surface=surface,
        detail_scale=_scale(stage),
        roughness=min(1.0, max(0.0, _number(stage, "roughnessFactor", 1.0))),
        metallic=min(1.0, max(0.0, _number(stage, "metallicFactor", 0.0))),
        clearcoat=min(1.0, max(0.0, _number(stage, "clearCoatFactor", 0.0))),
        clearcoat_roughness=min(1.0, max(0.0, _number(stage, "clearCoatRoughnessFactor", 0.0))),
        retroreflectivity=min(1.0, max(0.0, _number(stage, "retroreflectivity", 0.0))),
    )


def skin_stage_from_materials_json(data: dict, material_name: Optional[str] = None) -> Optional[dict]:
    mats = [m for m in data.values() if isinstance(m, dict) and m.get("Stages")]
    if material_name:
        mats = [m for m in mats if m.get("name") == material_name] or mats
    for mat in mats:
        for stage in reversed(mat["Stages"]):
            if isinstance(stage, dict) and stage.get("baseColorMap") and (
                    stage.get("opacityMap") or stage.get("opacityDetailMap")
                    or stage.get("colorPaletteMap")):
                return stage
    return None


_SKIN_MATERIAL_CACHE: dict[tuple, frozenset[str] | None] = {}


def _skin_targets_from_paths(vfs, paths: list[str]) -> frozenset[str] | None:
    from .jbeam_reader import decode_bytes, parse_loose_json

    stamp = tuple((path, vfs.stamp(path)) for path in paths)
    cache_key = (tuple(vfs.roots), stamp)
    if cache_key in _SKIN_MATERIAL_CACHE:
        return _SKIN_MATERIAL_CACHE[cache_key]

    targets: set[str] = set()
    catalog_read = False
    for path in paths:
        try:
            data = parse_loose_json(decode_bytes(vfs.read(path)))
        except (OSError, ValueError, KeyError) as e:
            print(f"[WARNING] model_preview.material: cannot read {path}: {e}")
            continue
        if not isinstance(data, dict):
            continue
        catalog_read = True
        for key, definition in data.items():
            if not isinstance(definition, dict):
                continue
            stages = definition.get("Stages")
            if not isinstance(stages, list):
                continue
            names = [
                name.casefold()
                for name in (key, definition.get("name"), definition.get("mapTo"))
                if isinstance(name, str) and name
            ]
            for name in names:
                head, dot, rest = name.partition(".")
                if dot and head and rest.startswith("skin"):
                    targets.add(head)
            if any(".skin." in name or "_skin_" in name for name in names):
                continue
            paintable = any(
                isinstance(stage, dict)
                and (bool(stage.get("colorPaletteMap")) or bool(stage.get("instanceDiffuse")))
                for stage in stages
            )
            if paintable:
                targets.update(names)
    result = frozenset(targets) if catalog_read else None
    _SKIN_MATERIAL_CACHE[cache_key] = result
    return result


def skin_target_materials(vfs, carid: str) -> frozenset[str] | None:
    paths = vfs.files(f"vehicles/{carid}/", ".materials.json")
    if not paths:
        return None
    return _skin_targets_from_paths(vfs, paths)


def skin_target_materials_for_dae(vfs, vpath: str) -> frozenset[str] | None:
    directory = posixpath.dirname(vpath)
    if not directory:
        return None
    paths = vfs.files(directory.rstrip("/") + "/", ".materials.json", recursive=False)
    return _skin_targets_from_paths(vfs, paths) if paths else None


SURFACE_VIEW_CAP = 1024
_SURFACE_MAP_KEYS = ("baseColorMap", "normalMap", "roughnessMap", "metallicMap", "ambientOcclusionMap")
_TEXTURE_EXTS = (".dds", ".png", ".jpg", ".jpeg", ".tga", ".bmp")
_FILE_CACHE: dict[tuple, dict] = {}


def _resolve_texture_vpath(vfs, base_dir: str, value: str) -> Optional[str]:
    value = value.replace("\\", "/").strip()
    if not value:
        return None
    if value.startswith("/"):
        bases = [value.lstrip("/")]
    else:
        bases = [posixpath.normpath(posixpath.join(base_dir, value)), value.lstrip("/")]
    for base in bases:
        if vfs.exists(base):
            return base
        stem, ext = posixpath.splitext(base)
        for alt in _TEXTURE_EXTS:
            if alt != ext.lower() and vfs.exists(stem + alt):
                return stem + alt
    return None


def _surface_stage(stages) -> Optional[dict]:
    stages = [s for s in (stages or []) if isinstance(s, dict)]
    for stage in stages:
        if any(isinstance(stage.get(k), str) and stage.get(k) for k in ("baseColorMap", "diffuseMap")):
            return stage
    return stages[0] if stages else None


def _paint_opacity_value(stages) -> Optional[str]:
    for stage in stages or []:
        if (isinstance(stage, dict) and isinstance(stage.get("opacityMap"), str) and stage["opacityMap"]
                and (stage.get("colorPaletteMap") or stage.get("instanceDiffuse"))):
            return stage["opacityMap"]
    return None


_DYNAMIC_MASK_TOKENS = ("dirt", "dust", "mud", "dmg", "damage")


def _paint_stage(stage) -> bool:
    return isinstance(stage, dict) and bool(stage.get("colorPaletteMap") or stage.get("instanceDiffuse"))


def _overlay_layers(stages, base) -> list[dict]:
    out: list[dict] = []
    seen = False
    for stage in stages or []:
        if stage is base:
            seen = True
            continue
        if not seen or not isinstance(stage, dict) or _paint_stage(stage):
            continue
        opacity = stage.get("opacityMap")
        if not (isinstance(opacity, str) and opacity):
            continue
        if any(token in opacity.lower() for token in _DYNAMIC_MASK_TOKENS):
            continue
        colour_map = stage.get("baseColorMap") or stage.get("diffuseMap")
        colour_map = colour_map if isinstance(colour_map, str) and colour_map else None
        factor = stage.get("baseColorFactor") or stage.get("diffuseColor")
        factor = list(factor[:3]) if isinstance(factor, (list, tuple)) and len(factor) >= 3 else None
        if colour_map is None and factor is None:
            continue
        out.append({"opacityMap": opacity, "baseColorMap": colour_map,
                    "baseColorFactor": factor, "opacityFactor": stage.get("opacityFactor")})
    return out


def _has_color_factor(stage: dict) -> bool:
    return any(isinstance(stage.get(k), (list, tuple)) and len(stage[k]) >= 3
               for k in ("baseColorFactor", "diffuseColor"))


def _resolve_surface_stage(vfs, base_dir: str, stage: dict) -> Optional[dict]:
    out = {k: v for k, v in stage.items() if k not in _SURFACE_MAP_KEYS and k != "diffuseMap"}
    sources = {
        "baseColorMap": stage.get("baseColorMap") or stage.get("diffuseMap"),
        "normalMap": stage.get("normalMap"),
        "roughnessMap": stage.get("roughnessMap"),
        "metallicMap": stage.get("metallicMap"),
        "ambientOcclusionMap": stage.get("ambientOcclusionMap"),
    }
    found = False
    paint_map = stage.get("_paintOpacity")
    out.pop("_paintOpacity", None)
    out.pop("_layers", None)
    layers = []
    for layer in stage.get("_layers") or []:
        opacity = _resolve_texture_vpath(vfs, base_dir, layer["opacityMap"])
        colour = _resolve_texture_vpath(vfs, base_dir, layer["baseColorMap"]) if layer.get("baseColorMap") else None
        if opacity is None or (colour is None and not layer.get("baseColorFactor")):
            continue
        layers.append({"opacityMap": opacity, "baseColorMap": colour,
                       "baseColorFactor": layer.get("baseColorFactor"),
                       "opacityFactor": layer.get("opacityFactor")})
    if layers:
        out["_layers"] = layers
    if isinstance(paint_map, str) and paint_map:
        vpath = _resolve_texture_vpath(vfs, base_dir, paint_map)
        if vpath:
            out["_paintOpacity"] = vpath
    for key, value in sources.items():
        if isinstance(value, str) and value:
            vpath = _resolve_texture_vpath(vfs, base_dir, value)
            if vpath:
                out[key] = vpath
                found = True
    if not found and not _has_color_factor(stage):
        return None
    return out


def _read_materials_file(vfs, vpath: str, needles: list[bytes]) -> Optional[dict]:
    from .jbeam_reader import decode_bytes, parse_loose_json

    try:
        cache_key = (tuple(vfs.roots), vfs.stamp(vpath))
    except KeyError:
        return None
    if cache_key in _FILE_CACHE:
        return _FILE_CACHE[cache_key]
    try:
        raw = vfs.read(vpath)
    except (OSError, KeyError):
        return None
    if not raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        low = raw.lower()
        if not any(n in low for n in needles):
            return None
    try:
        data = parse_loose_json(decode_bytes(raw))
    except (ValueError, KeyError) as e:
        print(f"[WARNING] model_preview.material: cannot read {vpath}: {e}")
        return None
    if not isinstance(data, dict):
        return None
    if len(_FILE_CACHE) > 300:
        _FILE_CACHE.clear()
    _FILE_CACHE[cache_key] = data
    return data


def build_material_defs(vfs, carid: str, dae_vpaths, needed) -> dict[str, dict]:
    wanted = {n.casefold() for n in needed if n}
    if not wanted:
        return {}
    needles = [n.encode("utf-8", "replace") for n in wanted]

    seen: set[str] = set()

    def files_in(dirs) -> list[str]:
        out = []
        for d in dirs:
            for vpath in vfs.files(d, "materials.json"):
                if vpath.lower() not in seen:
                    seen.add(vpath.lower())
                    out.append(vpath)
        return out

    car_dirs: list[str] = []
    if carid:
        car_dirs.append(f"vehicles/common/{carid}/")
    for vpath in dae_vpaths:
        d = posixpath.dirname(vpath).rstrip("/") + "/"
        if d not in car_dirs:
            car_dirs.append(d)
    if carid:
        car_dirs.append(f"vehicles/{carid}/")
    tiers = [
        lambda: files_in(car_dirs),
        lambda: files_in(["vehicles/common/"]),
        lambda: files_in(["vehicles/"]),
    ]

    exact: dict[str, tuple] = {}
    variants: dict[str, dict[str, tuple]] = {}

    def rank(n: str, key: str, definition: dict) -> tuple:
        own = 0 if n in (key.casefold(), str(definition.get("name") or "").casefold()) else 1
        return own, 0 if "black" in key.casefold() else 1

    for tier in tiers:
        if wanted <= exact.keys():
            break
        tier_exact: dict[str, tuple] = {}
        for vpath in tier():
            data = _read_materials_file(vfs, vpath, needles)
            if not data:
                continue
            for key, definition in data.items():
                if not isinstance(definition, dict) or not isinstance(definition.get("Stages"), list):
                    continue
                names = {
                    n.casefold() for n in (key, definition.get("name"), definition.get("mapTo"))
                    if isinstance(n, str) and n
                }
                if any(".skin." in n for n in names):
                    continue
                stage = _surface_stage(definition["Stages"])
                if stage is None:
                    continue
                paint_map = _paint_opacity_value(definition["Stages"])
                layers = (_overlay_layers(definition["Stages"], stage)
                          if any(_paint_stage(st) for st in definition["Stages"]) else [])
                extra_keys: dict = {}
                if paint_map:
                    extra_keys["_paintOpacity"] = paint_map
                if layers:
                    extra_keys["_layers"] = layers
                if (_paint_stage(stage) and not (stage.get("baseColorMap") or stage.get("diffuseMap"))
                        and not stage.get("opacityMap")):
                    extra_keys["_paintFull"] = True
                if extra_keys:
                    stage = dict(stage)
                    stage.update(extra_keys)
                for n in names:
                    entry = (vpath, key, stage, rank(n, key, definition))
                    if n in wanted:
                        if n not in exact and (n not in tier_exact or entry[3] <= tier_exact[n][3]):
                            tier_exact[n] = entry
                    else:
                        for i, ch in enumerate(n):
                            if ch == "." and n[:i] in wanted:
                                variants.setdefault(n[:i], {})[n] = (
                                    vpath, key, stage, (1, rank(n, key, definition)[1], len(n)))
        exact.update(tier_exact)

    out: dict[str, dict] = {}
    for n in wanted:
        entry = exact.get(n)
        if entry is None and n in variants:
            entry = min(variants[n].values(), key=lambda e: e[3])
        if entry is None:
            continue
        vpath, key, stage, _rank = entry
        resolved = _resolve_surface_stage(vfs, posixpath.dirname(vpath), stage)
        if resolved is not None:
            out[n] = {"name": key, "file": vpath, "stage": resolved}
    return out


def _color_factor(stage: dict) -> tuple:
    for key in ("baseColorFactor", "diffuseColor"):
        value = stage.get(key)
        if isinstance(value, (list, tuple)) and len(value) >= 3:
            try:
                return tuple(min(1.0, max(0.0, float(v))) for v in value[:3])
            except (TypeError, ValueError):
                continue
    return (1.0, 1.0, 1.0)


def build_surface_material(stage: dict,
                           extract: Callable[[str], Optional[str]],
                           load: Callable[[str], Optional[QImage]],
                           paint: Optional[tuple] = None) -> Optional[PreviewMaterial]:
    def load_vpath(vpath) -> Optional[QImage]:
        if not vpath:
            return None
        try:
            path = extract(vpath)
        except (OSError, KeyError):
            return None
        img = load(path) if path else None
        if img is None or img.isNull():
            return None
        if max(img.width(), img.height()) > SURFACE_VIEW_CAP:
            img = img.scaled(SURFACE_VIEW_CAP, SURFACE_VIEW_CAP, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return img

    def get(key: str) -> Optional[QImage]:
        return load_vpath(stage.get(key))

    layers = []
    for layer in stage.get("_layers") or []:
        mask_img = load_vpath(layer.get("opacityMap"))
        if mask_img is not None:
            layers.append((layer, mask_img))

    base = get("baseColorMap")
    normal = get("normalMap")
    rough_img = get("roughnessMap")
    metal_img = get("metallicMap")
    ao_img = get("ambientOcclusionMap")
    reference = base or normal or rough_img or metal_img
    if reference is None and not _has_color_factor(stage):
        return None

    if base is not None:
        arr = _to_array(base)
        w, h = base.width(), base.height()
    elif layers:
        arr = np.full((layers[0][1].height(), layers[0][1].width(), 4), 255, dtype=np.uint8)
        w, h = (reference.width(), reference.height()) if reference is not None else (arr.shape[1], arr.shape[0])
    else:
        arr = np.full((4, 4, 4), 255, dtype=np.uint8)
        w, h = (reference.width(), reference.height()) if reference is not None else (4, 4)
    arr[:, :, 3] = 255

    tint = np.array(_color_factor(stage), dtype=np.float32)
    if np.any(np.abs(tint - 1.0) > 1e-3):
        arr[:, :, :3] = np.clip(arr[:, :, :3].astype(np.float32) * tint, 0, 255).astype(np.uint8)
    if paint is not None and stage.get("_paintFull"):
        arr[:, :, :3] = np.clip(np.array(paint, dtype=np.float32) * 255.0, 0, 255).astype(np.uint8)
    paint_img = get("_paintOpacity") if paint is not None else None
    if paint_img is not None:
        cover = (_channel_r(paint_img, arr.shape[1], arr.shape[0]).astype(np.float32) / 255.0)[:, :, None]
        colour = np.array(paint, dtype=np.float32) * 255.0
        arr[:, :, :3] = np.clip(arr[:, :, :3].astype(np.float32) * (1.0 - cover) + colour * cover,
                                0, 255).astype(np.uint8)
    for layer, mask_img in layers:
        cover = (_channel_r(mask_img, arr.shape[1], arr.shape[0]).astype(np.float32) / 255.0)[:, :, None]
        opacity = layer.get("opacityFactor")
        if isinstance(opacity, (int, float)):
            cover = cover * min(1.0, max(0.0, float(opacity)))
        colour_img = load_vpath(layer.get("baseColorMap"))
        if colour_img is not None:
            colour = _to_array(_resized(colour_img, arr.shape[1], arr.shape[0]))[:, :, :3].astype(np.float32)
        else:
            colour = np.full((arr.shape[0], arr.shape[1], 3), 255.0, dtype=np.float32)
        factor = layer.get("baseColorFactor")
        if factor:
            try:
                colour = colour * np.clip(np.array([float(v) for v in factor[:3]], dtype=np.float32), 0.0, 1.0)
            except (TypeError, ValueError):
                pass
        arr[:, :, :3] = np.clip(arr[:, :, :3].astype(np.float32) * (1.0 - cover) + colour * cover,
                                0, 255).astype(np.uint8)
    if ao_img is not None:
        ao = _channel_r(ao_img, arr.shape[1], arr.shape[0]).astype(np.float32) / 255.0
        arr[:, :, :3] = (arr[:, :, :3].astype(np.float32) * (0.4 + 0.6 * ao[:, :, None])).astype(np.uint8)

    surface = None
    if normal is not None or rough_img is not None or metal_img is not None:
        sw, sh = (w, h) if base is not None else (reference.width(), reference.height())
        packed = np.empty((sh, sw, 4), dtype=np.uint8)
        packed[:, :, 0] = 128
        packed[:, :, 1] = 128
        packed[:, :, 2] = 255
        packed[:, :, 3] = 255
        if normal is not None:
            packed[:, :, 0:2] = _to_array(_resized(normal, sw, sh))[:, :, 0:2]
        if rough_img is not None:
            packed[:, :, 2] = _channel_r(rough_img, sw, sh)
        if metal_img is not None:
            packed[:, :, 3] = _channel_r(metal_img, sw, sh)
        surface = _to_image(packed)

    return PreviewMaterial(
        albedo=_to_image(arr),
        surface=surface,
        roughness=min(1.0, max(0.0, _number(stage, "roughnessFactor", 1.0 if rough_img is not None else 0.7))),
        metallic=min(1.0, max(0.0, _number(stage, "metallicFactor", 1.0 if metal_img is not None else 0.0))),
        clearcoat=min(1.0, max(0.0, _number(stage, "clearCoatFactor", 0.0))),
        clearcoat_roughness=min(1.0, max(0.0, _number(stage, "clearCoatRoughnessFactor", 0.0))),
    )


def build_surface_materials(defs: dict[str, dict], vfs, load: Callable[[str], Optional[QImage]],
                            paint: Optional[tuple] = None) -> dict[str, PreviewMaterial]:
    out: dict[str, PreviewMaterial] = {}
    for key, definition in defs.items():
        try:
            material = build_surface_material(definition["stage"], vfs.extract, load, paint)
        except Exception as e:
            print(f"[WARNING] model_preview.material: {definition.get('name')}: {type(e).__name__}: {e}")
            continue
        if material is not None:
            out[key] = material
    return out
