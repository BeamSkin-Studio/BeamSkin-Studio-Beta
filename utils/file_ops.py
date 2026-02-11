# file_ops.py
# edits the attached files in Add vehicles tab

import os
import shutil
import tempfile
import zipfile
import getpass
import re
import json

VEHICLE_FOLDER = "vehicles"
ADDED_VEHICLES_JSON = os.path.join("vehicles", "added_vehicles.json")

def sanitize_skin_id(name):

    print(f"[DEBUG] sanitize_skin_id called")
    return name.lower().replace(" ", "_")

def sanitize_mod_name(name):

    print(f"[DEBUG] sanitize_mod_name called")
    return name.strip().replace(" ", "_")

def get_beamng_mods_path():

    print(f"[DEBUG] get_beamng_mods_path called")
    username = getpass.getuser()
    return os.path.join(
        "C:\\Users",
        username,
        "AppData",
        "Local",
        "BeamNG",
        "BeamNG.drive",
        "current",
        "mods"
    )

def zip_folder(source_dir, zip_path):

    print(f"[DEBUG] zip_folder called")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root_dir, _, files in os.walk(source_dir):
            for file in files:
                full_path = os.path.join(root_dir, file)
                relative_path = os.path.relpath(full_path, source_dir)
                zipf.write(full_path, relative_path)

def create_vehicle_folders(carid):
    print(f"[DEBUG] create_vehicle_folders called for: {carid}")

    vehicle_path = os.path.join(VEHICLE_FOLDER, carid, "SKINNAME")
    os.makedirs(vehicle_path, exist_ok=True)

    print(f"[DEBUG] Created vehicle folders: {vehicle_path}")
    return True

def delete_vehicle_folders(carid):
    print(f"[DEBUG] delete_vehicle_folders called for: {carid}")

    try:

        vehicle_path = os.path.join(VEHICLE_FOLDER, carid)
        if os.path.exists(vehicle_path):
            shutil.rmtree(vehicle_path)
            print(f"[DEBUG] Deleted vehicle folder: {vehicle_path}")

        preview_path = os.path.join("imagesforgui", "vehicles", carid)
        if os.path.exists(preview_path):
            shutil.rmtree(preview_path)
            print(f"[DEBUG] Deleted preview folder: {preview_path}")

        return True
    except Exception as e:
        print(f"[ERROR] Failed to delete vehicle folders: {e}")
        raise

def load_added_vehicles_json():
    print(f"[DEBUG] load_added_vehicles_json called")

    if not os.path.exists(ADDED_VEHICLES_JSON):
        print(f"[DEBUG] {ADDED_VEHICLES_JSON} not found, returning empty dict")
        return {}

    try:
        with open(ADDED_VEHICLES_JSON, 'r', encoding='utf-8') as f:
            vehicles = json.load(f)
            print(f"[DEBUG] Loaded {len(vehicles)} vehicles from {ADDED_VEHICLES_JSON}")
            return vehicles
    except Exception as e:
        print(f"[ERROR] Failed to load {ADDED_VEHICLES_JSON}: {e}")
        return {}

def save_added_vehicles_json(vehicles_dict):
    print(f"[DEBUG] save_added_vehicles_json called with {len(vehicles_dict)} vehicles")

    try:

        os.makedirs(VEHICLE_FOLDER, exist_ok=True)

        with open(ADDED_VEHICLES_JSON, 'w', encoding='utf-8') as f:
            json.dump(vehicles_dict, f, indent=2)
        print(f"[DEBUG] Successfully saved to {ADDED_VEHICLES_JSON}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save {ADDED_VEHICLES_JSON}: {e}")
        raise

def add_vehicle_to_json(carid, carname):
    print(f"[DEBUG] add_vehicle_to_json called: {carid} = {carname}")

    vehicles = load_added_vehicles_json()

    vehicles[carid] = carname

    save_added_vehicles_json(vehicles)

    print(f"[DEBUG] Vehicle {carid} added to JSON successfully")
    return True

def remove_vehicle_from_json(carid):
    print(f"[DEBUG] remove_vehicle_from_json called: {carid}")

    vehicles = load_added_vehicles_json()

    if carid in vehicles:
        del vehicles[carid]
        save_added_vehicles_json(vehicles)
        print(f"[DEBUG] Vehicle {carid} removed from JSON successfully")
        return True
    else:
        print(f"[WARNING] Vehicle {carid} not found in JSON")
        return False

