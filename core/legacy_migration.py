
from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from typing import List

from core.settings import get_install_dir, get_bundle_path

_MIGRATED_MARKER = ".beamskin_migrated"

_LEGACY_DATA_SIGNS = (
    "app_settings.json",
    "project_registry.json",
    "added_vehicles.json",
    os.path.join("vehicles", "added_vehicles.json"),
)


@dataclass
class LegacyDataInfo:
    found:        bool
    legacy_dir:   str
    reasons:      List[str] = field(default_factory=list)
    project_count: int = 0
    vehicle_count: int = 0
    approx_size_kb: float = 0.0

    @property
    def has_meaningful_data(self) -> bool:
        return self.found and bool(self.reasons)


def _candidate_legacy_dirs() -> List[str]:
    candidates = set()

    for base in (get_install_dir(), get_bundle_path()):
        if not base:
            continue
        candidates.add(os.path.join(base, "data"))

    candidates.add(os.path.join(os.getcwd(), "data"))

    result = sorted(d for d in candidates if d)
    print(f"[DEBUG] _candidate_legacy_dirs: {result}")
    return result


def _looks_migrated(legacy_dir: str) -> bool:
    marker = os.path.join(legacy_dir, _MIGRATED_MARKER)
    result = os.path.exists(marker)
    print(f"[DEBUG] _looks_migrated: legacy_dir={legacy_dir!r} marker={marker!r} -> {result}")
    return result


def _dir_size_kb(path: str) -> float:
    print(f"[DEBUG] _dir_size_kb: walking {path!r}")
    total = 0
    file_count = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
                file_count += 1
            except OSError as e:
                print(f"[DEBUG] _dir_size_kb: could not stat {os.path.join(root, name)!r}: {e}")
    result = round(total / 1024, 1)
    print(f"[DEBUG] _dir_size_kb: {path!r} -> {file_count} files, {result} KB")
    return result


def _count_added_vehicles(legacy_dir: str) -> int:
    print(f"[DEBUG] _count_added_vehicles: scanning {legacy_dir!r}")
    for rel in ("added_vehicles.json", os.path.join("vehicles", "added_vehicles.json")):
        p = os.path.join(legacy_dir, rel)
        if os.path.isfile(p):
            print(f"[DEBUG] _count_added_vehicles: found {p!r}")
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    print(f"[DEBUG] _count_added_vehicles: {p!r} -> {len(data)} vehicle(s)")
                    return len(data)
                print(f"[DEBUG] _count_added_vehicles: {p!r} root is not a dict "
                      f"(type={type(data)}), skipping")
            except Exception as e:
                print(f"[DEBUG] _count_added_vehicles: ERROR reading {p!r}: {e}")
    print(f"[DEBUG] _count_added_vehicles: {legacy_dir!r} -> 0 (no readable file found)")
    return 0


