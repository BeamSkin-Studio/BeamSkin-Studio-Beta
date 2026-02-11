# file_ops.py
# Edit files in project tab


import os
import shutil
import tempfile
import zipfile
import getpass
import re
import json

def sanitize_skin_id(name):
    return name.replace(" ", "")

def sanitize_folder_name(name):
    return name.replace(" ", "_")

def sanitize_mod_name(name):
    return name.strip().replace(" ", "_")

def get_beamng_mods_path():

    try:
        from core.settings import get_mods_folder_path
        configured_path = get_mods_folder_path()
        if configured_path and os.path.exists(configured_path):
            print(f"[DEBUG] Using configured mods path: {configured_path}")
            return configured_path
        else:
            print(f"[DEBUG] Configured mods path not set or doesn't exist")
    except ImportError:
        print(f"[DEBUG] Could not import settings module")

    username = getpass.getuser()
    default_path = os.path.join(
        "C:\\Users",
        username,
        "AppData",
        "Local",
        "BeamNG.drive",
        "0.33",
        "mods"
    )
    print(f"[DEBUG] Using default mods path: {default_path}")
    return default_path

def zip_folder(source_dir, zip_path):

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root_dir, _, files in os.walk(source_dir):
            for file in files:
                full_path = os.path.join(root_dir, file)
                relative_path = os.path.relpath(full_path, source_dir)
                zipf.write(full_path, relative_path)

def validate_and_fix_dds_filenames(skin_folder_path, car_id):

    results = {
        'renamed': [],
        'already_correct': [],
        'errors': []
    }

    if not os.path.exists(skin_folder_path):
        results['errors'].append((skin_folder_path, "Folder does not exist"))
        return results

    correct_pattern = re.compile(rf'^{re.escape(car_id)}_skin_.*\.dds$', re.IGNORECASE)

    for filename in os.listdir(skin_folder_path):
        if not filename.lower().endswith('.dds'):
            continue

        file_path = os.path.join(skin_folder_path, filename)

        if correct_pattern.match(filename):
            print(f"[DEBUG] DDS file already correct: {filename}")
            results['already_correct'].append(filename)
            continue

        print(f"[DEBUG] DDS file needs correction: {filename}")

        skin_name = None

        if '_skin_' in filename.lower():
            parts = filename.split('_skin_')
            if len(parts) >= 2:

                skin_name = parts[-1].replace('.dds', '').replace('.DDS', '')

        elif filename.lower().startswith('skin_'):
            skin_name = filename[5:].replace('.dds', '').replace('.DDS', '')

        elif 'skin' in filename.lower():
            skin_index = filename.lower().find('skin')
            skin_name = filename[skin_index + 4:].replace('.dds', '').replace('.DDS', '')

            skin_name = skin_name.lstrip('_')

        else:
            skin_name = filename.replace('.dds', '').replace('.DDS', '')

        if not skin_name:
            results['errors'].append((filename, "Could not extract skin name"))
            continue

        new_filename = f"{car_id}_skin_{skin_name}.dds"
        new_file_path = os.path.join(skin_folder_path, new_filename)

        if os.path.exists(new_file_path) and new_file_path != file_path:
            results['errors'].append((filename, f"Target file already exists: {new_filename}"))
            continue

        try:
            os.rename(file_path, new_file_path)
            print(f"[DEBUG] Renamed: {filename} -> {new_filename}")
            results['renamed'].append((filename, new_filename))
        except Exception as e:
            results['errors'].append((filename, f"Rename failed: {str(e)}"))

    return results

