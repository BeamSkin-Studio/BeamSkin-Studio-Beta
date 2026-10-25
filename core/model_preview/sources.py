from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable

import numpy as np

from core.uv_exporter import mod_locations
from core.uv_exporter.mod_locations import ModDaeSource

from core.model_preview.dae_geometry import (
    DaeParseError,
    PreviewModel,
    apply_flexbody_placements,
    merge_models,
    parse_dae,
)

try:
    from core.uv_exporter.car_models import find_car_dae_sources, materialize as _materialize_game
except Exception as _e:
    print(f"[WARNING] model_preview: car_models unavailable ({type(_e).__name__}: {_e})")
    find_car_dae_sources = None
    _materialize_game = None


@dataclass
class PreviewSource:
    label: str
    resolve: Callable[[], str]
    key: str = ""
    carid: str = ""
    extra_roots: tuple = ()

    def __post_init__(self):
        if not self.key:
            self.key = self.label


def _squash(text: str) -> str:
    return "".join(c for c in text.lower() if c.isalnum())


def _rank(carid: str, label: str) -> int:
    stem = _squash(os.path.splitext(os.path.basename(label.replace("\\", "/")))[0])
    cid = _squash(carid)
    if stem == cid:
        return 0
    if cid and cid in stem:
        return 1
    return 2


def collect_sources(
    carid: str,
    extra_roots: tuple[str, ...] = (),
) -> list[PreviewSource]:
    out: list[PreviewSource] = []
    if find_car_dae_sources is not None:
        try:
            for s in find_car_dae_sources(carid):
                out.append(PreviewSource(s.label, lambda s=s: _materialize_game(s),
                                         carid=carid, extra_roots=tuple(extra_roots)))
        except Exception as e:
            print(f"[WARNING] model_preview: find_car_dae_sources failed: {type(e).__name__}: {e}")
    for s in mod_locations.find_dae_sources(carid):
        out.append(PreviewSource(s.label, lambda s=s: mod_locations.materialize(s),
                                 carid=carid, extra_roots=tuple(extra_roots)))
    out.sort(key=lambda p: _rank(carid, p.label))
    return out


_VFS_CACHE: dict[tuple, object] = {}


def _material_vfs(carid: str, extra_roots: tuple):
    from core.model_preview import variants
    from core.model_preview.vehicle_fs import VehicleFS

    try:
        mods = tuple(variants.added_mod_roots(carid))
    except Exception as e:
        print(f"[WARNING] model_preview: mod roots unavailable: {type(e).__name__}: {e}")
        mods = ()
    roots = tuple(variants.default_roots(carid, "", mods + tuple(extra_roots)))
    if roots not in _VFS_CACHE:
        if len(_VFS_CACHE) > 8:
            _VFS_CACHE.clear()
        _VFS_CACHE[roots] = VehicleFS(roots)
    return _VFS_CACHE[roots]


def _attach_material_defs(model: PreviewModel, source: PreviewSource) -> None:
    from core.model_preview import material as material_mod

    if not source.carid:
        return
    vfs = _material_vfs(source.carid, tuple(source.extra_roots))
    needed = {g.material for g in model.groups if g.material}
    model.material_defs = material_mod.build_material_defs(vfs, source.carid, [], needed)
    model.material_vfs = vfs


def _plan_parts(source: PreviewSource, chosen_parts: dict, mesh_names):
    from core.model_preview.placement import compute_part_plan

    vfs = _material_vfs(source.carid, tuple(source.extra_roots))
    return compute_part_plan(vfs.roots, source.carid, chosen_parts, mesh_names=mesh_names)


def _default_parts(source: PreviewSource, variant: str):
    from core.model_preview import variants

    try:
        vfs = _material_vfs(source.carid, tuple(source.extra_roots))
        return variants.default_chosen_parts(vfs, source.carid, variant)
    except Exception as e:
        print(f"[WARNING] model_preview: default parts lookup failed: {type(e).__name__}: {e}")
        return None


def _game_placements(mesh_names):
    if not mesh_names or os.environ.get("BEAMSKIN_GAME_PLACEMENTS", "1").strip() == "0":
        return None
    try:
        from core.model_preview.beamng_parts import placements_for
        return placements_for(mesh_names)
    except Exception as e:
        print(f"[WARNING] model_preview: game placements unavailable: {type(e).__name__}: {e}")
        return None


def _apply_part_placements(model: PreviewModel, notes, placements: dict, models: list) -> None:
    model.warnings.extend(notes)
    for m in models:
        present = {group.node for group in m.groups}
        apply_flexbody_placements(m, {k: v for k, v in placements.items() if k in present})


_DEBUG_DUMP = os.environ.get("BEAMSKIN_PLACEMENT_DEBUG", "1").strip() not in ("", "0")


