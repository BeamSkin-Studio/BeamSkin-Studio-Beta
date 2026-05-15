"""
mod_scanner.py — Auto-discover BeamNG vehicles/variants from a mod zip or folder.

Discovery rules
---------------
- Walks the mod looking for a ``vehicles/`` directory (up to 3 levels deep).
- Skips the ``common`` sub-folder (shared assets, no vehicle data).
- For each remaining sub-folder (= carid) it looks for:
    • A *skin materials* JSON  — skin.materials.json  >  *.materials.json with
      "skin" in name  >  main.materials.json  >  any *.materials.json
    • A *skin JBEAM*           — file whose content contains "paint_design"
      (the BeamNG slot type for skin parts).  Falls back to name heuristics.
    • A *preview image*        — default.jpg / any first .jpg found.
    • A *display name*         — info.json "Name" field, else prettified carid.
- Folders where neither JSON nor JBEAM was found are skipped entirely (likely
  pure texture / skin-overlay mods, not structural vehicle definitions).
- For ZIP inputs the archive is extracted to a temp directory; callers must
  clean it up after they are done with the paths.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DiscoveredVehicle:
    """One vehicle found inside a mod."""
    carid:         str
    display_name:  str
    json_path:     Optional[str]   # skin materials JSON
    jbeam_path:    Optional[str]   # skin JBEAM
    image_path:    Optional[str]   # preview image (optional)
    uv_map_paths:  List[str] = field(default_factory=list)  # UV layout images
    from_zip:      bool = False
    temp_dir:      Optional[str] = None  # extraction root (shared across results)
    warnings:      List[str] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        """True when both required files are present."""
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
    """A body variant found inside a mod (adds to an existing vehicle)."""
    carid:        str           # existing vehicle this variant belongs to
    suffix:       str           # variant suffix  e.g. "ambulance"
    display_name: str           # human-readable  e.g. "Ambulance"
    json_path:    Optional[str]
    jbeam_path:   Optional[str]
    image_path:   Optional[str]
    uv_map_paths: List[str] = field(default_factory=list)  # UV layout images
    from_zip:     bool = False
    temp_dir:     Optional[str] = None
    warnings:     List[str] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return bool(self.json_path and self.jbeam_path)

    @property
    def folder_preview(self) -> str:
        return f"vehicles/{self.carid}/SKINNAME_{self.suffix}/"


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

ScanResult = Tuple[List[DiscoveredVehicle], List[DiscoveredVariant], Optional[str]]


def scan_mod(path: str, known_carids: Optional[set] = None) -> ScanResult:
    """
    Scan a BeamNG mod (zip file or folder) for vehicles and variants.

    Parameters
    ----------
    path          : Absolute path to a .zip file or a directory.
    known_carids  : Set of vehicle IDs already known to the app.
                    Vehicles whose carid is in this set are classified as
                    *variants* (the mod adds something new to a known vehicle).
                    Pass ``None`` to skip variant detection entirely.

    Returns
    -------
    (vehicles, variants, temp_dir)
      temp_dir is set only for zip inputs and **must be deleted** by the caller
      once it is done with the file paths inside it.
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


# ─────────────────────────────────────────────────────────────────────────────
# ZIP handling
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# Folder walking
# ─────────────────────────────────────────────────────────────────────────────

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
            # This mod extends a vehicle we already know → look for new variants
            found_variants = _scan_for_variants(carid, car_dir)
            variants.extend(found_variants)
        else:
            v = _scan_vehicle_dir(carid, car_dir)
            if v is not None:
                vehicles.append(v)

    return vehicles, variants


