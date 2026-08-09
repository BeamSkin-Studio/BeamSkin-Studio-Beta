from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

try:
    from core.localization import t as _t
except Exception as _loc_e:
    print(f"[WARNING] mod_scanner: core.localization unavailable "
          f"({type(_loc_e).__name__}: {_loc_e}), using key fallback")
    def _t(key: str, **kw) -> str: return key


@dataclass
class DiscoveredVehicle:
    carid:         str
    display_name:  str
    json_path:     Optional[str]
    jbeam_path:    Optional[str]
    image_path:    Optional[str]
    uv_map_paths:  List[str] = field(default_factory=list)
    from_zip:      bool = False
    temp_dir:      Optional[str] = None
    warnings:      List[str] = field(default_factory=list)
    info_json_path: Optional[str] = None

    @property
    def ready(self) -> bool:
        return bool(self.json_path and self.jbeam_path)

    @property
    def status_text(self) -> str:
        parts = []
        parts.append("✓ JSON"  if self.json_path  else "✗ JSON")
        parts.append("✓ JBEAM" if self.jbeam_path else "✗ JBEAM")
        parts.append("✓ IMG"   if self.image_path else "— IMG")
        return "  ".join(parts)


@dataclass
class DiscoveredVariant:
    carid:        str
    suffix:       str
    display_name: str
    json_path:    Optional[str]
    jbeam_path:   Optional[str]
    image_path:   Optional[str]
    uv_map_paths: List[str] = field(default_factory=list)
    from_zip:     bool = False
    temp_dir:     Optional[str] = None
    warnings:     List[str] = field(default_factory=list)
    info_json_path: Optional[str] = None

    @property
    def ready(self) -> bool:
        return bool(self.json_path and self.jbeam_path)

    @property
    def folder_preview(self) -> str:
        return f"vehicles/{self.carid}/SKINNAME_{self.suffix}/"


ScanResult = Tuple[List[DiscoveredVehicle], List[DiscoveredVariant], Optional[str]]

ScanResultWithReason = Tuple[
    List[DiscoveredVehicle], List[DiscoveredVariant], Optional[str], Optional[str]
]


def scan_mod(path: str, known_carids: Optional[set] = None) -> ScanResultWithReason:
    print(f"[mod_scanner] scan_mod: path={path!r} known_carids={len(known_carids) if known_carids else 0}")

    if not os.path.exists(path):
        print(f"[mod_scanner] scan_mod: path does not exist: {path!r}")
        return [], [], None, _t("mod_scanner.path_not_exist")

    if os.path.isfile(path):
        if zipfile.is_zipfile(path):
            return _scan_zip(path, known_carids)
        print(f"[mod_scanner] scan_mod: file is not a zip: {path!r}")
        return [], [], None, _t("mod_scanner.not_a_zip")

    if os.path.isdir(path):
        vehicles, variants, reason = _scan_folder(path, known_carids)
        print(f"[mod_scanner] scan_mod: folder scan of {path!r} -> "
              f"{len(vehicles)} vehicle(s), {len(variants)} variant(s), reason={reason!r}")
        return vehicles, variants, None, reason

    print(f"[mod_scanner] scan_mod: unrecognised path type for {path!r}")
    return [], [], None, _t("mod_scanner.unknown_path_type")