def process_dds_files_in_mod(temp_mod_root):

    total_results = {
        'renamed': [],
        'already_correct': [],
        'errors': [],
        'skins_processed': 0
    }

    vehicles_path = os.path.join(temp_mod_root, "vehicles")

    if not os.path.exists(vehicles_path):
        print("[WARNING] No vehicles folder found in mod")
        return total_results

    for car_id in os.listdir(vehicles_path):
        car_path = os.path.join(vehicles_path, car_id)

        if not os.path.isdir(car_path):
            continue

        print(f"[DEBUG] Processing DDS files for car: {car_id}")

        for item in os.listdir(car_path):
            item_path = os.path.join(car_path, item)

            if not os.path.isdir(item_path):
                continue

            print(f"[DEBUG]   Processing skin folder: {item}")
            results = validate_and_fix_dds_filenames(item_path, car_id)

            total_results['renamed'].extend([(car_id, item, old, new) for old, new in results['renamed']])
            total_results['already_correct'].extend([(car_id, item, f) for f in results['already_correct']])
            total_results['errors'].extend([(car_id, item, f, err) for f, err in results['errors']])
            total_results['skins_processed'] += 1

    print(f"\n[DEBUG] DDS File Processing Summary:")
    print(f"[DEBUG]   Skins processed: {total_results['skins_processed']}")
    print(f"[DEBUG]   Files renamed: {len(total_results['renamed'])}")
    print(f"[DEBUG]   Files already correct: {len(total_results['already_correct'])}")
    print(f"[DEBUG]   Errors: {len(total_results['errors'])}")

    if total_results['renamed']:
        print(f"[DEBUG] Renamed files:")
        for car_id, skin, old, new in total_results['renamed']:
            print(f"[DEBUG]   {car_id}/{skin}: {old} -> {new}")

    if total_results['errors']:
        print(f"[DEBUG] Errors:")
        for car_id, skin, filename, error in total_results['errors']:
            print(f"[DEBUG]   {car_id}/{skin}/{filename}: {error}")

    return total_results

