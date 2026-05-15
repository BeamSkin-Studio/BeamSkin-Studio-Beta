"""
core/colorable_ops.py
"""

import os
import shutil
import json
import re


# ─────────────────────────────────────────────────────────────────────────────
# SANITISERS
# ─────────────────────────────────────────────────────────────────────────────

def sanitize_skin_id(name: str) -> str:
    name = name.replace(" ", "")
    return re.sub(r"[^a-zA-Z0-9\-]", "", name)


def sanitize_folder_name(name: str) -> str:
    return name.replace(" ", "_")


# ─────────────────────────────────────────────────────────────────────────────
# TEXTURE COPYING
# ─────────────────────────────────────────────────────────────────────────────

def _copy_texture_files(data_map_source, color_map_source, dest_folder, skin_id):
    """Copy the two PNGs for a normal (single-body) colorable skin."""
    os.makedirs(dest_folder, exist_ok=True)

    data_map_fn  = f"{skin_id}_b.color.png"
    color_map_fn = f"{skin_id}_cp.color.png"

    for src, fn, label in [
        (data_map_source,  data_map_fn,  "data map"),
        (color_map_source, color_map_fn, "color map"),
    ]:
        if src and os.path.exists(src):
            shutil.copy2(src, os.path.join(dest_folder, fn))
            print(f"[DEBUG] Copied {label}: {src} -> {os.path.join(dest_folder, fn)}")
        else:
            print(f"[WARNING] {label} source not found: {src}")

    return data_map_fn, color_map_fn


def _copy_texture_files_variant(
    data_map_source,    color_map_source,
    data_map_source_2,  color_map_source_2,
    dest_folder, skin_id, variant_suffix,
):
    """
    Copy all four PNGs for a variant colorable skin into dest_folder.

    Naming convention
    -----------------
    Car body    : {skin_id}_b.color.png          / {skin_id}_cp.color.png
    Variant body: {skin_id}_{suffix}_b.color.png / {skin_id}_{suffix}_cp.color.png

    Returns (car_data_fn, car_palette_fn, var_data_fn, var_palette_fn).
    """
    os.makedirs(dest_folder, exist_ok=True)

    car_data_fn    = f"{skin_id}_b.color.png"
    car_palette_fn = f"{skin_id}_cp.color.png"
    var_data_fn    = f"{skin_id}_{variant_suffix}_b.color.png"
    var_palette_fn = f"{skin_id}_{variant_suffix}_cp.color.png"

    for src, fn, label in [
        (data_map_source,   car_data_fn,    "car body – data map"),
        (color_map_source,  car_palette_fn, "car body – palette map"),
        (data_map_source_2, var_data_fn,    f"{variant_suffix} body – data map"),
        (color_map_source_2,var_palette_fn, f"{variant_suffix} body – palette map"),
    ]:
        if src and os.path.exists(src):
            shutil.copy2(src, os.path.join(dest_folder, fn))
            print(f"[DEBUG] Copied {label}: {fn}")
        else:
            print(f"[WARNING] Source not found for {label}: {src}")

    return car_data_fn, car_palette_fn, var_data_fn, var_palette_fn


# ─────────────────────────────────────────────────────────────────────────────
# JBEAM PROCESSING
# ─────────────────────────────────────────────────────────────────────────────

