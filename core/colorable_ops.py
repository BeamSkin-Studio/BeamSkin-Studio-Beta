import os
import shutil
import json
import re

def sanitize_skin_id(name):

    name = name.replace(" ", "")
    name = re.sub(r"[^a-zA-Z0-9\-]", "", name)
    return name

def sanitize_folder_name(name):

    return name.replace(" ", "_")

def _copy_texture_files(data_map_source, color_map_source, dest_folder, skin_id):

    os.makedirs(dest_folder, exist_ok=True)

    data_map_filename  = f"{skin_id}_b.color.png"
    color_map_filename = f"{skin_id}_cp.color.png"

    if data_map_source and os.path.exists(data_map_source):
        dest = os.path.join(dest_folder, data_map_filename)
        shutil.copy2(data_map_source, dest)
        print(f"[DEBUG] Copied data map:  {data_map_source} -> {dest}")
    else:
        print(f"[WARNING] Data map source not found: {data_map_source}")

    if color_map_source and os.path.exists(color_map_source):
        dest = os.path.join(dest_folder, color_map_filename)
        shutil.copy2(color_map_source, dest)
        print(f"[DEBUG] Copied color map: {color_map_source} -> {dest}")
    else:
        print(f"[WARNING] Color map source not found: {color_map_source}")

    return data_map_filename, color_map_filename

def _process_jbeam_files(folder_path, vehicle_id, skin_id, skin_name=None, author_name=None):

    for root_dir, _, files in os.walk(folder_path):
        for filename in files:
            if not filename.endswith(".jbeam"):
                continue

            file_path = os.path.join(root_dir, filename)
            with open(file_path, "r", encoding="utf-8") as fh:
                content = fh.read()

            def _val(m):  return f'"{m.group(1)}{skin_id}"'
            def _name(m): return f'{m.group(1)}{skin_id}"'

            content = re.sub(r'"([^"]+\.skin\.)[^"]+"',                    _val,  content)
            content = re.sub(r'"([^"]+\.skin_[^.]*\.)[^"]+"',              _val,  content)
            content = re.sub(r'("name"\s*:\s*"[^"]+\.skin\.)[^"]+"',       _name, content)
            content = re.sub(r'("mapTo"\s*:\s*"[^"]+\.skin\.)[^"]+"',      _name, content)
            content = re.sub(r'("name"\s*:\s*"[^"]+\.skin_[^.]*\.)[^"]+"',  _name, content)
            content = re.sub(r'("mapTo"\s*:\s*"[^"]+\.skin_[^.]*\.)[^"]+"', _name, content)
            content = re.sub(r'"([^"]*_extra\.skin\.)[^"]+"',               _val,  content)
            content = re.sub(r'("name"\s*:\s*"[^"]*_extra\.skin\.)[^"]+"',  _name, content)
            content = re.sub(r'("mapTo"\s*:\s*"[^"]*_extra\.skin\.)[^"]+"', _name, content)

            content = re.sub(r'_skin_SKINNAME\b', f'_skin_{skin_id}', content, flags=re.IGNORECASE)

            content = re.sub(
                r'("globalSkin"\s*:\s*)"SKINNAME"',
                f'\\1"{skin_id}"',
                content,
                flags=re.IGNORECASE,
            )

            if skin_name:
                content = content.replace('"YOUR SKIN NAME"', f'"{skin_name}"')

            if author_name:
                content = re.sub(
                    r'("authors"\s*:\s*)"YOU"',
                    f'\\1"{author_name}"',
                    content,
                    flags=re.IGNORECASE,
                )
            else:
                print(f"[WARNING] author_name not provided — 'YOU' placeholder left unreplaced in {file_path}")

            if vehicle_id:
                content = re.sub(
                    r'(?<![a-zA-Z0-9])carid', vehicle_id, content, flags=re.IGNORECASE
                )

            with open(file_path, "w", encoding="utf-8") as fh:
                fh.write(content)

            print(f"[DEBUG] Processed jbeam: {file_path}")

