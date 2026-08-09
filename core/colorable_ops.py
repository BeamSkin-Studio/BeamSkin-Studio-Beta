
import os
import shutil
import json
import re


_copied_file_cache: dict[str, dict[str, str]] = {}


def _copy_dedup(src: str, dest_folder: str, dest_filename: str) -> str:
    src_key = os.path.normcase(os.path.abspath(src))
    folder_cache = _copied_file_cache.setdefault(dest_folder, {})

    existing_fn = folder_cache.get(src_key)
    if existing_fn is not None:
        existing_path = os.path.join(dest_folder, existing_fn)
        if os.path.exists(existing_path):
            print(f"[DEBUG] Reusing already-copied file for {os.path.basename(src)}: "
                  f"{existing_fn} (skipped duplicate copy as {dest_filename})")
            return existing_fn

    shutil.copy2(src, os.path.join(dest_folder, dest_filename))
    folder_cache[src_key] = dest_filename
    print(f"[DEBUG] _copy_dedup: copied {src!r} -> {os.path.join(dest_folder, dest_filename)!r}")
    return dest_filename


def reset_copy_dedup_cache(dest_folder: str | None = None) -> None:
    print(f"[DEBUG] reset_copy_dedup_cache: dest_folder={dest_folder!r}")
    if dest_folder is None:
        _copied_file_cache.clear()
    else:
        _copied_file_cache.pop(dest_folder, None)


def sanitize_skin_id(name: str) -> str:
    name = name.replace(" ", "")
    result = re.sub(r"[^a-zA-Z0-9\-]", "", name)
    print(f"[DEBUG] sanitize_skin_id: -> {result!r}")
    return result


_ILLEGAL_WIN_CHARS = re.compile(r'[\\/:*?"<>|]')

def sanitize_folder_name(name: str) -> str:
    name = name.replace(" ", "_")
    name = _ILLEGAL_WIN_CHARS.sub("", name)
    name = re.sub(r"_+", "_", name)
    result = name.strip("_")
    print(f"[DEBUG] sanitize_folder_name: -> {result!r}")
    return result


def _copy_texture_files(data_map_source, color_map_source, dest_folder, skin_id):
    print(f"[DEBUG] _copy_texture_files: dest_folder={dest_folder!r} skin_id={skin_id!r}")
    os.makedirs(dest_folder, exist_ok=True)

    data_map_fn  = f"{skin_id}_b.color.png"
    color_map_fn = f"{skin_id}_cp.color.png"

    if data_map_source and os.path.exists(data_map_source):
        data_map_fn = _copy_dedup(data_map_source, dest_folder, data_map_fn)
        print(f"[DEBUG] Copied data map: {data_map_source} -> {os.path.join(dest_folder, data_map_fn)}")
    else:
        print(f"[WARNING] data map source not found: {data_map_source}")

    if color_map_source and os.path.exists(color_map_source):
        color_map_fn = _copy_dedup(color_map_source, dest_folder, color_map_fn)
        print(f"[DEBUG] Copied color map: {color_map_source} -> {os.path.join(dest_folder, color_map_fn)}")
    else:
        print(f"[WARNING] color map source not found: {color_map_source}")

    return data_map_fn, color_map_fn


