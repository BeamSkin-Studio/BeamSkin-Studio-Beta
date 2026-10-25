from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, replace

import numpy as np

from .jbeam_reader import FlexbodyPlacement


@dataclass
class PreviewGroup:
    name: str
    node: str
    material: str
    first: int
    count: int
    has_uv: bool
    uv_sets: int = 0
    uv_fallback: bool = False
    uv_range: tuple = ()
    source: str = ""
    part: str = ""
    active: bool = True


@dataclass
class PreviewModel:
    groups: list[PreviewGroup]
    vertices: np.ndarray
    bounds_min: np.ndarray
    bounds_max: np.ndarray
    warnings: list[str] = field(default_factory=list)
    uv_set_count: int = 1
    skin_materials: frozenset[str] | None = None
    variant_skin_materials: frozenset[str] = frozenset()
    material_defs: dict = field(default_factory=dict)
    material_vfs: object = None

    @property
    def triangle_count(self) -> int:
        return int(self.vertices.shape[0] // 3)


class DaeParseError(Exception):
    pass


def apply_flexbody_placements(
    model: PreviewModel,
    placements: dict[str, tuple[FlexbodyPlacement, ...]],
) -> None:
    if not placements:
        return

    axis = np.array([
        [1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0],
        [0.0, -1.0, 0.0],
    ])
    new_groups: list[PreviewGroup] = []
    blocks: list[np.ndarray] = []
    matched: set[str] = set()
    cursor = 0

    for group in model.groups:
        group_placements = placements.get(group.node)
        if not group_placements:
            block = model.vertices[group.first:group.first + group.count]
            new_groups.append(replace(group, first=cursor))
            blocks.append(block)
            cursor += block.shape[0]
            continue

        matched.add(group.node)
        original = model.vertices[group.first:group.first + group.count]
        for placement_index, placement in enumerate(group_placements, start=1):
            rx, ry, rz = np.radians(placement.rotation)
            sx, sy, sz = placement.scale
            cx, cy, cz = np.cos([rx, ry, rz])
            sin_x, sin_y, sin_z = np.sin([rx, ry, rz])
            rotate_x = np.array([
                [1.0, 0.0, 0.0],
                [0.0, cx, -sin_x],
                [0.0, sin_x, cx],
            ])
            rotate_y = np.array([
                [cy, 0.0, sin_y],
                [0.0, 1.0, 0.0],
                [-sin_y, 0.0, cy],
            ])
            rotate_z = np.array([
                [cz, -sin_z, 0.0],
                [sin_z, cz, 0.0],
                [0.0, 0.0, 1.0],
            ])
            linear = axis @ rotate_z @ rotate_y @ rotate_x @ np.diag([sx, sy, sz]) @ axis.T
            translation = axis @ np.asarray(placement.position, dtype=np.float64)
            block = original.copy()
            block[:, :3] = block[:, :3] @ linear.T + translation
            try:
                normal_matrix = np.linalg.inv(linear).T
            except np.linalg.LinAlgError:
                normal_matrix = np.linalg.pinv(linear).T
            normals = block[:, 3:6] @ normal_matrix.T
            lengths = np.linalg.norm(normals, axis=1, keepdims=True)
            lengths[lengths == 0] = 1.0
            block[:, 3:6] = normals / lengths

            name = group.name
            if len(group_placements) > 1:
                name = f"{name}@jbeam{placement_index}"
            new_groups.append(replace(group, name=name, first=cursor))
            blocks.append(block)
            cursor += block.shape[0]

    missing = sorted(set(placements) - matched)
    if missing:
        names = ", ".join(missing[:5]) + (" ..." if len(missing) > 5 else "")
        model.warnings.append(f"JBeam placement mesh(es) not found in the DAE: {names}")
    if blocks:
        model.groups = new_groups
        model.vertices = np.ascontiguousarray(np.concatenate(blocks, axis=0))
        model.bounds_min = model.vertices[:, :3].min(axis=0)
        model.bounds_max = model.vertices[:, :3].max(axis=0)


def _local(tag) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _floats(text: str | None) -> np.ndarray:
    if not text or not text.strip():
        return np.zeros(0, dtype=np.float64)
    return np.array(text.split(), dtype=np.float64)


def _ints(text: str | None) -> np.ndarray:
    if not text or not text.strip():
        return np.zeros(0, dtype=np.int64)
    return np.array(text.split(), dtype=np.int64)


def _children(el, name: str):
    return [c for c in el if _local(c.tag) == name]


def _child(el, name: str):
    for c in el:
        if _local(c.tag) == name:
            return c
    return None


def _ref(value: str | None) -> str:
    return (value or "").lstrip("#")


def _read_source(src) -> tuple[np.ndarray, int]:
    arr_el = None
    for c in src:
        if _local(c.tag) in ("float_array", "double_array"):
            arr_el = c
            break
    data = _floats(arr_el.text if arr_el is not None else "")
    stride = 0
    tc = _child(src, "technique_common")
    if tc is not None:
        acc = _child(tc, "accessor")
        if acc is not None:
            stride = int(acc.get("stride", "1"))
    if stride <= 0:
        stride = 3
    usable = (data.size // stride) * stride
    return data[:usable].reshape(-1, stride), stride


def _triangulate(vcount: np.ndarray) -> np.ndarray:
    starts = np.concatenate(([0], np.cumsum(vcount)[:-1])).astype(np.int64)
    parts = []
    for n in np.unique(vcount):
        if n < 3:
            continue
        s = starts[vcount == n]
        for i in range(1, int(n) - 1):
            parts.append(np.stack([s, s + i, s + i + 1], axis=1))
    if not parts:
        return np.zeros((0, 3), dtype=np.int64)
    return np.concatenate(parts, axis=0)


class _Prim:
    __slots__ = ("symbol", "pos", "nrm", "uv", "uv_sets", "uv_fallback", "uv0")

    def __init__(self, symbol, pos, nrm, uv, uv_sets=1, uv_fallback=False, uv0=None):
        self.uv0 = uv0
        self.symbol = symbol
        self.pos = pos
        self.nrm = nrm
        self.uv = uv
        self.uv_sets = uv_sets
        self.uv_fallback = uv_fallback


def _flat_normals(pos: np.ndarray) -> np.ndarray:
    tri = pos.reshape(-1, 3, 3)
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    length = np.linalg.norm(n, axis=1, keepdims=True)
    length[length == 0] = 1.0
    n = n / length
    return np.repeat(n, 3, axis=0)


def _parse_geometry(geom, uv_set: int, warnings: list[str]) -> list[_Prim]:
    mesh = _child(geom, "mesh")
    if mesh is None:
        return []
    sources = {s.get("id"): _read_source(s) for s in _children(mesh, "source")}
    vertices_map: dict[str, dict[str, str]] = {}
    for v in _children(mesh, "vertices"):
        vertices_map[v.get("id")] = {
            i.get("semantic"): _ref(i.get("source")) for i in _children(v, "input")
        }

    prims: list[_Prim] = []
    for el in mesh:
        kind = _local(el.tag)
        if kind not in ("triangles", "polylist", "polygons"):
            continue
        inputs = []
        for i in _children(el, "input"):
            inputs.append(
                (i.get("semantic"), _ref(i.get("source")), int(i.get("offset", "0")), int(i.get("set", "0")))
            )
        if not inputs:
            continue
        stride = max(i[2] for i in inputs) + 1

        if kind == "triangles":
            p_el = _child(el, "p")
            flat = _ints(p_el.text if p_el is not None else "")
            usable = (flat.size // stride) * stride
            idx = flat[:usable].reshape(-1, stride)
            tri_idx = np.arange(idx.shape[0] - idx.shape[0] % 3, dtype=np.int64).reshape(-1, 3)
        elif kind == "polylist":
            vc = _child(el, "vcount")
            p_el = _child(el, "p")
            vcount = _ints(vc.text if vc is not None else "")
            flat = _ints(p_el.text if p_el is not None else "")
            usable = (flat.size // stride) * stride
            idx = flat[:usable].reshape(-1, stride)
            tri_idx = _triangulate(vcount)
        else:
            chunks = []
            counts = []
            for p_el in _children(el, "p"):
                flat = _ints(p_el.text)
                usable = (flat.size // stride) * stride
                chunk = flat[:usable].reshape(-1, stride)
                chunks.append(chunk)
                counts.append(chunk.shape[0])
            if not chunks:
                continue
            idx = np.concatenate(chunks, axis=0)
            tri_idx = _triangulate(np.array(counts, dtype=np.int64))

        if tri_idx.size == 0 or idx.size == 0:
            continue
        tri_idx = tri_idx[(tri_idx < idx.shape[0]).all(axis=1)]
        sel = idx[tri_idx.reshape(-1)]

        pos_src = nrm_src = None
        pos_off = nrm_off = None
        uv_candidates = []
        for semantic, source, offset, set_no in inputs:
            if semantic == "VERTEX":
                vm = vertices_map.get(source, {})
                if "POSITION" in vm:
                    pos_src, pos_off = vm["POSITION"], offset
                if "NORMAL" in vm and nrm_src is None:
                    nrm_src, nrm_off = vm["NORMAL"], offset
            elif semantic == "NORMAL":
                nrm_src, nrm_off = source, offset
            elif semantic == "TEXCOORD":
                uv_candidates.append((set_no, source, offset))
        if pos_src is None or pos_src not in sources:
            continue

        pos_data = sources[pos_src][0][:, :3]
        pi = sel[:, pos_off]
        if pi.size and (pi.max() >= pos_data.shape[0] or pi.min() < 0):
            warnings.append(f"Geometry '{geom.get('name') or geom.get('id')}' has invalid indices.")
            continue
        pos = pos_data[pi]

        nrm = None
        if nrm_src in sources:
            nd = sources[nrm_src][0][:, :3]
            ni = sel[:, nrm_off]
            if ni.size and ni.max() < nd.shape[0] and ni.min() >= 0:
                nrm = nd[ni]
        if nrm is None:
            nrm = _flat_normals(pos)

        uv = None
        uv0 = None
        if uv_candidates:
            uv_candidates.sort(key=lambda c: c[0])
            _, usrc0, uoff0 = uv_candidates[0]
            if usrc0 in sources:
                ud0 = sources[usrc0][0][:, :2]
                ui0 = sel[:, uoff0]
                if ui0.size and ui0.max() < ud0.shape[0] and ui0.min() >= 0:
                    uv0 = ud0[ui0]
            chosen = next((c for c in uv_candidates if c[0] == uv_set), uv_candidates[min(uv_set, len(uv_candidates) - 1)])
            _, usrc, uoff = chosen
            if usrc in sources:
                ud = sources[usrc][0][:, :2]
                ui = sel[:, uoff]
                if ui.size and ui.max() < ud.shape[0] and ui.min() >= 0:
                    uv = ud[ui]

        prims.append(
            _Prim(
                el.get("material") or "", pos, nrm, uv,
                len(uv_candidates),
                bool(uv_candidates) and uv_set >= len(uv_candidates),
                uv0,
            )
        )
    return prims


def _node_matrix(node) -> np.ndarray:
    m = np.eye(4)
    for c in node:
        kind = _local(c.tag)
        if kind == "matrix":
            vals = _floats(c.text)
            if vals.size == 16:
                m = m @ vals.reshape(4, 4)
        elif kind == "translate":
            vals = _floats(c.text)
            if vals.size == 3:
                t = np.eye(4)
                t[:3, 3] = vals
                m = m @ t
        elif kind == "scale":
            vals = _floats(c.text)
            if vals.size == 3:
                m = m @ np.diag([vals[0], vals[1], vals[2], 1.0])
        elif kind == "rotate":
            vals = _floats(c.text)
            if vals.size == 4:
                axis = vals[:3]
                norm = np.linalg.norm(axis)
                if norm > 0:
                    x, y, z = axis / norm
                    a = np.radians(vals[3])
                    cs, sn = np.cos(a), np.sin(a)
                    r = np.eye(4)
                    r[:3, :3] = [
                        [cs + x * x * (1 - cs), x * y * (1 - cs) - z * sn, x * z * (1 - cs) + y * sn],
                        [y * x * (1 - cs) + z * sn, cs + y * y * (1 - cs), y * z * (1 - cs) - x * sn],
                        [z * x * (1 - cs) - y * sn, z * y * (1 - cs) + x * sn, cs + z * z * (1 - cs)],
                    ]
                    m = m @ r
    return m


def parse_dae(path: str, uv_set: int = 0) -> PreviewModel:
    try:
        tree = ET.parse(path)
    except (ET.ParseError, OSError) as e:
        raise DaeParseError(f"Cannot read .dae: {e}") from e
    root = tree.getroot()
    warnings: list[str] = []

    up_axis = "Y_UP"
    asset = _child(root, "asset")
    if asset is not None:
        ua = _child(asset, "up_axis")
        if ua is not None and ua.text:
            up_axis = ua.text.strip().upper()

    geometries: dict[str, list[_Prim]] = {}
    lib_geo = _child(root, "library_geometries")
    geo_names: dict[str, str] = {}
    if lib_geo is not None:
        for g in _children(lib_geo, "geometry"):
            gid = g.get("id")
            geo_names[gid] = g.get("name") or gid
            geometries[gid] = _parse_geometry(g, uv_set, warnings)

    materials: dict[str, str] = {}
    lib_mat = _child(root, "library_materials")
    if lib_mat is not None:
        for m in _children(lib_mat, "material"):
            materials[m.get("id")] = m.get("name") or m.get("id")

    lib_nodes: dict[str, ET.Element] = {}
    ln = _child(root, "library_nodes")
    if ln is not None:
        for n in _children(ln, "node"):
            lib_nodes[n.get("id")] = n

    instances: list[tuple[str, str, np.ndarray, dict[str, str]]] = []

    def walk(node, parent: np.ndarray, depth: int):
        if depth > 64:
            return
        world = parent @ _node_matrix(node)
        node_name = node.get("name") or node.get("id") or "node"
        for c in node:
            kind = _local(c.tag)
            if kind == "instance_geometry":
                binds: dict[str, str] = {}
                bm = _child(c, "bind_material")
                if bm is not None:
                    tc = _child(bm, "technique_common")
                    if tc is not None:
                        for im in _children(tc, "instance_material"):
                            target = _ref(im.get("target"))
                            binds[im.get("symbol")] = materials.get(target, target)
                instances.append((node_name, _ref(c.get("url")), world, binds))
            elif kind == "instance_node":
                target = lib_nodes.get(_ref(c.get("url")))
                if target is not None:
                    walk(target, world, depth + 1)
            elif kind == "node":
                walk(c, world, depth + 1)

    lib_scenes = _child(root, "library_visual_scenes")
    if lib_scenes is not None:
        for scene in _children(lib_scenes, "visual_scene"):
            for n in _children(scene, "node"):
                walk(n, np.eye(4), 0)

    if not instances:
        for gid in geometries:
            instances.append((geo_names.get(gid, gid), gid, np.eye(4), {}))

    if up_axis == "Z_UP":
        axis_fix = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], dtype=np.float64)
    elif up_axis == "X_UP":
        axis_fix = np.array([[0, 1, 0], [-1, 0, 0], [0, 0, 1]], dtype=np.float64)
    else:
        axis_fix = np.eye(3)

    groups: list[PreviewGroup] = []
    blocks: list[np.ndarray] = []
    used_names: dict[str, int] = {}
    cursor = 0
    for node_name, gid, world, binds in instances:
        prims = geometries.get(gid)
        if not prims:
            continue
        lin = world[:3, :3]
        trans = world[:3, 3]
        try:
            nrm_mat = np.linalg.inv(lin).T
        except np.linalg.LinAlgError:
            nrm_mat = np.eye(3)
        for prim in prims:
            material = binds.get(prim.symbol) or materials.get(prim.symbol) or prim.symbol or "material"
            pos = (prim.pos @ lin.T + trans) @ axis_fix.T
            nrm = (prim.nrm @ nrm_mat.T) @ axis_fix.T
            ln_ = np.linalg.norm(nrm, axis=1, keepdims=True)
            ln_[ln_ == 0] = 1.0
            nrm = nrm / ln_
            has_uv = prim.uv is not None
            uv = prim.uv if has_uv else np.zeros((pos.shape[0], 2))
            uv0 = prim.uv0 if prim.uv0 is not None else uv
            block = np.concatenate([pos, nrm, uv, uv0], axis=1).astype(np.float32)
            base = f"{node_name}:{material}"
            used_names[base] = used_names.get(base, 0) + 1
            name = base if used_names[base] == 1 else f"{base}#{used_names[base]}"
            uv_range = ()
            if has_uv and uv.shape[0]:
                lo, hi = uv.min(axis=0), uv.max(axis=0)
                uv_range = (float(lo[0]), float(lo[1]), float(hi[0]), float(hi[1]))
            groups.append(
                PreviewGroup(
                    name, node_name, material, cursor, block.shape[0], has_uv,
                    prim.uv_sets, prim.uv_fallback, uv_range,
                )
            )
            blocks.append(block)
            cursor += block.shape[0]

    if not blocks:
        raise DaeParseError("No triangle geometry found in this .dae file.")

    vertices = np.ascontiguousarray(np.concatenate(blocks, axis=0))
    uv_set_count = max(
        (p.uv_sets for prims in geometries.values() for p in prims),
        default=1,
    )
    return PreviewModel(
        groups=groups,
        vertices=vertices,
        bounds_min=vertices[:, :3].min(axis=0),
        bounds_max=vertices[:, :3].max(axis=0),
        warnings=warnings,
        uv_set_count=uv_set_count,
    )


def merge_models(models: list[PreviewModel], labels: list[str],
                 active: list | None = None, part_of: dict | None = None) -> PreviewModel:
    part_of = part_of or {}
    if len(models) == 1 and not part_of and not (active and active[0] is not None):
        only = models[0]
        for g in only.groups:
            g.source = g.source or (labels[0] if labels else "")
        return only
    groups: list[PreviewGroup] = []
    blocks: list[np.ndarray] = []
    warnings: list[str] = []
    seen: set[str] = set()
    cursor = 0
    for k, (m, label) in enumerate(zip(models, labels)):
        act = active[k] if active and k < len(active) else None
        for g in m.groups:
            name = g.name if g.name not in seen else f"{g.name}@{label}"
            n = 2
            while name in seen:
                name = f"{g.name}@{label}#{n}"
                n += 1
            seen.add(name)
            groups.append(replace(
                g, name=name, first=g.first + cursor, source=label,
                part=part_of.get(g.node, ""),
                active=True if act is None else g.node in act,
            ))
        blocks.append(m.vertices)
        warnings += [f"[{label}] {w}" for w in m.warnings]
        cursor += m.vertices.shape[0]
    v = np.ascontiguousarray(np.concatenate(blocks, axis=0))
    return PreviewModel(
        groups=groups, vertices=v,
        bounds_min=v[:, :3].min(axis=0), bounds_max=v[:, :3].max(axis=0),
        warnings=warnings,
        uv_set_count=max(m.uv_set_count for m in models),
    )
