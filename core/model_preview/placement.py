from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

from .jbeam_reader import (
    FlexbodyPlacement,
    VehicleIndex,
    add_common_parts,
    build_part_index,
    flexbody_placements,
    jbeam_node_positions,
    pressure_wheel_group_positions,
    slot_accepts,
)
from .beamng_parts import ACTIVE_PREFIX, base_mesh_name
from .vehicle_fs import VehicleFS, find_beamng_content

Placements = dict

SHIFT_UNPLACED_MESHES = True

_DEBUG_DUMP = os.environ.get("BEAMSKIN_PLACEMENT_DEBUG", "1").strip() not in ("", "0")


@dataclass
class PartPlan:
    placements: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)
    dae_dirs: tuple = ()
    shallow_dirs: tuple = ()
    extra_roots: tuple = ()
    active: tuple = ()
    meshes: tuple = ()
    mesh_part: dict = field(default_factory=dict)
    cargo: dict = field(default_factory=dict)
    anchored: frozenset = frozenset()
    mesh_dirs: dict = field(default_factory=dict)


def car_stems(content_dir: str) -> list[str]:
    try:
        names = os.listdir(os.path.join(content_dir, "vehicles"))
    except OSError:
        return []
    stems = {n[:-4] for n in names if n.lower().endswith(".zip") and n.lower() != "common.zip"}
    return sorted(stems, key=lambda x: (-len(x), x))


def _owner_stem(name: str, stems: list[str]) -> str:
    for stem in stems:
        if name == stem or name.startswith(stem + "_"):
            return stem
    return ""


def resolve_parts(index: VehicleIndex, chosen: dict, main_name: str = "") -> tuple[list[str], list[str]]:
    values = [v for v in chosen.values() if isinstance(v, str) and v]
    main = main_name if main_name in index.parts else next(
        (v for v in values if v in index.parts and index.parts[v].slot_type == "main"), ""
    ) or index.main_part()
    chosen_by_path = {
        key.strip("/"): value
        for key, value in chosen.items()
        if isinstance(key, str) and "/" in key
    }
    chosen_by_slot = {
        key: value
        for key, value in chosen.items()
        if isinstance(key, str) and "/" not in key
    }
    active: list[str] = []
    unresolved: list[str] = []
    seen: set[str] = set()
    index.offsets = {}

    def visit(name: str, path: str, depth: int, offset=(0.0, 0.0, 0.0)):
        if not name or depth > 40 or name in seen:
            return
        part = index.parts.get(name)
        if part is None:
            if name not in unresolved:
                unresolved.append(name)
            return
        seen.add(name)
        active.append(name)
        if any(offset):
            index.offsets[name] = offset
        for slot in part.slots:
            spath = f"{path}/{slot.name}"
            pick = chosen_by_path.get(spath.strip("/"), chosen_by_slot.get(slot.name))
            if not isinstance(pick, str):
                pick = slot.default
            visit(pick, spath, depth + 1,
                  tuple(a + b for a, b in zip(offset, getattr(slot, "node_offset", (0.0, 0.0, 0.0)))))

    visit(main, "", 0)
    for value in values:
        if value not in seen:
            visit(value, "", 0)
    return active, unresolved


def _cargobox_preview_alignment(
    active: list[str],
    index: VehicleIndex,
) -> Optional[tuple[float, set[str], set[str], set[str], set[str]]]:
    cargo_parts = [
        part
        for name in active
        if (part := index.parts.get(name)) is not None
        and "cargobox" in part.name.casefold()
        and "upfit" in part.slot_type.casefold()
    ]
    cab_parts = [
        part
        for name in active
        if (part := index.parts.get(name)) is not None
        and part.slot_type.casefold().endswith("_cab")
        and any(
            any(token in mesh.casefold() for token in ("daycab", "sleepercab", "cabover"))
            for mesh in part.meshes
        )
    ]
    if not cab_parts:
        cab_parts = [
            part
            for name in active
            if (part := index.parts.get(name)) is not None
            and part.slot_type.casefold().endswith("_cab")
            and part.meshes
            and jbeam_node_positions(part.node_rows)
        ]
    if len(cargo_parts) != 1 or not cab_parts:
        return None

    shift_y = 0.0

    alignment_roots = {cargo_parts[0].name}
    cargo_slot_type = cargo_parts[0].slot_type
    alignment_roots.update(
        part.name
        for name in active
        if (part := index.parts.get(name)) is not None
        and any(slot_accepts(slot, cargo_parts[0]) for slot in part.slots)
    )
    subtree = set(alignment_roots)
    pending = list(alignment_roots)
    while pending:
        parent = index.parts[pending.pop()]
        for slot in parent.slots:
            for child_name in active:
                child = index.parts.get(child_name)
                if child is not None and child_name not in subtree and slot_accepts(slot, child):
                    subtree.add(child_name)
                    pending.append(child_name)

    meshes = {mesh for name in subtree for mesh in index.parts[name].meshes}
    cab_meshes = {mesh for part in cab_parts for mesh in part.meshes}
    box_meshes = set(cargo_parts[0].meshes)
    return shift_y, subtree, meshes, cab_meshes, box_meshes


