
import re
from dataclasses import dataclass, field

from core.exterior_parts import has_exterior_part_name
from core.uv_exporter.mesh_data import UVMesh

_AREA_OUTLIER_RATIO = 10.0
_AREA_OUTLIER_MIN_GROUP_COUNT = 6

_DEGENERATE_SIZE = 1e-4

_OVERLAY_MATERIAL_TOKENS = {
    "lights",
    "light",
    "mirror",
    "raceparts",
    "racepart",
    "grille",
    "grill",
    "glass",
    "chrome",
}

_ALWAYS_OVERLAY_MATERIAL_TOKENS = {
    "emblems",
    "emblem",
    "decal",
    "decals",
    "sticker",
    "logo",
    "badge",
    "lettering",
    "details",
    "detail",
}

_MAIN_MATERIAL_TOKENS = {"main", "body", "paint"}

_MECHANICAL_NODE_TOKENS = {
    "wiper",
    "drumbrake",
    "caliper",
    "rotor",
    "tierod",
    "swaybar",
    "lowerarm",
    "upperarm",
    "control",
    "hub",
    "halfshaft",
    "driveshaft",
    "axle",
    "strut",
    "shock",
    "spring",
    "bushing",
    "bearing",
    "engine",
    "engbay",
    "radiator",
    "radhose",
    "intercooler",
    "icfan",
    "turbo",
    "downpipe",
    "exhaust",
    "oilcooler",
    "fuelcell",
    "drivechain",
    "differential",
    "gearbox",
    "transmission",
    "steering",
    "subframe",
    "chassis",
    "crossmember",
}

_NON_EXTERIOR_NODE_TOKENS = {
    "interior",
    "seat",
    "seats",
    "gauges",
    "gauge",
    "dash",
    "dashboard",
    "policeparts",
    "police",
    "steeringwheel",
    "pedals",
    "console",
    "carpet",
    "headliner",
    "rollcage",
    "rallyparts",
    "rallypart",
    "stretcher",
}

_TOKEN_SPLIT_RE = re.compile(r"[^0-9A-Za-z]+")
_CAMEL_BOUNDARY_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")

_VARIANT_SUFFIX_TOKENS = {
    "late",
    "early",
    "wide",
    "narrow",
    "race",
    "street",
    "plastic",
    "chrome",
    "mid",
    "int",
    "single",
    "filler",
    "alt",
    "kit",
    "a",
    "b",
    "c",
}


_EXCLUDED_NAME_PARTS = ("light", "glass", "window", "windshield", "windscreen")

_EXTRA_EXTERIOR_PARTS = ("quarterpanel", "quaterpanel")
_EXTRA_EXTERIOR_TOKENS = {
    "wall", "walls", "cabin", "cabindoor", "cabdoor", "door", "doors", "box",
    "cabinet", "cabinets",
}


def _is_lighting_or_glass(name: str) -> bool:
    low = name.lower()
    return any(part in low for part in _EXCLUDED_NAME_PARTS)


def _is_exterior_name(name: str) -> bool:
    squashed = "".join(c for c in name.lower() if c.isalnum())
    if any(part in squashed for part in _EXTRA_EXTERIOR_PARTS):
        return True
    if set(_tokenize(name)) & _EXTRA_EXTERIOR_TOKENS:
        return True
    return has_exterior_part_name(name)


def _tokenize(name: str) -> list[str]:
    tokens: list[str] = []
    for chunk in _TOKEN_SPLIT_RE.split(name):
        if not chunk:
            continue
        tokens.extend(_CAMEL_BOUNDARY_RE.split(chunk))
    return [t.lower() for t in tokens if t]


def _split_node_material(node_or_group_name: str) -> tuple[str, str]:
    if ":" in node_or_group_name:
        base, material = node_or_group_name.rsplit(":", 1)
    else:
        base, material = node_or_group_name, ""
    return base, material


def _variant_base_name(base_name: str) -> str:
    tokens = _tokenize(base_name)
    while tokens and tokens[-1] in _VARIANT_SUFFIX_TOKENS:
        tokens.pop()
    return "_".join(tokens)


@dataclass
class GroupVerdict:
    name: str
    include: bool
    reason: str = ""


@dataclass
class VariantConflict:

    base_name: str
    group_names: list[str] = field(default_factory=list)