def _process_json_files(
    folder_path, vehicle_id, skin_folder_name,
    data_map_filename, color_map_filename, skin_id
):

    base_map_path  = f"vehicles/{vehicle_id}/{skin_folder_name}/{data_map_filename}"
    color_map_path = f"vehicles/{vehicle_id}/{skin_folder_name}/{color_map_filename}"

    for root_dir, _, files in os.walk(folder_path):
        for filename in files:
            if not filename.endswith(".json") or filename.startswith("info"):
                continue

            file_path = os.path.join(root_dir, filename)

            with open(file_path, "r", encoding="utf-8") as fh:
                raw = fh.read()

            raw_clean = re.sub(r',(\s*[}\]])', r'\1', raw)

            try:
                data = json.loads(raw_clean)
                parsed_ok = True
            except json.JSONDecodeError as exc:
                print(f"[WARNING] JSON parse failed for {file_path}: {exc}")
                parsed_ok = False

            if parsed_ok:
                for material_key, material_data in data.items():
                    if not isinstance(material_data, dict):
                        continue
                    stages = material_data.get("Stages")
                    if not isinstance(stages, list):
                        continue

                    for idx in (0, 1):
                        if idx >= len(stages) or not isinstance(stages[idx], dict):
                            continue
                        stages[idx]["baseColorMap"] = base_map_path
                        print(f"[DEBUG] Stage {idx + 1} in '{material_key}':")
                        print(f"[DEBUG]   baseColorMap: {base_map_path}")
                        if idx == 0:
                            stages[idx]["colorPaletteMapUseUV"] = None
                            print(f"[DEBUG]   colorPaletteMapUseUV: null")
                        else:
                            stages[idx]["colorPaletteMap"]      = color_map_path
                            stages[idx]["colorPaletteMapUseUV"] = 1
                            print(f"[DEBUG]   colorPaletteMap:      {color_map_path}")
                            print(f"[DEBUG]   colorPaletteMapUseUV: 1")

                content = json.dumps(data, indent=2)
            else:
                print(f"[WARNING] Falling back to raw text for {file_path} — Stage edits skipped")
                content = raw

            def _val(m):  return f'"{m.group(1)}{skin_id}"'
            def _name(m): return f'{m.group(1)}{skin_id}"'

            content = re.sub(r'"([^"]+\.skin\.)[^"]+"',                    _val,  content)
            content = re.sub(r'"([^"]+\.skin_[^.]*\.)[^"]+"',              _val,  content)
            content = re.sub(r'("name"\s*:\s*"[^"]+\.skin\.)[^"]+"',       _name, content)
            content = re.sub(r'("mapTo"\s*:\s*"[^"]+\.skin\.)[^"]+"',      _name, content)
            content = re.sub(r'("name"\s*:\s*"[^"]+\.skin_[^.]*\.)[^"]+"',  _name, content)
            content = re.sub(r'("mapTo"\s*:\s*"[^"]+\.skin_[^.]*\.)[^"]+"', _name, content)
            content = re.sub(r'"([^"]*_extra\.skin\.)[^"]+"',               _val,  content)
            content = re.sub(r'("name"\s*:\s*"[^"]*_extra\.skin\.)[^"]+"',  _name, content)
            content = re.sub(r'("mapTo"\s*:\s*"[^"]*_extra\.skin\.)[^"]+"', _name, content)

            content = re.sub(r'/SKINNAME/', f'/{skin_folder_name}/', content, flags=re.IGNORECASE)
            content = re.sub(
                r'_skin_SKINNAME(\.[^"]+)', f'_skin_{skin_id}\\1', content, flags=re.IGNORECASE
            )
            content = re.sub(
                r'(?<![a-zA-Z0-9])carid', vehicle_id, content, flags=re.IGNORECASE
            )

            with open(file_path, "w", encoding="utf-8") as fh:
                fh.write(content)

            print(f"[DEBUG] Processed json: {file_path}")