def scan_mod_for_multiselect(
    path: str,
    known_carids: Optional[set] = None,
) -> dict:
    print(f"[DEBUG] scan_mod_for_multiselect: path={path!r} "
          f"known_carids={len(known_carids) if known_carids else 0}")
    vehicles_raw, variants_raw, temp_dir, _reason = scan_mod(path, known_carids)
    print(f"[DEBUG] scan_mod_for_multiselect: scan_mod returned "
          f"{len(vehicles_raw)} vehicle(s), {len(variants_raw)} variant(s), "
          f"temp_dir={temp_dir!r} reason={_reason!r}")

    vehicles_out: List[dict] = []
    variants_out: List[dict] = []

    for v in vehicles_raw:
        vehicles_out.append({
            "key":          f"vehicle::{v.carid}",
            "type":         "vehicle",
            "carid":        v.carid,
            "display_name": v.display_name,
            "json_path":    v.json_path,
            "jbeam_path":   v.jbeam_path,
            "image_path":   v.image_path,
            "uv_map_paths": v.uv_map_paths,
            "ready":        v.ready,
            "warnings":     v.warnings,
            "from_zip":     v.from_zip,
            "temp_dir":     v.temp_dir,
            "info_json_path": v.info_json_path,
        })

    for var in variants_raw:
        variants_out.append({
            "key":          f"variant::{var.carid}::{var.suffix}",
            "type":         "variant",
            "carid":        var.carid,
            "suffix":       var.suffix,
            "display_name": var.display_name,
            "json_path":    var.json_path,
            "jbeam_path":   var.jbeam_path,
            "image_path":   var.image_path,
            "uv_map_paths": var.uv_map_paths,
            "ready":        var.ready,
            "warnings":     var.warnings,
            "from_zip":     var.from_zip,
            "temp_dir":     var.temp_dir,
            "info_json_path": var.info_json_path,
        })

    all_items   = vehicles_out + variants_out
    ready_count = sum(1 for item in all_items if item["ready"])
    print(f"[DEBUG] scan_mod_for_multiselect: total_count={len(all_items)} "
          f"ready_count={ready_count}")

    return {
        "vehicles":    vehicles_out,
        "variants":    variants_out,
        "temp_dir":    temp_dir,
        "ready_count": ready_count,
        "total_count": len(all_items),
    }


def _scan_zip(zip_path: str, known_carids: Optional[set]) -> "ScanResultWithReason":
    tmp = tempfile.mkdtemp(prefix="bss_scan_")
    print(f"[mod_scanner] _scan_zip: extracting {zip_path!r} -> {tmp!r}")
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(tmp)
    except Exception as e:
        print(f"[ERROR] mod_scanner: failed to extract ZIP {zip_path!r}: {type(e).__name__}: {e}")
        shutil.rmtree(tmp, ignore_errors=True)
        return [], [], None, _t("mod_scanner.extract_failed", error=str(e))

    vehicles, variants, reason = _scan_folder(tmp, known_carids)
    for v in vehicles:
        v.from_zip = True
        v.temp_dir = tmp
    for v in variants:
        v.from_zip = True
        v.temp_dir = tmp
    print(f"[mod_scanner] _scan_zip: {zip_path!r} -> "
          f"{len(vehicles)} vehicle(s), {len(variants)} variant(s), reason={reason!r}")
    return vehicles, variants, tmp, reason


def _scan_folder(
    root: str,
    known_carids: Optional[set],
) -> Tuple[List[DiscoveredVehicle], List[DiscoveredVariant], Optional[str]]:
    vehicles_dir = _find_vehicles_dir(root)
    if not vehicles_dir:
        print(f"[mod_scanner] _scan_folder: no vehicles/ directory found under {root!r}")
        return [], [], _t("mod_scanner.no_vehicles_dir")

    print(f"[mod_scanner] _scan_folder: vehicles dir = {vehicles_dir!r}")

    vehicles: List[DiscoveredVehicle] = []
    variants: List[DiscoveredVariant] = []

    try:
        entries = sorted(os.listdir(vehicles_dir))
    except OSError as e:
        print(f"[ERROR] mod_scanner: cannot list {vehicles_dir!r}: {type(e).__name__}: {e}")
        return [], [], _t("mod_scanner.cannot_read_dir")

    print(f"[mod_scanner] _scan_folder: {len(entries)} entries in vehicles dir: {entries}")

    _SKIP_EXACT    = {"common"}
    _SKIP_CONTAINS = {"traffic"}

    for carid in entries:
        lower = carid.lower()
        if lower in _SKIP_EXACT or any(kw in lower for kw in _SKIP_CONTAINS):
            print(f"[mod_scanner] _scan_folder: skipping {carid!r} (matched skip list)")
            continue
        car_dir = os.path.join(vehicles_dir, carid)
        if not os.path.isdir(car_dir):
            print(f"[mod_scanner] _scan_folder: skipping {carid!r} (not a directory: {car_dir!r})")
            continue

        is_known = known_carids is not None and carid in known_carids

        if is_known:
            found = _scan_for_variants(carid, car_dir)
            print(f"[mod_scanner] _scan_folder: {carid!r} is known -> "
                  f"{len(found)} variant(s) found")
            variants.extend(found)
        else:
            v = _scan_vehicle_dir(carid, car_dir)
            if v is not None:
                print(f"[mod_scanner] _scan_folder: {carid!r} -> vehicle discovered "
                      f"(json={bool(v.json_path)}, jbeam={bool(v.jbeam_path)}, warnings={v.warnings})")
                vehicles.append(v)
            else:
                print(f"[mod_scanner] _scan_folder: {carid!r} -> no usable JSON/JBEAM, skipped entirely")

    return vehicles, variants, None


