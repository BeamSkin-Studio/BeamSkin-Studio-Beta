
import os
import shutil
import tempfile
import zipfile
import getpass
import re
import json
from typing import Optional

from core.colorable_ops import (
    generate_colorable_skin,
    generate_colorable_skin_variant,
    sanitize_skin_id,
    sanitize_folder_name,
    _apply_skin_reference_regexes,
)

try:
    from core.settings import get_vehicles_dir
except ImportError as _exc:
    print(f"[DEBUG] _pipe_tmp.py: import failed ({_exc}), using fallback")
    def get_vehicles_dir():
        return os.path.join(os.getcwd(), 'vehicles')


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
    return dest_filename


def _reset_copy_dedup_cache(dest_folder: Optional[str] = None) -> None:
    if dest_folder is None:
        _copied_file_cache.clear()
    else:
        _copied_file_cache.pop(dest_folder, None)


def sanitize_mod_name(name: str) -> str:
    result = name.strip().replace(" ", "_")
    print(f"[DEBUG] sanitize_mod_name: {name!r} -> {result!r}")
    return result


def get_beamng_mods_path():
    try:
        from core.settings import get_mods_folder_path
        configured = get_mods_folder_path()
        if configured and os.path.exists(configured):
            print(f"[DEBUG] Using configured mods path: {configured}")
            return configured
    except ImportError as _exc:
        print(f"[WARNING] get_beamng_mods_path: {type(_exc).__name__}: {_exc}")

    username = getpass.getuser()
    default  = os.path.join(
        "C:\\Users", username, "AppData", "Local",
        "BeamNG.drive", "0.33", "mods"
    )
    print(f"[DEBUG] Using default mods path: {default}")
    return default


def _get_vehicle_roots() -> list:
    try:
        from core.settings import get_bundle_path
    except ImportError as _exc:
        print(f"[WARNING] _get_vehicle_roots: {type(_exc).__name__}: {_exc}")
        def get_bundle_path():
            return os.getcwd()
    roots = [get_vehicles_dir(), os.path.join(get_bundle_path(), "vehicles")]
    print(f"[DEBUG] _get_vehicle_roots: {roots}")
    return roots


def _find_normal_template(base_carid: str) -> str:
    print(f"[DEBUG] _find_normal_template: base_carid={base_carid!r}")
    for root in _get_vehicle_roots():
        candidate = os.path.join(root, base_carid, "SKINNAME")
        if os.path.isdir(candidate):
            print(f"[DEBUG] _find_normal_template: found {candidate!r}")
            return candidate
    fallback = os.path.join(_get_vehicle_roots()[0], base_carid, "SKINNAME")
    print(f"[DEBUG] _find_normal_template: not found in any root, fallback={fallback!r}")
    return fallback


def _find_variant_template(base_carid: str, variant_suffix: str) -> str:
    target_lower = f"skinname{variant_suffix.lower()}"
    print(f"[DEBUG] _find_variant_template: base_carid={base_carid!r} "
          f"variant_suffix={variant_suffix!r} target_lower={target_lower!r}")

    for root in _get_vehicle_roots():
        vehicles_dir = os.path.join(root, base_carid)
        if os.path.isdir(vehicles_dir):
            for entry in os.listdir(vehicles_dir):
                if entry.lower() == target_lower and os.path.isdir(
                    os.path.join(vehicles_dir, entry)
                ):
                    found = os.path.join(vehicles_dir, entry)
                    print(f"[DEBUG] Found variant template: {found}")
                    return found

    fallback = os.path.join(
        _get_vehicle_roots()[0], base_carid, f"SKINNAME{variant_suffix.upper()}"
    )
    print(f"[DEBUG] Variant template fallback: {fallback}")
    return fallback


def zip_folder(source_dir, zip_path):
    print(f"[DEBUG] zip_folder: source_dir={source_dir!r} zip_path={zip_path!r}")
    file_count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root_dir, _, files in os.walk(source_dir):
            for file in files:
                full_path = os.path.join(root_dir, file)
                rel_path  = os.path.relpath(full_path, source_dir)
                zipf.write(full_path, rel_path)
                file_count += 1
    print(f"[DEBUG] zip_folder: wrote {file_count} file(s) to {zip_path!r}")


import datetime as _dt

_BSS_VERSION = "BeamSkin Studio"

def _write_bss_watermark(skin_folder: str, mod_name: str, author: str) -> None:
    print(f"[DEBUG] _write_bss_watermark: skin_folder={skin_folder!r} mod_name={mod_name!r} "
          f"author={author!r}")
    timestamp = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    comment_block = (
        f"// Generated by {_BSS_VERSION}\n"
        f"// https://beamskin-studio.github.io/BeamSkin-Studio-Beta/\n"
        f"// Mod    : {mod_name}\n"
        f"// Author : {author}\n"
        f"// Date   : {timestamp}\n"
    )

    readme_text = (
        f"Generated by {_BSS_VERSION}\n"
        f"https://beamskin-studio.github.io/BeamSkin-Studio-Beta/\n"
        f"\n"
        f"Mod    : {mod_name}\n"
        f"Author : {author}\n"
        f"Date   : {timestamp}\n"
    )
    try:
        with open(os.path.join(skin_folder, "README.txt"), "w", encoding="utf-8") as fh:
            fh.write(readme_text)
        print(f"[DEBUG] _write_bss_watermark: wrote README.txt to {skin_folder!r}")
    except Exception as e:
        print(f"[WARNING] Could not write README.txt watermark: {e}")

    stamped = 0
    for fn in os.listdir(skin_folder):
        if not (fn.endswith(".json") or fn.endswith(".jbeam")):
            continue
        fp = os.path.join(skin_folder, fn)
        try:
            with open(fp, "r", encoding="utf-8") as fh:
                original = fh.read()
            with open(fp, "w", encoding="utf-8") as fh:
                fh.write(comment_block + original)
            stamped += 1
            print(f"[DEBUG] BSS watermark comment added to {fn}")
        except Exception as e:
            print(f"[WARNING] Could not prepend watermark to {fn}: {e}")
    print(f"[DEBUG] _write_bss_watermark: stamped {stamped} json/jbeam file(s)")


def validate_and_fix_dds_filenames(skin_folder_path, car_id):
    print(f"[DEBUG] validate_and_fix_dds_filenames: skin_folder_path={skin_folder_path!r} "
          f"car_id={car_id!r}")
    results = {"renamed": [], "already_correct": [], "errors": []}
    if not os.path.exists(skin_folder_path):
        print("[DEBUG] validate_and_fix_dds_filenames: folder does not exist")
        results["errors"].append((skin_folder_path, "Folder does not exist"))
        return results

    correct_pattern = re.compile(rf'^{re.escape(car_id)}_skin_.*\.dds$', re.IGNORECASE)

    for filename in os.listdir(skin_folder_path):
        if not filename.lower().endswith(".dds"):
            continue
        file_path = os.path.join(skin_folder_path, filename)
        if correct_pattern.match(filename):
            results["already_correct"].append(filename)
            continue

        if "_skin_" in filename.lower():
            parts     = filename.split("_skin_")
            skin_name = parts[-1].replace(".dds", "").replace(".DDS", "") if len(parts) >= 2 else None
        elif filename.lower().startswith("skin_"):
            skin_name = filename[5:].replace(".dds", "").replace(".DDS", "")
        elif "skin" in filename.lower():
            idx       = filename.lower().find("skin")
            skin_name = filename[idx + 4:].replace(".dds", "").replace(".DDS", "").lstrip("_")
        else:
            skin_name = filename.replace(".dds", "").replace(".DDS", "")

        print(f"[DEBUG] validate_and_fix_dds_filenames: {filename!r} -> extracted skin_name={skin_name!r}")

        if not skin_name:
            results["errors"].append((filename, "Could not extract skin name"))
            continue

        new_filename = f"{car_id}_skin_{skin_name}.dds"
        new_file_path = os.path.join(skin_folder_path, new_filename)
        if os.path.exists(new_file_path) and new_file_path != file_path:
            results["errors"].append((filename, f"Target already exists: {new_filename}"))
            continue
        try:
            os.rename(file_path, new_file_path)
            results["renamed"].append((filename, new_filename))
            print(f"[DEBUG] Renamed: {filename} -> {new_filename}")
        except Exception as e:
            print(f"[WARNING] validate_and_fix_dds_filenames: {type(e).__name__}: {e}")
            results['errors'].append((filename, f'Rename failed: {e}'))

    print(f"[DEBUG] validate_and_fix_dds_filenames: renamed={len(results['renamed'])} "
          f"already_correct={len(results['already_correct'])} errors={len(results['errors'])}")
    return results


