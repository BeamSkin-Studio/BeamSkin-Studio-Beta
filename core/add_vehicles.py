import os
import shutil
from typing import Optional

from utils.file_ops import (
    create_vehicle_folders,
    delete_vehicle_folders,
    edit_material_json,
    edit_jbeam_material,
    edit_info_json,
    add_vehicle_to_json,
    remove_vehicle_from_json,
)
from core.settings import get_vehicles_dir, get_vehicle_previews_dir

try:
    from core.config import VEHICLE_IDS, is_rebadge_suffix
except ImportError as _exc:
    print(f"[DEBUG] _pipe_tmp.py: import failed ({_exc}), using fallback")
    VEHICLE_IDS = {}
    def is_rebadge_suffix(_c, _s):
        return False


def _is_builtin_carid(carid: str) -> bool:
    result = carid.strip().lower() in {k.lower() for k in VEHICLE_IDS}
    print(f"[DEBUG] _is_builtin_carid: carid={carid!r} -> {result}")
    return result


def _variant_already_exists(carid: str, variant_suffix: str) -> bool:
    if is_rebadge_suffix(carid, variant_suffix):
        print(f"[DEBUG] _variant_already_exists: {carid!r}+{variant_suffix!r} is a "
              f"registered rebadge -> True")
        return True
    existing = os.path.join(get_vehicles_dir(), carid, f"SKINNAME{variant_suffix.upper()}")
    result = os.path.isdir(existing)
    print(f"[DEBUG] _variant_already_exists: checking {existing!r} -> {result}")
    return result


def process_custom_vehicle(
    carid: str,
    carname: str,
    json_path: str,
    jbeam_path: str,
    image_path: Optional[str] = None,
    info_json_path: Optional[str] = None
) -> bool:
    print(f"[DEBUG] \n{'='*60}")
    print(f"[DEBUG] PROCESSING VEHICLE: {carname} ({carid})")
    print(f"[DEBUG] {'='*60}")
    print(f"[DEBUG] process_custom_vehicle: json_path={json_path!r} jbeam_path={jbeam_path!r} "
          f"image_path={image_path!r} info_json_path={info_json_path!r}")

    if _is_builtin_carid(carid):
        print(f"[ERROR] '{carid}' is a built-in vehicle that ships with the "
              f"program — refusing to overwrite it. Import as a variant "
              f"instead if you meant to add a body variant.")
        return False

    try:
        if not os.path.exists(json_path):
            print(f"[ERROR] JSON file not found: {json_path}")
            return False

        if not os.path.exists(jbeam_path):
            print(f"[ERROR] JBEAM file not found: {jbeam_path}")
            return False

        if image_path:
            if os.path.exists(image_path):
                if not image_path.lower().endswith(('.jpg', '.jpeg')):
                    print(f"[WARNING] Image is not a JPG, skipping: {image_path}")
                    image_path = None
            else:
                print(f"[WARNING] Image file not found: {image_path}")
                image_path = None

        try:
            create_vehicle_folders(carid)
        except Exception as e:
            print(f"[ERROR] Failed to create vehicle folders: {e}")
            return False

        car_folder = os.path.join(get_vehicles_dir(), carid)
        skinname_folder = os.path.join(car_folder, "SKINNAME")
        print(f"[DEBUG] process_custom_vehicle: car_folder={car_folder!r} "
              f"skinname_folder={skinname_folder!r}")

        if not os.path.exists(skinname_folder):
            print(f"[ERROR] SKINNAME folder was not created: {skinname_folder}")
            return False

        try:
            edit_material_json(json_path, skinname_folder, carid)
        except Exception as e:
            print(f"[ERROR] Failed to process JSON file: {e}")
            import traceback
            traceback.print_exc()
            delete_vehicle_folders(carid)
            return False

        try:
            edit_jbeam_material(jbeam_path, skinname_folder, carid)
        except Exception as e:
            print(f"[ERROR] Failed to process JBEAM file: {e}")
            import traceback
            traceback.print_exc()
            delete_vehicle_folders(carid)
            return False

        try:
            edit_info_json(info_json_path, car_folder)
        except Exception as e:
            print(f"[WARNING] Failed to create info_skinname.json: {e}")

        if image_path:
            try:
                preview_folder = os.path.join(get_vehicle_previews_dir(), carid)
                os.makedirs(preview_folder, exist_ok=True)
                shutil.copy2(image_path, os.path.join(preview_folder, "default.jpg"))
            except Exception as e:
                print(f"[WARNING] Failed to copy preview image: {e}")

        print(f"[DEBUG] ✓ SUCCESS: Vehicle {carid} processed successfully!")

        try:
            add_vehicle_to_json(carid, carname)
        except Exception as e:
            print(f"[WARNING] Failed to save to JSON: {e}")

        return True

    except Exception as e:
        print(f"[ERROR] Unexpected error processing vehicle files: {e}")
        import traceback
        traceback.print_exc()
        try:
            delete_vehicle_folders(carid)
        except Exception as _exc:
            print(f"[WARNING] process_custom_vehicle: {type(_exc).__name__}: {_exc}")
        return False