def fix_stage_two_material_properties(stage2, carid, prefix):
    print(f"[DEBUG] Fixing Stage 2 material properties for prefix: {prefix}...")

    properties_to_remove = [
        "instanceDiffuse",
        "baseColorFactor",
        "colorPaletteMap",
        "colorPaletteMapUseUV",
        "metallicMap",
        "metallicMapUseUV"
    ]

    removed_count = 0
    for prop in properties_to_remove:
        if prop in stage2:
            del stage2[prop]
            removed_count += 1
            print(f"[DEBUG]   ✓ Removed incorrect property: {prop}")

    required_properties = {
        "baseColorMap": "vehicles/carid/skinname/carid_skin_skinname.dds",
        "diffuseMapUseUV": 1,
        "metallicFactor": 0.5,
        "roughnessFactor": 0.5
    }

    added_count = 0
    for prop, value in required_properties.items():
        if prop not in stage2:
            stage2[prop] = value
            added_count += 1
            print(f"[DEBUG]   ✓ Added missing property: {prop} = {value}")
        elif prop == "baseColorMap":

            old_value = stage2[prop]
            stage2[prop] = value
            print(f"[DEBUG]   ✓ Replaced baseColorMap:")
            print(f"[DEBUG]     Old: {old_value}")
            print(f"[DEBUG]     New: {value}")

    if removed_count > 0:
        print(f"[DEBUG] Removed {removed_count} incorrect properties from Stage 2")
    if added_count > 0:
        print(f"[DEBUG] Added {added_count} missing properties to Stage 2")

    return stage2