def process_dds_files_in_mod(temp_mod_root):
    print(f"[DEBUG] process_dds_files_in_mod: temp_mod_root={temp_mod_root!r}")
    totals = {"renamed": [], "already_correct": [], "errors": [], "skins_processed": 0}
    vehicles_path = os.path.join(temp_mod_root, "vehicles")
    if not os.path.exists(vehicles_path):
        print("[DEBUG] process_dds_files_in_mod: vehicles_path does not exist")
        return totals

    for car_id in os.listdir(vehicles_path):
        car_path = os.path.join(vehicles_path, car_id)
        if not os.path.isdir(car_path):
            continue
        for item in os.listdir(car_path):
            item_path = os.path.join(car_path, item)
            if not os.path.isdir(item_path):
                continue
            res = validate_and_fix_dds_filenames(item_path, car_id)
            totals["renamed"].extend([(car_id, item, o, n) for o, n in res["renamed"]])
            totals["already_correct"].extend([(car_id, item, f) for f in res["already_correct"]])
            totals["errors"].extend([(car_id, item, f, e) for f, e in res["errors"]])
            totals["skins_processed"] += 1

    print(f"[DEBUG] process_dds_files_in_mod: skins_processed={totals['skins_processed']} "
          f"renamed={len(totals['renamed'])} errors={len(totals['errors'])}")
    return totals


