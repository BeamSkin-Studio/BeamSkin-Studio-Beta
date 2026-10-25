from __future__ import annotations

import json


SCHEMA = "beamSkinStudio.vehicleParts"

ACTIVE_PREFIX = "__active"

_PLACEMENTS: dict = {}


def placements_for(mesh_names):
    if not mesh_names:
        return None
    try:
        return _PLACEMENTS.get(frozenset(mesh_names))
    except TypeError:
        return None


def base_mesh_name(name: str) -> str:
    stripped = name.rstrip("D")
    return stripped if stripped and stripped != name else name


def with_base_names(names) -> frozenset:
    out = set()
    for name in names:
        out.add(name)
        out.add(base_mesh_name(name))
    return frozenset(out)


def read_part_export(path: str) -> tuple[str, frozenset[str], int, dict[str, str]]:
    with open(path, "r", encoding="utf-8-sig") as file:
        payload = json.load(file)
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        raise ValueError("This is not a BeamSkin Studio live-parts export.")
    if payload.get("version") != 1:
        raise ValueError(f"Unsupported live-parts export version: {payload.get('version')!r}")

    model = payload.get("model")
    if not isinstance(model, str):
        model = ""
    raw_meshes = payload.get("meshNames")
    if not isinstance(raw_meshes, list):
        raise ValueError("The live-parts export has no meshNames list.")
    mesh_names = frozenset(
        name.strip() for name in raw_meshes if isinstance(name, str) and name.strip()
    )
    mesh_names = with_base_names(mesh_names)
    if not mesh_names:
        raise ValueError("The live-parts export contains no mesh names.")

    parts = payload.get("chosenParts")
    part_count = (
        sum(1 for name in parts.values() if isinstance(name, str) and name.strip())
        if isinstance(parts, dict) else 0
    )
    chosen = {
        key.strip().strip("/"): name.strip()
        for key, name in parts.items()
        if isinstance(key, str) and isinstance(name, str) and name.strip()
    } if isinstance(parts, dict) else {}
    active = payload.get("parts")
    names = []
    if isinstance(active, list):
        names = [p.get("name") for p in active if isinstance(p, dict)]
    extra = payload.get("activePartNames")
    if isinstance(extra, list):
        names += extra
    for i, name in enumerate(sorted({n.strip() for n in names
                                     if isinstance(n, str) and n.strip() and not n.startswith("/")})):
        chosen[f"{ACTIVE_PREFIX}{i}"] = name

    _PLACEMENTS.clear()
    try:
        from .game_placements import parse_export
        game = parse_export(payload)
        if game is not None:
            _PLACEMENTS[mesh_names] = game
            print(f"[DEBUG] model_preview: export carries game placements: {game.flex_rows} flexbody "
                  f"rows, {game.prop_rows} prop rows ({game.prop_skipped} without usable nodes)")
    except Exception as e:
        print(f"[WARNING] model_preview: could not read the export's placements: "
              f"{type(e).__name__}: {e}")
    return model, mesh_names, part_count, chosen