def update_info_json_fields(json_path, config_type, config_name):

    try:
        print(f"[DEBUG] Updating info JSON fields in: {os.path.basename(json_path)}")

        with open(json_path, 'r', encoding='utf-8') as f:
            content = f.read()

        config_type_pattern = r'("Config Type"\s*:\s*")[^"]*(")'
        if re.search(config_type_pattern, content):
            content = re.sub(config_type_pattern, rf'\g<1>{config_type}\g<2>', content)
            print(f"[DEBUG]   ✓ Set Config Type to: {config_type}")
        else:
            print(f"[WARNING]   'Config Type' key not found")

        configuration_pattern = r'("Configuration"\s*:\s*")[^"]*(")'
        if re.search(configuration_pattern, content):
            content = re.sub(configuration_pattern, rf'\g<1>{config_name}\g<2>', content)
            print(f"[DEBUG]   ✓ Set Configuration to: {config_name}")
        else:
            print(f"[WARNING]   'Configuration' key not found")

        with open(json_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return True

    except Exception as e:
        print(f"[ERROR] Failed to update info JSON fields: {e}")
        return False

def process_skin_config_data(skin_data, base_carid, skin_name, temp_mod_root, template_path):

    if "config_data" not in skin_data:
        return True

    config_data = skin_data["config_data"]
    config_type = config_data.get("config_type", "Factory")
    config_name = config_data.get("config_name", skin_data.get("name", skin_name))
    pc_path = config_data.get("pc_file_path")
    jpg_path = config_data.get("jpg_file_path")

    print(f"[DEBUG] ===== Processing config data for {skin_name} =====")
    print(f"[DEBUG]   Config Type: {config_type}")
    print(f"[DEBUG]   Config Name (in-game): {config_name}")
    print(f"[DEBUG]   .pc file: {pc_path}")
    print(f"[DEBUG]   .jpg file: {jpg_path}")
    print(f"[DEBUG]   Template path: {template_path}")
    print(f"[DEBUG]   Template exists: {os.path.exists(template_path)}")

    has_errors = False
    if pc_path and not os.path.exists(pc_path):
        print(f"[ERROR]   .pc file not found: {pc_path}")
        has_errors = True
    if jpg_path and not os.path.exists(jpg_path):
        print(f"[ERROR]   .jpg file not found: {jpg_path}")
        has_errors = True

    if has_errors:
        print(f"[ERROR] Config data validation failed for {skin_name}")
        return False

    try:

        vehicle_root = os.path.join(temp_mod_root, "vehicles", base_carid)
        os.makedirs(vehicle_root, exist_ok=True)
        print(f"[DEBUG]   Vehicle root: {vehicle_root}")

        if pc_path:
            dest_pc = os.path.join(vehicle_root, f"{skin_name}.pc")
            shutil.copy2(pc_path, dest_pc)
            print(f"[DEBUG]   ✓ Exported .pc: {dest_pc}")

        if jpg_path:
            dest_jpg = os.path.join(vehicle_root, f"{skin_name}.jpg")
            shutil.copy2(jpg_path, dest_jpg)
            print(f"[DEBUG]   ✓ Exported .jpg: {dest_jpg}")

        print(f"[DEBUG]   Searching for info template...")

        vehicle_template_root = os.path.dirname(template_path)

        source_info_file = None

        if not os.path.exists(vehicle_template_root):
            print(f"[ERROR]   Vehicle template root does not exist: {vehicle_template_root}")
            return False

        print(f"[DEBUG]   Vehicle template root: {vehicle_template_root}")

        print(f"[DEBUG]   Files in vehicle root:")
        for f in os.listdir(vehicle_template_root):
            print(f"[DEBUG]     - {f}")

        for filename in ["info.json", "info_template.json"]:
            potential_path = os.path.join(vehicle_template_root, filename)
            if os.path.exists(potential_path):
                source_info_file = potential_path
                print(f"[DEBUG]   Found info file: {filename}")
                break

        if not source_info_file:
            for filename in os.listdir(vehicle_template_root):
                if filename.startswith("info") and filename.endswith(".json"):
                    source_info_file = os.path.join(vehicle_template_root, filename)
                    print(f"[DEBUG]   Found info file (wildcard): {filename}")
                    break

        if source_info_file:
            dest_info = os.path.join(vehicle_root, f"info_{skin_name}.json")
            print(f"[DEBUG]   Copying: {source_info_file}")
            print(f"[DEBUG]   To: {dest_info}")

            shutil.copy2(source_info_file, dest_info)

            if os.path.exists(dest_info):
                print(f"[DEBUG]   ✓ File copied successfully")

                result = update_info_json_fields(dest_info, config_type, config_name)

                if result:
                    print(f"[DEBUG]   ✓ FINAL: Exported info_{skin_name}.json")
                    print(f"[DEBUG]   ✓ Set Configuration to: '{config_name}'")
                else:
                    print(f"[WARNING]   Info JSON fields update failed")
            else:
                print(f"[ERROR]   File copy failed - destination does not exist!")
                return False
        else:
            print(f"[ERROR]   No info.json template found in {template_path}")
            return False

        print(f"[DEBUG] ===== Config data processing complete =====")
        return True

    except Exception as e:
        print(f"[ERROR] process_skin_config_data: {e}")
        import traceback
        traceback.print_exc()
        return False

def process_material_properties(skin_data, base_carid, skin_id, dest_skin_folder):

    if "material_properties" not in skin_data:
        return True

    material_props = skin_data["material_properties"]
    print(f"[DEBUG] ===== Processing material properties for {skin_id} =====")
    print(f"[DEBUG]   Materials to update: {len(material_props)}")
    print(f"[DEBUG]   Destination folder: {dest_skin_folder}")

    print(f"[DEBUG]   Material properties data structure (from skin_data):")
    import json as json_module
    print(f"[DEBUG]   {json_module.dumps(material_props, indent=4)}")
    for mat_name, stages in material_props.items():
        print(f"[DEBUG]     Material: {mat_name}")
        for stage_key, props in stages.items():
            print(f"[DEBUG]       Stage {stage_key} (type: {type(stage_key)}): {props}")

    try:

        materials_files = []
        for root, dirs, files in os.walk(dest_skin_folder):
            for filename in files:
                if filename.endswith('.materials.json') or filename == 'materials.json':
                    materials_files.append(os.path.join(root, filename))

        if not materials_files:
            print(f"[WARNING]   No .materials.json files found in {dest_skin_folder}")
            return False

        print(f"[DEBUG]   Found {len(materials_files)} material file(s)")
        for mf in materials_files:
            print(f"[DEBUG]     - {mf}")

        for material_file in materials_files:
            print(f"[DEBUG]   Processing: {os.path.basename(material_file)}")

            with open(material_file, 'r', encoding='utf-8') as f:
                content = f.read()

            content = re.sub(r',(\s*[}\]])', r'\1', content)

            try:
                materials_data = json.loads(content)
            except json.JSONDecodeError as e:
                print(f"[ERROR]     JSON decode error in {os.path.basename(material_file)}: {e}")
                print(f"[ERROR]     Line {e.lineno}, column {e.colno}")
                continue

            print(f"[DEBUG]     Materials in file: {list(materials_data.keys())}")

            file_modified = False

            for material_name_template, stages in material_props.items():

                if '.skin.' in material_name_template:
                    base_material = material_name_template.split('.skin.')[0]
                else:
                    base_material = material_name_template

                print(f"[DEBUG]     Looking for materials starting with: {base_material}.skin.")

                actual_material_name = None
                for mat_name in materials_data.keys():
                    if mat_name.startswith(f"{base_material}.skin."):
                        actual_material_name = mat_name
                        print(f"[DEBUG]     Found match: {material_name_template} → {actual_material_name}")
                        break

                if actual_material_name is None:
                    print(f"[DEBUG]     No material found matching '{base_material}.skin.*', skipping")
                    continue

                print(f"[DEBUG]     Found material '{actual_material_name}' in file")

                if "Stages" not in materials_data[actual_material_name]:
                    print(f"[DEBUG]     Material '{actual_material_name}' has no Stages, skipping")
                    continue

                material_stages = materials_data[actual_material_name]["Stages"]
                print(f"[DEBUG]     Material has {len(material_stages)} stages")

                for stage_num_str, properties in stages.items():
                    print(f"[DEBUG]     Processing stage_num_str: '{stage_num_str}' (type: {type(stage_num_str).__name__})")

                    try:
                        stage_num = int(stage_num_str)
                        print(f"[DEBUG]     Converted to stage_num: {stage_num} (type: int)")
                    except (ValueError, TypeError) as e:
                        print(f"[ERROR]     Cannot convert stage number '{stage_num_str}' to int: {e}")
                        continue

                    if stage_num >= len(material_stages):
                        print(f"[WARNING]     Stage {stage_num} does not exist for {actual_material_name} (material has {len(material_stages)} stages)")
                        continue

                    stage = material_stages[stage_num]
                    print(f"[DEBUG]     Updating stage {stage_num} with {len(properties)} properties")
                    print(f"[DEBUG]     Stage {stage_num} current keys: {list(stage.keys())}")
                    print(f"[DEBUG]     Properties to update: {properties}")

                    for prop_name, prop_value in properties.items():
                        old_value = stage.get(prop_name, "NOT_FOUND")
                        stage[prop_name] = prop_value
                        print(f"[DEBUG]       ✓ Set {actual_material_name}.Stages[{stage_num}].{prop_name}")
                        print(f"[DEBUG]         Old: {old_value}")
                        print(f"[DEBUG]         New: {prop_value}")
                        file_modified = True

            if file_modified:

                print(f"[DEBUG]   Writing updated material data to file...")
                print(f"[DEBUG]   Sample of updated materials (first material only):")
                first_material = list(materials_data.keys())[0] if materials_data else None
                if first_material and "Stages" in materials_data[first_material]:
                    import json as json_module
                    print(f"[DEBUG]   {first_material}:")
                    print(f"[DEBUG]   {json_module.dumps(materials_data[first_material]['Stages'], indent=6)}")

                with open(material_file, 'w', encoding='utf-8') as f:
                    json.dump(materials_data, f, indent=2)
                print(f"[DEBUG]   ✓ Updated {os.path.basename(material_file)}")

                print(f"[DEBUG]   Verifying file was written correctly...")
                with open(material_file, 'r', encoding='utf-8') as f:
                    verify_content = f.read()
                    if "0.69" in verify_content:
                        print(f"[DEBUG]   ✓ Verification: Found '0.69' in saved file")
                    else:
                        print(f"[WARNING]   Verification: Did NOT find '0.69' in saved file")
            else:
                print(f"[DEBUG]   No changes needed for {os.path.basename(material_file)}")

        print(f"[DEBUG] ===== Material properties processing complete =====")
        return True

    except Exception as e:
        print(f"[ERROR] process_material_properties: {e}")
        import traceback
        traceback.print_exc()
        return False

def generate_mod(
    mod_name,
    vehicle_id,
    skin_display_name,
    dds_path,
    output_path=None,
    progress_callback=None,
    author=None
):

    print(f"\n{'='*60}")
    print(f"SINGLE SKIN MOD GENERATION")
    print(f"{'='*60}")
    print(f"Mod Name: {mod_name}")
    print(f"Vehicle ID: {vehicle_id}")
    print(f"Skin Name: {skin_display_name}")
    print(f"DDS Path: {dds_path}")

    mod_name = sanitize_mod_name(mod_name)
    template_path = os.path.join(os.getcwd(), "vehicles", vehicle_id, "SKINNAME")

    if not os.path.exists(template_path):
        raise FileNotFoundError(f"No template found for vehicle '{vehicle_id}'")

    temp_dir = tempfile.mkdtemp()

    try:
        dest_skin_folder = os.path.join(temp_dir, "vehicles", vehicle_id, mod_name)

        def ignore_dds_files(directory, files):
            return [f for f in files if f.lower().endswith(".dds")]

        shutil.copytree(template_path, dest_skin_folder, ignore=ignore_dds_files)

        if progress_callback: progress_callback(0.2)

        dds_filename = os.path.basename(dds_path)
        shutil.copy(dds_path, os.path.join(dest_skin_folder, dds_filename))
        dds_last = os.path.splitext(dds_filename)[0].split("_")[-1]

        if progress_callback: progress_callback(0.4)

        process_jbeam_files(dest_skin_folder, dds_last, skin_display_name, author or "Unknown")

        if progress_callback: progress_callback(0.6)

        process_json_files(dest_skin_folder, vehicle_id, mod_name, dds_filename, dds_last)

        if progress_callback: progress_callback(0.8)

        mods_path = output_path or get_beamng_mods_path()
        os.makedirs(mods_path, exist_ok=True)
        zip_path = os.path.join(mods_path, f"{mod_name}.zip")

        zip_folder(temp_dir, zip_path)

        if progress_callback: progress_callback(1.0)

        return zip_path

    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

def generate_multi_skin_mod(
    project_data,
    output_path=None,
    progress_callback=None
):
    print(f"\n{'='*60}")
    print(f"MULTI-SKIN MOD GENERATION")
    print(f"{'='*60}")

    mod_name = sanitize_mod_name(project_data["mod_name"])
    author = project_data.get("author", "Unknown")
    cars = project_data["cars"]

    total_cars = len(cars)
    total_skins = sum(len(car_info['skins']) for car_info in cars.values())

    print(f"Mod Name: {mod_name}")
    print(f"Author: {author}")
    print(f"Total Cars: {total_cars}")
    print(f"Total Skins: {total_skins}")

    temp_dir = tempfile.mkdtemp()
    print(f"Temp directory: {temp_dir}")

    try:
        processed_skins = 0

        for car_instance_id, car_info in cars.items():
            base_carid = car_info.get("base_carid", car_instance_id)
            skins = car_info["skins"]

            print(f"\n--- Processing {base_carid} ({len(skins)} skins) ---")

            template_path = os.path.join(os.getcwd(), "vehicles", base_carid, "SKINNAME")

            if not os.path.exists(template_path):
                raise FileNotFoundError(
                    f"No template found for vehicle '{base_carid}'.\n"
                    f"Expected location: {template_path}\n\n"
                    f"Please make sure the vehicle exists in the Developer tab."
                )

            for skin_idx, skin in enumerate(skins):
                skin_id = sanitize_skin_id(skin["name"])
                skin_folder = sanitize_folder_name(skin["name"])
                dds_path = skin["dds_path"]

                print(f"  [{skin_idx + 1}/{len(skins)}] Processing: {skin['name']} -> {skin_folder}")

                dest_skin_folder = os.path.join(
                    temp_dir,
                    "vehicles",
                    base_carid,
                    skin_folder
                )

                def ignore_dds_files(directory, files):
                    return [f for f in files if f.lower().endswith(".dds")]

                shutil.copytree(template_path, dest_skin_folder, ignore=ignore_dds_files)

                dds_filename = os.path.basename(dds_path)
                dds_dest = os.path.join(dest_skin_folder, dds_filename)
                shutil.copy(dds_path, dds_dest)

                dds_identifier = os.path.splitext(dds_filename)[0].split("_")[-1]

                process_jbeam_files(
                    dest_skin_folder,
                    dds_identifier,
                    skin["name"],
                    author
                )

                process_json_files(
                    dest_skin_folder,
                    base_carid,
                    skin_folder,
                    dds_filename,
                    dds_identifier
                )

                if "config_data" in skin:
                    print(f"  → Processing config data...")
                    success = process_skin_config_data(
                        skin,
                        base_carid,
                        skin_folder,
                        temp_dir,
                        template_path
                    )
                    if not success:
                        print(f"  [WARNING] Config data processing failed for {skin_folder}")

                if "material_properties" in skin:
                    print(f"  → Processing material properties...")
                    success = process_material_properties(
                        skin,
                        base_carid,
                        skin_folder,
                        dest_skin_folder
                    )
                    if not success:
                        print(f"  [WARNING] Material properties processing failed for {skin_folder}")

                processed_skins += 1
                if progress_callback:

                    progress = 0.1 + (processed_skins / total_skins) * 0.75
                    progress_callback(progress)

        print(f"\n{'='*60}")
        print(f"VALIDATING AND FIXING DDS FILENAMES")
        print(f"{'='*60}")

        dds_results = process_dds_files_in_mod(temp_dir)

        if dds_results['renamed']:
            print(f"\n✓ Fixed {len(dds_results['renamed'])} DDS filename(s)")

            print(f"\nUpdating skin.materials.json files with new DDS paths...")
            for car_id, skin_folder, old_dds, new_dds in dds_results['renamed']:
                skin_folder_path = os.path.join(temp_dir, "vehicles", car_id, skin_folder)
                materials_json_path = os.path.join(skin_folder_path, "skin.materials.json")

                if os.path.exists(materials_json_path):
                    try:
                        with open(materials_json_path, "r", encoding="utf-8") as f:
                            content = f.read()

                        old_path = f"vehicles/{car_id}/{skin_folder}/{old_dds}"
                        new_path = f"vehicles/{car_id}/{skin_folder}/{new_dds}"

                        if old_path in content:
                            content = content.replace(old_path, new_path)

                            with open(materials_json_path, "w", encoding="utf-8") as f:
                                f.write(content)

                            print(f"  Updated {car_id}/{skin_folder}/skin.materials.json")
                            print(f"    {old_path} -> {new_path}")
                    except Exception as e:
                        print(f"  [WARNING] Failed to update materials.json for {car_id}/{skin_folder}: {e}")

        if dds_results['errors']:
            print(f"\n⚠ {len(dds_results['errors'])} DDS file(s) had errors")

        print(f"\nCreating final ZIP file...")

        if progress_callback:
            progress_callback(0.9)

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

    for root_dir, _, files in os.walk(folder_path):
        for file in files:
            if not file.endswith(".jbeam"):
                continue

            file_path = os.path.join(root_dir, file)

            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            content = re.sub(
                r'"([^"]+_skin_)[^"]*("\s*:\s*\{)',
                rf'"\g<1>{dds_identifier}\g<2>',
                content
            )

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

            content = re.sub(
                r'"([^"]+_skin_)skinname"',
                rf'"\g<1>{dds_identifier}"',
                content,
                flags=re.IGNORECASE
            )

            content = re.sub(
                r'("globalSkin"\s*:\s*")[^"]*(")',
                rf'\g<1>{dds_identifier}\g<2>',
                content,
                flags=re.IGNORECASE
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

                    if "Stages" in material_data and isinstance(material_data["Stages"], list):
                        stages = material_data["Stages"]

                        if len(stages) > 1 and isinstance(stages[1], dict):
                            stage2 = stages[1]
                            if "baseColorMap" in stage2:
                                old_path = stage2["baseColorMap"]

                                if "skinname" in old_path.lower():

                                    new_path = re.sub(r'/skinname/', f'/{skin_folder_name}/', old_path, flags=re.IGNORECASE)
                                    new_path = re.sub(r'_skin_skinname\.dds', f'_skin_{dds_identifier}.dds', new_path, flags=re.IGNORECASE)
                                    print(f"[DEBUG] Replaced skinname placeholder in baseColorMap for {material_key}:")
                                else:

                                    new_path = f"vehicles/{vehicle_id}/{skin_folder_name}/{dds_filename}"
                                    print(f"[DEBUG] Updated Stage 2 baseColorMap in {material_key}:")

                                stage2["baseColorMap"] = new_path
                                print(f"[DEBUG]   From: {old_path}")
                                print(f"[DEBUG]   To:   {new_path}")

                content = json.dumps(data, indent=2)

            except json.JSONDecodeError:

                print(f"[DEBUG] JSON parse failed for {file_path}, using regex fallback")
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

            def replace_skin_ref(match):
                return f'"{match.group(1)}{dds_identifier}"'

            content = re.sub(
                r'"([^"]+\.skin\.)[^"]+"',
                replace_skin_ref,
                content
            )

            def replace_skin_name(match):
                return f'{match.group(1)}{dds_identifier}"'

            content = re.sub(
                r'("name"\s*:\s*"[^"]+\.skin\.)[^"]+"',
                replace_skin_name,
                content
            )
            content = re.sub(
                r'("mapTo"\s*:\s*"[^"]+\.skin\.)[^"]+"',
                replace_skin_name,
                content
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

            content = re.sub(
                r'/skinname/',
                f'/{skin_folder_name}/',
                content,
                flags=re.IGNORECASE
            )
            content = re.sub(
                r'_skin_skinname\.dds',
                f'_skin_{dds_identifier}.dds',
                content,
                flags=re.IGNORECASE
            )

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)