def update_info_json_fields(json_path, config_type, config_name, extra_fields=None):
    print(f"[DEBUG] update_info_json_fields: json_path={json_path!r} config_type={config_type!r} "
          f"config_name={config_name!r} extra_fields={list((extra_fields or {}).keys())}")
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            content = f.read()

        for pattern, value, label in [
            (r'("Config Type"\s*:\s*")[^"]*(")',   config_type, "Config Type"),
            (r'("Configuration"\s*:\s*")[^"]*(")', config_name, "Configuration"),
        ]:
            if re.search(pattern, content):
                content = re.sub(pattern, rf'\g<1>{value}\g<2>', content)
                print(f"[DEBUG]   ✓ Set {label} to: {value}")
            else:
                print(f"[WARNING]   '{label}' key not found in {os.path.basename(json_path)}")

        for key, value in (extra_fields or {}).items():
            esc_key = re.escape(key)
            if isinstance(value, str):
                pattern = rf'("{esc_key}"\s*:\s*")[^"]*(")'
                if re.search(pattern, content):
                    content = re.sub(pattern, rf'\g<1>{value}\g<2>', content)
                    print(f"[DEBUG]   ✓ Set {key} to: {value!r}")
                else:
                    print(f"[WARNING]   '{key}' key not found in {os.path.basename(json_path)}")
            else:
                pattern = rf'("{esc_key}"\s*:\s*)-?\d+(?:\.\d+)?'
                if re.search(pattern, content):
                    content = re.sub(pattern, rf'\g<1>{value}', content)
                    print(f"[DEBUG]   ✓ Set {key} to: {value}")
                else:
                    print(f"[WARNING]   '{key}' key not found in {os.path.basename(json_path)}")

        with open(json_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[DEBUG] update_info_json_fields: write successful to {json_path!r}")
        return True
    except Exception as e:
        print(f"[ERROR] update_info_json_fields: {e}")
        return False


def process_skin_config_data(skin_data, base_carid, skin_name, temp_mod_root, template_path):
    if "config_data" not in skin_data:
        print(f"[DEBUG] process_skin_config_data: no config_data for {skin_name!r}, skipping")
        return True

    cd          = skin_data["config_data"]
    config_type = cd.get("config_type", "Factory")
    config_name = cd.get("config_name", skin_name)
    pc_path     = cd.get("pc_file_path")
    jpg_path    = cd.get("jpg_file_path")

    print(f"[DEBUG] ===== Config data for {skin_name} =====")
    print(f"[DEBUG] process_skin_config_data: config_type={config_type!r} "
          f"config_name={config_name!r} pc_path={pc_path!r} jpg_path={jpg_path!r}")

    has_errors = False
    if pc_path and not os.path.exists(pc_path):
        print(f"[ERROR] .pc not found: {pc_path}"); has_errors = True
    if jpg_path and not os.path.exists(jpg_path):
        print(f"[ERROR] .jpg not found: {jpg_path}"); has_errors = True
    if has_errors:
        return False

    try:
        vehicle_root = os.path.join(temp_mod_root, "vehicles", base_carid)
        os.makedirs(vehicle_root, exist_ok=True)

        if pc_path:
            shutil.copy2(pc_path,  os.path.join(vehicle_root, f"{skin_name}.pc"))
            print("[DEBUG]   ✓ Copied .pc")
        if jpg_path:
            shutil.copy2(jpg_path, os.path.join(vehicle_root, f"{skin_name}.jpg"))
            print("[DEBUG]   ✓ Copied .jpg")

        vehicle_template_root = os.path.dirname(template_path)
        source_info = None
        for fn in ["info.json", "info_template.json"]:
            p = os.path.join(vehicle_template_root, fn)
            if os.path.exists(p):
                source_info = p; break
        if not source_info:
            for fn in os.listdir(vehicle_template_root):
                if fn.startswith("info") and fn.endswith(".json"):
                    source_info = os.path.join(vehicle_template_root, fn); break

        print(f"[DEBUG] process_skin_config_data: vehicle_template_root={vehicle_template_root!r} "
              f"source_info={source_info!r}")

        if not source_info:
            print(f"[ERROR] No info.json template in {vehicle_template_root}")
            return False

        dest_info = os.path.join(vehicle_root, f"info_{skin_name}.json")
        shutil.copy2(source_info, dest_info)
        update_info_json_fields(dest_info, config_type, config_name, cd.get("info_data"))
        print("[DEBUG] ===== Config data complete =====")
        return True

    except Exception as e:
        import traceback
        print(f"[ERROR] process_skin_config_data: {e}")
        traceback.print_exc()
        return False


def process_material_properties(skin_data, base_carid, skin_id, dest_skin_folder):
    if "material_properties" not in skin_data:
        print(f"[DEBUG] process_material_properties: no material_properties for {skin_id!r}, skipping")
        return True

    material_props = skin_data["material_properties"]
    print(f"[DEBUG] ===== Processing material properties for {skin_id} =====")
    print(f"[DEBUG] process_material_properties: base_carid={base_carid!r} "
          f"dest_skin_folder={dest_skin_folder!r} props={material_props}")

    mat_files = []
    for root, _, files in os.walk(dest_skin_folder):
        for fn in files:
            if fn.endswith(".materials.json") or fn == "materials.json":
                mat_files.append(os.path.join(root, fn))

    if not mat_files:
        print(f"[WARNING] No .materials.json found in {dest_skin_folder}")
        return False

    print(f"[DEBUG] process_material_properties: found {len(mat_files)} materials.json file(s)")

    try:
        failed_files = []

        for mat_file in mat_files:
            with open(mat_file, "r", encoding="utf-8") as f:
                content = f.read()
            content = re.sub(r",(\s*[}\]])", r"\1", content)
            try:
                mat_data = json.loads(content)
            except json.JSONDecodeError as e:
                print(f"[ERROR] JSON decode error in {os.path.basename(mat_file)}: {e}")
                failed_files.append(os.path.basename(mat_file))
                continue

            modified = False
            for template_name, stages in material_props.items():
                prefix  = (template_name.split(".skin.")[0]
                           if ".skin." in template_name else template_name)
                actual  = next(
                    (k for k in mat_data if k.startswith(f"{prefix}.skin.")), None
                )
                if not actual or "Stages" not in mat_data[actual]:
                    continue
                for stage_str, props in stages.items():
                    try:
                        idx = int(stage_str)
                    except (ValueError, TypeError) as _exc:
                        print(f"[WARNING] process_material_properties: {type(_exc).__name__}: {_exc}")
                        continue
                    if idx >= len(mat_data[actual]["Stages"]):
                        continue
                    for k, v in props.items():
                        old = mat_data[actual]["Stages"][idx].get(k, "NOT_FOUND")
                        mat_data[actual]["Stages"][idx][k] = v
                        modified = True
                        print(f"[DEBUG]   ✓ {actual}.Stages[{idx}].{k}: {old} → {v}")

            if modified:
                with open(mat_file, "w", encoding="utf-8") as f:
                    json.dump(mat_data, f, indent=2)
                print(f"[DEBUG]   Saved {os.path.basename(mat_file)}")

        print("[DEBUG] ===== Material properties complete =====")

        if failed_files:
            print(f"[WARNING] process_material_properties: "
                  f"{len(failed_files)}/{len(mat_files)} materials.json file(s) "
                  f"could not be parsed and were left unmodified: "
                  f"{', '.join(failed_files)}")
            return False

        return True
    except Exception as e:
        import traceback
        print(f"[ERROR] process_material_properties: {e}")
        traceback.print_exc()
        return False


def process_jbeam_files(folder_path, dds_identifier, skin_display_name, author,
                        dds_prefix=None, carid=None):
    if carid is None:
        carid = dds_prefix

    print(f"[DEBUG] process_jbeam_files: folder_path={folder_path!r} dds_identifier={dds_identifier!r} "
          f"skin_display_name={skin_display_name!r} author={author!r} dds_prefix={dds_prefix!r} "
          f"carid={carid!r}")

    processed = 0
    for root_dir, _, files in os.walk(folder_path):
        for file in files:
            if not file.endswith(".jbeam"):
                continue
            file_path = os.path.join(root_dir, file)
            print(f"[DEBUG] process_jbeam_files: processing {file_path!r}")
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            content = re.sub(r'("authors"\s*:\s*")[^"]*(")', rf'\g<1>{author}\g<2>', content)
            content = re.sub(r'("name"\s*:\s*")[^"]*(")', rf'\g<1>{skin_display_name}\g<2>', content)
            if dds_prefix:
                content = re.sub(
                    rf'"({re.escape(dds_prefix)}_skin_)\w*"',
                    rf'"\g<1>{dds_identifier}"',
                    content,
                    flags=re.IGNORECASE,
                )
            else:
                content = re.sub(r'"([^"]+_skin_)SKINNAME\w*"', rf'"\g<1>{dds_identifier}"', content, flags=re.IGNORECASE)
            content = re.sub(r'_skin_SKINNAME\w*', f'_skin_{dds_identifier}', content, flags=re.IGNORECASE)
            content = re.sub(r'("globalSkin"\s*:\s*")[^"]*(")', rf'\g<1>{dds_identifier}\g<2>', content, flags=re.IGNORECASE)
            content = re.sub(r'("skinName"\s*:\s*")[^"]*(")', rf'\g<1>{dds_identifier}\g<2>', content, flags=re.IGNORECASE)

            def _extra(m):      return f'"{m.group(1)}{dds_identifier}"'
            def _extra_name(m): return f'{m.group(1)}{dds_identifier}"'
            content = re.sub(r'"([^"]*_extra\.skin\.)[^"]+"',           _extra,      content)
            content = re.sub(r'("name"\s*:\s*"[^"]*_extra\.skin\.)[^"]+"', _extra_name, content)
            content = re.sub(r'("mapTo"\s*:\s*"[^"]*_extra\.skin\.)[^"]+"',_extra_name, content)

            if carid:
                content = re.sub(r'(?<![a-zA-Z0-9])carid', carid, content, flags=re.IGNORECASE)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            processed += 1

    print(f"[DEBUG] process_jbeam_files: processed {processed} .jbeam file(s)")


def process_json_files(folder_path, vehicle_id, skin_folder_name, dds_filename, dds_identifier):
    print(f"[DEBUG] process_json_files: folder_path={folder_path!r} vehicle_id={vehicle_id!r} "
          f"skin_folder_name={skin_folder_name!r} dds_filename={dds_filename!r} "
          f"dds_identifier={dds_identifier!r}")
    processed = 0
    for root_dir, _, files in os.walk(folder_path):
        for file in files:
            if not file.endswith(".json") or file.startswith("info"):
                continue
            file_path = os.path.join(root_dir, file)
            print(f"[DEBUG] process_json_files: processing {file_path!r}")
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                for mat_key, mat_data in data.items():
                    if not isinstance(mat_data, dict):
                        continue
                    stages = mat_data.get("Stages", [])
                    if len(stages) > 1 and isinstance(stages[1], dict):
                        stage2 = stages[1]
                        if "baseColorMap" in stage2:
                            old = stage2["baseColorMap"]
                            if "SKINNAME" in old.upper():
                                new = re.sub(r'/SKINNAME/', f"/{skin_folder_name}/", old, flags=re.IGNORECASE)
                                new = re.sub(r'_skin_SKINNAME(\.\w+)', f"_skin_{dds_identifier}\\1", new, flags=re.IGNORECASE)
                                new = re.sub(r'(?<![a-zA-Z0-9])carid', vehicle_id, new, flags=re.IGNORECASE)
                            else:
                                new = f"vehicles/{vehicle_id}/{skin_folder_name}/{dds_filename}"
                            stage2["baseColorMap"] = new
                            print(f"[DEBUG] Stage 2 baseColorMap [{mat_key}]: {old} → {new}")

                content = json.dumps(data, indent=2)
            except json.JSONDecodeError as e:
                print(f"[DEBUG] process_json_files: JSON parse failed for {file_path!r}: {e}, "
                      f"falling back to raw text substitution")
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

            content = _apply_skin_reference_regexes(content, dds_identifier)
            content = re.sub(r'/SKINNAME/', f'/{skin_folder_name}/', content, flags=re.IGNORECASE)
            content = re.sub(r'_skin_SKINNAME(\.\w+)', f'_skin_{dds_identifier}\\1', content, flags=re.IGNORECASE)
            content = re.sub(r'(?<![a-zA-Z0-9])carid', vehicle_id, content, flags=re.IGNORECASE)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            processed += 1

    print(f"[DEBUG] process_json_files: processed {processed} json file(s)")


def process_json_files_variant_dds(
    folder_path, vehicle_id, skin_folder_name,
    car_dds_filename,
    var_dds_filename,
    dds_identifier,
    car_skin_folder_name=None,
    variant_suffix="",
):
    car_folder   = car_skin_folder_name or skin_folder_name
    car_dds_path = f"vehicles/{vehicle_id}/{car_folder}/{car_dds_filename}"
    var_dds_path = f"vehicles/{vehicle_id}/{skin_folder_name}/{var_dds_filename}"
    var_prefix   = f"{variant_suffix}.skin."

    print(f"[DEBUG] process_json_files_variant_dds: folder_path={folder_path!r} "
          f"vehicle_id={vehicle_id!r} skin_folder_name={skin_folder_name!r} "
          f"car_dds_path={car_dds_path!r} var_dds_path={var_dds_path!r} var_prefix={var_prefix!r}")

    for root_dir, _, files in os.walk(folder_path):
        for file in files:
            if not file.endswith(".json") or file.startswith("info"):
                continue
            file_path = os.path.join(root_dir, file)
            print(f"[DEBUG] process_json_files_variant_dds: {file_path}")

            with open(file_path, "r", encoding="utf-8") as f:
                raw = f.read()
            raw_clean = re.sub(r",(\s*[}\]])", r"\1", raw)

            try:
                data      = json.loads(raw_clean); parsed_ok = True
            except json.JSONDecodeError:
                print(f"[WARNING] JSON parse failed: {file_path}"); parsed_ok = False

            if parsed_ok:
                for mat_key, mat_data in data.items():
                    if not isinstance(mat_data, dict):
                        continue
                    stages = mat_data.get("Stages", [])
                    if len(stages) < 2 or not isinstance(stages[1], dict):
                        continue

                    is_var   = mat_key.lower().startswith(var_prefix.lower())
                    dds_path = var_dds_path if is_var else car_dds_path
                    label    = "variant body" if is_var else "car body"

                    old = stages[1].get("baseColorMap", "")
                    stages[1]["baseColorMap"] = dds_path
                    print(f"[DEBUG]   '{mat_key}' ({label}) Stage[1].baseColorMap: {old} → {dds_path}")

                content = json.dumps(data, indent=2)
            else:
                content = raw

            content = _apply_skin_reference_regexes(content, dds_identifier)
            content = re.sub(r'/SKINNAME/', f'/{skin_folder_name}/', content, flags=re.IGNORECASE)
            content = re.sub(r'_skin_SKINNAME(\.\w+)', f'_skin_{dds_identifier}\\1', content, flags=re.IGNORECASE)
            content = re.sub(r'(?<![a-zA-Z0-9])carid', vehicle_id, content, flags=re.IGNORECASE)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"[DEBUG] Processed json (variant-DDS): {file_path}")


