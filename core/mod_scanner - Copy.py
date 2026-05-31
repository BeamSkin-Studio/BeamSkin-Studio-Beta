from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


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

    @property
    def ready(self) -> bool:
        return bool(self.json_path and self.jbeam_path)

    @property
    def folder_preview(self) -> str:
        return f"vehicles/{self.carid}/SKINNAME_{self.suffix}/"


ScanResult = Tuple[List[DiscoveredVehicle], List[DiscoveredVariant], Optional[str]]


def scan_mod(path: str, known_carids: Optional[set] = None) -> ScanResult:
    """
    Scan a BeamNG mod (zip or folder) for vehicles and variants.
    Returns (vehicles, variants, temp_dir).
    temp_dir is set for zip inputs and must be deleted by the caller.
    """
    if not os.path.exists(path):
        return [], [], None

    if os.path.isfile(path):
        if zipfile.is_zipfile(path):
            return _scan_zip(path, known_carids)
        return [], [], None

    if os.path.isdir(path):
        vehicles, variants = _scan_folder(path, known_carids)
        return vehicles, variants, None

    return [], [], None


def scan_mod_for_multiselect(
    path: str,
    known_carids: Optional[set] = None,
) -> dict:
    """
    Scan a mod and return a dict ready for a multi-select UI.

    Each item in "vehicles" / "variants" has:
        key, type, carid, display_name, json_path, jbeam_path,
        image_path, uv_map_paths, ready, warnings, from_zip, temp_dir

    Caller must shutil.rmtree(result["temp_dir"]) when done if it's not None.
    """
    vehicles_raw, variants_raw, temp_dir = scan_mod(path, known_carids)

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
        })

    all_items   = vehicles_out + variants_out
    ready_count = sum(1 for item in all_items if item["ready"])

    return {
        "vehicles":    vehicles_out,
        "variants":    variants_out,
        "temp_dir":    temp_dir,
        "ready_count": ready_count,
        "total_count": len(all_items),
    }


def _scan_zip(zip_path: str, known_carids: Optional[set]) -> ScanResult:
    tmp = tempfile.mkdtemp(prefix="bss_scan_")
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(tmp)
    except Exception as e:
        print(f"[mod_scanner] Failed to extract ZIP: {e}")
        shutil.rmtree(tmp, ignore_errors=True)
        return [], [], None

    vehicles, variants = _scan_folder(tmp, known_carids)
    for v in vehicles:
        v.from_zip = True
        v.temp_dir = tmp
    for v in variants:
        v.from_zip = True
        v.temp_dir = tmp
    return vehicles, variants, tmp


def _scan_folder(
    root: str,
    known_carids: Optional[set],
) -> Tuple[List[DiscoveredVehicle], List[DiscoveredVariant]]:
    vehicles_dir = _find_vehicles_dir(root)
    if not vehicles_dir:
        return [], []

    vehicles: List[DiscoveredVehicle] = []
    variants: List[DiscoveredVariant] = []

    try:
        entries = sorted(os.listdir(vehicles_dir))
    except OSError:
        return [], []

    _SKIP_EXACT    = {"common"}
    _SKIP_CONTAINS = {"traffic"}

    for carid in entries:
        lower = carid.lower()
        if lower in _SKIP_EXACT or any(kw in lower for kw in _SKIP_CONTAINS):
            continue
        car_dir = os.path.join(vehicles_dir, carid)
        if not os.path.isdir(car_dir):
            continue

        is_known = known_carids is not None and carid in known_carids

        if is_known:
            variants.extend(_scan_for_variants(carid, car_dir))
        else:
            v = _scan_vehicle_dir(carid, car_dir)
            if v is not None:
                vehicles.append(v)

    return vehicles, variants


def _find_vehicles_dir(root: str) -> Optional[str]:
    """Search up to 3 levels deep for a vehicles/ directory."""
    for dirpath, dirnames, _ in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        depth = 0 if rel == "." else len(rel.split(os.sep))
        if depth > 3:
            dirnames.clear()
            continue
        if os.path.basename(dirpath).lower() == "vehicles":
            return dirpath
    return None