def _count_projects(legacy_dir: str) -> int:
    reg = os.path.join(legacy_dir, "project_registry.json")
    print(f"[DEBUG] _count_projects: checking {reg!r}")
    if os.path.isfile(reg):
        try:
            with open(reg, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                print(f"[DEBUG] _count_projects: {reg!r} -> {len(data)} project(s)")
                return len(data)
            print(f"[DEBUG] _count_projects: {reg!r} root is not a list "
                  f"(type={type(data)}), returning 0")
        except Exception as e:
            print(f"[DEBUG] _count_projects: ERROR reading {reg!r}: {e}")
    else:
        print(f"[DEBUG] _count_projects: {reg!r} does not exist")
    return 0


def _scan_legacy_dirs(ignore_migrated_marker: bool) -> LegacyDataInfo:
    print(f"[DEBUG] _scan_legacy_dirs: called with ignore_migrated_marker={ignore_migrated_marker}")
    for legacy_dir in _candidate_legacy_dirs():
        print(f"[DEBUG] _scan_legacy_dirs: checking candidate {legacy_dir!r}")
        if not os.path.isdir(legacy_dir):
            print(f"[DEBUG] _scan_legacy_dirs: {legacy_dir!r} is not a directory, skipping")
            continue
        if not ignore_migrated_marker and _looks_migrated(legacy_dir):
            print(f"[DEBUG] _scan_legacy_dirs: {legacy_dir!r} already migrated/skipped, "
                  f"skipping candidate")
            continue

        reasons = [
            sign for sign in _LEGACY_DATA_SIGNS
            if os.path.isfile(os.path.join(legacy_dir, sign))
        ]
        print(f"[DEBUG] _scan_legacy_dirs: {legacy_dir!r} reasons={reasons}")
        if not reasons:
            print(f"[DEBUG] _scan_legacy_dirs: {legacy_dir!r} has no recognizable data files, skipping")
            continue

        info = LegacyDataInfo(
            found=True,
            legacy_dir=legacy_dir,
            reasons=reasons,
            project_count=_count_projects(legacy_dir),
            vehicle_count=_count_added_vehicles(legacy_dir),
            approx_size_kb=_dir_size_kb(legacy_dir),
        )
        print(f"[DEBUG] _scan_legacy_dirs: match found -> {info}")
        return info

    print("[DEBUG] _scan_legacy_dirs: no candidate matched, returning found=False")
    return LegacyDataInfo(found=False, legacy_dir="")


def detect_legacy_data() -> LegacyDataInfo:
    print("[DEBUG] detect_legacy_data: called")
    result = _scan_legacy_dirs(ignore_migrated_marker=False)
    print(f"[DEBUG] detect_legacy_data: found={result.found} legacy_dir={result.legacy_dir!r}")
    return result


def find_legacy_data_for_settings() -> LegacyDataInfo:
    print("[DEBUG] find_legacy_data_for_settings: called")
    result = _scan_legacy_dirs(ignore_migrated_marker=True)
    print(f"[DEBUG] find_legacy_data_for_settings: found={result.found} "
          f"legacy_dir={result.legacy_dir!r}")
    return result


def migrate_legacy_data(legacy_dir: str, dest_dir: str) -> bool:
    print(f"[DEBUG] migrate_legacy_data: legacy_dir={legacy_dir!r} dest_dir={dest_dir!r}")
    ok = True
    os.makedirs(dest_dir, exist_ok=True)

    entries = os.listdir(legacy_dir)
    print(f"[DEBUG] migrate_legacy_data: {len(entries)} entries in legacy_dir: {entries}")

    copied = 0
    skipped_existing = 0
    for name in entries:
        if name == _MIGRATED_MARKER:
            print(f"[DEBUG] migrate_legacy_data: skipping marker file {name!r}")
            continue
        src = os.path.join(legacy_dir, name)
        dst = os.path.join(dest_dir, name)
        try:
            if os.path.isdir(src):
                print(f"[DEBUG] migrate_legacy_data: copytree {src!r} -> {dst!r}")
                shutil.copytree(src, dst, dirs_exist_ok=True)
                copied += 1
            else:
                if os.path.exists(dst):
                    print(f"[DEBUG] migrate_legacy_data: {dst!r} already exists, skipping")
                    skipped_existing += 1
                    continue
                print(f"[DEBUG] migrate_legacy_data: copy2 {src!r} -> {dst!r}")
                shutil.copy2(src, dst)
                copied += 1
        except Exception as e:
            print(f"[WARNING] legacy_migration: could not copy {src!r} -> {dst!r}: {e}")
            ok = False

    print(f"[DEBUG] migrate_legacy_data: copied={copied} skipped_existing={skipped_existing} ok={ok}")

    try:
        with open(os.path.join(legacy_dir, _MIGRATED_MARKER), "w", encoding="utf-8") as f:
            f.write(dest_dir)
        print(f"[DEBUG] migrate_legacy_data: wrote migration marker in {legacy_dir!r}")
    except Exception as e:
        print(f"[WARNING] legacy_migration: could not write migration marker in {legacy_dir!r}: {e}")

    print(f"[DEBUG] migrate_legacy_data: returning ok={ok}")
    return ok


def skip_legacy_data(legacy_dir: str) -> None:
    print(f"[DEBUG] skip_legacy_data: legacy_dir={legacy_dir!r}")
    try:
        with open(os.path.join(legacy_dir, _MIGRATED_MARKER), "w", encoding="utf-8") as f:
            f.write("SKIPPED_BY_USER")
        print(f"[DEBUG] skip_legacy_data: wrote skip marker in {legacy_dir!r}")
    except Exception as e:
        print(f"[WARNING] legacy_migration: could not write skip marker in {legacy_dir!r}: {e}")


def _copy_tree_merge(src_dir: str, dst_dir: str) -> bool:
    print(f"[DEBUG] _copy_tree_merge: src_dir={src_dir!r} dst_dir={dst_dir!r}")
    if not os.path.isdir(src_dir):
        print("[DEBUG] _copy_tree_merge: src_dir does not exist, nothing to copy")
        return True
    ok = True
    os.makedirs(dst_dir, exist_ok=True)
    entries = os.listdir(src_dir)
    print(f"[DEBUG] _copy_tree_merge: {len(entries)} entries in src_dir")
    copied = 0
    for name in entries:
        src = os.path.join(src_dir, name)
        dst = os.path.join(dst_dir, name)
        try:
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
                copied += 1
            else:
                if os.path.exists(dst):
                    print(f"[DEBUG] _copy_tree_merge: {dst!r} already exists, skipping")
                    continue
                shutil.copy2(src, dst)
                copied += 1
        except Exception as e:
            print(f"[WARNING] legacy_migration: could not copy {src!r} -> {dst!r}: {e}")
            ok = False
    print(f"[DEBUG] _copy_tree_merge: copied={copied} ok={ok}")
    return ok


def migrate_all_legacy_data(legacy_data_dir: str, dest_data_dir: str) -> bool:
    print(f"[DEBUG] migrate_all_legacy_data: legacy_data_dir={legacy_data_dir!r} "
          f"dest_data_dir={dest_data_dir!r}")
    root = os.path.dirname(os.path.abspath(legacy_data_dir))
    print(f"[DEBUG] migrate_all_legacy_data: root={root!r}")

    ok = migrate_legacy_data(legacy_data_dir, dest_data_dir)
    print(f"[DEBUG] migrate_all_legacy_data: root/data migration ok={ok}")

    legacy_vehicles = os.path.join(root, "vehicles")
    dest_vehicles = os.path.join(dest_data_dir, "vehicles")
    print(f"[DEBUG] migrate_all_legacy_data: migrating vehicles "
          f"{legacy_vehicles!r} -> {dest_vehicles!r}")
    if not _copy_tree_merge(legacy_vehicles, dest_vehicles):
        ok = False

    legacy_previews = os.path.join(root, "gui", "images", "vehicles")
    dest_previews = os.path.join(dest_data_dir, "vehicle_previews")
    print(f"[DEBUG] migrate_all_legacy_data: migrating previews "
          f"{legacy_previews!r} -> {dest_previews!r}")
    if not _copy_tree_merge(legacy_previews, dest_previews):
        ok = False

    print(f"[DEBUG] migrate_all_legacy_data: returning ok={ok}")
    return ok