def _copy_texture_files_variant(
    data_map_source,    color_map_source,
    data_map_source_2,  color_map_source_2,
    dest_folder, skin_id, variant_suffix,
):
    print(f"[DEBUG] _copy_texture_files_variant: dest_folder={dest_folder!r} skin_id={skin_id!r} "
          f"variant_suffix={variant_suffix!r}")
    os.makedirs(dest_folder, exist_ok=True)

    car_data_fn    = f"{skin_id}_b.color.png"
    car_palette_fn = f"{skin_id}_cp.color.png"
    var_data_fn    = f"{skin_id}_{variant_suffix}_b.color.png"
    var_palette_fn = f"{skin_id}_{variant_suffix}_cp.color.png"

    if data_map_source and os.path.exists(data_map_source):
        car_data_fn = _copy_dedup(data_map_source, dest_folder, car_data_fn)
        print(f"[DEBUG] Copied car body – data map: {car_data_fn}")
    else:
        print(f"[WARNING] Source not found for car body – data map: {data_map_source}")

    if color_map_source and os.path.exists(color_map_source):
        car_palette_fn = _copy_dedup(color_map_source, dest_folder, car_palette_fn)
        print(f"[DEBUG] Copied car body – palette map: {car_palette_fn}")
    else:
        print(f"[WARNING] Source not found for car body – palette map: {color_map_source}")

    if data_map_source_2 and os.path.exists(data_map_source_2):
        var_data_fn = _copy_dedup(data_map_source_2, dest_folder, var_data_fn)
        print(f"[DEBUG] Copied {variant_suffix} body – data map: {var_data_fn}")
    else:
        print(f"[WARNING] Source not found for {variant_suffix} body – data map: {data_map_source_2}")

    if color_map_source_2 and os.path.exists(color_map_source_2):
        var_palette_fn = _copy_dedup(color_map_source_2, dest_folder, var_palette_fn)
        print(f"[DEBUG] Copied {variant_suffix} body – palette map: {var_palette_fn}")
    else:
        print(f"[WARNING] Source not found for {variant_suffix} body – palette map: {color_map_source_2}")

    return car_data_fn, car_palette_fn, var_data_fn, var_palette_fn


def _apply_skin_reference_regexes(content: str, skin_id: str) -> str:
    def _val(m):  return f'"{m.group(1)}{skin_id}"'
    def _name(m): return f'{m.group(1)}{skin_id}"'

    print(f"[DEBUG] _apply_skin_reference_regexes: skin_id={skin_id!r}")

    content = re.sub(r'"([^"]+\.skin\.)[^"]+"',                     _val,  content)
    content = re.sub(r'"([^"]+\.skin_[^.]*\.)[^"]+"',               _val,  content)
    content = re.sub(r'("name"\s*:\s*"[^"]+\.skin\.)[^"]+"',        _name, content)
    content = re.sub(r'("mapTo"\s*:\s*"[^"]+\.skin\.)[^"]+"',       _name, content)
    content = re.sub(r'("name"\s*:\s*"[^"]+\.skin_[^.]*\.)[^"]+"',  _name, content)
    content = re.sub(r'("mapTo"\s*:\s*"[^"]+\.skin_[^.]*\.)[^"]+"', _name, content)
    content = re.sub(r'"([^"]*_extra\.skin\.)[^"]+"',                _val,  content)
    content = re.sub(r'("name"\s*:\s*"[^"]*_extra\.skin\.)[^"]+"',   _name, content)
    content = re.sub(r'("mapTo"\s*:\s*"[^"]*_extra\.skin\.)[^"]+"',  _name, content)
    return content


def _process_jbeam_files(folder_path, vehicle_id, skin_id,
                          skin_name=None, author_name=None):
    print(f"[DEBUG] _process_jbeam_files: folder_path={folder_path!r} vehicle_id={vehicle_id!r} "
          f"skin_id={skin_id!r} skin_name={skin_name!r} author_name={author_name!r}")
    for root_dir, _, files in os.walk(folder_path):
        for filename in files:
            if not filename.endswith(".jbeam"):
                continue

            file_path = os.path.join(root_dir, filename)
            with open(file_path, "r", encoding="utf-8") as fh:
                content = fh.read()

            content = _apply_skin_reference_regexes(content, skin_id)
            content = re.sub(r'_skin_SKINNAME\w*', f'_skin_{skin_id}',
                             content, flags=re.IGNORECASE)
            content = re.sub(r'("globalSkin"\s*:\s*")SKINNAME\w*(")',
                             lambda m: m.group(1) + skin_id + m.group(2),
                             content, flags=re.IGNORECASE)
            content = re.sub(r'("skinName"\s*:\s*")SKINNAME\w*(")',
                             lambda m: m.group(1) + skin_id + m.group(2),
                             content, flags=re.IGNORECASE)

            if author_name:
                content = re.sub(r'("authors"\s*:\s*")[^"]*"',
                                 rf'\g<1>{author_name}"', content)
            else:
                print(f"[WARNING] author_name not provided — author left unchanged in {file_path}")
            if skin_name:
                content = re.sub(
                    r'("name"\s*:\s*")(?![^"]*\.skin\.)[^"]*"',
                    rf'\g<1>{skin_name}"', content,
                )

            if vehicle_id:
                content = re.sub(r'(?<![a-zA-Z0-9])carid', vehicle_id,
                                 content, flags=re.IGNORECASE)

            with open(file_path, "w", encoding="utf-8") as fh:
                fh.write(content)
            print(f"[DEBUG] Processed jbeam: {file_path}")


