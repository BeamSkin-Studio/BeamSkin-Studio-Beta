import os
import shutil
import tempfile
import zipfile
import re
import json

from utils import config_helper

try:
    from core.settings import get_vehicles_dir, get_vehicle_previews_dir
except ImportError as _exc:
    print(f"[DEBUG] _pipe_tmp.py: import failed ({_exc}), using fallback")
    def get_vehicles_dir():
        return 'vehicles'
    def get_vehicle_previews_dir():
        return os.path.join('gui', 'images', 'vehicles')


VEHICLE_FOLDER = get_vehicles_dir()
ADDED_VEHICLES_JSON = os.path.join(get_vehicles_dir(), "added_vehicles.json")

try:
    from core.config import VEHICLE_IDS, is_rebadge_suffix
except ImportError as _exc:
    print(f"[DEBUG] _pipe_tmp.py: import failed ({_exc}), using fallback")
    VEHICLE_IDS = {}
    def is_rebadge_suffix(_c, _s):
        return False


def _is_builtin_carid(carid: str) -> bool:
    return carid.strip().lower() in {k.lower() for k in VEHICLE_IDS}


def _variant_folder_protected(carid: str, suffix_upper: str) -> bool:
    if is_rebadge_suffix(carid, suffix_upper.lower()):
        return True
    existing = os.path.join(get_vehicles_dir(), carid, f"SKINNAME{suffix_upper}")
    return os.path.isdir(existing)

def sanitize_skin_id(name):
    return name.lower().replace(" ", "_")

def sanitize_mod_name(name):
    return name.strip().replace(" ", "_")

def get_beamng_mods_path():
    return config_helper.get_beamng_mods_path()

def zip_folder(source_dir, zip_path):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root_dir, _, files in os.walk(source_dir):
            for file in files:
                full_path = os.path.join(root_dir, file)
                relative_path = os.path.relpath(full_path, source_dir)
                zipf.write(full_path, relative_path)

def create_vehicle_folders(carid):
    if _is_builtin_carid(carid):
        print(f"[ERROR] '{carid}' is a built-in vehicle — refusing to create/overwrite its folder")
        raise ValueError(f"'{carid}' is a built-in vehicle and cannot be overwritten")
    vehicle_path = os.path.join(get_vehicles_dir(), carid, "SKINNAME")
    os.makedirs(vehicle_path, exist_ok=True)
    return True

def create_variant_folders(carid, suffix_upper):
    if _variant_folder_protected(carid, suffix_upper):
        print(f"[ERROR] '{carid}/SKINNAME{suffix_upper}' already exists — refusing to overwrite it")
        raise ValueError(f"'{carid}+{suffix_upper}' already exists and cannot be overwritten")
    variant_path = os.path.join(get_vehicles_dir(), carid, f"SKINNAME{suffix_upper}")
    os.makedirs(variant_path, exist_ok=True)
    return True

def delete_vehicle_folders(carid):
    if _is_builtin_carid(carid):
        print(f"[ERROR] '{carid}' is a built-in vehicle — refusing to delete its folder")
        raise ValueError(f"'{carid}' is a built-in vehicle and cannot be deleted")
    try:
        vehicle_path = os.path.join(get_vehicles_dir(), carid)
        if os.path.exists(vehicle_path):
            shutil.rmtree(vehicle_path)

        preview_path = os.path.join(get_vehicle_previews_dir(), carid)
        if os.path.exists(preview_path):
            shutil.rmtree(preview_path)

        return True
    except Exception as e:
        print(f"[ERROR] Failed to delete vehicle folders: {e}")
        raise

def delete_variant_folders(carid, suffix_upper):
    if is_rebadge_suffix(carid, suffix_upper.lower()):
        print(f"[ERROR] '{carid}/SKINNAME{suffix_upper}' is a built-in rebadge — refusing to delete it")
        raise ValueError(f"'{carid}+{suffix_upper}' is a built-in vehicle and cannot be deleted")
    try:
        variant_path = os.path.join(get_vehicles_dir(), carid, f"SKINNAME{suffix_upper}")
        if os.path.exists(variant_path):
            shutil.rmtree(variant_path)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to delete variant folders: {e}")
        raise


