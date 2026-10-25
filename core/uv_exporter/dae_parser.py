
import xml.etree.ElementTree as ET

from core.uv_exporter.mesh_data import MeshParseError, UVGroup, UVMesh

COLLADA_NS_CANDIDATES = [
    "{http://www.collada.org/2005/11/COLLADASchema}",
    "",
]

def _local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag

def _find_all(elem, tag_name):
    return [e for e in elem.iter() if _local(e.tag) == tag_name]

def _find_direct(elem, tag_name):
    return [e for e in elem if _local(e.tag) == tag_name]

def _build_node_name_map(root) -> dict[str, str]:
    node_name_by_geom_id: dict[str, str] = {}
    instance_count_by_geom_id: dict[str, int] = {}

    for inst in _find_all(root, "instance_geometry"):
        url = (inst.get("url") or "").lstrip("#")
        if not url:
            continue
        instance_count_by_geom_id[url] = instance_count_by_geom_id.get(url, 0) + 1

    for node in _find_all(root, "node"):
        node_name = node.get("name") or node.get("id")
        if not node_name:
            continue
        for inst in _find_direct(node, "instance_geometry"):
            url = (inst.get("url") or "").lstrip("#")
            if url:
                node_name_by_geom_id.setdefault(url, node_name)

    return {
        geom_id: name
        for geom_id, name in node_name_by_geom_id.items()
        if instance_count_by_geom_id.get(geom_id, 0) == 1
    }

def _parse_float_array(text: str) -> list[float]:
    return [float(x) for x in text.split()]

def _parse_int_array(text: str) -> list[int]:
    return [int(x) for x in text.split()]

def _get_source_floats(mesh_elem, source_id: str) -> tuple[list[float], int]:
    source_id = source_id.lstrip("#")
    for source in _find_direct(mesh_elem, "source"):
        if source.get("id") == source_id:
            float_arrays = _find_direct(source, "float_array")
            if not float_arrays:
                return [], 0
            values = _parse_float_array(float_arrays[0].text or "")
            accessors = list(source.iter())
            stride = 2
            for e in accessors:
                if _local(e.tag) == "accessor":
                    stride = int(e.get("stride", "2"))
                    break
            return values, stride
    return [], 0

def _resolve_vertices_uv_source(mesh_elem, vertices_id: str) -> str | None:
    vertices_id = vertices_id.lstrip("#")
    for vtx in _find_direct(mesh_elem, "vertices"):
        if vtx.get("id") == vertices_id:
            for inp in _find_direct(vtx, "input"):
                if inp.get("semantic") == "TEXCOORD":
                    return inp.get("source")
    return None