def _bounds_by_node(models: list) -> dict:
    out: dict = {}
    for m in models:
        for g in m.groups:
            v = m.vertices[g.first:g.first + g.count, :3]
            v = v[np.isfinite(v).all(axis=1)]
            if not v.size:
                continue
            lo, hi = v.min(axis=0), v.max(axis=0)
            old = out.get(g.node)
            out[g.node] = (lo, hi) if old is None else (np.minimum(old[0], lo), np.maximum(old[1], hi))
    return out


def _write_bounds_dump(before: dict, after: dict, placements: dict) -> None:
    def fmt(b):
        return "x[{:.2f},{:.2f}] y[{:.2f},{:.2f}] z[{:.2f},{:.2f}]".format(
            b[0][0], b[1][0], b[0][1], b[1][1], b[0][2], b[1][2])
    lines = []
    for name in sorted(after, key=str.lower):
        count = len(placements.get(name, ()))
        if name in before:
            lines.append(f"{name:55s} copies={count}\n    dae  {fmt(before[name])}\n    live {fmt(after[name])}")
    for line in lines:
        print(f"[DEBUG] bounds: {line}")


CARGOBOX_CAB_GAP = 0.14


def _z_range(models: list, names_cf: set):
    lo, hi = np.inf, -np.inf
    for m in models:
        for g in m.groups:
            if g.node.casefold() not in names_cf:
                continue
            v = m.vertices[g.first:g.first + g.count, 2]
            v = v[np.isfinite(v)]
            if v.size:
                lo, hi = min(lo, float(v.min())), max(hi, float(v.max()))
    return lo, hi


def _align_cargobox(models: list, cargo: dict) -> str:
    cab = {n.casefold() for n in cargo.get("cab", ())}
    box = {n.casefold() for n in cargo.get("box", ())}
    sub = {n.casefold() for n in cargo.get("subtree", ())}
    if not cab or not box or not sub:
        return ""
    cab_rear, _ = _z_range(models, cab)
    _, box_front = _z_range(models, box)
    if not np.isfinite(cab_rear) or not np.isfinite(box_front):
        return "Cargo box not aligned: the cab or the box shell meshes were not found in the .dae files."
    dz = (cab_rear - CARGOBOX_CAB_GAP) - box_front
    if abs(dz) < 1e-4:
        return ""
    for m in models:
        for g in m.groups:
            if g.node.casefold() in sub:
                m.vertices[g.first:g.first + g.count, 2] += dz
    print(f"[DEBUG] model_preview: cargo box moved {dz:+.3f} m along the car to sit behind the cab")
    return ""


def _extra_models(
    source: PreviewSource, primary: PreviewModel, variant: str, mesh_names, uv_set: int,
    plan=None,
) -> dict:
    from core.model_preview import material as material_mod
    from core.model_preview.dae_search import dae_names, find_extra_daes, find_variant_daes

    out = {"models": [], "labels": [], "warnings": [], "names": set(),
           "variant_materials": frozenset(), "targets": set()}
    vfs = _material_vfs(source.carid, tuple(source.extra_roots))
    if plan is not None:
        for root in plan.extra_roots:
            vfs.add_root(root)
    if mesh_names:
        have = {group.node.casefold() for group in primary.groups}
        missing = {name for name in mesh_names if name.casefold() not in have}
        vpaths = [v for v, _hits in find_extra_daes(
            vfs, source.carid, variant, missing,
            extra_dirs=plan.dae_dirs if plan is not None else (),
            shallow_dirs=plan.shallow_dirs if plan is not None else (),
            mesh_dirs=plan.mesh_dirs if plan is not None else None,
        )]
    else:
        vpaths = find_variant_daes(vfs, source.carid, variant)
    key = _squash(variant)
    primary_materials = {group.material.casefold() for group in primary.groups}
    for vpath in vpaths:
        label = os.path.basename(vpath)
        try:
            model = parse_dae(vfs.extract(vpath), uv_set=uv_set)
        except Exception as e:
            out["warnings"].append(f"{label}: could not load ({type(e).__name__}: {e})")
            continue
        out["models"].append(model)
        out["labels"].append(label)
        try:
            out["names"] |= set(dae_names(vfs, vpath))
        except (OSError, KeyError):
            pass
        targets = material_mod.skin_target_materials_for_dae(vfs, vpath)
        if targets is not None:
            out["targets"] |= set(targets)
            if key and key in _squash(vpath):
                out["variant_materials"] = out["variant_materials"] | targets
            else:
                own = {group.material.casefold() for group in model.groups}
                out["variant_materials"] = out["variant_materials"] | {
                    t for t in targets if t in own and t not in primary_materials}
    return out