def _process_jbeam_files(folder_path, vehicle_id, skin_id,
                          skin_name=None, author_name=None):
    for root_dir, _, files in os.walk(folder_path):
        for filename in files:
            if not filename.endswith(".jbeam"):
                continue

            file_path = os.path.join(root_dir, filename)
            with open(file_path, "r", encoding="utf-8") as fh:
                content = fh.read()

            def _val(m):  return f'"{m.group(1)}{skin_id}"'
            def _name(m): return f'{m.group(1)}{skin_id}"'

            content = re.sub(r'"([^"]+\.skin\.)[^"]+"',                     _val,  content)
            content = re.sub(r'"([^"]+\.skin_[^.]*\.)[^"]+"',               _val,  content)
            content = re.sub(r'("name"\s*:\s*"[^"]+\.skin\.)[^"]+"',        _name, content)
            content = re.sub(r'("mapTo"\s*:\s*"[^"]+\.skin\.)[^"]+"',       _name, content)
            content = re.sub(r'("name"\s*:\s*"[^"]+\.skin_[^.]*\.)[^"]+"',  _name, content)
            content = re.sub(r'("mapTo"\s*:\s*"[^"]+\.skin_[^.]*\.)[^"]+"', _name, content)
            content = re.sub(r'"([^"]*_extra\.skin\.)[^"]+"',                _val,  content)
            content = re.sub(r'("name"\s*:\s*"[^"]*_extra\.skin\.)[^"]+"',   _name, content)
            content = re.sub(r'("mapTo"\s*:\s*"[^"]*_extra\.skin\.)[^"]+"',  _name, content)
            content = re.sub(r'_skin_SKINNAME\w*', f'_skin_{skin_id}',
                             content, flags=re.IGNORECASE)
            content = re.sub(r'("globalSkin"\s*:\s*")SKINNAME\w*(")',
                             f'\\1{skin_id}\\2', content, flags=re.IGNORECASE)

            if skin_name:
                content = content.replace('"YOUR SKIN NAME"', f'"{skin_name}"')
            if author_name:
                content = re.sub(r'("authors"\s*:\s*)"YOU"', f'\\1"{author_name}"',
                                 content, flags=re.IGNORECASE)
            else:
                print(f"[WARNING] author_name not provided — 'YOU' left in {file_path}")

            if vehicle_id:
                content = re.sub(r'(?<![a-zA-Z0-9])carid', vehicle_id,
                                 content, flags=re.IGNORECASE)

            with open(file_path, "w", encoding="utf-8") as fh:
                fh.write(content)
            print(f"[DEBUG] Processed jbeam: {file_path}")


# ─────────────────────────────────────────────────────────────────────────────
# SHARED REGEX PASS (SKINNAME placeholders → skin_id)
# ─────────────────────────────────────────────────────────────────────────────

def _apply_skin_id_regexes(content: str, skin_id: str,
                             skin_folder_name: str, vehicle_id: str) -> str:
    def _val(m):  return f'"{m.group(1)}{skin_id}"'
    def _name(m): return f'{m.group(1)}{skin_id}"'

    content = re.sub(r'"([^"]+\.skin\.)[^"]+"',                     _val,  content)
    content = re.sub(r'"([^"]+\.skin_[^.]*\.)[^"]+"',               _val,  content)
    content = re.sub(r'("name"\s*:\s*"[^"]+\.skin\.)[^"]+"',        _name, content)
    content = re.sub(r'("mapTo"\s*:\s*"[^"]+\.skin\.)[^"]+"',       _name, content)
    content = re.sub(r'("name"\s*:\s*"[^"]+\.skin_[^.]*\.)[^"]+"',  _name, content)
    content = re.sub(r'("mapTo"\s*:\s*"[^"]+\.skin_[^.]*\.)[^"]+"', _name, content)
    content = re.sub(r'"([^"]*_extra\.skin\.)[^"]+"',                _val,  content)
    content = re.sub(r'("name"\s*:\s*"[^"]*_extra\.skin\.)[^"]+"',   _name, content)
    content = re.sub(r'("mapTo"\s*:\s*"[^"]*_extra\.skin\.)[^"]+"',  _name, content)
    content = re.sub(r'/SKINNAME/', f'/{skin_folder_name}/',
                     content, flags=re.IGNORECASE)
    content = re.sub(r'_skin_SKINNAME(\.[^"]+)', f'_skin_{skin_id}\\1',
                     content, flags=re.IGNORECASE)
    content = re.sub(r'(?<![a-zA-Z0-9])carid', vehicle_id,
                     content, flags=re.IGNORECASE)
    return content


# ─────────────────────────────────────────────────────────────────────────────
# JSON PROCESSING — NORMAL (single-body, 2 PNGs)
# ─────────────────────────────────────────────────────────────────────────────

