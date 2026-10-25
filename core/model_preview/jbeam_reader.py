from __future__ import annotations

import ast
import json
import math
import posixpath
import re
from dataclasses import dataclass, field


_TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*.*?\*/', re.S)
_TRAILING = re.compile(r",(\s*[\]}])")
_MISSING = re.compile(r'([\]}"\d])([ \t]*\r?\n\s*)(["\[{\-\d])')
_NUM = re.compile(r"^-?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$")
_BARE = re.compile(r'[^\s,\]\}\[\{:"]+')


def _strip_comments(text: str) -> str:
    return _TOKEN.sub(lambda m: m.group() if m.group()[0] == '"' else " ", text)


class _Loose:

    def __init__(self, text: str):
        self.s = text
        self.i = 0
        self.n = len(text)

    def _ws(self):
        s, n = self.s, self.n
        while self.i < n:
            c = s[self.i]
            if c in " \t\r\n\ufeff,":
                self.i += 1
            elif c == "/" and s.startswith("//", self.i):
                j = s.find("\n", self.i)
                self.i = n if j < 0 else j + 1
            elif c == "/" and s.startswith("/*", self.i):
                j = s.find("*/", self.i + 2)
                self.i = n if j < 0 else j + 2
            else:
                break

    def parse(self):
        return self.value(0)

    def value(self, depth: int):
        if depth > 200:
            raise ValueError("nesting too deep")
        self._ws()
        if self.i >= self.n:
            raise ValueError("unexpected end of file")
        c = self.s[self.i]
        if c == "{":
            return self._obj(depth)
        if c == "[":
            return self._arr(depth)
        if c == '"':
            return self._str()
        m = _BARE.match(self.s, self.i)
        if not m:
            raise ValueError(f"unexpected {c!r} at offset {self.i}")
        self.i = m.end()
        tok = m.group()
        if tok == "true":
            return True
        if tok == "false":
            return False
        if tok == "null":
            return None
        if _NUM.match(tok):
            return float(tok) if any(ch in tok for ch in ".eE") else int(tok)
        return tok

    def _str(self):
        s, j = self.s, self.i + 1
        while j < self.n:
            ch = s[j]
            if ch == "\\":
                j += 2
                continue
            if ch == '"':
                break
            j += 1
        else:
            raise ValueError("unterminated string")
        raw = s[self.i:j + 1]
        self.i = j + 1
        try:
            return json.loads(raw, strict=False)
        except ValueError:
            return raw[1:-1]

    def _obj(self, depth: int):
        self.i += 1
        out = {}
        while True:
            self._ws()
            if self.i >= self.n:
                raise ValueError("unterminated object")
            if self.s[self.i] == "}":
                self.i += 1
                return out
            key = self.value(depth + 1)
            self._ws()
            if self.i < self.n and self.s[self.i] == ":":
                self.i += 1
            else:
                raise ValueError(f"expected ':' at offset {self.i}")
            out[str(key)] = self.value(depth + 1)

    def _arr(self, depth: int):
        self.i += 1
        out = []
        while True:
            self._ws()
            if self.i >= self.n:
                raise ValueError("unterminated array")
            if self.s[self.i] == "]":
                self.i += 1
                return out
            out.append(self.value(depth + 1))


def parse_loose_json(text: str):
    text = text.lstrip("\ufeff")
    cleaned = _strip_comments(text)
    fixed = _MISSING.sub(r"\1,\2\3", _TRAILING.sub(r"\1", cleaned))
    try:
        return json.loads(fixed, strict=False)
    except ValueError:
        pass
    return _Loose(text).parse()


def decode_bytes(data: bytes) -> str:
    return data.decode("utf-8-sig", errors="replace")


@dataclass
class SlotInfo:
    name: str
    default: str = ""
    node_offset: tuple = (0.0, 0.0, 0.0)
    allow_types: tuple = ()


@dataclass(frozen=True)
class FlexbodyPlacement:
    position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0)
    scale: tuple[float, float, float] = (1.0, 1.0, 1.0)