def delete_custom_vehicle(carid: str) -> bool:
    if _is_builtin_carid(carid):
        print(f"[ERROR] '{carid}' is a built-in vehicle — refusing to delete its folder.")
        return False
    try:
        print(f"[DEBUG] Deleting custom vehicle: {carid}")
        delete_vehicle_folders(carid)
        remove_vehicle_from_json(carid)
        print(f"[DEBUG] ✓ Vehicle {carid} deleted successfully")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to delete vehicle {carid}: {e}")
        return False


def process_custom_variant(
    carid: str,
    variant_suffix: str,
    json_path: str,
    jbeam_path: str,
    image_path: Optional[str] = None,
    info_json_path: Optional[str] = None,
) -> bool:
    from utils.file_ops import (
        create_variant_folders,
        delete_variant_folders,
        edit_material_json,
        edit_jbeam_material,
        edit_info_json,
        add_variant_to_json,
    )

    suffix_upper = variant_suffix.upper()
    suffix_lower = variant_suffix.lower()

    print(f"[DEBUG] {'='*60}")
    print(f"[DEBUG] PROCESSING VARIANT: {carid} + {suffix_upper}")
    print(f"[DEBUG] {'='*60}")
    print(f"[DEBUG] process_custom_variant: json_path={json_path!r} jbeam_path={jbeam_path!r} "
          f"image_path={image_path!r} info_json_path={info_json_path!r}")

    if _variant_already_exists(carid, suffix_lower):
        print(f"[ERROR] '{carid}+{suffix_upper}' already exists (either a "
              f"built-in vehicle variant or a previously added one) — "
              f"refusing to overwrite it.")
        return False

    try:
        if not os.path.exists(json_path):
            print(f"[ERROR] JSON file not found: {json_path}")
            return False
        if not os.path.exists(jbeam_path):
            print(f"[ERROR] JBEAM file not found: {jbeam_path}")
            return False
        if image_path and not os.path.exists(image_path):
            print(f"[WARNING] Image file not found, skipping: {image_path}")
            image_path = None

        try:
            create_variant_folders(carid, suffix_upper)
        except Exception as e:
            print(f"[ERROR] Failed to create variant folders: {e}")
            return False

        variant_folder = os.path.join(get_vehicles_dir(), carid, f"SKINNAME{suffix_upper}")
        if not os.path.exists(variant_folder):
            print(f"[ERROR] Variant folder was not created: {variant_folder}")
            return False
        print(f"[DEBUG] process_custom_variant: variant_folder={variant_folder!r}")

        try:
            edit_material_json(json_path, variant_folder, carid)
        except Exception as e:
            print(f"[ERROR] Failed to process JSON file: {e}")
            import traceback; traceback.print_exc()
            delete_variant_folders(carid, suffix_upper)
            return False

        try:
            edit_jbeam_material(jbeam_path, variant_folder, carid)
        except Exception as e:
            print(f"[ERROR] Failed to process JBEAM file: {e}")
            import traceback; traceback.print_exc()
            delete_variant_folders(carid, suffix_upper)
            return False

        try:
            car_folder = os.path.join(get_vehicles_dir(), carid)
            edit_info_json(info_json_path, car_folder, output_name=f"info_skinname_{suffix_lower}.json")
        except Exception as e:
            print(f"[WARNING] Failed to create info_skinname_{suffix_lower}.json: {e}")

        if image_path and image_path.lower().endswith(('.jpg', '.jpeg')):
            try:
                preview_folder = os.path.join(get_vehicle_previews_dir(), carid)
                os.makedirs(preview_folder, exist_ok=True)
                shutil.copy2(image_path, os.path.join(preview_folder, f"default_{suffix_lower}.jpg"))
            except Exception as e:
                print(f"[WARNING] Failed to copy preview image: {e}")

        try:
            add_variant_to_json(carid, suffix_lower)
        except Exception as e:
            print(f"[WARNING] Failed to save variant to JSON: {e}")

        print(f"[DEBUG] ✓ SUCCESS: Variant {carid}+{suffix_upper} processed successfully!")
        return True

    except Exception as e:
        print(f"[ERROR] Unexpected error processing variant: {e}")
        import traceback; traceback.print_exc()
        try:
            from utils.file_ops import delete_variant_folders as _dvf
            _dvf(carid, suffix_upper)
        except Exception as _exc:
            print(f"[WARNING] process_custom_variant: {type(_exc).__name__}: {_exc}")
        return False