def load_source(
    source: PreviewSource,
    uv_set: int = 0,
    chosen_parts: dict | None = None,
    mesh_names=None,
    variant: str = "",
) -> PreviewModel:
    primary = parse_dae(source.resolve(), uv_set=uv_set)
    models, labels = [primary], [source.label]
    plan = None
    plan_tried = False
    extra_warnings: list[str] = []

    default_name = ""
    if source.carid and variant and not chosen_parts and not mesh_names:
        default = _default_parts(source, variant)
        if default is not None:
            default_name, chosen_parts = default
            print(f"[DEBUG] model_preview: no live parts loaded, using default parts of "
                  f"{default_name}.pc for variant {variant!r}")

    def make_plan(names):
        nonlocal plan_tried
        plan_tried = True
        try:
            return _plan_parts(source, chosen_parts or {}, names)
        except Exception as e:
            print(f"[WARNING] model_preview: part placement failed: {type(e).__name__}: {e}")
            primary.warnings.append(f"Part placement failed: {type(e).__name__}: {e}")
            return None

    if source.carid and (chosen_parts or mesh_names):
        plan = make_plan(mesh_names)
    search_names = mesh_names or (set(plan.meshes) if plan is not None and plan.meshes else None)
    extra = None
    if source.carid and (search_names or variant):
        try:
            extra = _extra_models(source, primary, variant, search_names, uv_set, plan)
            models += extra["models"]
            labels += extra["labels"]
            extra_warnings = extra["warnings"]
        except Exception as e:
            print(f"[WARNING] model_preview: variant body lookup failed: {type(e).__name__}: {e}")
            extra_warnings.append(f"Variant body lookup failed: {type(e).__name__}: {e}")
    if plan is None and not plan_tried and source.carid and extra and extra["models"]:
        plan = make_plan(extra["names"])
    placements = dict(plan.placements) if plan is not None else {}
    game_moved: set = set()
    game = _game_placements(mesh_names)
    if game is not None:
        from core.model_preview import game_placements
        from core.model_preview.beamng_parts import base_mesh_name
        placements, game_moved = game_placements.merge(
            placements, game,
            {group.node for m in models for group in m.groups},
            plan.anchored if plan is not None else (),
            base_mesh_name,
        )
        print(f"[DEBUG] model_preview: {len(game_moved)} meshes placed from the game's own "
              f"flexbody/prop data")
    if plan is not None or game_moved:
        before = _bounds_by_node(models) if _DEBUG_DUMP else None
        _apply_part_placements(primary, plan.notes if plan is not None else [], placements, models)
        if before is not None:
            _write_bounds_dump(before, _bounds_by_node(models), placements)
        box_cf = {name.casefold() for name in (plan.cargo.get("box", ()) if plan is not None else ())}
        if plan is not None and plan.cargo and not (box_cf & {n.casefold() for n in game_moved}):
            note = _align_cargobox(models, plan.cargo)
            if note:
                extra_warnings.append(note)

    active: list = [None] * len(models)
    part_of: dict = {}
    if default_name and plan is not None and plan.meshes:
        wanted_cf = {name.casefold() for name in plan.meshes}
        sets = [frozenset(g.node for g in m.groups if g.node.casefold() in wanted_cf) for m in models]
        if any(sets):
            active = sets
            part_of = dict(plan.mesh_part)
    merged = merge_models(models, labels, active, part_of)
    merged.warnings.extend(extra_warnings)
    if default_name:
        merged.warnings.append(
            f"No BeamNG parts loaded: showing the default parts of {default_name}.pc.")
    if mesh_names:
        have = {group.node.casefold() for group in merged.groups}
        from core.model_preview.beamng_parts import base_mesh_name
        gone = sorted(n for n in mesh_names
                      if n.casefold() not in have and base_mesh_name(n).casefold() not in have)
        if gone:
            sample = ", ".join(gone[:5]) + (" ..." if len(gone) > 5 else "")
            merged.warnings.append(
                f"{len(gone)} of {len(mesh_names)} live mesh names were not found in any .dae: {sample}")
    if len(models) > 1:
        from core.model_preview import material as material_mod
        vfs = _material_vfs(source.carid, tuple(source.extra_roots))
        car_targets = material_mod.skin_target_materials(vfs, source.carid)
        dae_materials = {group.material.casefold() for group in merged.groups}
        if car_targets is not None or extra["targets"]:
            merged.skin_materials = (
                frozenset(set(car_targets or ()) | set(extra["targets"])) & dae_materials
            )
        if extra["variant_materials"]:
            merged.variant_skin_materials = frozenset(extra["variant_materials"]) & dae_materials
    try:
        _attach_material_defs(merged, source)
    except Exception as e:
        print(f"[WARNING] model_preview: material lookup failed: {type(e).__name__}: {e}")
    return merged