def _process_material_properties(folder_path, material_props, skin_id):
    if not material_props:
        return True

    print(f"[DEBUG] ===== _process_material_properties for {skin_id} =====")
    print(f"[DEBUG]   Materials to update: {len(material_props)}")

    materials_files = []
    for root_dir, _, files in os.walk(folder_path):
        for filename in files:
            if filename.endswith(".materials.json") or filename == "materials.json":
                materials_files.append(os.path.join(root_dir, filename))

    if not materials_files:
        print(f"[WARNING]   No .materials.json files found in {folder_path}")
        return False

    print(f"[DEBUG]   Found {len(materials_files)} material file(s):")
    for mf in materials_files:
        print(f"[DEBUG]     - {mf}")

    try:
        for material_file in materials_files:
            print(f"[DEBUG]   Processing: {os.path.basename(material_file)}")

            with open(material_file, "r", encoding="utf-8") as fh:
                raw = fh.read()

            raw_clean = re.sub(r",(\s*[}\]])", r"\1", raw)

            try:
                mat_data = json.loads(raw_clean)
            except json.JSONDecodeError as exc:
                print(f"[ERROR]   JSON decode error in {os.path.basename(material_file)}: {exc}")
                continue

            print(f"[DEBUG]   Materials in file: {list(mat_data.keys())}")

            file_modified = False

            for mat_name_template, stages in material_props.items():
                if ".skin." in mat_name_template:
                    base_prefix = mat_name_template.split(".skin.")[0]
                else:
                    base_prefix = mat_name_template

                print(f"[DEBUG]   Looking for materials starting with: {base_prefix}.skin.")

                actual_key = None
                for key in mat_data.keys():
                    if key.startswith(f"{base_prefix}.skin."):
                        actual_key = key
                        print(f"[DEBUG]   Matched: {mat_name_template} → {actual_key}")
                        break

                if actual_key is None:
                    print(f"[DEBUG]   No match found for '{base_prefix}.skin.*', skipping")
                    continue

                if "Stages" not in mat_data[actual_key]:
                    print(f"[DEBUG]   '{actual_key}' has no Stages, skipping")
                    continue

                mat_stages = mat_data[actual_key]["Stages"]

                for stage_num_str, properties in stages.items():
                    try:
                        stage_idx = int(stage_num_str)
                    except (ValueError, TypeError) as exc:
                        print(f"[ERROR]   Cannot convert stage number '{stage_num_str}': {exc}")
                        continue

                    if stage_idx >= len(mat_stages):
                        print(f"[WARNING]   Stage {stage_idx} out of range for {actual_key}")
                        continue

                    stage = mat_stages[stage_idx]
                    print(f"[DEBUG]   Updating {actual_key}.Stages[{stage_idx}] with {len(properties)} prop(s)")

                    for prop_name, prop_value in properties.items():
                        old_val = stage.get(prop_name, "NOT_FOUND")
                        stage[prop_name] = prop_value
                        print(f"[DEBUG]     ✓ {prop_name}: {old_val} → {prop_value}")
                        file_modified = True

            if file_modified:
                with open(material_file, "w", encoding="utf-8") as fh:
                    json.dump(mat_data, fh, indent=2)
                print(f"[DEBUG]   ✓ Saved {os.path.basename(material_file)}")
            else:
                print(f"[DEBUG]   No changes for {os.path.basename(material_file)}")

        print(f"[DEBUG] ===== _process_material_properties complete =====")
        return True

    except Exception as exc:
        print(f"[ERROR] _process_material_properties: {exc}")
        import traceback
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
):
    skin_id = sanitize_skin_id(skin_name)
    print(f"[DEBUG] generate_colorable_skin: '{skin_name}' -> folder='{skin_folder}' id='{skin_id}'")

    def _ignore(directory, contents):
        return [f for f in contents if f.lower().endswith((".dds", ".png"))]

    shutil.copytree(template_path, dest_skin_folder, ignore=_ignore)
    print(f"[DEBUG] Template copied to {dest_skin_folder}")

    data_map_filename, color_map_filename = _copy_texture_files(
        data_map_source, color_map_source, dest_skin_folder, skin_id
    )

    _process_jbeam_files(dest_skin_folder, vehicle_id, skin_id, skin_name=skin_name, author_name=author_name)

    _process_json_files(
        dest_skin_folder,
        vehicle_id,
        skin_folder,
        data_map_filename,
        color_map_filename,
        skin_id,
    )

    if material_properties:
        success = _process_material_properties(dest_skin_folder, material_properties, skin_id)
        if not success:
            print(f"[WARNING] Material properties processing failed for {skin_folder}")

    print(f"[DEBUG] generate_colorable_skin complete: {skin_folder}")