def _generate_variant_dds_skin(
    template_path,
    dest_skin_folder,
    base_carid,
    variant_suffix,
    skin,
    skin_folder,
    author,
):
    dds_path_1 = skin["dds_path"]
    dds_path_2 = skin.get("dds_path_2", "")

    print(f"[DEBUG] _generate_variant_dds_skin: base_carid={base_carid!r} "
          f"variant_suffix={variant_suffix!r} skin_folder={skin_folder!r} "
          f"dds_path_1={dds_path_1!r} dds_path_2={dds_path_2!r}")

    if not dds_path_1:
        raise ValueError(f"Missing dds_path for variant skin '{skin['name']}'")
    if not dds_path_2:
        raise ValueError(f"Missing dds_path_2 (variant body DDS) for skin '{skin['name']}'")

    def _ignore_dds(d, f):
        return [x for x in f if x.lower().endswith(".dds")]

    if os.path.exists(dest_skin_folder):
        shutil.rmtree(dest_skin_folder)
    _reset_copy_dedup_cache(dest_skin_folder)
    shutil.copytree(template_path, dest_skin_folder, ignore=_ignore_dds)
    print(f"[DEBUG] Variant template copied: {dest_skin_folder}")

    dds_identifier = sanitize_skin_id(skin["name"])
    car_fn = f"{base_carid}_skin_{dds_identifier}.dds"
    var_fn = f"{variant_suffix}_skin_{dds_identifier}.dds"

    car_fn = _copy_dedup(dds_path_1, dest_skin_folder, car_fn)
    var_fn = _copy_dedup(dds_path_2, dest_skin_folder, var_fn)
    print(f"[DEBUG] Copied car-body DDS  : {car_fn}")
    print(f"[DEBUG] Copied variant-body DDS: {var_fn}")

    process_jbeam_files(dest_skin_folder, dds_identifier, skin["name"], author, dds_prefix=base_carid)

    process_json_files_variant_dds(
        dest_skin_folder, base_carid, skin_folder,
        car_fn, var_fn, dds_identifier,
        variant_suffix=variant_suffix,
    )


MAX_TOTAL_LAYERS = 4

_CUSTOM_LAYER_KEY_ORDER = [
    "diffuseMapUseUV",
    "clearCoatFactor",
    "clearCoatRoughnessFactor",
    "metallicFactor",
    "metallicMapUseUV",
    "normalMapUseUV",
    "opacityMapUseUV",
    "retroreflectivity",
    "roughnessFactor",
    "roughnessMapUseUV",
    "emissiveFactor",
    "emissiveMapUseUV",
    "instanceDiffuse",
    "instanceEmissive",
    "colorPaletteMapUseUV",
    "baseColorMap",
    "colorPaletteMap",
    "normalMap",
    "opacityMap",
    "roughnessMap",
    "metallicMap",
    "emissiveMap",
]


def _existing_stage_count(mat_data: dict) -> int:
    count = 0
    for mat_val in mat_data.values():
        if isinstance(mat_val, dict):
            stages = mat_val.get("Stages", [])
            if isinstance(stages, list):
                count = max(count, len(stages))
    print(f"[DEBUG] _existing_stage_count: -> {count}")
    return count


def get_max_custom_layers(dest_skin_folder: str) -> int:
    highest = 0
    for root, _, files in os.walk(dest_skin_folder):
        for fn in files:
            if fn.endswith(".materials.json") or fn == "materials.json":
                fp = os.path.join(root, fn)
                try:
                    with open(fp, "r", encoding="utf-8") as fh:
                        raw = fh.read()
                    raw_clean = re.sub(r",(\s*[}\]])", r"\1", raw)
                    mat_data = json.loads(raw_clean)
                except (json.JSONDecodeError, OSError) as e:
                    print(f"[DEBUG] get_max_custom_layers: could not parse {fp!r}: {e}")
                    continue
                file_count = _existing_stage_count(mat_data)
                print(f"[DEBUG] get_max_custom_layers: {fp} -> {file_count} stage(s)")
                highest = max(highest, file_count)
    if highest == 0:
        highest = 2
        print(f"[DEBUG] get_max_custom_layers: no readable materials.json, defaulting highest={highest}")
    result = max(0, MAX_TOTAL_LAYERS - highest)
    print(f"[DEBUG] get_max_custom_layers: dest_skin_folder={dest_skin_folder!r} "
          f"highest={highest} -> {result}")
    return result


def _copy_layer_textures(layer: dict, layer_idx: int, base_carid: str,
                          skin_folder: str, dest_skin_folder: str,
                          skin_id: str, variant_suffix: str = ""):
    is_colorable = bool(layer.get("is_colorable"))
    prefix = f"{skin_id}_layer{layer_idx}"
    print(f"[DEBUG] _copy_layer_textures: layer_idx={layer_idx} base_carid={base_carid!r} "
          f"skin_id={skin_id!r} variant_suffix={variant_suffix!r} is_colorable={is_colorable}")

    def _dest_ref(fn):
        return f"vehicles/{base_carid}/{skin_folder}/{fn}"

    if is_colorable:
        dm_src = layer.get("data_map_path", "")
        pm_src = layer.get("color_map_path", "")
        if not dm_src or not pm_src:
            print(f"[WARNING] custom layer {layer_idx}: missing colorable body texture(s)")
            return None, None, is_colorable
        dm_fn = f"{prefix}_b.color.png"
        pm_fn = f"{prefix}_cp.color.png"
        dm_fn = _copy_dedup(dm_src, dest_skin_folder, dm_fn)
        pm_fn = _copy_dedup(pm_src, dest_skin_folder, pm_fn)
        ref_body = (_dest_ref(dm_fn), _dest_ref(pm_fn))
        print(f"[DEBUG] _copy_layer_textures: colorable ref_body={ref_body}")

        ref_variant = ref_body
        if variant_suffix:
            dm_src_2 = layer.get("data_map_path_2", "")
            pm_src_2 = layer.get("color_map_path_2", "")
            if dm_src_2 and pm_src_2:
                dm_fn_2 = f"{prefix}_{variant_suffix}_b.color.png"
                pm_fn_2 = f"{prefix}_{variant_suffix}_cp.color.png"
                dm_fn_2 = _copy_dedup(dm_src_2, dest_skin_folder, dm_fn_2)
                pm_fn_2 = _copy_dedup(pm_src_2, dest_skin_folder, pm_fn_2)
                ref_variant = (_dest_ref(dm_fn_2), _dest_ref(pm_fn_2))
                print(f"[DEBUG] _copy_layer_textures: colorable ref_variant={ref_variant}")
        return ref_body, ref_variant, is_colorable

    else:
        dds_src = layer.get("dds_path", "")
        if not dds_src:
            print(f"[WARNING] custom layer {layer_idx}: missing base texture")
            return None, None, is_colorable
        dds_fn = f"{prefix}.dds"
        dds_fn = _copy_dedup(dds_src, dest_skin_folder, dds_fn)
        ref_body = _dest_ref(dds_fn)
        print(f"[DEBUG] _copy_layer_textures: dds ref_body={ref_body}")

        ref_variant = ref_body
        if variant_suffix:
            dds_src_2 = layer.get("dds_path_2", "")
            if dds_src_2:
                dds_fn_2 = f"{prefix}_{variant_suffix}.dds"
                dds_fn_2 = _copy_dedup(dds_src_2, dest_skin_folder, dds_fn_2)
                ref_variant = _dest_ref(dds_fn_2)
                print(f"[DEBUG] _copy_layer_textures: dds ref_variant={ref_variant}")
        return ref_body, ref_variant, is_colorable