def _scan_vehicle_dir(carid: str, car_dir: str) -> Optional[DiscoveredVehicle]:
    json_path    = _find_skin_json(car_dir, carid)
    jbeam_path   = _find_skin_jbeam(car_dir, carid)
    image_path   = _find_preview_image(car_dir)
    uv_map_paths = _find_uv_maps(car_dir)
    display      = _read_display_name(car_dir, carid)

    warnings: List[str] = []
    if not json_path:
        warnings.append("No skin materials JSON found")
    if not jbeam_path:
        warnings.append("No skin JBEAM found")

    if not json_path and not jbeam_path:
        return None

    return DiscoveredVehicle(
        carid=carid, display_name=display,
        json_path=json_path, jbeam_path=jbeam_path,
        image_path=image_path, uv_map_paths=uv_map_paths,
        warnings=warnings,
    )


def _scan_for_variants(carid: str, car_dir: str) -> List[DiscoveredVariant]:
    """Find variant JBEAMs/JSONs matching {carid}_{suffix}.* patterns."""
    results: List[DiscoveredVariant] = []

    try:
        files = os.listdir(car_dir)
    except OSError:
        return results

    jbeam_by_suffix: dict[str, str] = {}
    json_by_suffix:  dict[str, str] = {}

    for f in files:
        lower = f.lower()

        if lower.endswith(".jbeam") and lower.startswith(f"{carid}_"):
            suffix = f[len(carid) + 1 : -6]
            fpath = os.path.join(car_dir, f)
            if _jbeam_is_skin(fpath):
                jbeam_by_suffix[suffix] = fpath

        if lower.endswith(".materials.json"):
            stem = f[: -len(".materials.json")]
            if "_" in stem:
                suffix = stem.rsplit("_", 1)[-1]
                json_by_suffix[suffix] = os.path.join(car_dir, f)

    all_suffixes = set(jbeam_by_suffix) | set(json_by_suffix)
    skip = {"main", "body", "base", "skin", "skins", "a", "b", "c"}
    uv_maps = _find_uv_maps(car_dir)

    for suffix in sorted(all_suffixes):
        if suffix in skip or len(suffix) < 2:
            continue
        results.append(DiscoveredVariant(
            carid=carid, suffix=suffix,
            display_name=suffix.replace("_", " ").title(),
            json_path=json_by_suffix.get(suffix),
            jbeam_path=jbeam_by_suffix.get(suffix),
            image_path=_find_preview_image(car_dir),
            uv_map_paths=uv_maps,
        ))

    return results


def _list_vehicle_files(car_dir: str, suffix: str) -> List[str]:
    """Return files matching suffix in car_dir and one level of subdirectories."""
    results: List[str] = []
    suffix_lower = suffix.lower()
    try:
        entries = sorted(os.scandir(car_dir), key=lambda e: e.name.lower())
    except OSError:
        return results

    subdirs: List[str] = []
    for e in entries:
        if e.is_file(follow_symlinks=False) and e.name.lower().endswith(suffix_lower):
            results.append(e.path)
        elif e.is_dir(follow_symlinks=False):
            subdirs.append(e.path)

    for sd in subdirs:
        try:
            for e in sorted(os.scandir(sd), key=lambda e: e.name.lower()):
                if e.is_file(follow_symlinks=False) and e.name.lower().endswith(suffix_lower):
                    results.append(e.path)
        except OSError:
            pass

    return results


