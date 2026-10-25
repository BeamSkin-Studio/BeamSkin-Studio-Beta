
from dataclasses import dataclass, field

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen

from core.uv_exporter.mesh_data import UVMesh

AA_DISABLE_THRESHOLD = 8192

DEFAULT_COLORS = [
    QColor(0, 0, 0, 255),
    QColor(200, 30, 30, 255),
    QColor(30, 120, 200, 255),
    QColor(40, 160, 60, 255),
    QColor(180, 120, 20, 255),
    QColor(150, 50, 180, 255),
    QColor(0, 150, 150, 255),
    QColor(200, 100, 150, 255),
]

@dataclass
class RenderOptions:
    width: int = 4096
    height: int = 4096
    line_width: float = 1.0
    line_color: tuple[int, int, int, int] = (0, 0, 0, 255)
    color_by_group: bool = False
    included_group_names: set[str] | None = None
    draw_checker_background: bool = False
    checker_size: int = 64
    checker_colors: tuple[tuple[int, int, int, int], tuple[int, int, int, int]] = (
        (235, 235, 235, 255),
        (215, 215, 215, 255),
    )
    island_silhouette_only: bool = False
    hide_quad_diagonals: bool = False
    island_fill: bool = False
    fill_color: tuple[int, int, int, int] = (255, 255, 255, 255)
    fill_opacity: float = 0.2
    boundary_line_width: float | None = None
    boundary_line_color: tuple[int, int, int, int] | None = None

    def __post_init__(self):
        if self.boundary_line_width is None:
            self.boundary_line_width = self.line_width
        if self.boundary_line_color is None:
            self.boundary_line_color = self.line_color

def _draw_checker(painter: QPainter, width: int, height: int, opts: RenderOptions) -> None:
    c1 = QColor(*opts.checker_colors[0])
    c2 = QColor(*opts.checker_colors[1])
    size = max(1, opts.checker_size)
    painter.setPen(Qt.NoPen)
    y = 0
    row = 0
    while y < height:
        x = 0
        col = 0
        while x < width:
            use_c1 = (row + col) % 2 == 0
            painter.setBrush(c1 if use_c1 else c2)
            w = min(size, width - x)
            h = min(size, height - y)
            painter.drawRect(x, y, w, h)
            x += size
            col += 1
        y += size
        row += 1

def _boundary_edges(triangles: list[tuple[int, int, int]]) -> set[tuple[int, int]]:
    edge_use_count: dict[tuple[int, int], int] = {}
    for a, b, c in triangles:
        for i1, i2 in ((a, b), (b, c), (c, a)):
            key = (i1, i2) if i1 < i2 else (i2, i1)
            edge_use_count[key] = edge_use_count.get(key, 0) + 1

    return {k for k, count in edge_use_count.items() if count == 1}

def _classify_edges(
    triangles: list[tuple[int, int, int]]
) -> tuple[set[tuple[int, int]], set[tuple[int, int]], dict[tuple[int, int], list[int]]]:
    edge_use_count: dict[tuple[int, int], int] = {}
    edge_opposite: dict[tuple[int, int], list[int]] = {}
    for a, b, c in triangles:
        for i1, i2, opp in ((a, b, c), (b, c, a), (c, a, b)):
            key = (i1, i2) if i1 < i2 else (i2, i1)
            edge_use_count[key] = edge_use_count.get(key, 0) + 1
            edge_opposite.setdefault(key, []).append(opp)

    boundary = {k for k, count in edge_use_count.items() if count == 1}
    interior = {k for k, count in edge_use_count.items() if count >= 2}
    return interior, boundary, edge_opposite

def _is_convex_quad(points: list[QPointF]) -> bool:
    n = len(points)
    sign = None
    for i in range(n):
        p0, p1, p2 = points[i], points[(i + 1) % n], points[(i + 2) % n]
        v1x, v1y = p1.x() - p0.x(), p1.y() - p0.y()
        v2x, v2y = p2.x() - p1.x(), p2.y() - p1.y()
        cross = v1x * v2y - v1y * v2x
        if abs(cross) < 1e-9:
            continue
        turn = cross > 0
        if sign is None:
            sign = turn
        elif turn != sign:
            return False
    return sign is not None