def auto_select_groups(
    mesh: UVMesh,
    skip_area_outlier: bool = False,
) -> tuple[list[GroupVerdict], list[VariantConflict]]:
    groups = mesh.groups
    verdicts: dict[str, GroupVerdict] = {}

    materials_by_node_base: dict[str, set[str]] = {}
    for group in groups:
        if not group.node_name:
            continue
        base, material = _split_node_material(group.node_name)
        materials_by_node_base.setdefault(base, set()).add(material)

    areas: list[float] = []
    for group in groups:
        min_u, min_v, max_u, max_v = group.bounds
        areas.append((max_u - min_u) * (max_v - min_v))
    sorted_areas = sorted(areas)
    median_area = sorted_areas[len(sorted_areas) // 2] if sorted_areas else 0.0

    for group, area in zip(groups, areas):
        min_u, min_v, max_u, max_v = group.bounds
        w, h = (max_u - min_u), (max_v - min_v)

        if w <= _DEGENERATE_SIZE or h <= _DEGENERATE_SIZE:
            verdicts[group.name] = GroupVerdict(
                group.name,
                False,
                "No usable UV data on the active UV channel (collapsed/near-zero "
                "area here; this mesh may only have data on a different channel).",
            )
            continue

        if (
            not skip_area_outlier
            and len(groups) >= _AREA_OUTLIER_MIN_GROUP_COUNT
            and median_area > 0
            and area > median_area * _AREA_OUTLIER_RATIO
        ):
            verdicts[group.name] = GroupVerdict(
                group.name,
                False,
                f"UV island is unusually large ({area / median_area:.0f}x the "
                "typical island size); likely broken or placeholder UVs rather "
                "than a real unwrap.",
            )
            continue

        node_base, material = (
            _split_node_material(group.node_name) if group.node_name else ("", "")
        )
        part_name = node_base or _split_node_material(group.name)[0]
        if _is_lighting_or_glass(part_name) or (material and _is_lighting_or_glass(material)):
            verdicts[group.name] = GroupVerdict(
                group.name,
                False,
                "Lights, windows and glass are not part of a paint template.",
            )
            continue

        if not _is_exterior_name(part_name):
            verdicts[group.name] = GroupVerdict(
                group.name,
                False,
                "Name does not contain a recognized exterior-part word.",
            )
            continue

        if node_base:
            node_tokens = set(_tokenize(node_base))
            mechanical_tokens = node_tokens & _MECHANICAL_NODE_TOKENS
            is_underbody_shield = bool(
                node_tokens & {"shield", "shields", "skid", "skidplate", "skidplates"}
            )
            if mechanical_tokens and not (
                mechanical_tokens == {"engine"} and is_underbody_shield
            ):
                verdicts[group.name] = GroupVerdict(
                    group.name,
                    False,
                    "Name suggests a mechanical/chassis part (suspension, brakes, "
                    "driveline, engine bay, etc), not an exterior paint panel.",
                )
                continue

            if node_tokens & _NON_EXTERIOR_NODE_TOKENS:
                verdicts[group.name] = GroupVerdict(
                    group.name,
                    False,
                    "Name suggests interior trim, gauges, or an accessory kit, not "
                    "an exterior paint panel.",
                )
                continue

        if material:
            material_tokens = set(_tokenize(material))
            if material_tokens & _NON_EXTERIOR_NODE_TOKENS:
                verdicts[group.name] = GroupVerdict(
                    group.name,
                    False,
                    "Material name suggests interior trim, gauges, or an accessory "
                    "kit, not an exterior paint panel.",
                )
                continue

            if material_tokens & _ALWAYS_OVERLAY_MATERIAL_TOKENS:
                verdicts[group.name] = GroupVerdict(
                    group.name,
                    False,
                    f"'{material}' is branding/decal content (badge, emblem, "
                    "lettering, sticker), not a paintable surface.",
                )
                continue

            if "chrome" in material_tokens and node_base:
                node_tokens_for_trim = set(_tokenize(node_base))
                if "trim" in node_tokens_for_trim:
                    verdicts[group.name] = GroupVerdict(
                        group.name,
                        False,
                        "Chrome-trim material on a trim part; this is a chrome-trim "
                        "overlay variant, not the base paintable trim.",
                    )
                    continue

        if material:
            material_tokens = set(_tokenize(material))
            is_overlay = bool(material_tokens & _OVERLAY_MATERIAL_TOKENS)
            if is_overlay and node_base:
                sibling_materials = materials_by_node_base.get(node_base, set())
                has_primary_sibling = any(
                    m != material
                    and not (set(_tokenize(m)) & _OVERLAY_MATERIAL_TOKENS)
                    and not (set(_tokenize(m)) & _ALWAYS_OVERLAY_MATERIAL_TOKENS)
                    and not (set(_tokenize(m)) & _NON_EXTERIOR_NODE_TOKENS)
                    for m in sibling_materials
                )
                if has_primary_sibling:
                    verdicts[group.name] = GroupVerdict(
                        group.name,
                        False,
                        f"'{material}' is a secondary/overlay material on this part "
                        "(a primary paint material exists on the same part); not "
                        "the paintable surface.",
                    )
                    continue

        verdicts[group.name] = GroupVerdict(group.name, True)

    survivors = [g for g in groups if verdicts[g.name].include and g.node_name]
    by_variant_base: dict[str, list[str]] = {}
    for group in survivors:
        node_base, _material = _split_node_material(group.node_name)
        vbase = _variant_base_name(node_base)
        by_variant_base.setdefault(vbase, []).append(group.node_name)

    conflicts = [
        VariantConflict(base_name=vbase, group_names=sorted(set(names)))
        for vbase, names in by_variant_base.items()
        if len(set(names)) > 1
    ]
    conflicts.sort(key=lambda c: c.base_name)

    return [verdicts[g.name] for g in groups], conflicts