@dataclass
class PartInfo:
    name: str
    file: str
    description: str = ""
    slot_type: str = ""
    slot_types: tuple = ()
    slots: list[SlotInfo] = field(default_factory=list)
    meshes: tuple = ()
    flexbody_rows: tuple = ()
    node_rows: tuple = ()
    pressure_wheel_rows: tuple = ()
    components: dict = field(default_factory=dict)


def _rows(value):
    return [r for r in value if isinstance(r, list) and r] if isinstance(value, list) else []


def _slot_offset(row) -> tuple:
    total = [0.0, 0.0, 0.0]
    for value in row:
        if not isinstance(value, dict):
            continue
        for key in ("nodeOffset", "nodeMove"):
            offset = value.get(key)
            if not isinstance(offset, dict):
                continue
            for i, axis in enumerate(("x", "y", "z")):
                try:
                    total[i] += float(offset.get(axis, 0.0))
                except (TypeError, ValueError):
                    pass
    return tuple(total)


def _slots(body: dict) -> list[SlotInfo]:
    out: list[SlotInfo] = []
    for row in _rows(body.get("slots2")):
        if not isinstance(row[0], str) or row[0] == "name":
            continue
        default = row[3] if len(row) > 3 and isinstance(row[3], str) else ""
        allow = row[1] if len(row) > 1 else ()
        if isinstance(allow, str):
            allow = (allow,)
        allow = tuple(a for a in allow if isinstance(a, str) and a) if isinstance(allow, (list, tuple)) else ()
        out.append(SlotInfo(row[0], default, _slot_offset(row), allow))
    for row in _rows(body.get("slots")):
        if not isinstance(row[0], str) or row[0] == "type":
            continue
        default = row[1] if len(row) > 1 and isinstance(row[1], str) else ""
        out.append(SlotInfo(row[0], default, _slot_offset(row)))
    return out


def _meshes(body: dict) -> tuple:
    names: list[str] = []
    for row in _rows(body.get("flexbodies")):
        if isinstance(row[0], str) and row[0] != "mesh" and row[0]:
            names.append(row[0])
    prop_rows = _rows(body.get("props"))
    col = 1
    for row in prop_rows:
        if row[0] == "func" and "mesh" in row:
            col = row.index("mesh")
            break
    for row in prop_rows:
        if row[0] == "func":
            continue
        if len(row) > col and isinstance(row[col], str) and row[col]:
            names.append(row[col])
    return tuple(dict.fromkeys(names))


def _component_value(path: str, components: dict) -> float:
    value = components
    for name in path.split("."):
        if not isinstance(value, dict) or name not in value:
            raise ValueError(f"unknown JBeam component '$components.{path}'")
        value = value[name]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"JBeam component '$components.{path}' is not numeric")
    return float(value)


def _eval_numeric(node) -> float:
    if isinstance(node, ast.Expression):
        return _eval_numeric(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.BinOp):
        left, right = _eval_numeric(node.left), _eval_numeric(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.Pow):
            return left**right
    if isinstance(node, ast.UnaryOp):
        value = _eval_numeric(node.operand)
        if isinstance(node.op, ast.UAdd):
            return value
        if isinstance(node.op, ast.USub):
            return -value
    raise ValueError("unsupported operation in JBeam numeric expression")


def _numeric_value(value, components: dict) -> float:
    if isinstance(value, str) and value.startswith("$="):
        expression = value[2:].strip()
        pattern = re.compile(r"\$components(?:\.[A-Za-z_]\w*)+")

        def replace_component(match):
            return repr(_component_value(match.group()[len("$components."):], components))

        expression = pattern.sub(replace_component, expression)
        if "$" in expression:
            raise ValueError("unsupported variable in JBeam numeric expression")
        result = _eval_numeric(ast.parse(expression, mode="eval"))
    else:
        result = float(value)
    if not math.isfinite(result):
        raise ValueError("coordinates must be finite")
    return result