def _added_vehicles_json_path() -> str:
    return os.path.join(get_vehicles_dir(), "added_vehicles.json")

def _load_raw_json() -> dict:
    path = _added_vehicles_json_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] _load_raw_json failed: {e}")
        return {}

def load_added_vehicles_json():
    path = _added_vehicles_json_path()
    if not os.path.exists(path):
        return {}
    try:
        raw = _load_raw_json()
        return {k: v for k, v in raw.items() if not k.startswith("__")}
    except Exception as e:
        print(f"[ERROR] Failed to load {path}: {e}")
        return {}

def load_added_variants_json() -> dict:
    raw = _load_raw_json()
    return raw.get("__variants__", {})

def save_added_vehicles_json(vehicles_dict):
    path = _added_vehicles_json_path()
    try:
        os.makedirs(get_vehicles_dir(), exist_ok=True)
        raw = _load_raw_json()
        reserved = {k: v for k, v in raw.items() if k.startswith("__")}
        merged = {**vehicles_dict, **reserved}
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(merged, f, indent=2)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save {path}: {e}")
        raise

def add_vehicle_to_json(carid, carname):
    if _is_builtin_carid(carid):
        print(f"[ERROR] '{carid}' is a built-in vehicle — refusing to register it as custom")
        raise ValueError(f"'{carid}' is a built-in vehicle and cannot be re-registered")
    raw = _load_raw_json()
    raw[carid] = carname
    os.makedirs(get_vehicles_dir(), exist_ok=True)
    with open(_added_vehicles_json_path(), 'w', encoding='utf-8') as f:
        json.dump(raw, f, indent=2)
    return True

def remove_vehicle_from_json(carid):
    raw = _load_raw_json()
    if carid in raw:
        del raw[carid]
        with open(_added_vehicles_json_path(), 'w', encoding='utf-8') as f:
            json.dump(raw, f, indent=2)
        return True
    else:
        print(f"[WARNING] Vehicle {carid} not found in JSON")
        return False

def add_variant_to_json(carid: str, suffix_lower: str) -> bool:
    if is_rebadge_suffix(carid, suffix_lower):
        print(f"[ERROR] '{carid}+{suffix_lower}' is a built-in rebadge — refusing to register it as custom")
        raise ValueError(f"'{carid}+{suffix_lower}' is a built-in vehicle and cannot be re-registered")
    key = f"{carid}__{suffix_lower}"
    raw = _load_raw_json()
    raw.setdefault("__variants__", {})[key] = {"carid": carid, "suffix": suffix_lower}
    os.makedirs(get_vehicles_dir(), exist_ok=True)
    with open(_added_vehicles_json_path(), 'w', encoding='utf-8') as f:
        json.dump(raw, f, indent=2)
    return True

def remove_variant_from_json(carid: str, suffix_lower: str) -> bool:
    if is_rebadge_suffix(carid, suffix_lower):
        print(f"[ERROR] '{carid}+{suffix_lower}' is a built-in rebadge — refusing to remove it")
        raise ValueError(f"'{carid}+{suffix_lower}' is a built-in vehicle and cannot be removed")
    key = f"{carid}__{suffix_lower}"
    raw = _load_raw_json()
    variants = raw.get("__variants__", {})
    if key in variants:
        del variants[key]
        if not variants:
            raw.pop("__variants__", None)
        else:
            raw["__variants__"] = variants
        with open(_added_vehicles_json_path(), 'w', encoding='utf-8') as f:
            json.dump(raw, f, indent=2)
        return True
    else:
        print(f"[WARNING] Variant {key} not found in JSON")
        return False

def fix_stage_two_material_properties(stage2, carid, prefix):
    properties_to_remove = [
        "instanceDiffuse",
        "baseColorFactor",
        "colorPaletteMap",
        "colorPaletteMapUseUV",
        "metallicMap",
        "metallicMapUseUV",
        "roughnessFactor",
    ]

    removed_count = 0
    for prop in properties_to_remove:
        if prop in stage2:
            del stage2[prop]
            removed_count += 1

    stage2["baseColorMap"] = "vehicles/carid/skinname/carid_skin_skinname.dds"

    return stage2