def delete_custom_variant(carid: str, suffix: str) -> bool:
    from utils.file_ops import delete_variant_folders, remove_variant_from_json

    suffix_upper = suffix.upper()
    suffix_lower = suffix.lower()

    print(f"[DEBUG] delete_custom_variant: carid={carid!r} suffix={suffix!r}")

    if is_rebadge_suffix(carid, suffix_lower):
        print(f"[ERROR] '{carid}+{suffix_upper}' is a built-in rebadge vehicle "
              f"that ships with the program — refusing to delete it.")
        return False

    try:
        delete_variant_folders(carid, suffix_upper)
        remove_variant_from_json(carid, suffix_lower)
        print(f"[DEBUG] ✓ Variant {carid}+{suffix_upper} deleted successfully")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to delete variant {carid}+{suffix}: {e}")
        return False


def process_multiple_vehicles(
    selections: list,
    known_carids: Optional[set] = None,
) -> dict:
    print(f"[DEBUG] Batch import: {len(selections)} item(s)")

    succeeded: list = []
    failed:    list = []
    skipped:   list = []

    for idx, sel in enumerate(selections):
        item_type = sel.get("type", "")
        carid     = sel.get("carid", "").strip()

        if not carid or item_type not in ("vehicle", "variant"):
            label = carid or f"item[{idx}]"
            print(f"[WARNING] Skipping {label}: unknown type or missing carid")
            skipped.append(label)
            continue

        json_path      = sel.get("json_path")  or ""
        jbeam_path     = sel.get("jbeam_path") or ""
        image_path     = sel.get("image_path") or None
        info_json_path = sel.get("info_json_path") or None

        if not json_path or not jbeam_path:
            label = carid if item_type == "vehicle" else f"{carid}+{sel.get('suffix', '?')}"
            print(f"[WARNING] Skipping {label}: missing json_path or jbeam_path")
            skipped.append(label)
            continue

        if item_type == "vehicle" and _is_builtin_carid(carid):
            print(f"[WARNING] Skipping {carid}: built-in vehicle, cannot overwrite")
            skipped.append(carid)
            continue

        if item_type == "variant":
            suffix_check = sel.get("suffix", "").strip().lower()
            if suffix_check and _variant_already_exists(carid, suffix_check):
                label = f"{carid}+{suffix_check}"
                print(f"[WARNING] Skipping {label}: variant already exists")
                skipped.append(label)
                continue

        if item_type == "vehicle":
            carname = sel.get("carname") or carid.replace("_", " ").title()
            print(f"\n[DEBUG] Importing vehicle {idx + 1}/{len(selections)}: {carid}")
            ok = process_custom_vehicle(
                carid=carid, carname=carname,
                json_path=json_path, jbeam_path=jbeam_path, image_path=image_path,
                info_json_path=info_json_path,
            )
            (succeeded if ok else failed).append(carid)

        elif item_type == "variant":
            suffix = sel.get("suffix", "").strip()
            if not suffix:
                print(f"[WARNING] Skipping variant for {carid}: missing suffix")
                skipped.append(f"{carid}+?")
                continue

            label = f"{carid}+{suffix}"
            print(f"\n[DEBUG] Importing variant {idx + 1}/{len(selections)}: {label}")
            ok = process_custom_variant(
                carid=carid, variant_suffix=suffix,
                json_path=json_path, jbeam_path=jbeam_path, image_path=image_path,
                info_json_path=info_json_path,
            )
            (succeeded if ok else failed).append(label)

    print(f"\n[DEBUG] {'='*60}")
    print(f"[DEBUG] BATCH COMPLETE — OK: {len(succeeded)}  Failed: {len(failed)}  Skipped: {len(skipped)}")
    if succeeded: print(f"[DEBUG]   ✓ {', '.join(succeeded)}")
    if failed:    print(f"[DEBUG]   ✗ {', '.join(failed)}")
    if skipped:   print(f"[DEBUG]   — {', '.join(skipped)}")
    print(f"[DEBUG] {'='*60}\n")

    return {"succeeded": succeeded, "failed": failed, "skipped": skipped}