def _vector3(
    value,
    default: tuple[float, float, float],
    components: dict,
) -> tuple[float, float, float]:
    if value is None:
        return default
    if isinstance(value, dict):
        raw = [value.get(axis, default[i]) for i, axis in enumerate(("x", "y", "z"))]
    elif isinstance(value, (list, tuple)) and len(value) >= 3:
        raw = value[:3]
    else:
        raise ValueError("expected three coordinates")
    return tuple(_numeric_value(component, components) for component in raw)


def jbeam_node_positions(rows, components: dict | None = None) -> dict[str, tuple[float, float, float]]:
    if not rows:
        return {}
    header = rows[0]
    if not isinstance(header, list):
        return {}
    columns = {
        str(name).casefold().rstrip(":"): index
        for index, name in enumerate(header)
        if isinstance(name, str)
    }
    id_index = columns.get("id")
    axis_indices = tuple(columns.get(f"pos{axis}") for axis in ("x", "y", "z"))
    if id_index is None or any(index is None for index in axis_indices):
        return {}

    positions = {}
    for row in rows[1:]:
        if not isinstance(row, list) or len(row) <= max((id_index, *axis_indices)):
            continue
        node_id = row[id_index]
        if not isinstance(node_id, str) or not node_id or node_id == "id":
            continue
        try:
            position = tuple(
                _numeric_value(row[index], components or {})
                for index in axis_indices
            )
        except (TypeError, ValueError, SyntaxError, ZeroDivisionError):
            continue
        positions[node_id] = position
    return positions


def pressure_wheel_group_positions(
    rows,
    node_positions: dict[str, tuple[float, float, float]],
) -> dict[str, tuple[float, float, float]]:
    if not rows or not isinstance(rows[0], list):
        return {}
    columns = {
        str(name).casefold().rstrip(":"): index
        for index, name in enumerate(rows[0])
        if isinstance(name, str)
    }
    group_indices = (columns.get("hubgroup"), columns.get("group"))
    node_indices = (columns.get("node1"), columns.get("node2"))
    if any(index is None for index in (*group_indices, *node_indices)):
        return {}

    positions = {}
    for row in rows[1:]:
        if not isinstance(row, list):
            continue
        if any(index >= len(row) for index in (*group_indices, *node_indices)):
            continue
        first = node_positions.get(row[node_indices[0]])
        second = node_positions.get(row[node_indices[1]])
        if first is None or second is None:
            continue
        midpoint = tuple((a + b) / 2 for a, b in zip(first, second))
        for index in group_indices:
            group = row[index]
            if isinstance(group, str) and group:
                positions[group] = midpoint
    return positions


def flexbody_placements(
    rows,
    components: dict | None = None,
    group_positions: dict[str, tuple[float, float, float]] | None = None,
) -> tuple[dict[str, tuple[FlexbodyPlacement, ...]], tuple[str, ...]]:
    placements: dict[str, list[FlexbodyPlacement]] = {}
    errors: list[str] = []
    components = components or {}
    group_positions = group_positions or {}
    for row in _rows(list(rows) if isinstance(rows, tuple) else rows):
        mesh = row[0]
        if not isinstance(mesh, str) or mesh in ("mesh", "func") or not mesh:
            continue
        options = {}
        for value in row[1:]:
            if isinstance(value, dict):
                options.update(value)
        keys = {str(key).casefold(): key for key in options}
        groups = row[1] if len(row) > 1 else ()
        if isinstance(groups, str):
            groups = (groups,)
        anchor = None
        if isinstance(groups, (list, tuple)):
            anchor = next(
                (group_positions[group] for group in groups
                 if isinstance(group, str) and group in group_positions),
                None,
            )
        if anchor is None and not keys.keys() & {"pos", "position", "rot", "rotation", "scale"}:
            continue
        try:
            position = _vector3(
                options.get(keys.get("pos", keys.get("position"))),
                (0.0, 0.0, 0.0), components,
            )
            rotation = _vector3(
                options.get(keys.get("rot", keys.get("rotation"))),
                (0.0, 0.0, 0.0), components,
            )
            scale = _vector3(
                options.get(keys.get("scale")),
                (1.0, 1.0, 1.0), components,
            )
            if anchor is not None:
                position = tuple(
                    anchor[axis] if coordinate == 0.0 else coordinate
                    for axis, coordinate in enumerate(position)
                )
        except (TypeError, ValueError) as e:
            errors.append(f"{mesh}: ignored invalid flexbody placement ({e})")
            continue
        placements.setdefault(mesh, []).append(FlexbodyPlacement(position, rotation, scale))
    return {name: tuple(items) for name, items in placements.items()}, tuple(errors)