def edit_material_json(source_json_path, target_folder, carid):
    print(f"[DEBUG] edit_material_json called")
    print(f"[DEBUG]   Source: {source_json_path}")
    print(f"[DEBUG]   Target: {target_folder}")
    print(f"[DEBUG]   CarID: {carid}")

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
            print(f"[DEBUG] Parsed JSON successfully (standard format)")
        except json.JSONDecodeError as e:
            print(f"[DEBUG] Standard JSON parse failed: {e}")
            print(f"[DEBUG] Attempting to fix JSON5 format (trailing commas, comments)...")

            content = re.sub(r'//[^\n]*', '', content)

            content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)

            content = re.sub(r',(\s*[}\]])', r'\1', content)

            try:
                data = json.loads(content)
                print(f"[DEBUG] Successfully parsed after JSON5 fixes")
            except json.JSONDecodeError as e2:
                print(f"[ERROR] Still cannot parse JSON after fixes: {e2}")
                print(f"[DEBUG] Falling back to direct copy without validation...")

                with open(source_json_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                with open(target_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"[DEBUG] Copied file directly (BeamNG will parse it)")
                return True

        skin_pattern_prefixes = [
            f"{carid}",
            f"{carid}_body",
            f"{carid}_extra",
            f"{carid}_aftermarket",
            f"{carid}_main",
            f"{carid}_mechanical"
        ]

        skin_groups = {}

        print(f"[DEBUG] Scanning for skin entries matching carid: {carid}")

        for key, value in data.items():

            for prefix in skin_pattern_prefixes:

                pattern = rf"^{re.escape(prefix)}\.skin[^.]*\.(.+)$"
                match = re.match(pattern, key)

                if match:

                    skinname = match.group(1)

                    if skinname:

                        if skinname not in skin_groups:
                            skin_groups[skinname] = {}
                        skin_groups[skinname][key] = (key, value, prefix)
                        print(f"[DEBUG] Found skin entry: {key} (skinname: {skinname})")
                    break

        if not skin_groups:
            print(f"[WARNING] No skin entries found matching carid: {carid}")
            with open(target_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            return True

        selected_skinname = max(skin_groups.keys(), key=lambda k: len(skin_groups[k]))
        selected_entries = skin_groups[selected_skinname]

        print(f"[DEBUG] Selected skinname: {selected_skinname} ({len(selected_entries)} entries)")
        print(f"[DEBUG] Available skin groups: {list(skin_groups.keys())}")

        filtered_data = {}

        for key, (original_key, value, prefix) in selected_entries.items():

            normalized_key = f"{prefix}.skin.skinname"

            print(f"[DEBUG] Transforming: {original_key} → {normalized_key}")

            import copy
            new_value = copy.deepcopy(value)

            if "name" in new_value and isinstance(new_value["name"], str):

                new_value["name"] = new_value["name"].replace(selected_skinname, "skinname")

            if "mapTo" in new_value and isinstance(new_value["mapTo"], str):

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
                    print(f"[DEBUG] Removed field: {field} from {normalized_key}")

            if "Stages" in new_value and isinstance(new_value["Stages"], list):
                original_length = len(new_value["Stages"])

                new_value["Stages"] = new_value["Stages"][:2]

                stage_fields_to_remove = ["colorPaletteMap", "colorPaletteMapUseUV"]
                for stage_idx, stage in enumerate(new_value["Stages"]):
                    if isinstance(stage, dict):
                        for field in stage_fields_to_remove:
                            if field in stage:
                                del stage[field]
                                print(f"[DEBUG] Removed {field} from {normalized_key} Stage {stage_idx}")

                new_length = len(new_value["Stages"])
                print(f"[DEBUG] Trimmed Stages array in {normalized_key}: {original_length} -> {new_length} stages")

            filtered_data[normalized_key] = new_value
            print(f"[DEBUG] Transformed: {original_key} -> {normalized_key}")

        with open(target_path, 'w', encoding='utf-8') as f:
            json.dump(filtered_data, f, indent=2)

        print(f"[DEBUG] Wrote {len(filtered_data)} skin entries to: {target_path}")
        print(f"[DEBUG] Removed {len(data) - len(filtered_data)} non-matching entries")
        return True

    except Exception as e:
        print(f"[ERROR] Failed to process materials JSON: {e}")
        import traceback
        traceback.print_exc()
        raise

def edit_jbeam_material(source_jbeam_path, target_folder, carid):
    print(f"[DEBUG] edit_jbeam_material called")
    print(f"[DEBUG]   Source: {source_jbeam_path}")
    print(f"[DEBUG]   Target: {target_folder}")
    print(f"[DEBUG]   CarID: {carid}")

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

        print(f"[DEBUG] Created template JBeam file: {target_path}")
        print(f"[DEBUG] Template uses carid: {carid}")
        return True

    except Exception as e:
        print(f"[ERROR] Failed to process JBeam file: {e}")
        import traceback
        traceback.print_exc()
        raise

def edit_info_json(source_json_path, target_folder):
    print(f"[DEBUG] edit_info_json called")
    print(f"[DEBUG]   Source: {source_json_path}")
    print(f"[DEBUG]   Target: {target_folder}")

    try:

        output_name = os.path.basename(source_json_path)
        target_path = os.path.join(target_folder, output_name)

        info_template = {
            "name": "skinname",
            "author": "author"
        }

        with open(target_path, 'w', encoding='utf-8') as f:
            json.dump(info_template, f, indent=2)

        print(f"[DEBUG] Created template info file: {target_path}")
        return True

    except Exception as e:
        print(f"[ERROR] Failed to process info JSON: {e}")
        import traceback
        traceback.print_exc()
        raise

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

    print(f"[DEBUG] create_single_skin_mod called")
    temp_dir = tempfile.mkdtemp(prefix="beamng_mod_")

    try:
        if progress_callback:
            progress_callback(0.0)

        skin_id = sanitize_skin_id(skin_name)
        dds_identifier = skin_id
        dds_filename = os.path.basename(dds_path)

        template_path = os.path.join(VEHICLE_FOLDER, vehicle_id, "SKINNAME")

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

    print(f"[DEBUG] create_multi_skin_mod called")
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

            template_path = os.path.join(VEHICLE_FOLDER, vehicle_id, "SKINNAME")

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

        print(f"\nCreating mod info file...")

        mod_info = {
            "name": mod_name,
            "version": "1.0",
            "author": author
        }

        mod_info_path = os.path.join(temp_dir, "info.json")
        with open(mod_info_path, 'w', encoding='utf-8') as f:
            json.dump(mod_info, f, indent=2)

        print(f"Creating ZIP file...")

        mods_path = output_path or get_beamng_mods_path()
        os.makedirs(mods_path, exist_ok=True)
        zip_path = os.path.join(mods_path, f"{mod_name}.zip")

        print(f"ZIP path: {zip_path}")

        if os.path.exists(zip_path):
            raise FileExistsError(
                f"A mod named '{mod_name}.zip' already exists.\n"
                f"Please choose a different name or delete the existing file."
            )

        print(f"\n[DEBUG] Files being zipped from {temp_dir}:")
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, temp_dir)
                print(f"[DEBUG]   {rel_path}")

        zip_folder(temp_dir, zip_path)

        if progress_callback:
            progress_callback(1.0)

        print(f"\n✓ Multi-skin mod created successfully!")
        print(f"  Cars: {total_cars}")
        print(f"  Skins: {total_skins}")
        print(f"  Location: {zip_path}")
        print(f"{'='*60}\n")

        return zip_path

    finally:

        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

def process_jbeam_files(folder_path, dds_identifier, skin_display_name, author):

    print(f"[DEBUG] process_jbeam_files called")
    for root_dir, _, files in os.walk(folder_path):
        for file in files:
            if not file.endswith(".jbeam"):
                continue

            file_path = os.path.join(root_dir, file)

            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

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
                print(f"[DEBUG] replace_first_skin_key called")
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
                print(f"[DEBUG] replace_extra_skin called")
                return f'"{match.group(1)}{dds_identifier}"'

            content = re.sub(
                r'"([^"]*_extra\.skin\.)[^"]+"',
                replace_extra_skin,
                content
            )

            def replace_extra_skin_name(match):

                print(f"[DEBUG] replace_extra_skin_name called")
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
    print(f"[DEBUG] process_json_files called")
    print(f"[DEBUG]   vehicle_id: {vehicle_id}")
    print(f"[DEBUG]   skin_folder_name: {skin_folder_name}")
    print(f"[DEBUG]   dds_identifier: {dds_identifier}")

    for root_dir, _, files in os.walk(folder_path):
        for file in files:
            if not file.endswith(".json") or file.startswith("info"):
                continue

            file_path = os.path.join(root_dir, file)
            print(f"[DEBUG] Processing JSON file: {file_path}")

            try:

                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                for material_key, material_data in data.items():
                    if not isinstance(material_data, dict):
                        continue

                    print(f"[DEBUG]   Processing material: {material_key}")

                    if "name" in material_data and ".skin." in material_data["name"]:
                        old_name = material_data["name"]
                        material_data["name"] = re.sub(
                            r'(\.skin\.)[^"]+$',
                            rf'\1{dds_identifier}',
                            material_data["name"]
                        )
                        if old_name != material_data["name"]:
                            print(f"[DEBUG]     Updated name: {old_name} -> {material_data['name']}")

                    if "mapTo" in material_data and ".skin." in material_data["mapTo"]:
                        old_mapTo = material_data["mapTo"]
                        material_data["mapTo"] = re.sub(
                            r'(\.skin\.)[^"]+$',
                            rf'\1{dds_identifier}',
                            material_data["mapTo"]
                        )
                        if old_mapTo != material_data["mapTo"]:
                            print(f"[DEBUG]     Updated mapTo: {old_mapTo} -> {material_data['mapTo']}")

                    if "Stages" in material_data and isinstance(material_data["Stages"], list):
                        stages = material_data["Stages"]

                        if len(stages) > 1 and isinstance(stages[1], dict):
                            stage2 = stages[1]

                            new_path = f"vehicles/{vehicle_id}/{skin_folder_name}/{vehicle_id}_skin_{dds_identifier}.dds"

                            if "baseColorMap" in stage2:
                                original_path = stage2["baseColorMap"]
                                stage2["baseColorMap"] = new_path
                                print(f"[DEBUG]     Updated Stage 2 baseColorMap:")
                                print(f"[DEBUG]       From: {original_path}")
                                print(f"[DEBUG]       To:   {new_path}")
                            else:
                                stage2["baseColorMap"] = new_path
                                print(f"[DEBUG]     Added Stage 2 baseColorMap: {new_path}")

                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

                print(f"[DEBUG]   Successfully processed: {file_path}")

            except json.JSONDecodeError as e:
                print(f"[ERROR] Failed to parse JSON file {file_path}: {e}")
                print(f"[DEBUG] Falling back to regex-based processing for malformed JSON")

                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()

                    def replace_skin_ref(match):
                        return f'"{match.group(1)}{dds_identifier}"'

                    content = re.sub(
                        r'"([^"]+\.skin\.)[^"]+"',
                        replace_skin_ref,
                        content,
                        count=1
                    )

                    def replace_skin_name(match):
                        return f'{match.group(1)}{dds_identifier}"'

                    content = re.sub(
                        r'("name"\s*:\s*"[^"]+\.skin\.)[^"]+"',
                        replace_skin_name,
                        content,
                        count=1
                    )
                    content = re.sub(
                        r'("mapTo"\s*:\s*"[^"]+\.skin\.)[^"]+"',
                        replace_skin_name,
                        content,
                        count=1
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
    print(f"[DEBUG] process_skin_config_data called for {skin_id}")

    if "config_data" not in skin:
        print(f"[DEBUG] No config data found for {skin_id}")
        return True

    try:
        config_data = skin["config_data"]

        config_path = os.path.join(temp_dir, "vehicles", vehicle_id, skin_id, "configs")
        os.makedirs(config_path, exist_ok=True)

        config_file_path = os.path.join(config_path, f"{skin_id}_config.json")

        with open(config_file_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2)

        print(f"[DEBUG] Created config file: {config_file_path}")
        return True

    except Exception as e:
        print(f"[ERROR] Failed to process config data: {e}")
        import traceback
        traceback.print_exc()
        return False