def _process_json_files(
    folder_path, vehicle_id, skin_folder_name,
    data_map_filename, color_map_filename, skin_id,
):
    """
    Normal colorable skin: every material entry gets the same PNG pair.
    Stage 0 → baseColorMap = data map,  colorPaletteMapUseUV = null
    Stage 1 → baseColorMap = data map,  colorPaletteMap = palette map,
              colorPaletteMapUseUV = 1
    """
    data_path    = f"vehicles/{vehicle_id}/{skin_folder_name}/{data_map_filename}"
    palette_path = f"vehicles/{vehicle_id}/{skin_folder_name}/{color_map_filename}"

    for root_dir, _, files in os.walk(folder_path):
        for filename in files:
            if not filename.endswith(".json") or filename.startswith("info"):
                continue
            file_path = os.path.join(root_dir, filename)

            with open(file_path, "r", encoding="utf-8") as fh:
                raw = fh.read()
            raw_clean = re.sub(r',(\s*[}\]])', r'\1', raw)
            try:
                data = json.loads(raw_clean); parsed_ok = True
            except json.JSONDecodeError as exc:
                print(f"[WARNING] JSON parse failed {file_path}: {exc}"); parsed_ok = False

            if parsed_ok:
                for mat_data in data.values():
                    if not isinstance(mat_data, dict):
                        continue
                    stages = mat_data.get("Stages")
                    if not isinstance(stages, list):
                        continue
                    for idx in (0, 1):
                        if idx >= len(stages) or not isinstance(stages[idx], dict):
                            continue
                        stages[idx]["baseColorMap"] = data_path
                        if idx == 0:
                            stages[idx]["colorPaletteMapUseUV"] = None
                        else:
                            # diffuseMapUseUV is not a valid BeamNG property and causes the
                            # skin layer to never blend.  Remove it from any template that
                            # carries it before writing the output.
                            stages[idx].pop("diffuseMapUseUV", None)
                            stages[idx]["colorPaletteMap"]      = palette_path
                            stages[idx]["colorPaletteMapUseUV"] = 1
                content = json.dumps(data, indent=2)
            else:
                content = raw

            content = _apply_skin_id_regexes(content, skin_id, skin_folder_name, vehicle_id)
            with open(file_path, "w", encoding="utf-8") as fh:
                fh.write(content)
            print(f"[DEBUG] Processed json (normal): {file_path}")


# ─────────────────────────────────────────────────────────────────────────────
# JSON PROCESSING — VARIANT COLORABLE (4 PNGs, 2 material entries)
# ─────────────────────────────────────────────────────────────────────────────