def _derive_chosen(index: VehicleIndex, live_cf: set[str], main: str, exact=frozenset()) -> dict:
    by_slot: dict[str, list[str]] = {}
    for part in index.parts.values():
        for slot_type in (part.slot_types or ((part.slot_type,) if part.slot_type else ())):
            by_slot.setdefault(slot_type, []).append(part.name)

    def candidates(slot) -> list[str]:
        names: list[str] = []
        for slot_type in (slot.name, *getattr(slot, "allow_types", ())):
            for cand in by_slot.get(slot_type, ()):
                if cand not in names:
                    names.append(cand)
        if slot.default and slot.default in index.parts and slot.default not in names:
            names.append(slot.default)
        return names

    memo: dict[str, float] = {}
    visiting: set[str] = set()

    def score(name: str, depth: int = 0) -> float:
        if name in memo:
            return memo[name]
        part = index.parts.get(name)
        if part is None or name in visiting or depth > 30:
            return 0.0
        visiting.add(name)
        hits = sum(1 for mesh in part.meshes if mesh.casefold() in live_cf)
        total = hits - 0.5 * (len(part.meshes) - hits)
        if name in exact:
            total += 1000.0
        for slot in part.slots:
            total += max([0.0] + [score(c, depth + 1) for c in candidates(slot)])
        visiting.discard(name)
        memo[name] = total
        return total

    chosen: dict[str, str] = {}
    seen: set[str] = set()

    def walk(name: str, path: str, depth: int):
        part = index.parts.get(name)
        if part is None or depth > 40 or name in seen:
            return
        seen.add(name)
        for slot in part.slots:
            spath = f"{path}/{slot.name}"
            best_name, best_score = "", 0.0
            for cand in sorted(candidates(slot)):
                s = score(cand)
                if s > best_score or (s == best_score and s > 0 and cand == slot.default):
                    best_name, best_score = cand, s
            pick = best_name if best_score > 0 else slot.default
            if pick:
                chosen[spath.strip("/")] = pick
                walk(pick, spath, depth + 1)

    walk(main, "", 0)
    return chosen


def _backfill_parts(index: VehicleIndex, live_cf: set[str], active: list[str]) -> list[str]:
    covered = {m.casefold() for name in active for m in index.parts[name].meshes}
    uncovered = live_cf - covered
    taken: list[str] = []
    skip = set(active)
    while uncovered and len(taken) < 200:
        best, best_key = "", None
        for part in index.parts.values():
            if part.name in skip or not part.meshes:
                continue
            hits = sum(1 for m in part.meshes if m.casefold() in uncovered)
            if not hits:
                continue
            key = (hits, -(len(part.meshes) - hits), part.name)
            if best_key is None or key > best_key:
                best, best_key = part.name, key
        if not best:
            break
        taken.append(best)
        skip.add(best)
        uncovered -= {m.casefold() for m in index.parts[best].meshes}
    return taken


def _main_part(index: VehicleIndex, carid: str) -> str:
    part = index.parts.get(carid)
    if part is not None and part.slot_type == "main":
        return carid
    return index.main_part()