def _extract_polygon_uvs(
    mesh_elem, poly_elem, target_uv_set: str | None
) -> tuple[list[tuple[float, float]], list[tuple[int, int, int]], str | None] | None:

    inputs = _find_direct(poly_elem, "input")
    if not inputs:
        return None

    max_offset = max((int(inp.get("offset", "0")) for inp in inputs), default=0)

    uv_input = None
    first_texcoord = None
    vertex_derived_uv_input = None
    uv_inputs_by_set: dict[str, ET.Element] = {}
    for inp in inputs:
        semantic = inp.get("semantic")
        if semantic == "TEXCOORD":
            if first_texcoord is None:
                first_texcoord = inp
            if target_uv_set is not None:
                if inp.get("set") == target_uv_set:
                    uv_input = inp
            else:
                set_id = inp.get("set")
                if set_id is not None and set_id not in uv_inputs_by_set:
                    uv_inputs_by_set[set_id] = inp
        elif semantic == "VERTEX" and vertex_derived_uv_input is None:
            resolved = _resolve_vertices_uv_source(mesh_elem, inp.get("source"))
            if resolved:
                vertex_derived_uv_input = ET.Element(
                    "input",
                    {"semantic": "TEXCOORD", "source": resolved, "offset": inp.get("offset", "0")},
                )

    if target_uv_set is None:
        if "1" in uv_inputs_by_set:
            uv_input = uv_inputs_by_set["1"]
        elif "0" in uv_inputs_by_set:
            uv_input = uv_inputs_by_set["0"]

    if uv_input is None:
        uv_input = first_texcoord or vertex_derived_uv_input

    if uv_input is None:
        return None

    uv_offset = int(uv_input.get("offset", "0"))
    stride = max_offset + 1

    flat_uvs, uv_stride = _get_source_floats(mesh_elem, uv_input.get("source"))
    uv_stride = uv_stride or 2
    uv_count = len(flat_uvs) // uv_stride
    uvs = [
        (flat_uvs[i * uv_stride], flat_uvs[i * uv_stride + 1])
        for i in range(uv_count)
    ]

    triangles: list[tuple[int, int, int]] = []
    local_tag = _local(poly_elem.tag)

    p_elements = _find_direct(poly_elem, "p")

    if local_tag == "triangles":
        for p in p_elements:
            idx = _parse_int_array(p.text or "")
            n = len(idx) // stride
            for tri in range(n // 3):
                a = idx[(tri * 3 + 0) * stride + uv_offset]
                b = idx[(tri * 3 + 1) * stride + uv_offset]
                c = idx[(tri * 3 + 2) * stride + uv_offset]
                triangles.append((a, b, c))

    elif local_tag in ("polylist", "polygons"):
        vcount_elem = _find_direct(poly_elem, "vcount")
        if local_tag == "polylist" and vcount_elem:
            vcounts = _parse_int_array(vcount_elem[0].text or "")
            idx = _parse_int_array(p_elements[0].text or "") if p_elements else []
            cursor = 0
            for vc in vcounts:
                face_uv_idx = []
                for k in range(vc):
                    face_uv_idx.append(idx[(cursor + k) * stride + uv_offset])
                cursor += vc
                for i in range(1, vc - 1):
                    triangles.append((face_uv_idx[0], face_uv_idx[i], face_uv_idx[i + 1]))
        else:
            for p in p_elements:
                idx = _parse_int_array(p.text or "")
                vc = len(idx) // stride
                face_uv_idx = [idx[k * stride + uv_offset] for k in range(vc)]
                for i in range(1, vc - 1):
                    triangles.append((face_uv_idx[0], face_uv_idx[i], face_uv_idx[i + 1]))

    if not triangles:
        return None

    resolved_set = uv_input.get("set")
    return uvs, triangles, resolved_set

def _list_uv_sets_from_root(root) -> list[str]:
    seen: list[str] = []
    seen_set = set()
    for elem in root.iter():
        if _local(elem.tag) != "input" or elem.get("semantic") != "TEXCOORD":
            continue
        set_id = elem.get("set", "0")
        if set_id not in seen_set:
            seen_set.add(set_id)
            seen.append(set_id)
    return seen

def list_uv_sets(path: str) -> list[str]:
    try:
        tree = ET.parse(path)
    except (ET.ParseError, OSError):
        return []
    return _list_uv_sets_from_root(tree.getroot())

def parse_dae(path: str, uv_set: str | None = None) -> UVMesh:
    mesh = UVMesh(source_path=path, format_name="COLLADA (.dae)")

    try:
        tree = ET.parse(path)
    except ET.ParseError as e:
        raise MeshParseError(f"Malformed XML in .dae file: {e}") from e
    except OSError as e:
        raise MeshParseError(f"Could not read .dae file: {e}") from e

    root = tree.getroot()

    mesh.available_uv_sets = _list_uv_sets_from_root(root) or ["0"]
    if uv_set is not None:
        mesh.active_uv_set = uv_set
    elif "1" in mesh.available_uv_sets:
        mesh.active_uv_set = "1"
    elif "0" in mesh.available_uv_sets:
        mesh.active_uv_set = "0"
    else:
        mesh.active_uv_set = mesh.available_uv_sets[0]

    geometries = _find_all(root, "geometry")

    if not geometries:
        raise MeshParseError("No <geometry> elements found in this COLLADA file.")

    node_name_by_geom_id = _build_node_name_map(root)

    skipped = 0
    fallback_groups: list[str] = []

    for geom in geometries:
        geom_name = geom.get("name") or geom.get("id") or "geometry"
        geom_node_name = node_name_by_geom_id.get(geom.get("id") or "", "")
        mesh_elems = _find_direct(geom, "mesh")
        if not mesh_elems:
            continue
        mesh_elem = mesh_elems[0]

        poly_group_count = 0
        for tag_name in ("triangles", "polylist", "polygons"):
            for poly_elem in _find_direct(mesh_elem, tag_name):
                material_name = poly_elem.get("material")
                group_name = f"{geom_name}:{material_name}" if material_name else geom_name
                group_node_name = (
                    f"{geom_node_name}:{material_name}"
                    if geom_node_name and material_name
                    else geom_node_name
                )

                result = _extract_polygon_uvs(mesh_elem, poly_elem, uv_set)
                if result is None:
                    skipped += 1
                    continue

                uvs, triangles, resolved_set = result
                if uv_set is not None and resolved_set != uv_set:
                    fallback_groups.append(group_name)

                used_indices = sorted({i for tri in triangles for i in tri})
                remap = {old: new for new, old in enumerate(used_indices)}
                try:
                    group_uvs = [uvs[i] for i in used_indices]
                except IndexError:
                    mesh.warnings.append(
                        f"Group '{group_name}' had UV indices out of range; skipped."
                    )
                    continue
                remapped_tris = [(remap[a], remap[b], remap[c]) for a, b, c in triangles]
                mesh.groups.append(
                    UVGroup(
                        name=group_name,
                        uvs=group_uvs,
                        triangles=remapped_tris,
                        node_name=group_node_name,
                    )
                )
                poly_group_count += 1

        if poly_group_count == 0:
            mesh.warnings.append(f"Mesh '{geom_name}' had no usable UV-mapped polygon data.")

    if fallback_groups:
        if len(fallback_groups) <= 5:
            for name in fallback_groups:
                mesh.warnings.append(
                    f"Group '{name}' has no UV set '{uv_set}'; used the closest available set instead."
                )
        else:
            mesh.warnings.append(
                f"{len(fallback_groups)} group(s) had no UV set '{uv_set}' and used "
                "the closest available set instead."
            )

    if skipped:
        mesh.warnings.append(
            f"{skipped} polygon group(s) had no TEXCOORD data and were skipped."
        )

    if mesh.is_empty:
        raise MeshParseError(
            "Parsed the .dae file but found no UV-mapped triangles. "
            "The mesh may not have texture coordinates, or they may be under "
            "a UV channel name this tool didn't detect."
        )

    return mesh