def _process_json_files_variant(
    folder_path, vehicle_id, skin_folder_name,
    car_data_filename,   car_palette_filename,   # PNGs 1 & 2  → car body
    var_data_filename,   var_palette_filename,   # PNGs 3 & 4  → variant body
    skin_id,
):
    """
    Variant colorable skin: route each material entry to its own PNG pair.

    Routing rule
    ------------
    Material key starts with "{vehicle_id}.skin."  → car body   → PNGs 1 & 2
    Any other material key                          → variant body → PNGs 3 & 4

    This matches the materials.json structure, e.g.:
      pickup.skin.SKINNAMEAMBULANCE    → car body
      ambulance.skin.SKINNAMEAMBULANCE → ambulance body
    """
    car_data_path    = f"vehicles/{vehicle_id}/{skin_folder_name}/{car_data_filename}"
    car_palette_path = f"vehicles/{vehicle_id}/{skin_folder_name}/{car_palette_filename}"
    var_data_path    = f"vehicles/{vehicle_id}/{skin_folder_name}/{var_data_filename}"
    var_palette_path = f"vehicles/{vehicle_id}/{skin_folder_name}/{var_palette_filename}"

    var_prefix = f"{variant_suffix}.skin."  # e.g. "ambulance.skin."

    for root_dir, _, files in os.walk(folder_path):
        for filename in files:
            if not filename.endswith(".json") or filename.startswith("info"):
                continue
            file_path = os.path.join(root_dir, filename)
            print(f"[DEBUG] Processing variant json: {file_path}")

            with open(file_path, "r", encoding="utf-8") as fh:
                raw = fh.read()
            raw_clean = re.sub(r',(\s*[}\]])', r'\1', raw)
            try:
                data = json.loads(raw_clean); parsed_ok = True
            except json.JSONDecodeError as exc:
                print(f"[WARNING] JSON parse failed {file_path}: {exc}"); parsed_ok = False

            if parsed_ok:
                for mat_key, mat_data in data.items():
                    if not isinstance(mat_data, dict):
                        continue
                    stages = mat_data.get("Stages")
                    if not isinstance(stages, list):
                        continue

                    # Variant body = material whose key starts with "<variant_suffix>.skin."
                    # Car body = everything else (md_series_main.skin.*, pickup.skin.*, etc.)
                    is_var   = mat_key.lower().startswith(var_prefix.lower())
                    d_path   = var_data_path    if is_var else car_data_path
                    p_path   = var_palette_path if is_var else car_palette_path
                    label    = "variant body" if is_var else "car body"

                    print(f"[DEBUG]   '{mat_key}' → {label}")

                    for idx in (0, 1):
                        if idx >= len(stages) or not isinstance(stages[idx], dict):
                            continue
                        stages[idx]["baseColorMap"] = d_path
                        if idx == 0:
                            stages[idx]["colorPaletteMapUseUV"] = None
                            print(f"[DEBUG]     Stage 0 baseColorMap = {d_path}")
                        else:
                            # diffuseMapUseUV is not a valid BeamNG property — strip it.
                            stages[idx].pop("diffuseMapUseUV", None)
                            stages[idx]["colorPaletteMap"]      = p_path
                            stages[idx]["colorPaletteMapUseUV"] = 1
                            print(f"[DEBUG]     Stage 1 baseColorMap = {d_path}")
                            print(f"[DEBUG]     Stage 1 colorPaletteMap = {p_path}")

                content = json.dumps(data, indent=2)
            else:
                content = raw

            content = _apply_skin_id_regexes(content, skin_id, skin_folder_name, vehicle_id)
            with open(file_path, "w", encoding="utf-8") as fh:
                fh.write(content)
            print(f"[DEBUG] Processed json (variant-colorable): {file_path}")


# ─────────────────────────────────────────────────────────────────────────────
# MATERIAL PROPERTY OVERRIDES
# ─────────────────────────────────────────────────────────────────────────────