def _find_vehicles_dir(root: str) -> Optional[str]:
    """
    Locate the ``vehicles/`` directory inside a mod root.

    BeamNG mod layouts vary:
      mods/{name}/vehicles/{carid}/
      mods/unpacked/{name}/vehicles/{carid}/
      mods/repo/{name}.zip → extracted → vehicles/{carid}/
    We search up to 3 directory levels deep.
    """
    for dirpath, dirnames, _ in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        depth = 0 if rel == "." else len(rel.split(os.sep))
        if depth > 3:
            dirnames.clear()   # prune walk
            continue
        if os.path.basename(dirpath).lower() == "vehicles":
            return dirpath
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Vehicle detection
# ─────────────────────────────────────────────────────────────────────────────

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

    # Skip folders with no structural files — likely skin/texture-only mods.
    if not json_path and not jbeam_path:
        return None

    return DiscoveredVehicle(
        carid         = carid,
        display_name  = display,
        json_path     = json_path,
        jbeam_path    = jbeam_path,
        image_path    = image_path,
        uv_map_paths  = uv_map_paths,
        warnings      = warnings,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Variant detection
# ─────────────────────────────────────────────────────────────────────────────

def _scan_for_variants(carid: str, car_dir: str) -> List[DiscoveredVariant]:
    """
    Look for variant-specific jbeams / materials inside an existing vehicle's
    mod folder.  A variant is identified by a jbeam whose filename matches
    ``{carid}_{suffix}.jbeam`` (e.g. ``muscle_ambulance.jbeam``) and that
    contains ``paint_design`` slot entries, OR by a matching materials JSON.
    """
    results: List[DiscoveredVariant] = []

    try:
        files = os.listdir(car_dir)
    except OSError:
        return results

    # Group files by potential suffix
    jbeam_by_suffix: dict[str, str] = {}
    json_by_suffix:  dict[str, str] = {}

    for f in files:
        lower = f.lower()

        # Candidate variant jbeam: {carid}_{suffix}.jbeam
        if lower.endswith(".jbeam") and lower.startswith(f"{carid}_"):
            suffix = f[len(carid) + 1 : -6]   # strip prefix and .jbeam
            # Only keep if it actually has paint_design content
            fpath = os.path.join(car_dir, f)
            if _jbeam_is_skin(fpath):
                jbeam_by_suffix[suffix] = fpath

        # Candidate variant json: *_{suffix}.materials.json
        if lower.endswith(".materials.json"):
            # Try to infer suffix from the filename
            stem = f[: -len(".materials.json")]
            if "_" in stem:
                suffix = stem.rsplit("_", 1)[-1]
                json_by_suffix[suffix] = os.path.join(car_dir, f)

    # Merge by suffix
    all_suffixes = set(jbeam_by_suffix) | set(json_by_suffix)
    # Exclude trivially bad suffixes (single letters, "main", etc.)
    skip = {"main", "body", "base", "skin", "skins", "a", "b", "c"}
    uv_maps = _find_uv_maps(car_dir)   # shared across all variants in this folder
    for suffix in sorted(all_suffixes):
        if suffix in skip or len(suffix) < 2:
            continue
        jbeam = jbeam_by_suffix.get(suffix)
        json_ = json_by_suffix.get(suffix)
        img   = _find_preview_image(car_dir)
        results.append(DiscoveredVariant(
            carid        = carid,
            suffix       = suffix,
            display_name = suffix.replace("_", " ").title(),
            json_path    = json_,
            jbeam_path   = jbeam,
            image_path   = img,
            uv_map_paths = uv_maps,
        ))

    return results


# ─────────────────────────────────────────────────────────────────────────────
# File finders
# ─────────────────────────────────────────────────────────────────────────────

def _list_vehicle_files(car_dir: str, suffix: str) -> List[str]:
    """Return all files ending with *suffix* found in car_dir and its immediate
    sub-directories.

    BeamNG mods use two common layouts:

    Flat  :  vehicles/{carid}/skin.materials.json
             vehicles/{carid}/ccf_skins.jbeam

    Nested:  vehicles/{carid}/materials/skin.materials.json
             vehicles/{carid}/jbeams/ccf_skins.jbeam

    Walking one level deep covers both without going too deep into unrelated
    asset trees (textures/, skins/, lua/, art/, …).
    Files are yielded root-first so that flat-layout hits rank above nested
    ones, which preserves the priority of simpler mods.
    """
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
    """Return True if the JSON file defines skin/livery materials.

    A skin materials file is identified by having at least one top-level key
    whose name contains ``.skin.`` (e.g. ``sprinfox20_paint.skin.furbbt``)
    or whose name ends with ``_skin`` / starts with ``skin_``.

    This distinguishes the real livery files (``skins/furbbt/skin.materials.json``)
    from base-material files (``txt/main.materials.json``,
    ``txt/glass/main.materials.json``) that also live inside the vehicle folder.

    We only read the first 4 KB — enough to see several key names — so this
    stays fast even on large files.
    """
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            chunk = f.read(4096)
        # Look for quoted keys that look like  "something.skin.something"  or
        # match the simpler  "skin.something" / "something_skin"  patterns.
        # A plain regex on the raw text (before full parse) is intentional:
        # skin.materials.json files use JBEAM-style // comments so strict
        # JSON parsing would fail.
        import re as _re
        return bool(_re.search(r'"[^"]*\.skin\.[^"]*"', chunk))
    except OSError:
        return False


def _find_skin_jsons_in_skins_dir(car_dir: str) -> List[str]:
    """Walk the ``skins/`` sub-directory (if present) recursively and collect
    all ``skin.materials.json`` files found there.

    Mods like ``mb_sprinter_2020_fox`` nest their skin JSONs two levels deep::

        vehicles/sprinfox20_fox/skins/furbbt/skin.materials.json
        vehicles/sprinfox20_fox/skins/lftl/skin.materials.json
        …

    The standard ``_list_vehicle_files`` only goes ONE level deep from
    ``car_dir``, so it never reaches these files.  This helper targets the
    ``skins/`` sub-tree specifically.
    """
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
    """Find the best skin materials JSON in a vehicle directory (flat or nested).

    Priority order
    --------------
    1.  ``skins/*/skin.materials.json`` files found by recursive walk —
        validated with :func:`_json_is_skin_materials`.  This handles mods
        like ``mb_sprinter_2020_fox`` where the real livery JSONs are nested
        two levels deep under a ``skins/`` sub-directory.
    2.  Named candidates in ``car_dir`` itself or a ``materials/`` sub-folder
        (flat/CCF-style layout) — also validated when possible.
    3.  Any ``*.materials.json`` one level deep whose name contains ``skin``
        and that passes the content check.
    4.  Any ``*.materials.json`` one level deep that passes the content check.
    5.  ``main.materials.json`` as a last resort (no content check) — this is
        intentionally last because ``main.materials.json`` most often defines
        *base* materials (paint, glass, chrome) rather than livery skins.
    """
    # ── 1. Recursive skins/ sub-directory ────────────────────────────────────
    skins_jsons = _find_skin_jsons_in_skins_dir(car_dir)
    # Prefer files literally named skin.materials.json, then any validated one
    for p in skins_jsons:
        if os.path.basename(p).lower() == "skin.materials.json" and _json_is_skin_materials(p):
            return p
    for p in skins_jsons:
        if _json_is_skin_materials(p):
            return p
    # Fallback: any file in skins/ even without validation (rare edge case)
    if skins_jsons:
        return skins_jsons[0]

    # ── 2. Named candidates in car_dir / materials/ (flat layout) ────────────
    named_candidates = [
        "skin.materials.json",
        f"{carid}_skin.materials.json",
        f"{carid}.skin.materials.json",
        f"{carid}.materials.json",
    ]
    search_roots = [car_dir, os.path.join(car_dir, "materials")]
    for root in search_roots:
        for name in named_candidates:
            p = os.path.join(root, name)
            if os.path.isfile(p):
                return p

    # ── 3–4. Walk one level deep, content-validated ──────────────────────────
    all_json = _list_vehicle_files(car_dir, ".materials.json")

    # Exclude main.materials.json from the validated pass — save it for last.
    non_main = [p for p in all_json if os.path.basename(p).lower() != "main.materials.json"]

    for p in non_main:
        if "skin" in os.path.basename(p).lower() and _json_is_skin_materials(p):
            return p
    for p in non_main:
        if _json_is_skin_materials(p):
            return p

    # ── 5. Last resort: main.materials.json (no content check) ───────────────
    for p in all_json:
        if os.path.basename(p).lower() == "main.materials.json":
            return p
    if all_json:
        return all_json[0]

    return None


def _find_skin_jbeam(car_dir: str, carid: str) -> Optional[str]:
    """Find the best skin JBEAM in a vehicle directory (flat or nested)."""
    # Named candidates — checked in car_dir itself AND in a 'jbeams' sub-folder
    # (common in complex mods such as CCF).
    candidates = [
        f"{carid}_skins.jbeam",
        f"{carid}_skin.jbeam",
        f"{carid}_skintones.jbeam",
        f"{carid}_paintdesigns.jbeam",
        "main.jbeam",
        f"{carid}.jbeam",
    ]
    search_roots = [car_dir, os.path.join(car_dir, "jbeams")]
    for root in search_roots:
        for name in candidates:
            p = os.path.join(root, name)
            if os.path.isfile(p) and _jbeam_is_skin(p):
                return p

    # Fallback: walk the full vehicle tree (one level deep)
    all_jbeam = _list_vehicle_files(car_dir, ".jbeam")

    # Any jbeam with "skin" in name that has paint_design content
    for p in all_jbeam:
        if "skin" in os.path.basename(p).lower() and _jbeam_is_skin(p):
            return p

    # Any jbeam with paint_design content
    for p in all_jbeam:
        if _jbeam_is_skin(p):
            return p

    # Last resort: first jbeam found (no content check)
    if all_jbeam:
        return all_jbeam[0]

    return None


def _jbeam_is_skin(path: str) -> bool:
    """Return True if the jbeam file contains paint_design slot entries."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(8192)   # read first 8 KB only (fast)
        return "paint_design" in content
    except OSError:
        return False


_UV_KEYWORDS = ("uv", "uvmap", "uv_map", "uv_layout", "uv1_layout")
_UV_EXTS     = (".dds", ".png", ".jpg", ".jpeg", ".pdn")

# BeamNG uses double-extension names for typed textures: name.color.dds,
# name.data.dds, name.normal.dds, etc.  These are skin/livery textures, not
# UV layout guides — reject anything whose stem ends with one of these.
# Older BeamNG mods use a single-letter underscore suffix instead of the
# dot-style double extension (e.g. name_d.dds, name_n.dds).  Drive-side
# mirror variants (_rhd / _lhd) are duplicated textures, not UV templates.
_UV_TYPE_QUALIFIERS = (
    # dot-style double-extension qualifiers (PBR pipeline)
    ".color", ".colour", ".data", ".normal", ".nrm",
    ".metallic", ".roughness", ".alpha", ".ao",
    # underscore single-letter legacy BeamNG texture-type suffixes
    "_d",    # diffuse / albedo
    "_n",    # normal map
    "_s",    # specular
    "_f",    # emissive / illumination
    # underscore descriptive suffixes that indicate non-UV content
    "_rhd",  # right-hand-drive mirror variant
    "_lhd",  # left-hand-drive mirror variant
)

# Substrings that, when found *anywhere* in the stem, identify the file as a
# functional / operational texture rather than a UV layout guide.
# These catch names like fullsuv_headlight_f.dds, fullsuv_climatescreens.png,
# fullsuv_entertainmentscreen.png and fullsuv_square_texgrid.jpg which all
# contain "uv" (embedded in the vehicle prefix "fullsuv") but are not maps.
_UV_FUNC_KEYWORDS = (
    "headlight", "foglight", "taillight", "brakelight", "turnlight",
    "reverselight", "interiorlight",
    "climatescreens", "entertainmentscreen", "screen", "display",
    "texgrid", "checkerboard",
    "temporarymesh",
)

# Simple UV layout templates have short, human-readable names (e.g.
# "muscle_UV", "picnic_skin_UV").  Livery textures have many underscore
# segments that encode the vehicle, skin set and variant
# (e.g. "ccf_cup_skin_blank_palette_uv1").  Reject names with 4 or more
# underscore-separated parts.
_UV_MAX_UNDERSCORES = 3


def _find_uv_maps(car_dir: str) -> List[str]:
    """Return paths of UV-layout template images found anywhere inside a
    vehicle directory.

    A file qualifies as a UV layout map when ALL conditions hold:

    1.  Extension is one of the supported image types
        (.dds, .png, .jpg, .jpeg).
    2.  The stem (filename minus extension) contains a UV keyword
        (uv, uvmap, uv_map, uv_layout, uv1_layout).
    3.  The stem does **not** end with a BeamNG texture-type qualifier
        (.color, .data, .normal, …) — catches double-extension names like
        ``ccf_wrap_palette_uv1.color.dds`` that are livery colour maps.
        Also rejects underscore-style legacy suffixes (_d, _n, _s, _f) and
        drive-side variants (_rhd, _lhd).
    3b. The stem does **not** contain a functional-texture keyword
        (headlight, screen, texgrid, temporarymesh, …).  This blocks files
        where "uv" appears only as part of the vehicle-name prefix
        (e.g. ``fullsuv_headlight_f.dds``) rather than as a layout marker.
    4.  The stem has at most ``_UV_MAX_UNDERSCORES`` underscores — simple
        template names like ``muscle_UV`` (1) or ``picnic_skin_UV`` (2)
        pass; long livery names like ``ccf_cup_skin_blank_palette_uv1``
        (5 underscores) are rejected.

    All sub-directories within *car_dir* are searched recursively so that
    mods which nest assets under ``art/``, ``textures/``, ``skins/``, etc.
    are handled correctly.
    """
    results: List[str] = []
    seen: set = set()

    for dirpath, _dirs, filenames in os.walk(car_dir):
        for fn in sorted(filenames):
            lower = fn.lower()

            # 1. Extension check
            if not any(lower.endswith(ext) for ext in _UV_EXTS):
                continue

            # Split off the real extension to get the stem.
            # For "name.color.dds"  → stem = "name.color"
            # For "muscle_UV.png"   → stem = "muscle_uv"
            stem = os.path.splitext(lower)[0]

            # 2. UV keyword check
            if not any(kw in stem for kw in _UV_KEYWORDS):
                continue

            # 3. Texture-type qualifier check
            # Reject if the stem itself ends with a qualifier OR contains one
            # as an embedded "sub-extension" (e.g. "…palette_uv1.color").
            if any(stem.endswith(q) or (q + ".") in stem
                   for q in _UV_TYPE_QUALIFIERS):
                continue

            # 3b. Functional-texture keyword check
            # Reject stems that contain a keyword indicating this is an
            # operational texture (headlight emission, screen overlay, texture
            # grid, temporary mesh, …) rather than a UV layout template.
            # This catches cases where "uv" appears only in the vehicle-name
            # prefix (e.g. "fullsuv_headlight_f") and not as a layout marker.
            if any(kw in stem for kw in _UV_FUNC_KEYWORDS):
                continue

            # 4. Complexity / segment-count check
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
    """Remove // single-line comments and trailing commas from JBEAM-style JSON.

    BeamNG's info.json files are parsed by BeamNG's own lenient JBEAM reader,
    which accepts both // comments and trailing commas before } or ].
    Standard Python json.loads() rejects both, so we strip them here.

    Comment removal uses a negative lookbehind so that :// inside URL strings
    is preserved.  Trailing-comma removal handles cases like:

        "Gold": { ... },   ← last entry in an object/array
        }
    """
    # 1. Strip // comments
    text = re.sub(r'(?<!:)//[^\n]*', '', text)
    # 2. Strip trailing commas before a closing } or ]
    text = re.sub(r',(\s*[}\]])', r'\1', text)
    return text


def _read_display_name(car_dir: str, carid: str) -> str:
    """Try to read a human-readable name from info.json, else prettify carid.

    Prefers "Brand Name" (e.g. "Hirochi CCF") when both fields are present.
    Handles JBEAM-style // comments that make info.json invalid standard JSON.
    Falls back to whichever single field exists, then to a prettified carid.
    """
    # Search car_dir directly, then one level up (handles zips that extract with
    # an extra nesting layer).  Also do a case-insensitive match for Linux.
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
            print(f"[mod_scanner] Failed to read display name from {p}: {type(e).__name__}: {e}")
    else:
        print(f"[mod_scanner] No info.json found in {car_dir!r}")

    return carid.replace("_", " ").title()