def _quad_diagonal_edges(
    interior_edges: set[tuple[int, int]],
    edge_opposite: dict[tuple[int, int], list[int]],
    uvs_px: list[QPointF],
) -> set[tuple[int, int]]:
    diagonals = set()
    for key in interior_edges:
        opps = edge_opposite.get(key, [])
        if len(opps) != 2:
            continue
        i1, i2 = key
        opp1, opp2 = opps
        try:
            p1, p2 = uvs_px[i1], uvs_px[i2]
            po1, po2 = uvs_px[opp1], uvs_px[opp2]
        except IndexError:
            continue
        if _is_convex_quad([p1, po1, p2, po2]):
            diagonals.add(key)
    return diagonals

def _polygon_signed_area(points: list[QPointF]) -> float:
    area = 0.0
    n = len(points)
    for i in range(n):
        x1, y1 = points[i].x(), points[i].y()
        x2, y2 = points[(i + 1) % n].x(), points[(i + 1) % n].y()
        area += x1 * y2 - x2 * y1
    return area / 2.0

def _bbox(points: list[QPointF]) -> tuple[float, float, float, float]:
    xs = [p.x() for p in points]
    ys = [p.y() for p in points]
    return (min(xs), min(ys), max(xs), max(ys))

def _bbox_fully_inside(inner: tuple[float, float, float, float], outer: tuple[float, float, float, float]) -> bool:
    return (
        inner[0] >= outer[0]
        and inner[1] >= outer[1]
        and inner[2] <= outer[2]
        and inner[3] <= outer[3]
    )

def _point_in_polygon(pt: QPointF, points: list[QPointF]) -> bool:
    x, y = pt.x(), pt.y()
    inside = False
    n = len(points)
    for i in range(n):
        x1, y1 = points[i].x(), points[i].y()
        x2, y2 = points[(i + 1) % n].x(), points[(i + 1) % n].y()
        if (y1 > y) != (y2 > y):
            x_at_y = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < x_at_y:
                inside = not inside
    return inside

def _polygon_fully_inside(
    inner: list[QPointF],
    outer: list[QPointF],
    inner_bbox: tuple[float, float, float, float] | None = None,
    outer_bbox: tuple[float, float, float, float] | None = None,
) -> bool:
    if inner_bbox is None:
        inner_bbox = _bbox(inner)
    if outer_bbox is None:
        outer_bbox = _bbox(outer)
    if not _bbox_fully_inside(inner_bbox, outer_bbox):
        return False
    return all(_point_in_polygon(p, outer) for p in inner)

def _group_loops_into_islands(loops_px: list[list[QPointF]]) -> list[list[list[QPointF]]]:
    indexed = sorted(
        range(len(loops_px)),
        key=lambda i: abs(_polygon_signed_area(loops_px[i])),
        reverse=True,
    )
    by_area = [loops_px[i] for i in indexed]
    bboxes = [_bbox(loop) for loop in by_area]

    islands: list[list[list[QPointF]]] = []
    placed: list[list[QPointF]] = []
    placed_bboxes: list[tuple[float, float, float, float]] = []

    for loop, loop_bbox in zip(by_area, bboxes):
        containing_indices: list[int] = []
        parent_idx = None
        parent_area = None
        for idx, (candidate, candidate_bbox) in enumerate(zip(placed, placed_bboxes)):
            if _polygon_fully_inside(loop, candidate, loop_bbox, candidate_bbox):
                containing_indices.append(idx)
                area = abs(_polygon_signed_area(candidate))
                if parent_area is None or area < parent_area:
                    parent_area = area
                    parent_idx = idx

        if parent_idx is None:
            islands.append([loop])
        else:
            depth = len(containing_indices)
            if depth % 2 == 1:
                for island in islands:
                    if island[0] is placed[parent_idx] or any(
                        h is placed[parent_idx] for h in island[1:]
                    ):
                        island.append(loop)
                        break
                else:
                    islands.append([loop])
            else:
                islands.append([loop])

        placed.append(loop)
        placed_bboxes.append(loop_bbox)

    return islands

