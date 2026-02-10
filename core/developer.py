"""
Core Developer Module - Vehicle File Processing
"""
import os
import shutil
from typing import Optional

from utils.file_ops import (
    create_vehicle_folders,
    delete_vehicle_folders,
    edit_material_json,
    edit_jbeam_material,
    add_vehicle_to_json,
    remove_vehicle_from_json,
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
        print(f"[DEBUG]   Source: {json_path}")
        print(f"[DEBUG]   Target folder: {skinname_folder}")
        
        try:
            edit_material_json(json_path, skinname_folder, carid)
            print(f"[DEBUG]   ✓ JSON file processed and saved")
        except Exception as e:
            print(f"[ERROR] Failed to process JSON file: {e}")
            import traceback
            traceback.print_exc()
            # Clean up on failure
            delete_vehicle_folders(carid)
            return False
        
        # Step 4: Process JBEAM file
        print(f"\n[DEBUG] Step 4: Processing JBEAM file...")
        print(f"[DEBUG]   Source: {jbeam_path}")
        print(f"[DEBUG]   Target folder: {skinname_folder}")
        
        try:
            edit_jbeam_material(jbeam_path, skinname_folder, carid)
            print(f"[DEBUG]   ✓ JBEAM file processed and saved")
        except Exception as e:
            print(f"[ERROR] Failed to process JBEAM file: {e}")
            import traceback
            traceback.print_exc()
            # Clean up on failure
            delete_vehicle_folders(carid)
            return False
        
        # Step 5: Copy preview image if provided
        if image_path:
            print(f"\n[DEBUG] Step 5: Copying preview image...")
            print(f"[DEBUG]   Source: {image_path}")
            
            try:
                preview_folder = os.path.join("imagesforgui", "vehicles", carid)
                os.makedirs(preview_folder, exist_ok=True)
                
                image_target = os.path.join(preview_folder, "default.jpg")
                shutil.copy2(image_path, image_target)
                
                print(f"[DEBUG]   ✓ Preview image copied to: {image_target}")
            except Exception as e:
                print(f"[WARNING] Failed to copy preview image (non-critical): {e}")
        else:
            print(f"\n[DEBUG] Step 5: Skipping preview image (none provided)")
        
        # Success!
        print(f"\n[DEBUG] {'='*60}")
        print(f"[DEBUG] ✓ SUCCESS: Vehicle {carid} processed successfully!")
        print(f"[DEBUG] {'='*60}\n")
        
        # Add vehicle to added_vehicles.json
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
        
        # Try to clean up on failure
        try:
            delete_vehicle_folders(carid)
            print(f"[DEBUG] Cleaned up partial vehicle files")
        except:
            pass
        
        return False


def delete_custom_vehicle(carid: str) -> bool:
    """
    Delete a custom vehicle and all its files
    
    Args:
        carid: Vehicle ID
    
    Returns:
        True if successful, False otherwise
    """
    print(f"[DEBUG] delete_custom_vehicle called")
    try:
        print(f"[DEBUG] Deleting custom vehicle: {carid}")
        
        # Delete vehicle folders
        delete_vehicle_folders(carid)
        print(f"[DEBUG] ✓ Vehicle folders deleted")
        
        # Remove from JSON
        remove_vehicle_from_json(carid)
        print(f"[DEBUG] ✓ Vehicle removed from JSON")
        
        print(f"[DEBUG] ✓ Vehicle {carid} deleted successfully")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to delete vehicle {carid}: {e}")
        return False


def get_vehicle_folder_path(carid: str) -> Optional[str]:
    """
    Get the path to a vehicle's folder
    
    Args:
        carid: Vehicle ID
    
    Returns:
        Path to vehicle folder, or None if not found
    """
    print(f"[DEBUG] get_vehicle_folder_path called")
    vehicle_folder = os.path.join(VEHICLE_FOLDER, carid)
    
    if os.path.exists(vehicle_folder):
        return vehicle_folder
    return None


def validate_vehicle_files(carid: str) -> bool:
    """
    Validate that a vehicle has all required files
    
    Args:
        carid: Vehicle ID
    
    Returns:
        True if valid, False otherwise
    """
    print(f"[DEBUG] validate_vehicle_files called")
    vehicle_folder = get_vehicle_folder_path(carid)
    if not vehicle_folder:
        print(f"[DEBUG] Vehicle folder not found: {carid}")
        return False
    
    # Check for SKINNAME folder
    skinname_folder = os.path.join(vehicle_folder, "SKINNAME")
    if not os.path.exists(skinname_folder):
        print(f"[DEBUG] SKINNAME folder not found for {carid}")
        return False
    
    # Check for required files in SKINNAME folder
    required_files = [
        "skin.materials.json"
    ]
    
    for filename in required_files:
        filepath = os.path.join(skinname_folder, filename)
        if not os.path.exists(filepath):
            print(f"[DEBUG] Missing required file: {filename}")
            return False
    
    # Check for at least one JBEAM file
    jbeam_files = [f for f in os.listdir(skinname_folder) if f.endswith('.jbeam')]
    if not jbeam_files:
        print(f"[DEBUG] No JBEAM files found for {carid}")
        return False
    
    print(f"[DEBUG] ✓ Vehicle {carid} has all required files")
    return True


def list_custom_vehicles() -> list:
    """
    List all custom vehicles in the vehicles folder
    
    Returns:
        List of vehicle IDs (carids)
    """
    print(f"[DEBUG] list_custom_vehicles called")
    if not os.path.exists(VEHICLE_FOLDER):
        return []
    
    vehicles = []
    for item in os.listdir(VEHICLE_FOLDER):
        item_path = os.path.join(VEHICLE_FOLDER, item)
        if os.path.isdir(item_path):
            # Check if it has a SKINNAME folder
            skinname_path = os.path.join(item_path, "SKINNAME")
            if os.path.exists(skinname_path):
                vehicles.append(item)
    
    return vehicles


if __name__ == "__main__":
    # Test code
    print("Core Developer Module - Vehicle File Processing")
    print("=" * 60)
    print("This module integrates with utils.file_ops for processing")
    print("vehicle files and adding them to BeamSkin Studio")
    print("=" * 60)
    
    # List existing vehicles
    vehicles = list_custom_vehicles()
    if vehicles:
        print(f"\nFound {len(vehicles)} custom vehicle(s):")
        for vehicle in vehicles:
            print(f"  - {vehicle}")
    else:
        print("\nNo custom vehicles found")