def _find_vehicles_dir(root: str) -> Optional[str]:
    print(f"[DEBUG] _find_vehicles_dir: walking {root!r}")
    for dirpath, _dirnames, _ in os.walk(root):
        if os.path.basename(dirpath).lower() == "vehicles":
            print(f"[DEBUG] _find_vehicles_dir: found {dirpath!r}")
            return dirpath
    print(f"[DEBUG] _find_vehicles_dir: no vehicles dir under {root!r}")
    return None


def _scan_vehicle_dir(carid: str, car_dir: str) -> Optional[DiscoveredVehicle]:
    print(f"[DEBUG] _scan_vehicle_dir: carid={carid!r} car_dir={car_dir!r}")
    json_path    = _find_skin_json(car_dir, carid)
    jbeam_path   = _find_skin_jbeam(car_dir, carid)
    image_path   = _find_preview_image(car_dir)
    uv_map_paths = _find_uv_maps(car_dir)
    display      = _read_display_name(car_dir, carid)
    info_json_path = _find_info_json(car_dir)
    print(f"[DEBUG] _scan_vehicle_dir: {carid!r} json_path={json_path!r} "
          f"jbeam_path={jbeam_path!r} image_path={image_path!r} "
          f"uv_map_count={len(uv_map_paths)} display={display!r} "
          f"info_json_path={info_json_path!r}")

    warnings: List[str] = []
    if not json_path:
        warnings.append("No skin materials JSON found")
    if not jbeam_path:
        warnings.append("No skin JBEAM found")

    if not json_path and not jbeam_path:
        print(f"[DEBUG] _scan_vehicle_dir: {carid!r} has neither JSON nor JBEAM -> None")
        return None

    print(f"[DEBUG] _scan_vehicle_dir: {carid!r} warnings={warnings}")
    return DiscoveredVehicle(
        carid=carid, display_name=display,
        json_path=json_path, jbeam_path=jbeam_path,
        image_path=image_path, uv_map_paths=uv_map_paths,
        warnings=warnings, info_json_path=info_json_path,
    )