def _process_material_properties(folder_path, material_props, skin_id):
    if not material_props:
        return True
    print(f"[DEBUG] ===== _process_material_properties for {skin_id} =====")

    mat_files = []
    for root_dir, _, files in os.walk(folder_path):
        for fn in files:
            if fn.endswith(".materials.json") or fn == "materials.json":
                mat_files.append(os.path.join(root_dir, fn))

    if not mat_files:
        print(f"[WARNING] No .materials.json found in {folder_path}")
        return False

    try:
        for mat_file in mat_files:
            with open(mat_file, "r", encoding="utf-8") as fh:
                raw = fh.read()
            raw_clean = re.sub(r",(\s*[}\]])", r"\1", raw)
            try:
                mat_data = json.loads(raw_clean)
            except json.JSONDecodeError as exc:
                print(f"[ERROR] JSON decode error in {os.path.basename(mat_file)}: {exc}")
                continue

            modified = False
            for template_name, stages in material_props.items():
                prefix = (template_name.split(".skin.")[0]
                          if ".skin." in template_name else template_name)
                actual = next((k for k in mat_data if k.startswith(f"{prefix}.skin.")), None)
                if not actual or "Stages" not in mat_data[actual]:
                    continue
                for stage_str, props in stages.items():
                    try:
                        idx = int(stage_str)
                    except (ValueError, TypeError):
                        continue
                    if idx >= len(mat_data[actual]["Stages"]):
                        continue
                    for k, v in props.items():
                        mat_data[actual]["Stages"][idx][k] = v
                        modified = True
                        print(f"[DEBUG]   ✓ {actual}.Stages[{idx}].{k} = {v}")

            if modified:
                with open(mat_file, "w", encoding="utf-8") as fh:
                    json.dump(mat_data, fh, indent=2)

        print(f"[DEBUG] ===== _process_material_properties complete =====")
        return True

    except Exception as exc:
        import traceback
        print(f"[ERROR] _process_material_properties: {exc}")
        traceback.print_exc()
        return False


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def generate_colorable_skin(
    template_path,
    dest_skin_folder,
    vehicle_id,
    skin_name,
    skin_folder,
    data_map_source,
    color_map_source,
    author_name=None,
    material_properties=None,
):
    """
    Normal (single-body) colorable skin — 2 PNGs.

    Used for all vehicles with a plain SKINNAME template folder where
    every material entry shares the same texture pair.
    """
    skin_id = sanitize_skin_id(skin_name)
    print(f"[DEBUG] generate_colorable_skin: '{skin_name}' folder='{skin_folder}' id='{skin_id}'")

    shutil.copytree(
        template_path, dest_skin_folder,
        ignore=lambda d, f: [x for x in f if x.lower().endswith((".dds", ".png"))]
    )
    print(f"[DEBUG] Template copied to {dest_skin_folder}")

    dm_fn, cm_fn = _copy_texture_files(
        data_map_source, color_map_source, dest_skin_folder, skin_id
    )
    _process_jbeam_files(
        dest_skin_folder, vehicle_id, skin_id,
        skin_name=skin_name, author_name=author_name,
    )
    _process_json_files(
        dest_skin_folder, vehicle_id, skin_folder, dm_fn, cm_fn, skin_id,
    )
    if material_properties:
        if not _process_material_properties(dest_skin_folder, material_properties, skin_id):
            print(f"[WARNING] Material properties processing failed for {skin_folder}")

    print(f"[DEBUG] generate_colorable_skin complete: {skin_folder}")


def generate_colorable_skin_variant(
    template_path,
    dest_skin_folder,
    vehicle_id,
    variant_suffix,
    skin_name,
    skin_folder,
    data_map_source,
    color_map_source,
    data_map_source_2,
    color_map_source_2,
    author_name=None,
    material_properties=None,
):
    """
    Variant colorable skin — 4 PNGs, ONE template folder.

    template_path must point to the variant template folder, e.g.:
      vehicles/pickup/SKINNAMEAMBULANCE

    That folder's materials.json contains TWO entries:
      pickup.skin.SKINNAMEAMBULANCE    ← car body    ← PNGs 1 & 2
      ambulance.skin.SKINNAMEAMBULANCE ← variant body ← PNGs 3 & 4

    The car-body entry is identified by its key starting with
    "<vehicle_id>.skin."; the variant-body entry is everything else.
    """
    skin_id = sanitize_skin_id(skin_name)
    print(f"[DEBUG] generate_colorable_skin_variant: '{skin_name}' "
          f"({variant_suffix}) → 4 PNGs, single folder")

    shutil.copytree(
        template_path, dest_skin_folder,
        ignore=lambda d, f: [x for x in f if x.lower().endswith((".dds", ".png"))]
    )
    print(f"[DEBUG] Variant template copied to {dest_skin_folder}")

    car_dm, car_pm, var_dm, var_pm = _copy_texture_files_variant(
        data_map_source,    color_map_source,
        data_map_source_2,  color_map_source_2,
        dest_skin_folder, skin_id, variant_suffix,
    )
    _process_jbeam_files(
        dest_skin_folder, vehicle_id, skin_id,
        skin_name=skin_name, author_name=author_name,
    )
    _process_json_files_variant(
        dest_skin_folder, vehicle_id, skin_folder,
        car_dm, car_pm, var_dm, var_pm, skin_id,
    )
    if material_properties:
        if not _process_material_properties(dest_skin_folder, material_properties, skin_id):
            print(f"[WARNING] Material properties processing failed for {skin_folder}")

    print(f"[DEBUG] generate_colorable_skin_variant complete: {skin_folder}")