def _build_island_loops(triangles: list[tuple[int, int, int]]) -> list[list[int]]:
    boundary = _boundary_edges(triangles)
    if not boundary:
        return []

    directed: dict[int, int] = {}
    for a, b, c in triangles:
        for i1, i2 in ((a, b), (b, c), (c, a)):
            key = (i1, i2) if i1 < i2 else (i2, i1)
            if key in boundary:
                directed[i1] = i2

    if len(directed) != len(boundary):
        return []

    visited_starts: set[int] = set()
    loops: list[list[int]] = []
    for start in directed:
        if start in visited_starts:
            continue
        loop = [start]
        visited_starts.add(start)
        current = directed[start]
        steps = 0
        while current != start and steps <= len(directed) + 1:
            loop.append(current)
            visited_starts.add(current)
            nxt = directed.get(current)
            if nxt is None:
                return []
            current = nxt
            steps += 1
        if current != start:
            return []
        loops.append(loop)

    return loops

def render_uv_template(mesh: UVMesh, opts: RenderOptions) -> QImage:
    width = opts.width
    height = opts.height
    img = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)

    painter = QPainter(img)
    try:
        painter.setRenderHint(
            QPainter.Antialiasing, max(width, height) <= AA_DISABLE_THRESHOLD
        )

        if opts.draw_checker_background:
            _draw_checker(painter, width, height, opts)

        base_pen = QPen(QColor(*opts.line_color))
        base_pen.setWidthF(max(0.1, opts.line_width))
        base_pen.setCosmetic(False)
        painter.setPen(base_pen)

        groups = mesh.groups
        if opts.included_group_names is not None:
            groups = [g for g in groups if g.name in opts.included_group_names]

        if opts.island_fill:
            boundary_pen = QPen(QColor(*opts.boundary_line_color))
            boundary_pen.setWidthF(max(0.1, opts.boundary_line_width))
            boundary_pen.setCosmetic(False)

            interior_pen = QPen(QColor(*opts.line_color))
            interior_pen.setWidthF(max(0.1, opts.line_width))
            interior_pen.setCosmetic(False)

            fill_base = QColor(*opts.fill_color)
            fill_alpha = round(fill_base.alpha() * max(0.0, min(1.0, opts.fill_opacity)))
            fill_color = QColor(fill_base.red(), fill_base.green(), fill_base.blue(), fill_alpha)

            group_loops: list[list[list[int]]] = []
            group_uvs_px: list[list[QPointF]] = []
            for group in groups:
                group_uvs_px.append(
                    [QPointF(u * width, (1.0 - v) * height) for (u, v) in group.uvs]
                )
                group_loops.append(_build_island_loops(group.triangles))

            shared_fill_path: QPainterPath | None = None
            if not opts.color_by_group:
                shared_fill_path = QPainterPath()
                shared_fill_path.setFillRule(Qt.WindingFill)

            for gi, group in enumerate(groups):
                uvs_px = group_uvs_px[gi]
                loops = group_loops[gi]
                if not loops:
                    continue

                loops_px: list[list[QPointF]] = []
                for loop in loops:
                    try:
                        points = [uvs_px[i] for i in loop]
                    except IndexError:
                        continue
                    if len(points) >= 3:
                        loops_px.append(points)
                if not loops_px:
                    continue

                group_fill_path = QPainterPath()
                group_fill_path.setFillRule(Qt.WindingFill)
                for island_loops in _group_loops_into_islands(loops_px):
                    for loop_points in island_loops:
                        island_path = QPainterPath()
                        island_path.moveTo(loop_points[0])
                        for pt in loop_points[1:]:
                            island_path.lineTo(pt)
                        island_path.closeSubpath()
                        group_fill_path.addPath(island_path)

                if opts.color_by_group:
                    color = DEFAULT_COLORS[gi % len(DEFAULT_COLORS)]
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(color)
                    painter.drawPath(group_fill_path)
                    painter.setBrush(Qt.NoBrush)
                else:
                    shared_fill_path.addPath(group_fill_path)

            if shared_fill_path is not None:
                painter.setPen(Qt.NoPen)
                painter.setBrush(fill_color)
                painter.drawPath(shared_fill_path)
                painter.setBrush(Qt.NoBrush)

            for gi, group in enumerate(groups):
                uvs_px = group_uvs_px[gi]
                loops = group_loops[gi]

                if opts.color_by_group:
                    color = DEFAULT_COLORS[gi % len(DEFAULT_COLORS)]
                    boundary_pen = QPen(color)
                    boundary_pen.setWidthF(max(0.1, opts.boundary_line_width))
                    interior_pen = QPen(color)
                    interior_pen.setWidthF(max(0.1, opts.line_width))

                if not opts.island_silhouette_only:
                    painter.setPen(interior_pen)
                    interior_edges, _boundary, edge_opposite = _classify_edges(group.triangles)
                    if opts.hide_quad_diagonals:
                        interior_edges = interior_edges - _quad_diagonal_edges(
                            interior_edges, edge_opposite, uvs_px
                        )
                    for i1, i2 in interior_edges:
                        try:
                            painter.drawLine(uvs_px[i1], uvs_px[i2])
                        except IndexError:
                            continue

                painter.setPen(boundary_pen)
                if loops:
                    for loop in loops:
                        try:
                            points = [uvs_px[i] for i in loop]
                        except IndexError:
                            continue
                        if len(points) < 2:
                            continue
                        for i in range(len(points)):
                            painter.drawLine(points[i], points[(i + 1) % len(points)])
                else:
                    boundary = _boundary_edges(group.triangles)
                    for i1, i2 in boundary:
                        try:
                            painter.drawLine(uvs_px[i1], uvs_px[i2])
                        except IndexError:
                            continue
        else:
            for gi, group in enumerate(groups):
                if opts.color_by_group:
                    color = DEFAULT_COLORS[gi % len(DEFAULT_COLORS)]
                    boundary_pen = QPen(color)
                    boundary_pen.setWidthF(max(0.1, opts.boundary_line_width))
                    interior_pen = QPen(color)
                    interior_pen.setWidthF(max(0.1, opts.line_width))
                else:
                    boundary_pen = QPen(QColor(*opts.boundary_line_color))
                    boundary_pen.setWidthF(max(0.1, opts.boundary_line_width))
                    interior_pen = QPen(QColor(*opts.line_color))
                    interior_pen.setWidthF(max(0.1, opts.line_width))

                uvs_px = [
                    QPointF(u * width, (1.0 - v) * height) for (u, v) in group.uvs
                ]

                interior_edges, boundary_edges, edge_opposite = _classify_edges(group.triangles)

                if not opts.island_silhouette_only:
                    if opts.hide_quad_diagonals:
                        interior_edges = interior_edges - _quad_diagonal_edges(
                            interior_edges, edge_opposite, uvs_px
                        )
                    painter.setPen(interior_pen)
                    for i1, i2 in interior_edges:
                        try:
                            painter.drawLine(uvs_px[i1], uvs_px[i2])
                        except IndexError:
                            continue

                painter.setPen(boundary_pen)
                for i1, i2 in boundary_edges:
                    try:
                        painter.drawLine(uvs_px[i1], uvs_px[i2])
                    except IndexError:
                        continue
    finally:
        painter.end()

    return img

def save_render(img: QImage, out_path: str) -> bool:
    return img.save(out_path, "PNG")