def _apply_skin_id_regexes(content: str, skin_id: str,
                             skin_folder_name: str, vehicle_id: str) -> str:
    print(f"[DEBUG] _apply_skin_id_regexes: skin_id={skin_id!r} "
          f"skin_folder_name={skin_folder_name!r} vehicle_id={vehicle_id!r}")
    content = _apply_skin_reference_regexes(content, skin_id)
    content = re.sub(r'/SKINNAME/', f'/{skin_folder_name}/',
                     content, flags=re.IGNORECASE)
    content = re.sub(r'_skin_SKINNAME(\.[^"]+)', f'_skin_{skin_id}\\1',
                     content, flags=re.IGNORECASE)
    content = re.sub(r'(?<![a-zA-Z0-9])carid', vehicle_id,
                     content, flags=re.IGNORECASE)
    return content


def _process_json_files(
    folder_path, vehicle_id, skin_folder_name,
    data_map_filename, color_map_filename, skin_id,
):
    data_path    = f"vehicles/{vehicle_id}/{skin_folder_name}/{data_map_filename}"
    palette_path = f"vehicles/{vehicle_id}/{skin_folder_name}/{color_map_filename}"

    print(f"[DEBUG] _process_json_files: folder_path={folder_path!r} vehicle_id={vehicle_id!r} "
          f"data_path={data_path!r} palette_path={palette_path!r}")

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
                        if idx == 0:
                            stages[idx]["colorPaletteMapUseUV"] = None
                        else:
                            stages[idx]["baseColorMap"]         = data_path
                            stages[idx]["diffuseMapUseUV"]      = 1
                            stages[idx]["colorPaletteMap"]      = palette_path
                            stages[idx]["colorPaletteMapUseUV"] = 1
                content = json.dumps(data, indent=2)
            else:
                content = raw

            content = _apply_skin_id_regexes(content, skin_id, skin_folder_name, vehicle_id)
            with open(file_path, "w", encoding="utf-8") as fh:
                fh.write(content)
            print(f"[DEBUG] Processed json (normal): {file_path}")


def _process_json_files_variant(
    folder_path, vehicle_id, skin_folder_name,
    car_data_filename,   car_palette_filename,
    var_data_filename,   var_palette_filename,
    skin_id, variant_suffix,
):
    car_data_path    = f"vehicles/{vehicle_id}/{skin_folder_name}/{car_data_filename}"
    car_palette_path = f"vehicles/{vehicle_id}/{skin_folder_name}/{car_palette_filename}"
    var_data_path    = f"vehicles/{vehicle_id}/{skin_folder_name}/{var_data_filename}"
    var_palette_path = f"vehicles/{vehicle_id}/{skin_folder_name}/{var_palette_filename}"

    var_prefix = f"{variant_suffix}.skin."

    print(f"[DEBUG] _process_json_files_variant: folder_path={folder_path!r} "
          f"vehicle_id={vehicle_id!r} var_prefix={var_prefix!r} "
          f"car_data_path={car_data_path!r} var_data_path={var_data_path!r}")

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

                    is_var   = mat_key.lower().startswith(var_prefix.lower())
                    d_path   = var_data_path    if is_var else car_data_path
                    p_path   = var_palette_path if is_var else car_palette_path
                    label    = "variant body" if is_var else "car body"

                    print(f"[DEBUG]   '{mat_key}' → {label}")

                    for idx in (0, 1):
                        if idx >= len(stages) or not isinstance(stages[idx], dict):
                            continue
                        if idx == 0:
                            stages[idx]["colorPaletteMapUseUV"] = None
                            print("[DEBUG]     Stage 0 baseColorMap preserved (unchanged)")
                        else:
                            stages[idx]["baseColorMap"]         = d_path
                            stages[idx]["diffuseMapUseUV"]      = 1
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