def _dae_dirs(index: VehicleIndex, active: list[str], carid: str) -> tuple[tuple, tuple]:
    dirs: set[str] = {f"vehicles/{carid}/", f"vehicles/common/{carid}/"}
    shallow: set[str] = set()
    for name in active:
        file = index.parts[name].file
        pieces = file.lower().split("/")
        if len(pieces) > 2 and pieces[1] != "common" and pieces[1] != carid.lower():
            dirs.add(f"vehicles/common/{pieces[1]}/")
        folder = file.rsplit("/", 1)[0] + "/" if "/" in file else ""
        if not folder:
            continue
        if folder.lower() in ("vehicles/", "vehicles/common/"):
            shallow.add(folder)
        else:
            dirs.add(folder)
    return tuple(sorted(dirs)), tuple(sorted(shallow))


_CACHE: dict[tuple, PartPlan] = {}


def _mtime(path: str) -> float:
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


def compute_placements(roots, carid, chosen, content_dir="", mesh_names=None):
    plan = compute_part_plan(roots, carid, chosen, content_dir, mesh_names)
    return plan.placements, plan.notes


def compute_part_plan(
    roots: list[str],
    carid: str,
    chosen: dict,
    content_dir: str = "",
    mesh_names=None,
) -> PartPlan:
    chosen = {k: v for k, v in (chosen or {}).items()
              if isinstance(k, str) and isinstance(v, str) and v}
    exact = frozenset(v for k, v in chosen.items() if k.startswith(ACTIVE_PREFIX))
    chosen = {k: v for k, v in chosen.items() if not k.startswith(ACTIVE_PREFIX)}
    mesh_names = frozenset(n for n in (mesh_names or ()) if isinstance(n, str) and n)
    if not chosen and not mesh_names and not exact:
        return PartPlan()
    cache_key = (
        carid, tuple(sorted(exact)), tuple((r, _mtime(r)) for r in roots), tuple(sorted(chosen.items())),
        () if chosen else tuple(sorted(mesh_names)),
    )
    hit = _CACHE.get(cache_key)
    if hit is not None:
        return hit

    notes: list[str] = []
    vfs = VehicleFS(roots)
    content_dir = content_dir or find_beamng_content()
    index = build_part_index(vfs, carid)
    derived = not chosen
    live_cf = {n.casefold() for n in mesh_names}
    live_cf |= {base_mesh_name(n).casefold() for n in mesh_names}
    main_name = ""

    def resolve():
        nonlocal chosen
        if derived:
            chosen = _derive_chosen(index, live_cf, main_name, exact)
        if exact:
            known = [n for n in sorted(exact) if n in index.parts]
            chosen = dict(chosen)
            for i, n in enumerate(known):
                chosen[f"__exact{i}"] = n
        result_ = resolve_parts(index, chosen, main_name)
        if live_cf:
            extras = _backfill_parts(index, live_cf, result_[0])
            if extras:
                chosen = dict(chosen)
                for i, extra in enumerate(extras):
                    chosen[f"__live{i}"] = extra
                result_ = resolve_parts(index, chosen, main_name)
        return result_

    if derived:
        covered = {m.casefold() for part in index.parts.values() for m in part.meshes}
        uncovered = {n for n in mesh_names if n.casefold() not in covered}
        if uncovered:
            add_common_parts(vfs, index, only_names=uncovered)
        main_name = _main_part(index, carid)
        if not any(m.casefold() in live_cf for part in index.parts.values() for m in part.meshes):
            return PartPlan(notes=["No part of the jbeams draws any of the live mesh names, so no "
                                   "part offsets were applied."])
    elif live_cf:
        covered = {m.casefold() for part in index.parts.values() for m in part.meshes}
        uncovered = {n for n in mesh_names if n.casefold() not in covered}
        if uncovered:
            add_common_parts(vfs, index, only_names=uncovered)
    active, unresolved = resolve()

    stems = car_stems(content_dir) if content_dir else []
    extra_cars: list[str] = []
    added_roots: list[str] = []
    for _round in range(2):
        owners = []
        for name in unresolved:
            owner = _owner_stem(name, stems)
            if owner and owner != carid and owner not in extra_cars and owner not in owners:
                owners.append(owner)
        if not owners:
            break
        for owner in owners[:4]:
            wanted_names = {n for n in unresolved if _owner_stem(n, stems) == owner}
            zip_path = os.path.join(content_dir, "vehicles", owner + ".zip")
            vfs.add_root(zip_path)
            if zip_path in vfs.roots:
                added_roots.append(zip_path)
                other = build_part_index(vfs, owner, only_names=wanted_names)
                for part in other.parts.values():
                    index.parts.setdefault(part.name, part)
                index.errors += other.errors
            extra_cars.append(owner)
        active, unresolved = resolve()
    for _round in range(12):
        if not unresolved:
            break
        known_parts = len(index.parts)
        add_common_parts(vfs, index, only_names=unresolved)
        active, unresolved = resolve()
        if len(index.parts) == known_parts:
            break

    unresolved = [n for n in unresolved
                  if n.startswith(carid) or _owner_stem(n, stems) == carid]
    if exact and derived:
        fitted = [n for n in active
                  if n in exact or index.parts[n].slot_type == "main"]
        if len(fitted) >= max(1, len(exact & set(index.parts)) // 2):
            active = fitted
    for err in index.errors[:5]:
        notes.append(f"jbeam not readable: {err}")
    if not active:
        notes.append("None of the live parts could be found in the jbeams, so no part offsets were applied.")
        return PartPlan(notes=notes)
    if unresolved:
        shown = ", ".join(unresolved[:6]) + (" ..." if len(unresolved) > 6 else "")
        notes.append(f"{len(unresolved)} part(s) of the car were not found in the jbeams: {shown}")

    component_values: dict = {}
    for name in active:
        for component, values in index.parts[name].components.items():
            if isinstance(values, dict):
                component_values.setdefault(component, {}).update(values)
    cargo_alignment = _cargobox_preview_alignment(active, index)
    cargo_shift_y, cargo_parts, cargo_meshes, cab_meshes, box_meshes = (
        cargo_alignment if cargo_alignment is not None
        else (0.0, set(), set(), set(), set())
    )

    node_positions: dict = {}
    for name in active:
        shift = index.offsets.get(name, (0.0, 0.0, 0.0))
        for node, position in jbeam_node_positions(
            index.parts[name].node_rows, component_values
        ).items():
            position = tuple(a + b for a, b in zip(position, shift))
            previous = node_positions.get(node)
            if previous is None or sum(value != 0.0 for value in position) > sum(
                value != 0.0 for value in previous
            ):
                node_positions[node] = position
    wheel_group_positions: dict = {}
    for name in active:
        wheel_group_positions.update(
            pressure_wheel_group_positions(index.parts[name].pressure_wheel_rows, node_positions)
        )

    result: Placements = {}
    anchored_all: set = set()
    dump: list[str] = []
    if _DEBUG_DUMP:
        dump.append(f"wheel groups: {wheel_group_positions}")
    for name in active:
        part = index.parts[name]
        placements_by_mesh, errors = flexbody_placements(
            part.flexbody_rows, component_values, wheel_group_positions
        )
        if _DEBUG_DUMP:
            dump.append(f"== {name}  file={part.file}  slot_offset={index.offsets.get(name)}"
                        f"  cargo={name in cargo_parts}")
            keep = ("pos", "position", "rot", "rotation", "scale",
                    "ignorenodeoffset", "nodemove", "nodeoffset")
            for row in part.flexbody_rows:
                if not (isinstance(row, list) and row and isinstance(row[0], str)):
                    continue
                groups = row[1] if len(row) > 1 else ()
                groups = [groups] if isinstance(groups, str) else list(groups) \
                    if isinstance(groups, (list, tuple)) else []
                options = {}
                for value in row[1:]:
                    if isinstance(value, dict):
                        options.update(value)
                shown = {k: v for k, v in options.items() if str(k).casefold() in keep}
                hit = next((g for g in groups if g in wheel_group_positions), None)
                dump.append(f"   row {row[0]}  groups={groups}  {shown}"
                            f"  anchor={hit}:{wheel_group_positions.get(hit)}")
        shift = index.offsets.get(name)
        if name in cargo_parts:
            shift = None
        anchored = set()
        for row in part.flexbody_rows:
            if isinstance(row, list) and len(row) > 1 and isinstance(row[0], str):
                groups = (row[1],) if isinstance(row[1], str) else row[1]
                if isinstance(groups, list) and any(g in wheel_group_positions for g in groups):
                    anchored.add(row[0])
        anchored_all.update(anchored)
        if shift:
            raw_by_mesh, _raw_errors = flexbody_placements(part.flexbody_rows, component_values, {})
            for mesh in part.meshes:
                if mesh in anchored:
                    raws = raw_by_mesh.get(mesh)
                    placed = placements_by_mesh.get(mesh)
                    if raws and placed and len(raws) == len(placed):
                        placements_by_mesh[mesh] = tuple(
                            FlexbodyPlacement(
                                tuple(
                                    p.position[i] if p.position[i] != r.position[i]
                                    else r.position[i] + shift[i]
                                    for i in range(3)
                                ),
                                p.rotation, p.scale)
                            for p, r in zip(placed, raws)
                        )
                    continue
                if mesh not in placements_by_mesh and not SHIFT_UNPLACED_MESHES:
                    continue
                existing = placements_by_mesh.get(mesh, (FlexbodyPlacement(),))
                placements_by_mesh[mesh] = tuple(
                    FlexbodyPlacement(
                        tuple(a + b for a, b in zip(p.position, shift)), p.rotation, p.scale)
                    for p in existing
                )
        if name in cargo_parts:
            for mesh in part.meshes:
                if mesh not in cargo_meshes:
                    continue
                existing = placements_by_mesh.get(mesh, (FlexbodyPlacement(),))
                placements_by_mesh[mesh] = tuple(
                    FlexbodyPlacement(
                        (p.position[0], p.position[1] + cargo_shift_y, p.position[2]),
                        p.rotation, p.scale)
                    for p in existing
                )
        if _DEBUG_DUMP:
            for mesh, placements in placements_by_mesh.items():
                finals = [tuple(round(c, 3) for c in p.position) for p in placements]
                dump.append(f"   final {mesh}: {finals}")
        for mesh, placements in placements_by_mesh.items():
            if derived and not exact and mesh in result:
                continue
            result[mesh] = result.get(mesh, ()) + placements
        notes.extend(f"{name}: {error}" for error in errors)

    if live_cf:
        drawn = {m.casefold() for name in active for m in index.parts[name].meshes}
        orphan = sorted(n for n in mesh_names
                        if n.casefold() not in drawn and base_mesh_name(n).casefold() not in drawn)
        if orphan:
            sample = ", ".join(orphan[:5]) + (" ..." if len(orphan) > 5 else "")
            notes.append(f"{len(orphan)} live mesh name(s) are drawn by no part found in the jbeams: {sample}")
    if any("cargobox" in index.parts[n].name.casefold() for n in active) and cargo_alignment is None:
        notes.append("A cargo box is fitted but could not be aligned behind the cab "
                     "(cab or box part not found), so it sits where its jbeam puts it.")

    dae_dirs, shallow_dirs = _dae_dirs(index, active, carid)
    print(f"[DEBUG] model_preview.placement: {carid}: {len(active)} parts"
          f"{' (derived from meshes)' if derived else ''}, "
          f"{len(result)} placed meshes, {len(wheel_group_positions)} wheel groups, "
          f"{len(dae_dirs)} dae folders")
    if _DEBUG_DUMP:
        for line in dump:
            print(f"[DEBUG] placement: {line}")
    mesh_part: dict = {}
    for name in active:
        for mesh in index.parts[name].meshes:
            mesh_part.setdefault(mesh, name)
    mesh_dirs: dict = {}
    for mesh, owner in mesh_part.items():
        owner_file = index.parts[owner].file
        if "/" in owner_file:
            mesh_dirs.setdefault(mesh.casefold(), owner_file.rsplit("/", 1)[0] + "/")
    cargo = ({"cab": frozenset(cab_meshes), "box": frozenset(box_meshes),
              "subtree": frozenset(cargo_meshes)} if cargo_alignment is not None else {})
    plan = PartPlan(result, notes, dae_dirs, shallow_dirs, tuple(added_roots), tuple(active),
                    tuple(mesh_part), mesh_part, cargo, frozenset(anchored_all), mesh_dirs)
    if len(_CACHE) > 16:
        _CACHE.clear()
    _CACHE[cache_key] = plan
    return plan
