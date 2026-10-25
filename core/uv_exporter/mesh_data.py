
from dataclasses import dataclass, field

@dataclass
class UVGroup:

    name: str
    uvs: list[tuple[float, float]]
    triangles: list[tuple[int, int, int]]
    node_name: str = ""

    @property
    def triangle_count(self) -> int:
        return len(self.triangles)

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        if not self.uvs:
            return (0.0, 0.0, 1.0, 1.0)
        us = [u for u, _ in self.uvs]
        vs = [v for _, v in self.uvs]
        return (min(us), min(vs), max(us), max(vs))

    @property
    def display_name(self) -> str:
        return self.node_name or self.name

@dataclass
class UVMesh:

    source_path: str
    format_name: str
    groups: list[UVGroup] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    available_uv_sets: list[str] = field(default_factory=lambda: ["0"])
    active_uv_set: str = "0"

    @property
    def total_triangles(self) -> int:
        return sum(g.triangle_count for g in self.groups)

    @property
    def is_empty(self) -> bool:
        return len(self.groups) == 0 or self.total_triangles == 0

class MeshParseError(Exception):
    pass
