"""
Core Developer Module - Vehicle File Processing
"""
import os
import shutil
from typing import Optional

from utils.file_ops import (
    create_vehicle_folders,
    create_variant_folders,
    delete_vehicle_folders,
    delete_variant_folders,
    edit_material_json,
    edit_jbeam_material,
    add_vehicle_to_json,
    remove_vehicle_from_json,
    add_variant_to_json,
    remove_variant_from_json,
    VEHICLE_FOLDER
)


def process_custom_vehicle(
    carid: str,
    carname: str,
    json_path: str,
    jbeam_path: str,
    image_path: Optional[str] = None
) -> bool:

    print(f"[DEBUG] process_custom_vehicle called")
    print(f"[DEBUG] \n{'='*60}")
    print(f"[DEBUG] PROCESSING VEHICLE: {carname} ({carid})")
    print(f"[DEBUG] {'='*60}")
    
    try:
        # Step 1: Validate input files
        print(f"[DEBUG] Step 1: Validating input files...")
        
        if not os.path.exists(json_path):
            print(f"[ERROR] JSON file not found: {json_path}")
            return False
        print(f"[DEBUG]   ✓ JSON file exists: {json_path}")
        
        if not os.path.exists(jbeam_path):
            print(f"[ERROR] JBEAM file not found: {jbeam_path}")
            return False
        print(f"[DEBUG]   ✓ JBEAM file exists: {jbeam_path}")
        
        if image_path:
            if os.path.exists(image_path):
                if image_path.lower().endswith(('.jpg', '.jpeg')):
                    print(f"[DEBUG]   ✓ Preview image exists: {image_path}")
                else:
                    print(f"[WARNING] Image file is not a JPG, skipping: {image_path}")
                    image_path = None
            else:
                print(f"[WARNING] Image file not found: {image_path}")
                image_path = None
        else:
            print(f"[DEBUG]   ℹ No preview image provided")
        
        print(f"\n[DEBUG] Step 2: Creating vehicle folder structure...")
        print(f"[DEBUG]   Target: vehicles/{carid}/SKINNAME")
        
        try:
            create_vehicle_folders(carid)
            print(f"[DEBUG]   ✓ Vehicle folders created")
        except Exception as e:
            print(f"[ERROR] Failed to create vehicle folders: {e}")
            return False
        
        car_folder = os.path.join(VEHICLE_FOLDER, carid)
        skinname_folder = os.path.join(car_folder, "SKINNAME")
        
        if not os.path.exists(skinname_folder):
            print(f"[ERROR] SKINNAME folder was not created: {skinname_folder}")
            return False
        
        # Step 3: Process JSON file
        print(f"\n[DEBUG] Step 3: Processing JSON file...")
        try:
            edit_material_json(json_path, skinname_folder, carid)
            print(f"[DEBUG]   ✓ JSON file processed and saved")
        except Exception as e:
            print(f"[ERROR] Failed to process JSON file: {e}")
            import traceback
            traceback.print_exc()
            delete_vehicle_folders(carid)
            return False
        
        # Step 4: Process JBEAM file
        print(f"\n[DEBUG] Step 4: Processing JBEAM file...")
        try:
            edit_jbeam_material(jbeam_path, skinname_folder, carid)
            print(f"[DEBUG]   ✓ JBEAM file processed and saved")
        except Exception as e:
            print(f"[ERROR] Failed to process JBEAM file: {e}")
            import traceback
            traceback.print_exc()
            delete_vehicle_folders(carid)
            return False
        
        # Step 5: Copy preview image if provided
        if image_path:
            print(f"\n[DEBUG] Step 5: Copying preview image...")
            try:
                preview_folder = os.path.join("gui", "images", "vehicles", carid)
                os.makedirs(preview_folder, exist_ok=True)
                image_target = os.path.join(preview_folder, "default.jpg")
                shutil.copy2(image_path, image_target)
                print(f"[DEBUG]   ✓ Preview image copied to: {image_target}")
            except Exception as e:
                print(f"[WARNING] Failed to copy preview image (non-critical): {e}")
        else:
            print(f"\n[DEBUG] Step 5: Skipping preview image (none provided)")
        
        print(f"\n[DEBUG] {'='*60}")
        print(f"[DEBUG] ✓ SUCCESS: Vehicle {carid} processed successfully!")
        print(f"[DEBUG] {'='*60}\n")
        
        try:
            add_vehicle_to_json(carid, carname)
            print(f"[DEBUG] ✓ Vehicle saved to added_vehicles.json")
        except Exception as e:
            print(f"[WARNING] Failed to save to JSON (non-critical): {e}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Unexpected error processing vehicle files: {e}")
        import traceback
        traceback.print_exc()
        try:
            delete_vehicle_folders(carid)
            print(f"[DEBUG] Cleaned up partial vehicle files")
        except:
            pass
        return False