def _scan_for_variants(carid: str, car_dir: str) -> List[DiscoveredVariant]:
    print(f"[DEBUG] _scan_for_variants: carid={carid!r} car_dir={car_dir!r}")
    results: List[DiscoveredVariant] = []

    try:
        files = os.listdir(car_dir)
    except OSError as e:
        print(f"[DEBUG] _scan_for_variants: cannot list {car_dir!r}: {e}")
        return results

    print(f"[DEBUG] _scan_for_variants: {len(files)} file(s) in {car_dir!r}")

    jbeam_by_suffix: dict[str, str] = {}
    json_by_suffix:  dict[str, str] = {}

    for f in files:
        lower = f.lower()

        if lower.endswith(".jbeam") and lower.startswith(f"{carid}_"):
            suffix = f[len(carid) + 1 : -6]
            fpath = os.path.join(car_dir, f)
            if _jbeam_is_skin(fpath):
                jbeam_by_suffix[suffix] = fpath
                print(f"[DEBUG] _scan_for_variants: jbeam suffix={suffix!r} -> {fpath!r}")

        if lower.endswith(".materials.json"):
            stem = f[: -len(".materials.json")]
            if "_" in stem:
                suffix = stem.rsplit("_", 1)[-1]
                json_by_suffix[suffix] = os.path.join(car_dir, f)
                print(f"[DEBUG] _scan_for_variants: json suffix={suffix!r} -> {json_by_suffix[suffix]!r}")

    all_suffixes = set(jbeam_by_suffix) | set(json_by_suffix)
    skip = {"main", "body", "base", "skin", "skins", "a", "b", "c"}
    uv_maps = _find_uv_maps(car_dir)
    info_json_path = _find_info_json(car_dir)
    print(f"[DEBUG] _scan_for_variants: all_suffixes={sorted(all_suffixes)} "
          f"uv_map_count={len(uv_maps)} info_json_path={info_json_path!r}")

    for suffix in sorted(all_suffixes):
        if suffix in skip or len(suffix) < 2:
            print(f"[DEBUG] _scan_for_variants: skipping suffix {suffix!r} "
                  f"(in skip list or too short)")
            continue
        results.append(DiscoveredVariant(
            carid=carid, suffix=suffix,
            display_name=suffix.replace("_", " ").title(),
            json_path=json_by_suffix.get(suffix),
            jbeam_path=jbeam_by_suffix.get(suffix),
            image_path=_find_preview_image(car_dir),
            uv_map_paths=uv_maps,
            info_json_path=info_json_path,
        ))
        print(f"[DEBUG] _scan_for_variants: added variant suffix={suffix!r}")

    print(f"[DEBUG] _scan_for_variants: {carid!r} -> {len(results)} variant(s)")
    return results


def _list_vehicle_files(car_dir: str, suffix: str) -> List[str]:
    results: List[str] = []
    suffix_lower = suffix.lower()
    for dirpath, _dirs, filenames in os.walk(car_dir):
        for fn in sorted(filenames):
            if fn.lower().endswith(suffix_lower):
                results.append(os.path.join(dirpath, fn))
    print(f"[DEBUG] _list_vehicle_files: car_dir={car_dir!r} suffix={suffix!r} -> "
          f"{len(results)} file(s)")
    return results


def _json_is_skin_materials(path: str) -> bool:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            chunk = f.read(4096)
        import re as _re
        result = bool(_re.search(r'"[^"]*\.skin\.[^"]*"', chunk))
        print(f"[DEBUG] _json_is_skin_materials: {path!r} -> {result}")
        return result
    except OSError as e:
        print(f"[DEBUG] _json_is_skin_materials: OSError reading {path!r}: {e}")
        return False


def _find_skin_jsons_in_skins_dir(car_dir: str) -> List[str]:
    results: List[str] = []
    skins_dir = os.path.join(car_dir, "skins")
    if not os.path.isdir(skins_dir):
        print(f"[DEBUG] _find_skin_jsons_in_skins_dir: {skins_dir!r} does not exist")
        return results
    for dirpath, _dirs, filenames in os.walk(skins_dir):
        for fn in sorted(filenames):
            if fn.lower().endswith(".materials.json"):
                results.append(os.path.join(dirpath, fn))
    print(f"[DEBUG] _find_skin_jsons_in_skins_dir: {skins_dir!r} -> {len(results)} file(s)")
    return results