def _process_material_properties(folder_path, material_props, skin_id):
    if not material_props:
        print(f"[DEBUG] _process_material_properties: no material_props for {skin_id!r}, skipping")
        return True
    print(f"[DEBUG] ===== _process_material_properties for {skin_id} =====")

    mat_files = []
    for root_dir, _, files in os.walk(folder_path):
        for fn in files:
            if fn.endswith(".materials.json") or fn == "materials.json":
                mat_files.append(os.path.join(root_dir, fn))

    print(f"[DEBUG] _process_material_properties: found {len(mat_files)} materials.json file(s)")

    if not mat_files:
        print(f"[WARNING] No .materials.json found in {folder_path}")
        return False

    try:
        failed_files = []

        for mat_file in mat_files:
            with open(mat_file, "r", encoding="utf-8") as fh:
                raw = fh.read()
            raw_clean = re.sub(r",(\s*[}\]])", r"\1", raw)
            try:
                mat_data = json.loads(raw_clean)
            except json.JSONDecodeError as exc:
                print(f"[ERROR] JSON decode error in {os.path.basename(mat_file)}: {exc}")
                failed_files.append(os.path.basename(mat_file))
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
                    except (ValueError, TypeError) as _exc:
                        print(f"[WARNING] _process_material_properties: {type(_exc).__name__}: {_exc}")
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

        print("[DEBUG] ===== _process_material_properties complete =====")

        if failed_files:
            print(f"[WARNING] _process_material_properties: "
                  f"{len(failed_files)}/{len(mat_files)} materials.json file(s) "
                  f"could not be parsed and were left unmodified: "
                  f"{', '.join(failed_files)}")
            return False

        return True

    except Exception as exc:
        import traceback
        print(f"[ERROR] _process_material_properties: {exc}")
        traceback.print_exc()
        return False


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
    skin_data_ref=None,
):
    from core.file_ops import apply_emissive_glow

    skin_id = sanitize_skin_id(skin_name)
    print(f"[DEBUG] generate_colorable_skin: '{skin_name}' folder='{skin_folder}' id='{skin_id}'")
    print(f"[DEBUG] generate_colorable_skin: vehicle_id={vehicle_id!r} template_path={template_path!r} "
          f"dest_skin_folder={dest_skin_folder!r} data_map_source={data_map_source!r} "
          f"color_map_source={color_map_source!r} author_name={author_name!r}")

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

    if skin_data_ref and skin_data_ref.get("emissive_dds_path"):
        if not apply_emissive_glow(skin_data_ref, vehicle_id, skin_folder, dest_skin_folder):
            print(f"[WARNING] Emissive glow failed for {skin_folder}")

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
    skin_data_ref=None,
):
    from core.file_ops import apply_emissive_glow

    skin_id = sanitize_skin_id(skin_name)
    print(f"[DEBUG] generate_colorable_skin_variant: '{skin_name}' "
          f"({variant_suffix}) → 4 PNGs, single folder")
    print(f"[DEBUG] generate_colorable_skin_variant: vehicle_id={vehicle_id!r} "
          f"template_path={template_path!r} dest_skin_folder={dest_skin_folder!r} "
          f"author_name={author_name!r}")

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
        car_dm, car_pm, var_dm, var_pm, skin_id, variant_suffix,
    )
    if material_properties:
        if not _process_material_properties(dest_skin_folder, material_properties, skin_id):
            print(f"[WARNING] Material properties processing failed for {skin_folder}")

    if skin_data_ref and skin_data_ref.get("emissive_dds_path"):
        if not apply_emissive_glow(skin_data_ref, vehicle_id, skin_folder, dest_skin_folder):
            print(f"[WARNING] Emissive glow failed for {skin_folder}")

    print(f"[DEBUG] generate_colorable_skin_variant complete: {skin_folder}")
