from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional

import numpy as np

from .jbeam_reader import FlexbodyPlacement

ORIENT_PROPS = True

_EPS = 1e-6


@dataclass
class GamePlacements:
    flex: dict = field(default_factory=dict)
    props: dict = field(default_factory=dict)
    flex_rows: int = 0
    prop_rows: int = 0
    prop_skipped: int = 0


def _vec(value, default=None):
    if isinstance(value, (list, tuple)) and len(value) == 3:
        try:
            return tuple(float(v) for v in value)
        except (TypeError, ValueError):
            return default
    if isinstance(value, dict) and all(k in value for k in "xyz"):
        try:
            return (float(value["x"]), float(value["y"]), float(value["z"]))
        except (TypeError, ValueError):
            return default
    return default


def rotation_matrix(euler_deg) -> np.ndarray:
    rx, ry, rz = np.radians(euler_deg)
    cx, cy, cz = math.cos(rx), math.cos(ry), math.cos(rz)
    sx, sy, sz = math.sin(rx), math.sin(ry), math.sin(rz)
    rot_x = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]], dtype=float)
    rot_y = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]], dtype=float)
    rot_z = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]], dtype=float)
    return rot_z @ rot_y @ rot_x


def euler_from_matrix(matrix: np.ndarray) -> tuple[float, float, float]:
    sy = -float(matrix[2, 0])
    sy = max(-1.0, min(1.0, sy))
    ry = math.asin(sy)
    if abs(sy) < 1.0 - 1e-9:
        rx = math.atan2(matrix[2, 1], matrix[2, 2])
        rz = math.atan2(matrix[1, 0], matrix[0, 0])
    else:
        rx = 0.0
        rz = math.atan2(-matrix[0, 1], matrix[1, 1])
    return tuple(math.degrees(v) for v in (rx, ry, rz))


def node_frame(ref, xp, yp) -> Optional[np.ndarray]:
    ref, xp, yp = (np.asarray(v, dtype=float) for v in (ref, xp, yp))
    x = xp - ref
    nx = np.linalg.norm(x)
    if nx < _EPS:
        return None
    x = x / nx
    z = np.cross(x, yp - ref)
    nz = np.linalg.norm(z)
    if nz < _EPS:
        return None
    z = z / nz
    y = np.cross(z, x)
    return np.column_stack([x, y, z])


def _degrees(value):
    if value is None:
        return None
    return tuple(math.degrees(v) for v in value)


def prop_placement(row: dict, radians: bool = False) -> Optional[FlexbodyPlacement]:
    ref = _vec(row.get("refPos"))
    if ref is None:
        return None
    base_translation = _vec(row.get("baseTranslation"), (0.0, 0.0, 0.0))
    base_rotation = _vec(row.get("baseRotation"), (0.0, 0.0, 0.0))
    global_translation = _vec(row.get("baseTranslationGlobal"), (0.0, 0.0, 0.0))
    global_rotation = _vec(row.get("baseRotationGlobal"), (0.0, 0.0, 0.0))
    if radians:
        base_rotation = _degrees(base_rotation)
        global_rotation = _degrees(global_rotation)
    rotation = np.eye(3)
    translation = np.asarray(ref, dtype=float) + np.asarray(global_translation, dtype=float)
    if ORIENT_PROPS:
        xp, yp = _vec(row.get("xPos")), _vec(row.get("yPos"))
        frame = node_frame(ref, xp, yp) if xp is not None and yp is not None else None
        if frame is not None:
            rotation = (rotation_matrix(global_rotation) @ frame @ rotation_matrix(base_rotation))
            translation = translation + frame @ np.asarray(base_translation, dtype=float)
        else:
            rotation = rotation_matrix(global_rotation) @ rotation_matrix(base_rotation)
            translation = translation + np.asarray(base_translation, dtype=float)
    return FlexbodyPlacement(
        tuple(float(v) for v in translation),
        euler_from_matrix(rotation),
        (1.0, 1.0, 1.0),
    )


def parse_export(payload: dict) -> Optional[GamePlacements]:
    flex_rows = payload.get("flexbodies")
    prop_rows = payload.get("props")
    if not isinstance(flex_rows, list) and not isinstance(prop_rows, list):
        return None
    out = GamePlacements()
    radians = payload.get("angleUnit") != "deg"
    for row in flex_rows if isinstance(flex_rows, list) else []:
        if not isinstance(row, dict) or not isinstance(row.get("mesh"), str):
            continue
        out.flex_rows += 1
        placement = FlexbodyPlacement(
            _vec(row.get("pos"), (0.0, 0.0, 0.0)),
            _vec(row.get("rot"), (0.0, 0.0, 0.0)),
            _vec(row.get("scale"), (1.0, 1.0, 1.0)),
        )
        out.flex.setdefault(row["mesh"], []).append(placement)
    for row in prop_rows if isinstance(prop_rows, list) else []:
        if not isinstance(row, dict) or not isinstance(row.get("mesh"), str):
            continue
        out.prop_rows += 1
        placement = prop_placement(row, radians)
        if placement is None:
            out.prop_skipped += 1
            continue
        out.props.setdefault(row["mesh"], []).append(placement)
    if not out.flex and not out.props:
        return None
    return out


def is_identity(placement: FlexbodyPlacement) -> bool:
    return (
        all(abs(v) < _EPS for v in placement.position)
        and all(abs(v) < _EPS for v in placement.rotation)
        and all(abs(v - 1.0) < _EPS for v in placement.scale)
    )


def merge(
    plan_placements: dict,
    game: GamePlacements,
    group_names: Iterable[str],
    anchored: Iterable[str],
    base_name: Callable[[str], str],
) -> tuple[dict, set]:
    names = {name.casefold(): name for name in group_names}
    anchored_cf = {name.casefold() for name in anchored}
    rows: dict[str, list] = {}
    for source in (game.flex, game.props):
        for exported, placements in source.items():
            node = names.get(exported.casefold())
            if node is None:
                node = names.get(base_name(exported).casefold())
            if node is not None:
                rows.setdefault(node, []).extend(placements)
    out = dict(plan_placements)
    moved: set = set()
    for node, placements in rows.items():
        if all(is_identity(p) for p in placements):
            if node.casefold() not in anchored_cf:
                out.pop(node, None)
            continue
        out[node] = tuple(placements)
        moved.add(node)
    return out, moved