def _copy_layer_opacity(layer: dict, layer_idx: int, base_carid: str,
                         skin_folder: str, dest_skin_folder: str,
                         skin_id: str, variant_suffix: str = ""):
    prefix = f"{skin_id}_layer{layer_idx}"
    print(f"[DEBUG] _copy_layer_opacity: layer_idx={layer_idx} base_carid={base_carid!r} "
          f"variant_suffix={variant_suffix!r}")

    def _dest_ref(fn):
        return f"vehicles/{base_carid}/{skin_folder}/{fn}"

    mask_src = layer.get("opacity_map_path", "")
    if not mask_src:
        print("[DEBUG] _copy_layer_opacity: no opacity_map_path, returning (None, None)")
        return None, None

    mask_fn = f"{prefix}_opacity.png"
    mask_fn = _copy_dedup(mask_src, dest_skin_folder, mask_fn)
    ref_body = _dest_ref(mask_fn)
    print(f"[DEBUG] _copy_layer_opacity: ref_body={ref_body}")

    ref_variant = ref_body
    if variant_suffix:
        mask_src_2 = layer.get("opacity_map_path_2", "")
        if mask_src_2:
            mask_fn_2 = f"{prefix}_{variant_suffix}_opacity.png"
            mask_fn_2 = _copy_dedup(mask_src_2, dest_skin_folder, mask_fn_2)
            ref_variant = _dest_ref(mask_fn_2)
            print(f"[DEBUG] _copy_layer_opacity: ref_variant={ref_variant}")
    return ref_body, ref_variant


def _copy_layer_map(layer: dict, layer_idx: int, base_carid: str,
                     skin_folder: str, dest_skin_folder: str,
                     skin_id: str, path_key: str, suffix: str,
                     variant_suffix: str = ""):
    prefix = f"{skin_id}_layer{layer_idx}"
    print(f"[DEBUG] _copy_layer_map: layer_idx={layer_idx} path_key={path_key!r} "
          f"suffix={suffix!r} variant_suffix={variant_suffix!r}")

    def _dest_ref(fn):
        return f"vehicles/{base_carid}/{skin_folder}/{fn}"

    src = layer.get(path_key, "")
    if not src:
        print(f"[DEBUG] _copy_layer_map: no {path_key!r}, returning (None, None)")
        return None, None

    fn = f"{prefix}_{suffix}.png"
    fn = _copy_dedup(src, dest_skin_folder, fn)
    ref_body = _dest_ref(fn)
    print(f"[DEBUG] _copy_layer_map: ref_body={ref_body}")

    ref_variant = ref_body
    if variant_suffix:
        src_2 = layer.get(f"{path_key}_2", "")
        if src_2:
            fn_2 = f"{prefix}_{variant_suffix}_{suffix}.png"
            fn_2 = _copy_dedup(src_2, dest_skin_folder, fn_2)
            ref_variant = _dest_ref(fn_2)
            print(f"[DEBUG] _copy_layer_map: ref_variant={ref_variant}")
    return ref_body, ref_variant


def _copy_layer_normal(layer: dict, layer_idx: int, base_carid: str,
                        skin_folder: str, dest_skin_folder: str,
                        skin_id: str, variant_suffix: str = ""):
    prefix = f"{skin_id}_layer{layer_idx}"
    print(f"[DEBUG] _copy_layer_normal: layer_idx={layer_idx} variant_suffix={variant_suffix!r}")

    def _dest_ref(fn):
        return f"vehicles/{base_carid}/{skin_folder}/{fn}"

    src = layer.get("normal_map_path", "")
    if not src:
        print("[DEBUG] _copy_layer_normal: no normal_map_path, returning (None, None)")
        return None, None

    fn = f"{prefix}_normal.normal.png"
    fn = _copy_dedup(src, dest_skin_folder, fn)
    ref_body = _dest_ref(fn)
    print(f"[DEBUG] _copy_layer_normal: ref_body={ref_body}")

    ref_variant = ref_body
    if variant_suffix:
        src_2 = layer.get("normal_map_path_2", "")
        if src_2:
            fn_2 = f"{prefix}_{variant_suffix}_normal.normal.png"
            fn_2 = _copy_dedup(src_2, dest_skin_folder, fn_2)
            ref_variant = _dest_ref(fn_2)
            print(f"[DEBUG] _copy_layer_normal: ref_variant={ref_variant}")
    return ref_body, ref_variant


def _copy_layer_emissive(layer: dict, layer_idx: int, base_carid: str,
                          skin_folder: str, dest_skin_folder: str,
                          skin_id: str, variant_suffix: str = ""):
    prefix = f"{skin_id}_layer{layer_idx}"
    print(f"[DEBUG] _copy_layer_emissive: layer_idx={layer_idx} variant_suffix={variant_suffix!r}")

    def _dest_ref(fn):
        return f"vehicles/{base_carid}/{skin_folder}/{fn}"

    em_src = layer.get("emissive_dds_path", "")
    if not em_src:
        print("[DEBUG] _copy_layer_emissive: no emissive_dds_path, returning (None, None)")
        return None, None

    em_fn = f"{prefix}_emissive.dds"
    em_fn = _copy_dedup(em_src, dest_skin_folder, em_fn)
    ref_body = _dest_ref(em_fn)
    print(f"[DEBUG] _copy_layer_emissive: ref_body={ref_body}")

    ref_variant = ref_body
    if variant_suffix:
        em_src_2 = layer.get("emissive_dds_path_2", "")
        if em_src_2:
            em_fn_2 = f"{prefix}_{variant_suffix}_emissive.dds"
            em_fn_2 = _copy_dedup(em_src_2, dest_skin_folder, em_fn_2)
            ref_variant = _dest_ref(em_fn_2)
            print(f"[DEBUG] _copy_layer_emissive: ref_variant={ref_variant}")
    return ref_body, ref_variant