def _find_skin_json(car_dir: str, carid: str) -> Optional[str]:
    print(f"[DEBUG] _find_skin_json: car_dir={car_dir!r} carid={carid!r}")
    skins_jsons = _find_skin_jsons_in_skins_dir(car_dir)
    for p in skins_jsons:
        if os.path.basename(p).lower() == "skin.materials.json" and _json_is_skin_materials(p):
            print(f"[DEBUG] _find_skin_json: matched skin.materials.json -> {p!r}")
            return p
    for p in skins_jsons:
        if _json_is_skin_materials(p):
            print(f"[DEBUG] _find_skin_json: matched skins-dir skin materials -> {p!r}")
            return p
    if skins_jsons:
        print(f"[DEBUG] _find_skin_json: falling back to first skins-dir json -> {skins_jsons[0]!r}")
        return skins_jsons[0]

    named_candidates = [
        "skin.materials.json",
        f"{carid}_skin.materials.json",
        f"{carid}.skin.materials.json",
        f"{carid}.materials.json",
    ]
    for root in [car_dir, os.path.join(car_dir, "materials")]:
        for name in named_candidates:
            p = os.path.join(root, name)
            if os.path.isfile(p):
                print(f"[DEBUG] _find_skin_json: matched named candidate -> {p!r}")
                return p

    all_json = _list_vehicle_files(car_dir, ".materials.json")
    non_main = [p for p in all_json if os.path.basename(p).lower() != "main.materials.json"]
    print(f"[DEBUG] _find_skin_json: all_json={len(all_json)} non_main={len(non_main)}")

    for p in non_main:
        if "skin" in os.path.basename(p).lower() and _json_is_skin_materials(p):
            print(f"[DEBUG] _find_skin_json: matched non-main skin-named json -> {p!r}")
            return p
    for p in non_main:
        if _json_is_skin_materials(p):
            print(f"[DEBUG] _find_skin_json: matched non-main skin materials -> {p!r}")
            return p
    for p in all_json:
        if os.path.basename(p).lower() == "main.materials.json":
            print(f"[DEBUG] _find_skin_json: falling back to main.materials.json -> {p!r}")
            return p
    if all_json:
        print(f"[DEBUG] _find_skin_json: falling back to first all_json entry -> {all_json[0]!r}")
        return all_json[0]

    print(f"[DEBUG] _find_skin_json: no candidate found for {carid!r}")
    return None


def _find_skin_jbeam(car_dir: str, carid: str) -> Optional[str]:
    print(f"[DEBUG] _find_skin_jbeam: car_dir={car_dir!r} carid={carid!r}")
    candidates = [
        f"{carid}_skins.jbeam",
        f"{carid}_skin.jbeam",
        f"{carid}_skintones.jbeam",
        f"{carid}_paintdesigns.jbeam",
        "main.jbeam",
        f"{carid}.jbeam",
    ]
    for root in [car_dir, os.path.join(car_dir, "jbeams")]:
        for name in candidates:
            p = os.path.join(root, name)
            if os.path.isfile(p) and _jbeam_is_skin(p):
                print(f"[DEBUG] _find_skin_jbeam: matched named candidate -> {p!r}")
                return p

    all_jbeam = _list_vehicle_files(car_dir, ".jbeam")
    print(f"[DEBUG] _find_skin_jbeam: all_jbeam={len(all_jbeam)}")

    for p in all_jbeam:
        if "skin" in os.path.basename(p).lower() and _jbeam_is_skin(p):
            print(f"[DEBUG] _find_skin_jbeam: matched skin-named jbeam -> {p!r}")
            return p
    for p in all_jbeam:
        if _jbeam_is_skin(p):
            print(f"[DEBUG] _find_skin_jbeam: matched jbeam with paint_design -> {p!r}")
            return p
    if all_jbeam:
        print(f"[DEBUG] _find_skin_jbeam: falling back to first all_jbeam entry -> {all_jbeam[0]!r}")
        return all_jbeam[0]

    print(f"[DEBUG] _find_skin_jbeam: no candidate found for {carid!r}")
    return None