def process_custom_variant(
    carid: str,
    variant_suffix: str,
    json_path: str,
    jbeam_path: str,
    image_path: Optional[str] = None
) -> bool:
    """
    Add a custom body variant template (e.g. SKINNAMEBOX) for an existing vehicle.

    Creates  vehicles/{carid}/SKINNAME{SUFFIX.upper()}/
    with the processed materials.json and .jbeam, then records the variant
    in the __variants__ section of added_vehicles.json so it survives restarts.

    Args:
        carid:          Vehicle ID (must already exist as a built-in or custom vehicle)
        variant_suffix: Suffix appended to SKINNAME, e.g. "box", "ambulance"
        json_path:      Path to the template materials.json
        jbeam_path:     Path to the template .jbeam
        image_path:     Optional preview .jpg path (saved as gui/images/vehicles/{carid}/{suffix}.jpg)

    Returns:
        True on success, False otherwise.
    """
    suffix_upper = variant_suffix.strip().upper()
    suffix_lower = variant_suffix.strip().lower()

    print(f"[DEBUG] process_custom_variant called")
    print(f"[DEBUG] {'='*60}")
    print(f"[DEBUG] PROCESSING VARIANT: {carid} / SKINNAME{suffix_upper}")
    print(f"[DEBUG] {'='*60}")

    if not suffix_upper:
        print(f"[ERROR] variant_suffix is empty")
        return False

    try:
        # Step 1: Validate inputs
        print(f"[DEBUG] Step 1: Validating input files...")

        if not os.path.exists(json_path):
            print(f"[ERROR] JSON file not found: {json_path}")
            return False
        print(f"[DEBUG]   ✓ JSON file exists: {json_path}")

        if not os.path.exists(jbeam_path):
            print(f"[ERROR] JBEAM file not found: {jbeam_path}")
            return False
        print(f"[DEBUG]   ✓ JBEAM file exists: {jbeam_path}")

        if image_path:
            if os.path.exists(image_path):
                if image_path.lower().endswith(('.jpg', '.jpeg')):
                    print(f"[DEBUG]   ✓ Preview image exists: {image_path}")
                else:
                    print(f"[WARNING] Image not a JPG, skipping: {image_path}")
                    image_path = None
            else:
                print(f"[WARNING] Image file not found: {image_path}")
                image_path = None

        # Step 2: Create variant folder  vehicles/{carid}/SKINNAME{SUFFIX}
        print(f"\n[DEBUG] Step 2: Creating variant folder structure...")
        try:
            create_variant_folders(carid, suffix_upper)
            print(f"[DEBUG]   ✓ Variant folders created")
        except Exception as e:
            print(f"[ERROR] Failed to create variant folders: {e}")
            return False

        variant_folder = os.path.join(VEHICLE_FOLDER, carid, f"SKINNAME{suffix_upper}")
        if not os.path.exists(variant_folder):
            print(f"[ERROR] Variant folder was not created: {variant_folder}")
            return False

        # Step 3: Process JSON
        print(f"\n[DEBUG] Step 3: Processing JSON file...")
        try:
            edit_material_json(json_path, variant_folder, carid)
            print(f"[DEBUG]   ✓ JSON processed and saved")
        except Exception as e:
            print(f"[ERROR] Failed to process JSON file: {e}")
            import traceback
            traceback.print_exc()
            delete_variant_folders(carid, suffix_upper)
            return False

        # Step 4: Process JBEAM
        print(f"\n[DEBUG] Step 4: Processing JBEAM file...")
        try:
            edit_jbeam_material(jbeam_path, variant_folder, carid)
            print(f"[DEBUG]   ✓ JBEAM processed and saved")
        except Exception as e:
            print(f"[ERROR] Failed to process JBEAM file: {e}")
            import traceback
            traceback.print_exc()
            delete_variant_folders(carid, suffix_upper)
            return False

        # Step 5: Copy preview image
        if image_path:
            print(f"\n[DEBUG] Step 5: Copying preview image...")
            try:
                preview_folder = os.path.join("gui", "images", "vehicles", carid)
                os.makedirs(preview_folder, exist_ok=True)
                image_target = os.path.join(preview_folder, f"{suffix_lower}.jpg")
                shutil.copy2(image_path, image_target)
                print(f"[DEBUG]   ✓ Preview image copied to: {image_target}")
            except Exception as e:
                print(f"[WARNING] Failed to copy preview image (non-critical): {e}")
        else:
            print(f"\n[DEBUG] Step 5: Skipping preview image (none provided)")

        print(f"\n[DEBUG] {'='*60}")
        print(f"[DEBUG] ✓ SUCCESS: Variant {carid}/SKINNAME{suffix_upper} processed!")
        print(f"[DEBUG] {'='*60}\n")

        try:
            add_variant_to_json(carid, suffix_lower)
            print(f"[DEBUG] ✓ Variant saved to added_vehicles.json")
        except Exception as e:
            print(f"[WARNING] Failed to save variant to JSON (non-critical): {e}")

        return True

    except Exception as e:
        print(f"[ERROR] Unexpected error processing variant: {e}")
        import traceback
        traceback.print_exc()
        try:
            delete_variant_folders(carid, suffix_upper)
            print(f"[DEBUG] Cleaned up partial variant files")
        except:
            pass
        return False