def _norm_factor(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        result = int(value) if value == int(value) else value
        return result
    return value


def _build_layer_stage(layer: dict, base_color_ref, opacity_ref, emissive_ref,
                        roughness_ref=None, metallic_ref=None, normal_ref=None) -> dict:
    is_colorable = bool(layer.get("is_colorable"))
    print(f"[DEBUG] _build_layer_stage: is_colorable={is_colorable} "
          f"has_opacity={bool(opacity_ref)} has_normal={bool(normal_ref)} "
          f"has_roughness={bool(roughness_ref)} has_metallic={bool(metallic_ref)} "
          f"glowing={bool(layer.get('glowing'))}")

    stage = {
        "diffuseMapUseUV":         1,
        "clearCoatFactor":         _norm_factor(layer.get("clear_coat_factor", 0.4)),
        "clearCoatRoughnessFactor": _norm_factor(layer.get("clear_coat_roughness_factor", 0.1)),
        "metallicFactor":          _norm_factor(layer.get("metallic_factor", 0.0)),
        "roughnessFactor":         _norm_factor(layer.get("roughness_factor", 0.45)),
        "retroreflectivity":       _norm_factor(layer.get("retroreflectivity", 0.0)),
    }

    if is_colorable:
        data_ref, palette_ref = base_color_ref
        stage["baseColorMap"]         = data_ref
        stage["colorPaletteMap"]      = palette_ref
        stage["colorPaletteMapUseUV"] = 1
    else:
        stage["baseColorMap"] = base_color_ref

    if opacity_ref:
        stage["opacityMap"]       = opacity_ref
        stage["opacityMapUseUV"]  = 1

    if normal_ref:
        stage["normalMap"]      = normal_ref
        stage["normalMapUseUV"] = 1

    if roughness_ref:
        stage["roughnessMap"]      = roughness_ref
        stage["roughnessMapUseUV"] = 1

    if metallic_ref:
        stage["metallicMap"]      = metallic_ref
        stage["metallicMapUseUV"] = 1

    if layer.get("glowing") and emissive_ref:
        stage["emissiveMap"]      = emissive_ref
        stage["emissiveMapUseUV"] = 1
        stage["emissiveFactor"]   = layer.get(
            "emissive_factor", [10.000001, 10.000001, 10.000001]
        )
        stage["instanceDiffuse"]  = True
        stage["instanceEmissive"] = True

    ordered = {k: stage[k] for k in _CUSTOM_LAYER_KEY_ORDER if k in stage}
    ordered.update({k: v for k, v in stage.items() if k not in ordered})
    print(f"[DEBUG] _build_layer_stage: built stage with keys={list(ordered.keys())}")
    return ordered


def _inject_custom_layers(skin_data, base_carid, skin_folder, dest_skin_folder,
                           variant_suffix=""):
    layers = skin_data.get("custom_layers") or []
    if not layers:
        print("[DEBUG] _inject_custom_layers: no custom_layers for skin, skipping")
        return True

    skin_id = sanitize_skin_id(skin_data.get("name", ""))
    is_variant = bool(variant_suffix)
    var_prefix = f"{variant_suffix}.skin."

    print(f"[DEBUG] _inject_custom_layers: base_carid={base_carid!r} skin_id={skin_id!r} "
          f"layer_count={len(layers)} is_variant={is_variant} variant_suffix={variant_suffix!r}")

    per_layer_refs = []
    for idx, layer in enumerate(layers):
        base_body, base_var, is_colorable = _copy_layer_textures(
            layer, idx, base_carid, skin_folder, dest_skin_folder, skin_id, variant_suffix
        )
        if base_body is None:
            print(f"[WARNING] _inject_custom_layers: skipping layer {idx} — no base texture")
            per_layer_refs.append(None)
            continue
        opacity_body, opacity_var = _copy_layer_opacity(
            layer, idx, base_carid, skin_folder, dest_skin_folder, skin_id, variant_suffix
        )
        roughness_body, roughness_var = _copy_layer_map(
            layer, idx, base_carid, skin_folder, dest_skin_folder, skin_id,
            "roughness_map_path", "roughness", variant_suffix
        )
        metallic_body, metallic_var = _copy_layer_map(
            layer, idx, base_carid, skin_folder, dest_skin_folder, skin_id,
            "metallic_map_path", "metallic", variant_suffix
        )
        normal_body, normal_var = _copy_layer_normal(
            layer, idx, base_carid, skin_folder, dest_skin_folder, skin_id, variant_suffix
        )
        emissive_body, emissive_var = (None, None)
        if layer.get("glowing"):
            emissive_body, emissive_var = _copy_layer_emissive(
                layer, idx, base_carid, skin_folder, dest_skin_folder, skin_id, variant_suffix
            )
            if not emissive_body:
                print(f"[WARNING] _inject_custom_layers: layer {idx} has glowing enabled "
                      f"but no emissive map — glow skipped for this layer")

        per_layer_refs.append({
            "body":    (base_body, opacity_body, emissive_body, roughness_body, metallic_body, normal_body),
            "variant": (base_var if is_variant else base_body,
                        opacity_var if is_variant else opacity_body,
                        emissive_var if is_variant else emissive_body,
                        roughness_var if is_variant else roughness_body,
                        metallic_var if is_variant else metallic_body,
                        normal_var if is_variant else normal_body),
        })

    mat_files = []
    for root, _, files in os.walk(dest_skin_folder):
        for fn in files:
            if fn.endswith(".materials.json") or fn == "materials.json":
                mat_files.append(os.path.join(root, fn))

    print(f"[DEBUG] _inject_custom_layers: found {len(mat_files)} materials.json file(s), "
          f"per_layer_refs prepared for {sum(1 for r in per_layer_refs if r)} of "
          f"{len(per_layer_refs)} layer(s)")

    if not mat_files:
        print(f"[WARNING] _inject_custom_layers: no .materials.json in {dest_skin_folder}")
        return False

    failed_files = []

    for mat_file in mat_files:
        with open(mat_file, "r", encoding="utf-8") as fh:
            raw = fh.read()
        raw_clean = re.sub(r",(\s*[}\]])", r"\1", raw)
        try:
            mat_data = json.loads(raw_clean)
        except json.JSONDecodeError as exc:
            print(f"[WARNING] _inject_custom_layers JSON error in {os.path.basename(mat_file)}: {exc}")
            failed_files.append(os.path.basename(mat_file))
            continue

        modified = False
        for mat_key, mat_val in mat_data.items():
            if not isinstance(mat_val, dict):
                continue
            stages = mat_val.get("Stages", [])
            if not isinstance(stages, list) or not stages:
                continue

            is_var_body = mat_key.lower().startswith(var_prefix.lower())
            use_variant = is_var_body and is_variant
            body_key = "variant" if use_variant else "body"
            label     = "variant body" if use_variant else "body"

            room = max(0, MAX_TOTAL_LAYERS - len(stages))
            layers_to_apply = layers[:room] if room < len(layers) else layers
            if room < len(layers):
                print(f"[WARNING] _inject_custom_layers: '{mat_key}' only has room for "
                      f"{room} more layer(s) (cap {MAX_TOTAL_LAYERS}) — "
                      f"{len(layers) - room} layer(s) skipped")

            for idx, layer in enumerate(layers_to_apply):
                refs = per_layer_refs[idx] if idx < len(per_layer_refs) else None
                if not refs:
                    continue
                base_ref, opacity_ref, emissive_ref, roughness_ref, metallic_ref, normal_ref = refs[body_key]

                stage = _build_layer_stage(layer, base_ref, opacity_ref, emissive_ref,
                                            roughness_ref, metallic_ref, normal_ref)
                stages.append(stage)
                modified = True
                print(f"[DEBUG]   ✓ custom layer {idx} ({label}) appended to "
                      f"'{mat_key}' Stage[{len(stages)-1}]")

            mat_val["Stages"]       = stages
            mat_val["activeLayers"] = len(stages)

        if modified:
            with open(mat_file, "w", encoding="utf-8") as fh:
                json.dump(mat_data, fh, indent=2)
            print(f"[DEBUG]   Saved {os.path.basename(mat_file)}")

    if failed_files:
        print(f"[WARNING] _inject_custom_layers: {len(failed_files)}/{len(mat_files)} "
              f"materials.json file(s) could not be parsed and were left "
              f"unmodified: {', '.join(failed_files)}")
        return False

    print(f"[DEBUG] _inject_custom_layers: complete, patched {len(mat_files) - len(failed_files)} "
          f"materials.json file(s)")
    return True


_GLOW_KEYS = {
    "emissiveFactor",
    "emissiveMap",
    "emissiveMapUseUV",
    "instanceDiffuse",
    "instanceEmissive",
    "metallicFactor",
    "metallicMapUseUV",
    "roughnessMapUseUV",
}


def apply_emissive_glow(skin_data, base_carid, skin_folder, dest_skin_folder):
    emissive_src = skin_data.get("emissive_dds_path", "")
    print(f"[DEBUG] apply_emissive_glow: base_carid={base_carid!r} skin_folder={skin_folder!r} "
          f"emissive_src={emissive_src!r}")
    if not emissive_src:
        print("[DEBUG] apply_emissive_glow: no emissive_dds_path, skipping")
        return True
    if not os.path.exists(emissive_src):
        print(f"[WARNING] apply_emissive_glow: source not found: {emissive_src}")
        return False

    emissive_filename = _copy_dedup(
        emissive_src, dest_skin_folder, os.path.basename(emissive_src)
    )
    print(f"[DEBUG] Copied emissive DDS: {emissive_src} → "
          f"{os.path.join(dest_skin_folder, emissive_filename)}")

    emissive_ref = f"vehicles/{base_carid}/{skin_folder}/{emissive_filename}"

    glow_block = {
        "emissiveFactor":    [10.000001, 10.000001, 10.000001],
        "emissiveMap":       emissive_ref,
        "emissiveMapUseUV":  1,
        "instanceDiffuse":   True,
        "instanceEmissive":  True,
        "metallicFactor":    1,
        "metallicMapUseUV":  1,
        "roughnessMapUseUV": 1,
    }

    mat_files = []
    for root, _, files in os.walk(dest_skin_folder):
        for fn in files:
            if fn.endswith(".materials.json") or fn == "materials.json":
                mat_files.append(os.path.join(root, fn))

    if not mat_files:
        print(f"[WARNING] apply_emissive_glow: no .materials.json in {dest_skin_folder}")
        return False

    failed_files = []

    for mat_file in mat_files:
        with open(mat_file, "r", encoding="utf-8") as fh:
            raw = fh.read()
        raw_clean = re.sub(r",(\s*[}\]])", r"\1", raw)
        try:
            mat_data = json.loads(raw_clean)
        except json.JSONDecodeError as exc:
            print(f"[WARNING] apply_emissive_glow JSON error in "
                  f"{os.path.basename(mat_file)}: {exc}")
            failed_files.append(os.path.basename(mat_file))
            continue

        modified = False
        for mat_key, mat_val in mat_data.items():
            if not isinstance(mat_val, dict):
                continue
            stages = mat_val.get("Stages", [])
            if len(stages) < 2 or not isinstance(stages[1], dict):
                continue

            stage1 = stages[1]

            removed = [k for k in _GLOW_KEYS if k in stage1]
            for k in removed:
                del stage1[k]
            if removed:
                print(f"[DEBUG]   Removed existing glow keys from '{mat_key}' "
                      f"Stage[1]: {removed}")

            stage1.update(glow_block)
            modified = True
            print(f"[DEBUG]   ✓ Emissive glow applied to '{mat_key}' Stage[1] "
                  f"→ {emissive_ref}")

        if modified:
            with open(mat_file, "w", encoding="utf-8") as fh:
                json.dump(mat_data, fh, indent=2)
            print(f"[DEBUG]   Saved {os.path.basename(mat_file)}")

    if failed_files:
        print(f"[WARNING] apply_emissive_glow: {len(failed_files)}/{len(mat_files)} "
              f"materials.json file(s) could not be parsed and were left "
              f"unmodified: {', '.join(failed_files)}")
        return False

    print(f"[DEBUG] apply_emissive_glow: complete, patched {len(mat_files) - len(failed_files)} "
          f"materials.json file(s)")
    return True


def generate_mod(
    mod_name, vehicle_id, skin_display_name, dds_path,
    output_path=None, progress_callback=None, author=None,
):
    print(f"\n{'='*60}\nSINGLE SKIN MOD GENERATION\n{'='*60}")
    mod_name      = sanitize_mod_name(mod_name)
    template_path = _find_normal_template(vehicle_id)
    print(f"[DEBUG] generate_mod: mod_name={mod_name!r} vehicle_id={vehicle_id!r} "
          f"skin_display_name={skin_display_name!r} dds_path={dds_path!r} "
          f"template_path={template_path!r}")
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"No template found for vehicle '{vehicle_id}'")

    temp_dir = tempfile.mkdtemp()
    print(f"[DEBUG] generate_mod: temp_dir={temp_dir!r}")
    try:
        dest = os.path.join(temp_dir, "vehicles", vehicle_id, mod_name)
        if os.path.exists(dest):
            shutil.rmtree(dest)
        shutil.copytree(template_path, dest,
                        ignore=lambda d, f: [x for x in f if x.lower().endswith(".dds")])
        print(f"[DEBUG] generate_mod: template copied to {dest!r}")
        if progress_callback: progress_callback(0.2)

        dds_filename   = os.path.basename(dds_path)
        shutil.copy(dds_path, os.path.join(dest, dds_filename))
        dds_identifier = os.path.splitext(dds_filename)[0].split("_")[-1]
        print(f"[DEBUG] generate_mod: dds_filename={dds_filename!r} dds_identifier={dds_identifier!r}")
        if progress_callback: progress_callback(0.4)

        process_jbeam_files(dest, dds_identifier, skin_display_name, author or "Unknown", dds_prefix=vehicle_id)
        if progress_callback: progress_callback(0.6)
        process_json_files(dest, vehicle_id, mod_name, dds_filename, dds_identifier)
        _write_bss_watermark(dest, mod_name, author or "Unknown")
        if progress_callback: progress_callback(0.8)

        mods_path = output_path or get_beamng_mods_path()
        os.makedirs(mods_path, exist_ok=True)
        zip_path = os.path.join(mods_path, f"{mod_name}.zip")
        zip_folder(temp_dir, zip_path)
        print(f"[DEBUG] generate_mod: complete, zip_path={zip_path!r}")
        if progress_callback: progress_callback(1.0)
        return zip_path
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print(f"[DEBUG] generate_mod: removed temp_dir {temp_dir!r}")


