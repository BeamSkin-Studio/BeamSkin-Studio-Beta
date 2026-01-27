# file_ops.py
# Complete file operations module for BeamNG Skin Studio


import os
import shutil
import tempfile
import zipfile
import getpass
import re

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def sanitize_skin_id(name):
    """
    Convert skin name to valid ID format.
    Example: "My Cool Skin" -> "my_cool_skin"
    """
    return name.lower().replace(" ", "_")

def sanitize_mod_name(name):
    """
    Clean mod name for file system use.
    Removes spaces and strips whitespace.
    """
    return name.strip().replace(" ", "_")

def get_beamng_mods_path():
    """
    Get the BeamNG.drive mods folder path from settings.
    Falls back to default path if not configured.
    
    Returns: Path to BeamNG mods folder
    """
    # Try to get configured path from settings
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
    
    # Fallback to default path
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
    """
    Create a ZIP file from a directory.
    
    Args:
        source_dir: Directory to zip
        zip_path: Path where ZIP file should be created
    """
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root_dir, _, files in os.walk(source_dir):
            for file in files:
                full_path = os.path.join(root_dir, file)
                relative_path = os.path.relpath(full_path, source_dir)
                zipf.write(full_path, relative_path)

# =============================================================================
# CONFIG DATA PROCESSING
# =============================================================================