def _jbeam_is_skin(path: str) -> bool:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(8192)
        result = "paint_design" in content
        print(f"[DEBUG] _jbeam_is_skin: {path!r} -> {result}")
        return result
    except OSError as e:
        print(f"[DEBUG] _jbeam_is_skin: OSError reading {path!r}: {e}")
        return False


_UV_KEYWORDS = ("uv", "uvmap", "uv_map", "uv_layout", "uv1_layout")
_UV_EXTS     = (".dds", ".png", ".jpg", ".jpeg", ".pdn")

_UV_TYPE_QUALIFIERS = (
    ".color", ".colour", ".data", ".normal", ".nrm",
    ".metallic", ".roughness", ".alpha", ".ao",
    "_d", "_n", "_s", "_f",
    "_rhd", "_lhd",
)

_UV_FUNC_KEYWORDS = (
    "headlight", "foglight", "taillight", "brakelight", "turnlight",
    "reverselight", "interiorlight",
    "climatescreens", "entertainmentscreen", "screen", "display",
    "texgrid", "checkerboard",
    "temporarymesh",
)

_UV_MAX_UNDERSCORES = 3


def _find_uv_maps(car_dir: str) -> List[str]:
    print(f"[DEBUG] _find_uv_maps: walking {car_dir!r}")
    results: List[str] = []
    seen: set = set()

    for dirpath, _dirs, filenames in os.walk(car_dir):
        for fn in sorted(filenames):
            lower = fn.lower()

            if not any(lower.endswith(ext) for ext in _UV_EXTS):
                continue

            stem = os.path.splitext(lower)[0]

            if not any(kw in stem for kw in _UV_KEYWORDS):
                continue

            if any(stem.endswith(q) or (q + ".") in stem for q in _UV_TYPE_QUALIFIERS):
                continue

            if any(kw in stem for kw in _UV_FUNC_KEYWORDS):
                continue

            if stem.count("_") > _UV_MAX_UNDERSCORES:
                continue

            full_path = os.path.join(dirpath, fn)
            if full_path not in seen:
                seen.add(full_path)
                results.append(full_path)
                print(f"[DEBUG] _find_uv_maps: matched {full_path!r}")

    result = sorted(results)
    print(f"[DEBUG] _find_uv_maps: {car_dir!r} -> {len(result)} match(es)")
    return result


def _find_preview_image(car_dir: str) -> Optional[str]:
    for name in ("default.jpg", "default.jpeg", "default.png"):
        p = os.path.join(car_dir, name)
        if os.path.isfile(p):
            print(f"[DEBUG] _find_preview_image: matched default name -> {p!r}")
            return p
    try:
        for f in sorted(os.listdir(car_dir)):
            if f.lower().endswith((".jpg", ".jpeg")):
                p = os.path.join(car_dir, f)
                print(f"[DEBUG] _find_preview_image: falling back to first jpg -> {p!r}")
                return p
    except OSError as e:
        print(f"[DEBUG] _find_preview_image: OSError listing {car_dir!r}: {e}")
    print(f"[DEBUG] _find_preview_image: no preview image found in {car_dir!r}")
    return None


_INFO_JSON_RE = re.compile(r'^info_.+\.json$', re.IGNORECASE)