def edit_material_json(source_json_path, target_folder, carid):
    try:
        source_basename = os.path.basename(source_json_path)

        if source_basename.startswith("skin."):
            output_name = "skin.materials.json"
        else:
            output_name = "materials.json"

        target_path = os.path.join(target_folder, output_name)

        with open(source_json_path, 'r', encoding='utf-8') as f:
            content = f.read()

        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            print(f"[DEBUG] edit_material_json: standard JSON parse failed for {source_json_path!r} ({e}), trying JSON5-style fixes")

            content = re.sub(r'//[^\n]*', '', content)
            content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
            content = re.sub(r',(\s*[}\]])', r'\1', content)

            try:
                data = json.loads(content)
            except json.JSONDecodeError as e2:
                print(f"[ERROR] Still cannot parse JSON after fixes: {e2}")
                print(f"[ERROR] '{source_json_path}' was NOT processed — "
                      f"skin-key rewriting and Stage[1] fixes were skipped. "
                      f"The file needs to be fixed by hand (check for a real "
                      f"JSON syntax error beyond simple trailing-comma/comment "
                      f"issues) and re-run this step.")
                return False

        general_skin_pattern = r"^(.+?)\.skin(?:_lbe)?\.(.+)$"

        _EXCLUDE_PREFIX_KEYWORDS = ("sign", "display")

        skin_groups = {}

        for key, value in data.items():
            match = re.match(general_skin_pattern, key)
            if match:
                prefix   = match.group(1)
                skinname = match.group(2)
                if any(kw in prefix.lower() for kw in _EXCLUDE_PREFIX_KEYWORDS):
                    continue
                if skinname:
                    if skinname not in skin_groups:
                        skin_groups[skinname] = {}
                    skin_groups[skinname][key] = (key, value, prefix)

        if not skin_groups:
            print(f"[WARNING] No skin entries found matching carid: {carid}")
            with open(target_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            return True

        selected_skinname = max(skin_groups.keys(), key=lambda k: len(skin_groups[k]))
        selected_entries = skin_groups[selected_skinname]

        filtered_data = {}

        for key, (original_key, value, prefix) in selected_entries.items():
            normalized_key = f"{prefix}.skin.skinname"

            import copy
            new_value = copy.deepcopy(value)

            if "name" in new_value and isinstance(new_value["name"], str):
                new_value["name"] = new_value["name"].replace(".skin_lbe.", ".skin.")
                new_value["name"] = new_value["name"].replace(selected_skinname, "skinname")

            if "mapTo" in new_value and isinstance(new_value["mapTo"], str):
                new_value["mapTo"] = new_value["mapTo"].replace(".skin_lbe.", ".skin.")
                new_value["mapTo"] = new_value["mapTo"].replace(selected_skinname, "skinname")

            if "Stages" in new_value and isinstance(new_value["Stages"], list):
                for stage in new_value["Stages"]:
                    if isinstance(stage, dict) and "baseColorMap" in stage:
                        if isinstance(stage["baseColorMap"], str):
                            stage["baseColorMap"] = stage["baseColorMap"].replace(selected_skinname, "skinname")

            if "Stages" in new_value and isinstance(new_value["Stages"], list):
                if len(new_value["Stages"]) >= 2:
                    stage2 = new_value["Stages"][1]
                    if isinstance(stage2, dict):
                        new_value["Stages"][1] = fix_stage_two_material_properties(stage2, carid, prefix)

            fields_to_remove = [
                "colorPaletteMap",
                "colorPaletteMapUseUV",
                "clearCoatFactor",
                "clearCoatRoughnessFactor",
                "instanceDiffuse",
                "metallicFactor"
            ]

            for field in fields_to_remove:
                if field in new_value:
                    del new_value[field]

            if "Stages" in new_value and isinstance(new_value["Stages"], list):
                stage_fields_to_remove = ["colorPaletteMap", "colorPaletteMapUseUV"]
                for stage_idx, stage in enumerate(new_value["Stages"]):
                    if isinstance(stage, dict):
                        for field in stage_fields_to_remove:
                            if field in stage:
                                del stage[field]

                while new_value["Stages"] and not new_value["Stages"][-1]:
                    new_value["Stages"].pop()

            filtered_data[normalized_key] = new_value

        with open(target_path, 'w', encoding='utf-8') as f:
            json.dump(filtered_data, f, indent=2)

        print(f"[DEBUG] edit_material_json: wrote {len(filtered_data)} skin entries to {target_path} "
              f"({len(data) - len(filtered_data)} non-matching entries dropped)")
        return True

    except Exception as e:
        print(f"[ERROR] Failed to process materials JSON: {e}")
        import traceback
        traceback.print_exc()
        raise

def edit_jbeam_material(source_jbeam_path, target_folder, carid):
    try:
        output_name = os.path.basename(source_jbeam_path)
        target_path = os.path.join(target_folder, output_name)

        template = f'''{{
    "{carid}_skin_SKINNAME": {{
        "information":{{
            "authors":"author",
            "name":"SKIN NAME",
            "value":200
        }},
        "slotType" : "paint_design",
        "globalSkin" : "SKINNAME"
    }}
}}'''

        with open(target_path, 'w', encoding='utf-8') as f:
            f.write(template)

        return True

    except Exception as e:
        print(f"[ERROR] Failed to process JBeam file: {e}")
        import traceback
        traceback.print_exc()
        raise

def edit_info_json(source_json_path, target_folder, output_name="info_skinname.json"):
    fallback_template = {
        "Configuration": "SKIN NAME",
        "Description": "DESCRIPTION",
        "Config Type": "Factory",
        "Population": 0,
    }

    try:
        target_path = os.path.join(target_folder, output_name)

        data = None
        if source_json_path and os.path.exists(source_json_path):
            try:
                with open(source_json_path, "r", encoding="utf-8-sig") as f:
                    content = f.read()
                try:
                    data = json.loads(content)
                except json.JSONDecodeError as _exc:
                    print(f"[WARNING] edit_info_json: {type(_exc).__name__}: {_exc}")
                    content = re.sub('//[^\\n]*', '', content)
                    content = re.sub('/\\*.*?\\*/', '', content, flags=re.DOTALL)
                    content = re.sub(',(\\s*[}\\]])', '\\1', content)
                    data = json.loads(content)
            except Exception as e:
                print(f"[WARNING] Failed to parse source info JSON, using fallback template: {e}")
                data = None

        if data is None:
            data = dict(fallback_template)
        else:
            data["Configuration"] = "SKIN NAME"
            data["Description"] = "DESCRIPTION"

        with open(target_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        return True

    except Exception as e:
        print(f"[ERROR] Failed to process info JSON: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_single_skin_mod(
    vehicle_id,
    skin_name,
    dds_path,
    mod_name,
    author,
    preview_image_path=None,
    output_path=None,
    progress_callback=None
):
    temp_dir = tempfile.mkdtemp(prefix="beamng_mod_")

    try:
        if progress_callback:
            progress_callback(0.0)

        skin_id = sanitize_skin_id(skin_name)
        dds_identifier = skin_id
        dds_filename = os.path.basename(dds_path)

        template_path = os.path.join(get_vehicles_dir(), vehicle_id, "SKINNAME")

        if not os.path.exists(template_path):
            raise FileNotFoundError(
                f"No template found for vehicle '{vehicle_id}'.\n"
                f"Please add this vehicle in the Developer tab first."
            )

        mod_vehicle_dir = os.path.join(temp_dir, "vehicles", vehicle_id, skin_id)
        os.makedirs(mod_vehicle_dir, exist_ok=True)

        if progress_callback:
            progress_callback(0.2)

        for file in os.listdir(template_path):
            source_file = os.path.join(template_path, file)
            target_file = os.path.join(mod_vehicle_dir, file)
            shutil.copy2(source_file, target_file)

        shutil.copy2(dds_path, os.path.join(mod_vehicle_dir, dds_filename))

        if progress_callback:
            progress_callback(0.4)

        process_jbeam_files(mod_vehicle_dir, dds_identifier, skin_name, author)
        process_json_files(mod_vehicle_dir, vehicle_id, skin_id, dds_filename, dds_identifier)

        if progress_callback:
            progress_callback(0.6)

        if preview_image_path and os.path.exists(preview_image_path):
            preview_dir = os.path.join(temp_dir, "imagesforgui", "vehicles", vehicle_id)
            os.makedirs(preview_dir, exist_ok=True)
            preview_ext = os.path.splitext(preview_image_path)[1]
            preview_name = f"{skin_id}{preview_ext}"
            preview_target = os.path.join(preview_dir, preview_name)
            shutil.copy2(preview_image_path, preview_target)

        if progress_callback:
            progress_callback(0.8)

        mod_info = {
            "name": mod_name,
            "version": "1.0",
            "author": author
        }

        mod_info_path = os.path.join(temp_dir, "info.json")
        with open(mod_info_path, 'w', encoding='utf-8') as f:
            json.dump(mod_info, f, indent=2)

        mods_path = output_path or get_beamng_mods_path()
        os.makedirs(mods_path, exist_ok=True)
        zip_path = os.path.join(mods_path, f"{mod_name}.zip")

        if os.path.exists(zip_path):
            raise FileExistsError(
                f"A mod named '{mod_name}.zip' already exists.\n"
                f"Please choose a different name or delete the existing file."
            )

        zip_folder(temp_dir, zip_path)

        if progress_callback:
            progress_callback(1.0)

        print(f"✓ Mod created successfully at: {zip_path}")
        return zip_path

    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

def create_multi_skin_mod(
    skins_data,
    mod_name,
    author,
    output_path=None,
    progress_callback=None
):
    temp_dir = tempfile.mkdtemp(prefix="beamng_mod_multi_")

    try:
        print(f"\n{'='*60}")
        print(f"Creating Multi-Skin Mod: {mod_name}")
        print(f"{'='*60}\n")

        if progress_callback:
            progress_callback(0.0)

        total_skins = len(skins_data)
        total_cars = len(set(skin["vehicle_id"] for skin in skins_data))

        print(f"Total skins to process: {total_skins}")
        print(f"Total vehicles: {total_cars}\n")

        for idx, skin in enumerate(skins_data):
            vehicle_id = skin["vehicle_id"]
            skin_name = skin["skin_name"]
            dds_path = skin["dds_path"]
            preview_image_path = skin.get("preview_image_path")

            print(f"[{idx + 1}/{total_skins}] Processing: {vehicle_id} - {skin_name}")

            base_progress = idx / total_skins
            skin_progress_weight = 1.0 / total_skins

            skin_id = sanitize_skin_id(skin_name)
            dds_identifier = skin_id
            dds_filename = os.path.basename(dds_path)

            template_path = os.path.join(get_vehicles_dir(), vehicle_id, "SKINNAME")

            if not os.path.exists(template_path):
                print(f"[WARNING] No template found for vehicle '{vehicle_id}', skipping...")
                continue

            mod_vehicle_dir = os.path.join(temp_dir, "vehicles", vehicle_id, skin_id)
            os.makedirs(mod_vehicle_dir, exist_ok=True)

            if progress_callback:
                progress_callback(base_progress + (skin_progress_weight * 0.2))

            for file in os.listdir(template_path):
                source_file = os.path.join(template_path, file)
                target_file = os.path.join(mod_vehicle_dir, file)
                shutil.copy2(source_file, target_file)

            shutil.copy2(dds_path, os.path.join(mod_vehicle_dir, dds_filename))

            if progress_callback:
                progress_callback(base_progress + (skin_progress_weight * 0.4))

            process_jbeam_files(mod_vehicle_dir, dds_identifier, skin_name, author)
            process_json_files(mod_vehicle_dir, vehicle_id, skin_id, dds_filename, dds_identifier)

            if progress_callback:
                progress_callback(base_progress + (skin_progress_weight * 0.6))

            if preview_image_path and os.path.exists(preview_image_path):
                preview_dir = os.path.join(temp_dir, "imagesforgui", "vehicles", vehicle_id)
                os.makedirs(preview_dir, exist_ok=True)
                preview_ext = os.path.splitext(preview_image_path)[1]
                preview_name = f"{skin_id}{preview_ext}"
                preview_target = os.path.join(preview_dir, preview_name)
                shutil.copy2(preview_image_path, preview_target)

            if "config_data" in skin:
                process_skin_config_data(skin, vehicle_id, skin_id, temp_dir, template_path)

            if progress_callback:
                progress_callback(base_progress + (skin_progress_weight * 0.8))

            print(f"  ✓ Completed: {skin_name}")

        print("\nCreating mod info file...")

        mod_info = {
            "name": mod_name,
            "version": "1.0",
            "author": author
        }

        mod_info_path = os.path.join(temp_dir, "info.json")
        with open(mod_info_path, 'w', encoding='utf-8') as f:
            json.dump(mod_info, f, indent=2)

        print("Creating ZIP file...")

        mods_path = output_path or get_beamng_mods_path()
        os.makedirs(mods_path, exist_ok=True)
        zip_path = os.path.join(mods_path, f"{mod_name}.zip")

        print(f"ZIP path: {zip_path}")

        if os.path.exists(zip_path):
            raise FileExistsError(
                f"A mod named '{mod_name}.zip' already exists.\n"
                f"Please choose a different name or delete the existing file."
            )

        file_count = sum(len(files) for _, _, files in os.walk(temp_dir))
        print(f"[DEBUG] Zipping {file_count} files from {temp_dir}")

        zip_folder(temp_dir, zip_path)

        if progress_callback:
            progress_callback(1.0)

        print("\n✓ Multi-skin mod created successfully!")
        print(f"  Cars: {total_cars}")
        print(f"  Skins: {total_skins}")
        print(f"  Location: {zip_path}")
        print(f"{'='*60}\n")

        return zip_path

    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

def process_jbeam_files(folder_path, dds_identifier, skin_display_name, author):
    for root_dir, _, files in os.walk(folder_path):
        for file in files:
            if not file.endswith(".jbeam"):
                continue

            file_path = os.path.join(root_dir, file)

            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            content = content.replace('.skin_lbe.', '.skin.')

            content = re.sub(
                r'("authors"\s*:\s*")[^"]*(")',
                rf'\g<1>{author}\g<2>',
                content
            )

            content = re.sub(
                r'("name"\s*:\s*")[^"]*(")',
                rf'\g<1>{skin_display_name}\g<2>',
                content
            )

            def replace_first_skin_key(match):
                return f'"{match.group(1)}{dds_identifier}":'

            content = re.sub(
                r'"([^"]*_)[^"]+":',
                replace_first_skin_key,
                content,
                count=1
            )

            content = re.sub(
                r'("globalSkin"\s*:\s*")[^"]*(")',
                rf'\g<1>{dds_identifier}\g<2>',
                content
            )

            def replace_extra_skin(match):
                return f'"{match.group(1)}{dds_identifier}"'

            content = re.sub(
                r'"([^"]*_extra\.skin\.)[^"]+"',
                replace_extra_skin,
                content
            )

            def replace_extra_skin_name(match):
                return f'{match.group(1)}{dds_identifier}"'

            content = re.sub(
                r'("name"\s*:\s*"[^"]*_extra\.skin\.)[^"]+"',
                replace_extra_skin_name,
                content
            )
            content = re.sub(
                r'("mapTo"\s*:\s*"[^"]*_extra\.skin\.)[^"]+"',
                replace_extra_skin_name,
                content
            )

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

def process_json_files(folder_path, vehicle_id, skin_folder_name, dds_filename, dds_identifier):
    for root_dir, _, files in os.walk(folder_path):
        for file in files:
            if not file.endswith(".json") or file.startswith("info"):
                continue

            file_path = os.path.join(root_dir, file)

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                for material_key, material_data in data.items():
                    if not isinstance(material_data, dict):
                        continue

                    if "name" in material_data and (".skin." in material_data["name"] or ".skin_lbe." in material_data["name"]):
                        material_data["name"] = material_data["name"].replace(".skin_lbe.", ".skin.")
                        material_data["name"] = re.sub(
                            r'(\.skin\.)[^"]+$',
                            rf'\1{dds_identifier}',
                            material_data["name"]
                        )

                    if "mapTo" in material_data and (".skin." in material_data["mapTo"] or ".skin_lbe." in material_data["mapTo"]):
                        material_data["mapTo"] = material_data["mapTo"].replace(".skin_lbe.", ".skin.")
                        material_data["mapTo"] = re.sub(
                            r'(\.skin\.)[^"]+$',
                            rf'\1{dds_identifier}',
                            material_data["mapTo"]
                        )

                    if "Stages" in material_data and isinstance(material_data["Stages"], list):
                        stages = material_data["Stages"]
                        if len(stages) > 1 and isinstance(stages[1], dict):
                            stage2 = stages[1]
                            new_path = f"vehicles/{vehicle_id}/{skin_folder_name}/{vehicle_id}_skin_{dds_identifier}.dds"
                            stage2["baseColorMap"] = new_path

                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

            except json.JSONDecodeError as e:
                print(f"[ERROR] Failed to parse JSON file {file_path}: {e}")
                print(f"[DEBUG] process_json_files: falling back to regex-based processing for {file_path}")

                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()

                    def replace_skin_ref(match):
                        return f'"{match.group(1)}{dds_identifier}"'

                    content = re.sub(
                        r'"([^"]+\.skin\.)[^"]+"',
                        replace_skin_ref,
                        content,
                    )

                    def replace_skin_name(match):
                        return f'{match.group(1)}{dds_identifier}"'

                    content = content.replace('.skin_lbe.', '.skin.')

                    content = re.sub(
                        r'("name"\s*:\s*"[^"]+\.skin\.)[^"]+"',
                        replace_skin_name,
                        content,
                    )
                    content = re.sub(
                        r'("mapTo"\s*:\s*"[^"]+\.skin\.)[^"]+"',
                        replace_skin_name,
                        content,
                    )

                    def replace_extra_skin_all(match):
                        return f'"{match.group(1)}{dds_identifier}"'

                    content = re.sub(
                        r'"([^"]*_extra\.skin\.)[^"]+"',
                        replace_extra_skin_all,
                        content
                    )

                    def replace_extra_skin_name_all(match):
                        return f'{match.group(1)}{dds_identifier}"'

                    content = re.sub(
                        r'("name"\s*:\s*"[^"]*_extra\.skin\.)[^"]+"',
                        replace_extra_skin_name_all,
                        content
                    )
                    content = re.sub(
                        r'("mapTo"\s*:\s*"[^"]*_extra\.skin\.)[^"]+"',
                        replace_extra_skin_name_all,
                        content
                    )

                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(content)

                    print(f"[DEBUG]   Processed via regex fallback: {file_path}")

                except Exception as fallback_error:
                    print(f"[ERROR] Regex fallback also failed for {file_path}: {fallback_error}")
                    import traceback
                    traceback.print_exc()

            except Exception as e:
                print(f"[ERROR] Failed to process {file_path}: {e}")
                import traceback
                traceback.print_exc()

def process_skin_config_data(skin, vehicle_id, skin_id, temp_dir, template_path):
    if "config_data" not in skin:
        return True

    try:
        config_data = skin["config_data"]

        config_path = os.path.join(temp_dir, "vehicles", vehicle_id, skin_id, "configs")
        os.makedirs(config_path, exist_ok=True)

        config_file_path = os.path.join(config_path, f"{skin_id}_config.json")

        with open(config_file_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2)

        return True

    except Exception as e:
        print(f"[ERROR] Failed to process config data: {e}")
        import traceback
        traceback.print_exc()
        return False