def generate_multi_skin_mod(project_data, output_path=None, progress_callback=None, unpacked=False):
    print(f"\n{'='*60}\nMULTI-SKIN MOD GENERATION\n{'='*60}")

    mod_name    = sanitize_mod_name(project_data["mod_name"])
    author      = project_data.get("author", "Unknown")
    cars        = project_data["cars"]
    total_cars  = len(cars)
    total_skins = sum(len(ci["skins"]) for ci in cars.values())

    print(f"Mod:    {mod_name}")
    print(f"Author: {author}")
    print(f"Cars:   {total_cars}   Skins: {total_skins}")
    print(f"[DEBUG] generate_multi_skin_mod: unpacked={unpacked} output_path={output_path!r} "
          f"car_instance_ids={list(cars.keys())}")

    try:
        from core.config import is_rebadge_suffix as _dup_is_rebadge_suffix
    except ImportError as _exc:
        print(f"[WARNING] generate_multi_skin_mod: {type(_exc).__name__}: {_exc}")
        def _dup_is_rebadge_suffix(_c, _s):
            return False

    seen_folders_by_carid: dict = {}
    for car_instance_id, car_info in cars.items():
        base_carid = car_info.get("base_carid", car_instance_id)
        _vsuffix   = car_info.get("variant_suffix", "")
        _is_rebadge = bool(_vsuffix) and _dup_is_rebadge_suffix(base_carid, _vsuffix)
        seen_folders = seen_folders_by_carid.setdefault(base_carid, {})
        for skin in car_info.get("skins", []):
            if _is_rebadge:
                folder = f"{_vsuffix.lower()}/{sanitize_folder_name(skin['name'])}"
            else:
                folder = sanitize_folder_name(skin["name"]) + (_vsuffix if _vsuffix else "")
            if folder in seen_folders:
                raise ValueError(
                    f"Vehicle '{base_carid}' has two skins that produce the same "
                    f"folder name '{folder}':\n"
                    f"  • {seen_folders[folder]!r}\n"
                    f"  • {skin['name']!r}\n\n"
                    f"Please give each skin a unique name."
                )
            seen_folders[folder] = skin["name"]

    temp_dir = tempfile.mkdtemp()
    print(f"Temp:   {temp_dir}")
    print(f"[DEBUG] generate_multi_skin_mod: seen_folders_by_carid={seen_folders_by_carid}")

    try:
        processed_skins = 0

        for car_instance_id, car_info in cars.items():
            base_carid     = car_info.get("base_carid", car_instance_id)
            variant_suffix = car_info.get("variant_suffix", "")
            skins          = car_info["skins"]
            is_variant     = variant_suffix != ""
            try:
                from core.config import is_single_layer_variant
            except ImportError as _exc:
                print(f"[WARNING] generate_multi_skin_mod: {type(_exc).__name__}: {_exc}")
                def is_single_layer_variant(_c, _s):
                    return False
            needs_double_layer = is_variant and not is_single_layer_variant(base_carid, variant_suffix)

            try:
                from core.config import is_rebadge_suffix
            except ImportError as _exc:
                print(f"[WARNING] generate_multi_skin_mod: {type(_exc).__name__}: {_exc}")
                def is_rebadge_suffix(_c, _s):
                    return False
            is_rebadge = is_variant and is_rebadge_suffix(base_carid, variant_suffix)
            if is_rebadge:
                dds_prefix = variant_suffix.lower()
            else:
                dds_prefix = base_carid

            print(f"[DEBUG] generate_multi_skin_mod: car_instance_id={car_instance_id!r} "
                  f"base_carid={base_carid!r} variant_suffix={variant_suffix!r} "
                  f"is_variant={is_variant} needs_double_layer={needs_double_layer} "
                  f"is_rebadge={is_rebadge} dds_prefix={dds_prefix!r}")

            print(f"\n--- {base_carid}"
                  f"{f' [{variant_suffix}]' if is_variant else ''}"
                  f" ({len(skins)} skins) ---")

            if is_variant:
                template_path = _find_variant_template(base_carid, variant_suffix)
            else:
                template_path = _find_normal_template(base_carid)

            if not os.path.exists(template_path):
                raise FileNotFoundError(
                    f"No template found for vehicle '{base_carid}'"
                    f"{f' variant={variant_suffix}' if is_variant else ''}.\n"
                    f"Expected: {template_path}\n\n"
                    f"Make sure the vehicle (and its variant template) exists "
                    f"in the Developer tab."
                )
            print(f"[DEBUG] generate_multi_skin_mod: template_path={template_path!r}")

            for skin_idx, skin in enumerate(skins):
                skin_name    = skin["name"]
                skin_id      = sanitize_skin_id(skin_name)
                if is_rebadge:
                    skin_folder = f"{variant_suffix.lower()}/{sanitize_folder_name(skin_name)}"
                else:
                    skin_folder = sanitize_folder_name(skin_name) + (variant_suffix if is_variant else "")
                is_colorable = skin.get("is_colorable", False)

                print(f"  [{skin_idx+1}/{len(skins)}] '{skin_name}' → {skin_folder}"
                      f" ({'colorable' if is_colorable else 'DDS'}"
                      f"{' + variant' if is_variant else ''}"
                      f"{' (single-layer)' if is_variant and not needs_double_layer else ''})")

                dest_skin_folder = os.path.join(
                    temp_dir, "vehicles", base_carid, skin_folder
                )
                print(f"[DEBUG] generate_multi_skin_mod: skin_id={skin_id!r} "
                      f"dest_skin_folder={dest_skin_folder!r} is_colorable={is_colorable}")

                if is_colorable:
                    if needs_double_layer:
                        generate_colorable_skin_variant(
                            template_path      = template_path,
                            dest_skin_folder   = dest_skin_folder,
                            vehicle_id         = base_carid,
                            variant_suffix     = variant_suffix,
                            skin_name          = skin_name,
                            skin_folder        = skin_folder,
                            data_map_source    = skin["data_map_path"],
                            color_map_source   = skin["color_map_path"],
                            data_map_source_2  = skin["data_map_path_2"],
                            color_map_source_2 = skin["color_map_path_2"],
                            author_name        = author,
                            material_properties= skin.get("material_properties"),
                            skin_data_ref      = skin,
                        )
                    else:
                        generate_colorable_skin(
                            template_path      = template_path,
                            dest_skin_folder   = dest_skin_folder,
                            vehicle_id         = base_carid,
                            skin_name          = skin_name,
                            skin_folder        = skin_folder,
                            data_map_source    = skin["data_map_path"],
                            color_map_source   = skin["color_map_path"],
                            author_name        = author,
                            material_properties= skin.get("material_properties"),
                            skin_data_ref      = skin,
                        )

                else:
                    if needs_double_layer:
                        _generate_variant_dds_skin(
                            template_path    = template_path,
                            dest_skin_folder = dest_skin_folder,
                            base_carid       = base_carid,
                            variant_suffix   = variant_suffix,
                            skin             = skin,
                            skin_folder      = skin_folder,
                            author           = author,
                        )
                    else:
                        dds_path = skin["dds_path"]

                        if os.path.exists(dest_skin_folder):
                            shutil.rmtree(dest_skin_folder)
                        _reset_copy_dedup_cache(dest_skin_folder)
                        shutil.copytree(
                            template_path, dest_skin_folder,
                            ignore=lambda d, f: [x for x in f if x.lower().endswith(".dds")]
                        )
                        dds_identifier = skin_id
                        dds_filename   = f"{dds_prefix}_skin_{skin_id}.dds"
                        dds_filename   = _copy_dedup(dds_path, dest_skin_folder, dds_filename)

                        process_jbeam_files(
                            dest_skin_folder, dds_identifier, skin_name, author,
                            dds_prefix=dds_prefix, carid=base_carid,
                        )
                        process_json_files(
                            dest_skin_folder, base_carid, skin_folder,
                            dds_filename, dds_identifier,
                        )

                if "config_data" in skin:
                    print("  → Config data...")
                    ok = process_skin_config_data(
                        skin, base_carid, skin_folder, temp_dir, template_path
                    )
                    if not ok:
                        print(f"  [WARNING] Config data failed for {skin_folder}")

                if "material_properties" in skin and not is_colorable:
                    print("  → Material properties...")
                    ok = process_material_properties(
                        skin, base_carid, skin_folder, dest_skin_folder
                    )
                    if not ok:
                        print(f"  [WARNING] Material properties failed for {skin_folder}")

                if skin.get("custom_layers"):
                    print("  → Custom layers...")
                    ok = _inject_custom_layers(
                        skin, base_carid, skin_folder, dest_skin_folder,
                        variant_suffix=variant_suffix,
                    )
                    if not ok:
                        print(f"  [WARNING] Custom layer injection failed for {skin_folder}")

                if "emissive_dds_path" in skin:
                    print("  → Emissive glow...")
                    ok = apply_emissive_glow(
                        skin, base_carid, skin_folder, dest_skin_folder
                    )
                    if not ok:
                        print(f"  [WARNING] Emissive glow failed for {skin_folder}")

                _write_bss_watermark(dest_skin_folder, mod_name, author)

                processed_skins += 1
                if progress_callback:
                    progress_callback(0.1 + (processed_skins / total_skins) * 0.75)

        print(f"[DEBUG] generate_multi_skin_mod: all {processed_skins}/{total_skins} skin(s) processed")

        print(f"\n{'='*60}\nVALIDATING DDS FILENAMES\n{'='*60}")
        dds_results = process_dds_files_in_mod(temp_dir)

        if dds_results["renamed"]:
            print(f"✓ Fixed {len(dds_results['renamed'])} DDS filename(s)")
            for car_id, skin_folder, old_dds, new_dds in dds_results["renamed"]:
                skin_folder_path = os.path.join(temp_dir, "vehicles", car_id, skin_folder)
                for mat_fn in ["skin.materials.json", "materials.json"]:
                    mat_path = os.path.join(skin_folder_path, mat_fn)
                    if os.path.exists(mat_path):
                        try:
                            with open(mat_path, "r", encoding="utf-8") as f:
                                content = f.read()
                            old_path = f"vehicles/{car_id}/{skin_folder}/{old_dds}"
                            new_path = f"vehicles/{car_id}/{skin_folder}/{new_dds}"
                            if old_path in content:
                                content = content.replace(old_path, new_path)
                                with open(mat_path, "w", encoding="utf-8") as f:
                                    f.write(content)
                                print(f"  Updated {car_id}/{skin_folder}/{mat_fn}")
                        except Exception as e:
                            print(f"  [WARNING] materials.json update failed: {e}")

        print(f"\n{'Copying unpacked mod folder' if unpacked else 'Creating ZIP'}…")
        print(f"[DEBUG] generate_multi_skin_mod: dds_renamed={len(dds_results['renamed'])} "
              f"dds_already_correct={len(dds_results['already_correct'])} "
              f"dds_errors={len(dds_results['errors'])}")
        if progress_callback:
            progress_callback(0.9)

        mods_path = output_path or get_beamng_mods_path()
        os.makedirs(mods_path, exist_ok=True)

        if unpacked:
            dest_folder = os.path.join(mods_path, mod_name)
            if os.path.exists(dest_folder):
                raise FileExistsError(
                    f"A mod folder named '{mod_name}' already exists.\n"
                    f"Please choose a different name or delete the existing folder."
                )
            shutil.copytree(temp_dir, dest_folder)
            if progress_callback:
                progress_callback(1.0)
            print("\n✓ Multi-skin mod created (unpacked)!")
            print(f"  Cars: {total_cars}  Skins: {total_skins}")
            print(f"  Location: {dest_folder}")
            print(f"{'='*60}\n")
            return dest_folder
        else:
            zip_path = os.path.join(mods_path, f"{mod_name}.zip")
            if os.path.exists(zip_path):
                raise FileExistsError(
                    f"A mod named '{mod_name}.zip' already exists.\n"
                    f"Please choose a different name or delete the existing file."
                )
            print(f"[DEBUG] Files to zip from {temp_dir}:")
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    print(f"[DEBUG]   {os.path.relpath(os.path.join(root, file), temp_dir)}")
            zip_folder(temp_dir, zip_path)
            if progress_callback:
                progress_callback(1.0)
            print("\n✓ Multi-skin mod created!")
            print(f"  Cars: {total_cars}  Skins: {total_skins}")
            print(f"  Location: {zip_path}")
            print(f"{'='*60}\n")
            return zip_path

    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