def _json_is_skin_materials(path: str) -> bool:
    """Check first 4 KB for .skin. key patterns."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            chunk = f.read(4096)
        import re as _re
        return bool(_re.search(r'"[^"]*\.skin\.[^"]*"', chunk))
    except OSError:
        return False


def _find_skin_jsons_in_skins_dir(car_dir: str) -> List[str]:
    """Recursively collect *.materials.json files from vehicles/{carid}/skins/."""
    results: List[str] = []
    skins_dir = os.path.join(car_dir, "skins")
    if not os.path.isdir(skins_dir):
        return results
    for dirpath, _dirs, filenames in os.walk(skins_dir):
        for fn in sorted(filenames):
            if fn.lower().endswith(".materials.json"):
                results.append(os.path.join(dirpath, fn))
    return results


def _find_skin_json(car_dir: str, carid: str) -> Optional[str]:
    """
    Find the best skin materials JSON. Priority:
    1. skins/*/skin.materials.json (validated)
    2. Named candidates in car_dir / materials/
    3. Any *.materials.json with "skin" in name (validated)
    4. Any *.materials.json (validated)
    5. main.materials.json (last resort)
    """
    skins_jsons = _find_skin_jsons_in_skins_dir(car_dir)
    for p in skins_jsons:
        if os.path.basename(p).lower() == "skin.materials.json" and _json_is_skin_materials(p):
            return p
    for p in skins_jsons:
        if _json_is_skin_materials(p):
            return p
    if skins_jsons:
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
                return p

    all_json = _list_vehicle_files(car_dir, ".materials.json")
    non_main = [p for p in all_json if os.path.basename(p).lower() != "main.materials.json"]

    for p in non_main:
        if "skin" in os.path.basename(p).lower() and _json_is_skin_materials(p):
            return p
    for p in non_main:
        if _json_is_skin_materials(p):
            return p
    for p in all_json:
        if os.path.basename(p).lower() == "main.materials.json":
            return p
    if all_json:
        return all_json[0]

    return None


def _find_skin_jbeam(car_dir: str, carid: str) -> Optional[str]:
    """Find the best skin JBEAM. Checks named candidates, then walks the tree."""
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
                return p

    all_jbeam = _list_vehicle_files(car_dir, ".jbeam")

    for p in all_jbeam:
        if "skin" in os.path.basename(p).lower() and _jbeam_is_skin(p):
            return p
    for p in all_jbeam:
        if _jbeam_is_skin(p):
            return p
    if all_jbeam:
        return all_jbeam[0]

    return None


def _jbeam_is_skin(path: str) -> bool:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(8192)
        return "paint_design" in content
    except OSError:
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
    """Return UV layout template images, filtering out typed/functional textures."""
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

    return sorted(results)


def _find_preview_image(car_dir: str) -> Optional[str]:
    for name in ("default.jpg", "default.jpeg", "default.png"):
        p = os.path.join(car_dir, name)
        if os.path.isfile(p):
            return p
    try:
        for f in sorted(os.listdir(car_dir)):
            if f.lower().endswith((".jpg", ".jpeg")):
                return os.path.join(car_dir, f)
    except OSError:
        pass
    return None


def _strip_json_comments(text: str) -> str:
    """Strip // comments, trailing commas, and missing commas between entries."""
    text = re.sub(r'(?<!:)//[^\n]*', '', text)
    text = re.sub(r',(\s*[}\]])', r'\1', text)
    # Insert missing commas: value/closing-bracket on one line, quoted key on next
    text = re.sub(r'(["\d\w\]}])\s*\n(\s*")', r'\1,\n\2', text)
    return text


def _read_display_name(car_dir: str, carid: str) -> str:
    """Read display name from info.json (Brand + Name), or prettify carid."""
    candidates: List[str] = []
    try:
        for entry in os.scandir(car_dir):
            if entry.name.lower() == "info.json" and entry.is_file():
                candidates.append(entry.path)
    except OSError:
        pass

    p = candidates[0] if candidates else ""

    if p:
        try:
            with open(p, "r", encoding="utf-8-sig") as f:
                raw = f.read()
            data  = json.loads(_strip_json_comments(raw))
            brand = (data.get("Brand") or data.get("brand") or "").strip()
            name  = (data.get("Name")  or data.get("name")  or "").strip()
            if brand and name:
                return f"{brand} {name}"
            if name:
                return name
            if brand:
                return brand
        except Exception as e:
            print(f"[mod_scanner] Failed to parse info.json at {p}: {type(e).__name__}: {e}")
    else:
        print(f"[mod_scanner] No info.json found in {car_dir!r}")

    return carid.replace("_", " ").title()