def update_info_json_fields(json_path, config_type, config_name):
    """
    Update the 'Config Type' and 'Configuration' fields in the info JSON file using Regex.
    This preserves comments and handles existing values.
    
    Args:
        json_path: Path to the info JSON file
        config_type: Value for "Config Type" field (e.g., "Police", "Factory")
        config_name: Value for "Configuration" field (e.g., "Highway Patrol Unit 23")
    """
    try:
        print(f"[DEBUG] Updating info JSON fields in: {os.path.basename(json_path)}")
        
        with open(json_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Update "Config Type"
        config_type_pattern = r'("Config Type"\s*:\s*")[^"]*(")'
        if re.search(config_type_pattern, content):
            content = re.sub(config_type_pattern, rf'\g<1>{config_type}\g<2>', content)
            print(f"[DEBUG]   ✓ Set Config Type to: {config_type}")
        else:
            print(f"[WARNING]   'Config Type' key not found")
        
        # Update "Configuration" - NOW USES CUSTOM NAME
        configuration_pattern = r'("Configuration"\s*:\s*")[^"]*(")'
        if re.search(configuration_pattern, content):
            content = re.sub(configuration_pattern, rf'\g<1>{config_name}\g<2>', content)
            print(f"[DEBUG]   ✓ Set Configuration to: {config_name}")
        else:
            print(f"[WARNING]   'Configuration' key not found")
        
        # Write back to file
        with open(json_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to update info JSON fields: {e}")
        return False

def process_skin_config_data(skin_data, base_carid, skin_name, temp_mod_root, template_path):
    """
    Process config data for a skin. 
    Copies .pc, .jpg, and generates info_skinname.json in vehicles/<carid>/
    NOW USES custom configuration name from user input
    """
    if "config_data" not in skin_data:
        return True
    
    config_data = skin_data["config_data"]
    config_type = config_data.get("config_type", "Factory")
    config_name = config_data.get("config_name", skin_data.get("name", skin_name))  # NEW: Use custom name
    pc_path = config_data.get("pc_path")
    jpg_path = config_data.get("jpg_path")
    
    print(f"[DEBUG] ===== Processing config data for {skin_name} =====")
    print(f"[DEBUG]   Config Type: {config_type}")
    print(f"[DEBUG]   Config Name (in-game): {config_name}")  # NEW: Show custom name
    print(f"[DEBUG]   .pc file: {pc_path}")
    print(f"[DEBUG]   .jpg file: {jpg_path}")
    print(f"[DEBUG]   Template path: {template_path}")
    print(f"[DEBUG]   Template exists: {os.path.exists(template_path)}")
    
    try:
        # Destination: vehicles/<carid>/
        vehicle_root = os.path.join(temp_mod_root, "vehicles", base_carid)
        os.makedirs(vehicle_root, exist_ok=True)
        print(f"[DEBUG]   Vehicle root: {vehicle_root}")
        
        # 1. Copy and Rename .pc file
        if pc_path and os.path.exists(pc_path):
            dest_pc = os.path.join(vehicle_root, f"{skin_name}.pc")
            shutil.copy2(pc_path, dest_pc)
            print(f"[DEBUG]   ✓ Exported .pc: {dest_pc}")
        elif pc_path:
            print(f"[WARNING]   .pc file not found: {pc_path}")

        # 2. Copy and Rename .jpg file
        if jpg_path and os.path.exists(jpg_path):
            dest_jpg = os.path.join(vehicle_root, f"{skin_name}.jpg")
            shutil.copy2(jpg_path, dest_jpg)
            print(f"[DEBUG]   ✓ Exported .jpg: {dest_jpg}")
        elif jpg_path:
            print(f"[WARNING]   .jpg file not found: {jpg_path}")

        # 3. Handle info_skinname.json
        print(f"[DEBUG]   Searching for info template...")
        
        # The info file is in vehicles/<carid>/, not in vehicles/<carid>/SKINNAME/
        # So we need to go up one level from template_path
        vehicle_template_root = os.path.dirname(template_path)
        
        # Look for the base info.json in the vehicle root folder
        source_info_file = None
        
        # First check if vehicle template root exists
        if not os.path.exists(vehicle_template_root):
            print(f"[ERROR]   Vehicle template root does not exist: {vehicle_template_root}")
            return False
        
        print(f"[DEBUG]   Vehicle template root: {vehicle_template_root}")
        
        # List all files in vehicle root for debugging
        print(f"[DEBUG]   Files in vehicle root:")
        for f in os.listdir(vehicle_template_root):
            print(f"[DEBUG]     - {f}")
        
        # Check for standard names
        for filename in ["info.json", "info_template.json"]:
            potential_path = os.path.join(vehicle_template_root, filename)
            if os.path.exists(potential_path):
                source_info_file = potential_path
                print(f"[DEBUG]   Found info file: {filename}")
                break
        
        # If no specific name found, grab the first .json starting with 'info'
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
            
            # Verify the file was created
            if os.path.exists(dest_info):
                print(f"[DEBUG]   ✓ File copied successfully")
                
                # Edit the "Config Type" and "Configuration" fields inside the newly created file
                # Use custom config_name instead of skin_display_name
                result = update_info_json_fields(dest_info, config_type, config_name)
                
                if result:
                    print(f"[DEBUG]   ✓ FINAL: Exported info_{skin_name}.json")
                    print(f"[DEBUG]   ✓ Set Configuration to: '{config_name}'")  # NEW: Confirm custom name
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

# =============================================================================
# SINGLE SKIN GENERATION (LEGACY)
# =============================================================================

def generate_mod(
    mod_name,
    vehicle_id,
    skin_display_name,
    dds_path,
    output_path=None,
    progress_callback=None,
    author=None
):
    """Legacy function for single skin generation"""
    
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

# =============================================================================
# MULTI-SKIN GENERATION
# =============================================================================

def generate_multi_skin_mod(
    project_data,
    output_path=None,
    progress_callback=None
):
    """
    Generate a mod with multiple cars and multiple skins per car.
    """
    print(f"\n{'='*60}")
    print(f"MULTI-SKIN MOD GENERATION")
    print(f"{'='*60}")
    
    # Extract project data
    mod_name = sanitize_mod_name(project_data["mod_name"])
    author = project_data.get("author", "Unknown")
    cars = project_data["cars"]
    
    # Calculate totals
    total_cars = len(cars)
    total_skins = sum(len(car_info['skins']) for car_info in cars.values())
    
    print(f"Mod Name: {mod_name}")
    print(f"Author: {author}")
    print(f"Total Cars: {total_cars}")
    print(f"Total Skins: {total_skins}")
    
    # Create temporary directory
    temp_dir = tempfile.mkdtemp()
    print(f"Temp directory: {temp_dir}")
    
    try:
        processed_skins = 0
        
        # Process each car
        for car_instance_id, car_info in cars.items():
            base_carid = car_info.get("base_carid", car_instance_id)
            skins = car_info["skins"]
            
            print(f"\n--- Processing {base_carid} ({len(skins)} skins) ---")
            
            # Find template folder
            template_path = os.path.join(os.getcwd(), "vehicles", base_carid, "SKINNAME")
            
            if not os.path.exists(template_path):
                raise FileNotFoundError(
                    f"No template found for vehicle '{base_carid}'.\n"
                    f"Expected location: {template_path}\n\n"
                    f"Please make sure the vehicle exists in the Developer tab."
                )
            
            # Process each skin for this car
            for skin_idx, skin in enumerate(skins):
                skin_id = sanitize_skin_id(skin["name"])
                dds_path = skin["dds_path"]
                
                print(f"  [{skin_idx + 1}/{len(skins)}] Processing: {skin['name']} -> {skin_id}")
                
                # Create destination folder
                dest_skin_folder = os.path.join(
                    temp_dir,
                    "vehicles",
                    base_carid,
                    skin_id
                )
                
                # Copy template folder (exclude existing .dds files)
                def ignore_dds_files(directory, files):
                    return [f for f in files if f.lower().endswith(".dds")]
                
                shutil.copytree(template_path, dest_skin_folder, ignore=ignore_dds_files)
                
                # Copy DDS file
                dds_filename = os.path.basename(dds_path)
                dds_dest = os.path.join(dest_skin_folder, dds_filename)
                shutil.copy(dds_path, dds_dest)
                
                # Extract skin identifier from DDS filename
                dds_identifier = os.path.splitext(dds_filename)[0].split("_")[-1]
                
                # Process JBEAM files
                process_jbeam_files(
                    dest_skin_folder,
                    dds_identifier,
                    skin["name"],  # Use original display name
                    author
                )
                
                # Process JSON files
                process_json_files(
                    dest_skin_folder,
                    base_carid,
                    skin_id,
                    dds_filename,
                    dds_identifier
                )
                
                # Process config data (if present)
                if "config_data" in skin:
                    print(f"  → Processing config data...")
                    success = process_skin_config_data(
                        skin,
                        base_carid,
                        skin_id,
                        temp_dir,
                        template_path
                    )
                    if not success:
                        print(f"  [WARNING] Config data processing failed for {skin_id}")
                
                # Update progress
                processed_skins += 1
                if progress_callback:
                    # Progress: 10% to 85% for skin processing
                    progress = 0.1 + (processed_skins / total_skins) * 0.75
                    progress_callback(progress)
        
        # Create ZIP file
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
        
        # List all files being zipped for verification
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
        # Clean up temporary directory
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

# =============================================================================
# FILE PROCESSING FUNCTIONS
# =============================================================================

def process_jbeam_files(folder_path, dds_identifier, skin_display_name, author):
    """
    Process all JBEAM files in the folder.
    Updates skin references, author, and display name.
    """
    for root_dir, _, files in os.walk(folder_path):
        for file in files:
            if not file.endswith(".jbeam"):
                continue
            
            file_path = os.path.join(root_dir, file)
            
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Update author
            content = re.sub(
                r'("authors"\s*:\s*")[^"]*(")',
                rf'\g<1>{author}\g<2>',
                content
            )
            
            # Update skin display name
            content = re.sub(
                r'("name"\s*:\s*")[^"]*(")',
                rf'\g<1>{skin_display_name}\g<2>',
                content
            )
            
            # Update first skin reference
            def replace_first_skin_key(match):
                return f'"{match.group(1)}{dds_identifier}":'
            
            content = re.sub(
                r'"([^"]*_)[^"]+":',
                replace_first_skin_key,
                content,
                count=1
            )
            
            # Update globalSkin
            content = re.sub(
                r'("globalSkin"\s*:\s*")[^"]*(")',
                rf'\g<1>{dds_identifier}\g<2>',
                content
            )
            
            # Update _extra.skin references
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
    """
    Process all JSON files in the folder.
    Updates skin references and texture paths.
    Skips info_*.json files to avoid conflicts.
    """
    for root_dir, _, files in os.walk(folder_path):
        for file in files:
            if not file.endswith(".json") or file.startswith("info"):
                continue
            
            file_path = os.path.join(root_dir, file)
            
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Update generic .skin. references
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
            
            # Update _extra.skin references
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
            
            # Update baseColorMap path
            baseColorMap_replacement = f'"baseColorMap": "vehicles/{vehicle_id}/{skin_folder_name}/{dds_filename}"'
            content = re.sub(
                r'"baseColorMap"\s*:\s*"[^"]+\.dds"',
                baseColorMap_replacement,
                content
            )
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)