def parts_from_data(vpath: str, data) -> list[PartInfo]:
    out: list[PartInfo] = []
    if not isinstance(data, dict):
        return out
    for name, body in data.items():
        if not isinstance(body, dict):
            continue
        info = body.get("information")
        desc = info.get("name", "") if isinstance(info, dict) and isinstance(info.get("name"), str) else ""
        slot_type = body.get("slotType")
        if isinstance(slot_type, (list, tuple)):
            types = tuple(t for t in slot_type if isinstance(t, str) and t)
            slot_type = types[0] if types else ""
        else:
            types = (slot_type,) if isinstance(slot_type, str) and slot_type else ()
        out.append(PartInfo(
            name=name, file=vpath, description=desc,
            slot_type=slot_type if isinstance(slot_type, str) else "",
            slot_types=types,
            slots=_slots(body), meshes=_meshes(body),
            flexbody_rows=tuple(_rows(body.get("flexbodies"))),
            node_rows=tuple(_rows(body.get("nodes"))),
            pressure_wheel_rows=tuple(_rows(body.get("pressureWheels"))),
            components=body.get("components") if isinstance(body.get("components"), dict) else {},
        ))
    return out


@dataclass
class VehicleIndex:
    parts: dict[str, PartInfo] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    files: int = 0
    offsets: dict[str, tuple] = field(default_factory=dict)

    def main_part(self) -> str:
        for p in self.parts.values():
            if p.slot_type == "main":
                return p.name
        return ""


_FILE_CACHE: dict[tuple, list[PartInfo]] = {}


def _load_file(vfs, vpath: str, index: VehicleIndex, only_names=None):
    stamp = vfs.stamp(vpath)
    cached = _FILE_CACHE.get(stamp)
    if cached is None:
        try:
            raw = vfs.read(vpath)
            if only_names is not None and not any(b'"' + n.encode("utf-8") + b'"' in raw for n in only_names):
                return
            data = parse_loose_json(decode_bytes(raw))
            cached = parts_from_data(vpath, data)
        except (ValueError, OSError, KeyError) as e:
            index.errors.append(f"{vpath}: {e}")
            cached = []
        _FILE_CACHE[stamp] = cached
    index.files += 1
    for p in cached:
        index.parts[p.name] = p


def build_part_index(vfs, carid: str, only_names=None) -> VehicleIndex:
    index = VehicleIndex()
    seen: set[str] = set()
    for prefix in (f"vehicles/{carid}/", f"vehicles/common/{carid}/"):
        for vpath in vfs.files(prefix, ".jbeam"):
            if vpath.lower() not in seen:
                seen.add(vpath.lower())
                _load_file(vfs, vpath, index, only_names)
    return index


def add_common_parts(
    vfs, index: VehicleIndex, shared_dirs=("vehicles/common/",), only_names=None
) -> None:
    known = {p.file.lower() for p in index.parts.values()}
    for prefix in shared_dirs:
        for vpath in vfs.files(prefix, ".jbeam"):
            if vpath.lower() not in known:
                _load_file(vfs, vpath, index, only_names)


def slot_accepts(slot: SlotInfo, part: PartInfo) -> bool:
    types = part.slot_types or ((part.slot_type,) if part.slot_type else ())
    return any(t == slot.name or t in slot.allow_types for t in types)


def dir_of(vpath: str) -> str:
    return posixpath.dirname(vpath) + "/"