def _find_info_json(car_dir: str) -> Optional[str]:
    print(f"[DEBUG] _find_info_json: walking {car_dir!r}")
    candidates: List[str] = []
    for dirpath, _dirs, filenames in os.walk(car_dir):
        for fn in sorted(filenames):
            if _INFO_JSON_RE.match(fn):
                candidates.append(os.path.join(dirpath, fn))

    print(f"[DEBUG] _find_info_json: {len(candidates)} candidate(s): {candidates}")

    if not candidates:
        return None
    if len(candidates) == 1:
        print(f"[DEBUG] _find_info_json: only one candidate -> {candidates[0]!r}")
        return candidates[0]

    def load(path: str) -> Optional[dict]:
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                return json.loads(_strip_json_comments(f.read()))
        except Exception as e:
            print(f"[DEBUG] _find_info_json.load: could not parse {path!r}: {e}")
            return None

    parsed = {p: load(p) for p in candidates}

    standard = [
        p for p, data in parsed.items()
        if data is not None and not data.get("isAuxiliary") and "Power" in data
    ]
    pool = standard or candidates
    print(f"[DEBUG] _find_info_json: standard={standard} pool_size={len(pool)}")

    def score(path: str) -> Tuple[int, int]:
        data = parsed.get(path)
        if not data:
            return (0, 0)
        is_factory = str(data.get("Config Type", "")).lower() == "factory"
        try:
            population = int(data.get("Population", 0) or 0)
        except (TypeError, ValueError) as _exc:
            print(f"[WARNING] score: {type(_exc).__name__}: {_exc}")
            population = 0
        return (1 if is_factory else 0, population)

    chosen = max(pool, key=score)
    print(f"[DEBUG] _find_info_json: chosen -> {chosen!r} (score={score(chosen)})")
    return chosen


def _strip_json_comments(text: str) -> str:
    text = re.sub(r'(?<!:)//[^\n]*', '', text)
    text = re.sub(r',(\s*[}\]])', r'\1', text)
    text = re.sub(r'(["\d\w\]}])\s*\n(\s*")', r'\1,\n\2', text)
    return text


_BRAND_RE = re.compile(r'"[Bb]rand"\s*:\s*"([^"]*)"')
_NAME_RE  = re.compile(r'"[Nn]ame"\s*:\s*"([^"]*)"')


def _extract_brand_name_fallback(raw: str) -> Tuple[str, str]:
    brand_match = _BRAND_RE.search(raw)
    name_match  = _NAME_RE.search(raw)
    brand = brand_match.group(1).strip() if brand_match else ""
    name  = name_match.group(1).strip() if name_match else ""
    return brand, name


def _read_display_name(car_dir: str, carid: str) -> str:
    print(f"[DEBUG] _read_display_name: car_dir={car_dir!r} carid={carid!r}")
    candidates: List[str] = []
    try:
        for entry in os.scandir(car_dir):
            if entry.name.lower() == "info.json" and entry.is_file():
                candidates.append(entry.path)
    except OSError as e:
        print(f"[DEBUG] _read_display_name: OSError scanning {car_dir!r}: {e}")

    p = candidates[0] if candidates else ""
    print(f"[DEBUG] _read_display_name: candidates={candidates} using={p!r}")

    if p:
        raw = ""
        try:
            with open(p, "r", encoding="utf-8-sig") as f:
                raw = f.read()
            data  = json.loads(_strip_json_comments(raw))
            brand = (data.get("Brand") or data.get("brand") or "").strip()
            name  = (data.get("Name")  or data.get("name")  or "").strip()
            print(f"[DEBUG] _read_display_name: brand={brand!r} name={name!r}")
            if brand and name:
                result = f"{brand} {name}"
                print(f"[DEBUG] _read_display_name: -> {result!r}")
                return result
            if name:
                print(f"[DEBUG] _read_display_name: -> {name!r}")
                return name
            if brand:
                print(f"[DEBUG] _read_display_name: -> {brand!r}")
                return brand
        except Exception as e:
            print(f"[mod_scanner] Failed to parse info.json at {p}: {type(e).__name__}: {e}")
            if raw:
                brand, name = _extract_brand_name_fallback(raw)
                print(f"[DEBUG] _read_display_name: regex fallback brand={brand!r} name={name!r}")
                if brand and name:
                    result = f"{brand} {name}"
                    print(f"[DEBUG] _read_display_name: -> {result!r} (regex fallback)")
                    return result
                if name:
                    return name
                if brand:
                    return brand
    else:
        print(f"[mod_scanner] No info.json found in {car_dir!r}")

    fallback = carid.replace("_", " ").title()
    print(f"[DEBUG] _read_display_name: falling back to carid-derived name -> {fallback!r}")
    return fallback