def build_selections_from_scan(
    vehicles: list,
    variants: list,
    selected_carids: Optional[set] = None,
    selected_variant_keys: Optional[set] = None,
) -> list:
    selections: list = []

    print(f"[DEBUG] build_selections_from_scan: vehicles={len(vehicles)} variants={len(variants)} "
          f"selected_carids={selected_carids} selected_variant_keys={selected_variant_keys}")

    for v in vehicles:
        if not v.ready:
            continue
        if selected_carids is not None and v.carid not in selected_carids:
            continue
        selections.append({
            "type": "vehicle", "carid": v.carid, "carname": v.display_name,
            "json_path": v.json_path, "jbeam_path": v.jbeam_path, "image_path": v.image_path,
            "info_json_path": v.info_json_path,
        })

    for var in variants:
        if not var.ready:
            continue
        key = f"{var.carid}__{var.suffix}"
        if selected_variant_keys is not None and key not in selected_variant_keys:
            continue
        selections.append({
            "type": "variant", "carid": var.carid, "suffix": var.suffix,
            "json_path": var.json_path, "jbeam_path": var.jbeam_path, "image_path": var.image_path,
            "info_json_path": var.info_json_path,
        })

    print(f"[DEBUG] build_selections_from_scan: built {len(selections)} selection(s)")
    return selections


def delete_multiple_vehicles(carids: list) -> dict:
    succeeded: list = []
    failed:    list = []
    for carid in carids:
        ok = delete_custom_vehicle(carid)
        (succeeded if ok else failed).append(carid)
    print(f"[DEBUG] Batch delete: {len(succeeded)} OK, {len(failed)} failed")
    return {"succeeded": succeeded, "failed": failed}


def delete_multiple_variants(variant_pairs: list) -> dict:
    succeeded: list = []
    failed:    list = []
    for carid, suffix in variant_pairs:
        label = f"{carid}+{suffix}"
        ok = delete_custom_variant(carid, suffix)
        (succeeded if ok else failed).append(label)
    print(f"[DEBUG] Batch delete variants: {len(succeeded)} OK, {len(failed)} failed")
    return {"succeeded": succeeded, "failed": failed}


def get_vehicle_folder_path(carid: str) -> Optional[str]:
    vehicle_folder = os.path.join(get_vehicles_dir(), carid)
    result = vehicle_folder if os.path.exists(vehicle_folder) else None
    print(f"[DEBUG] get_vehicle_folder_path: carid={carid!r} -> {result!r}")
    return result


def validate_vehicle_files(carid: str) -> bool:
    vehicle_folder = get_vehicle_folder_path(carid)
    if not vehicle_folder:
        print(f"[DEBUG] Vehicle folder not found: {carid}")
        return False

    skinname_folder = os.path.join(vehicle_folder, "SKINNAME")
    if not os.path.exists(skinname_folder):
        print(f"[DEBUG] SKINNAME folder not found for {carid}")
        return False

    if not os.path.exists(os.path.join(skinname_folder, "skin.materials.json")):
        print("[DEBUG] Missing required file: skin.materials.json")
        return False

    jbeam_files = [f for f in os.listdir(skinname_folder) if f.endswith('.jbeam')]
    if not jbeam_files:
        print(f"[DEBUG] No JBEAM files found for {carid}")
        return False

    print(f"[DEBUG] ✓ Vehicle {carid} has all required files")
    return True


def list_custom_vehicles() -> list:
    vehicle_folder = get_vehicles_dir()
    print(f"[DEBUG] list_custom_vehicles: scanning {vehicle_folder!r}")
    if not os.path.exists(vehicle_folder):
        print("[DEBUG] list_custom_vehicles: folder does not exist, returning []")
        return []

    vehicles = []
    for item in os.listdir(vehicle_folder):
        item_path = os.path.join(vehicle_folder, item)
        if os.path.isdir(item_path):
            if os.path.exists(os.path.join(item_path, "SKINNAME")):
                vehicles.append(item)

    print(f"[DEBUG] list_custom_vehicles: found {len(vehicles)} vehicle(s): {vehicles}")
    return vehicles


if __name__ == "__main__":
    print("Core Developer Module - Vehicle File Processing")
    vehicles = list_custom_vehicles()
    if vehicles:
        print(f"\nFound {len(vehicles)} custom vehicle(s):")
        for vehicle in vehicles:
            print(f"  - {vehicle}")
    else:
        print("\nNo custom vehicles found")