def delete_custom_variant(carid: str, variant_suffix: str) -> bool:
    """
    Delete a custom body variant and remove it from added_vehicles.json.

    Args:
        carid:          Vehicle ID
        variant_suffix: Suffix used when the variant was created (lowercase)

    Returns:
        True on success, False otherwise.
    """
    suffix_upper = variant_suffix.strip().upper()
    suffix_lower = variant_suffix.strip().lower()

    print(f"[DEBUG] delete_custom_variant called: {carid}/SKINNAME{suffix_upper}")
    try:
        delete_variant_folders(carid, suffix_upper)
        print(f"[DEBUG] ✓ Variant folders deleted")

        remove_variant_from_json(carid, suffix_lower)
        print(f"[DEBUG] ✓ Variant removed from JSON")

        # Also remove the preview image if it exists
        preview_path = os.path.join(
            "gui", "images", "vehicles", carid, f"{suffix_lower}.jpg"
        )
        if os.path.exists(preview_path):
            try:
                os.remove(preview_path)
                print(f"[DEBUG] ✓ Preview image removed")
            except Exception as e:
                print(f"[WARNING] Could not remove preview image: {e}")

        print(f"[DEBUG] ✓ Variant {carid}/{suffix_lower} deleted successfully")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to delete variant {carid}/{suffix_lower}: {e}")
        return False


def delete_custom_vehicle(carid: str) -> bool:
    """Delete a custom vehicle and all its files."""
    print(f"[DEBUG] delete_custom_vehicle called")
    try:
        print(f"[DEBUG] Deleting custom vehicle: {carid}")
        delete_vehicle_folders(carid)
        print(f"[DEBUG] ✓ Vehicle folders deleted")
        remove_vehicle_from_json(carid)
        print(f"[DEBUG] ✓ Vehicle removed from JSON")
        print(f"[DEBUG] ✓ Vehicle {carid} deleted successfully")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to delete vehicle {carid}: {e}")
        return False


def get_vehicle_folder_path(carid: str) -> Optional[str]:
    vehicle_folder = os.path.join(VEHICLE_FOLDER, carid)
    if os.path.exists(vehicle_folder):
        return vehicle_folder
    return None


def validate_vehicle_files(carid: str) -> bool:
    vehicle_folder = get_vehicle_folder_path(carid)
    if not vehicle_folder:
        return False
    skinname_folder = os.path.join(vehicle_folder, "SKINNAME")
    if not os.path.exists(skinname_folder):
        return False
    jbeam_files = [f for f in os.listdir(skinname_folder) if f.endswith('.jbeam')]
    return bool(jbeam_files)


def list_custom_vehicles() -> list:
    if not os.path.exists(VEHICLE_FOLDER):
        return []
    vehicles = []
    for item in os.listdir(VEHICLE_FOLDER):
        item_path = os.path.join(VEHICLE_FOLDER, item)
        if os.path.isdir(item_path):
            skinname_path = os.path.join(item_path, "SKINNAME")
            if os.path.exists(skinname_path):
                vehicles.append(item)
    return vehicles