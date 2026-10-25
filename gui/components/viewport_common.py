from __future__ import annotations

import math

import numpy as np

TEX_CAP_NORMAL = 2048
TEX_CAP_FULL = 16384

DEFAULT_YAW = 215.0
DEFAULT_PITCH = 14.0

_SOFTWARE_MARKERS = (
    "llvmpipe", "softpipe", "swrast", "software", "gdi generic",
    "basic render", "swiftshader", "warp", "lavapipe", "microsoft basic",
)


def pot(value: int, cap: int = TEX_CAP_NORMAL) -> int:
    return min(cap, 1 << max(0, (max(1, value) - 1).bit_length()))


def looks_like_software(renderer_name: str) -> bool:
    low = (renderer_name or "").lower()
    return any(m in low for m in _SOFTWARE_MARKERS)


def group_bounds(model) -> list[tuple[np.ndarray, np.ndarray]]:
    out = []
    for g in model.groups:
        pos = model.vertices[g.first:g.first + g.count, :3]
        pos = pos[np.isfinite(pos).all(axis=1)]
        if pos.shape[0] == 0:
            nan = np.full(3, np.nan)
            out.append((nan, nan))
        else:
            out.append((pos.min(axis=0), pos.max(axis=0)))
    return out


MODE_GLASS = 0
MODE_SKIN = 1
MODE_PLAIN = 2
MODE_SURFACE = 3


def build_ranges(model, visible: set[str], unskinned: set[str],
                 plain: set[str] | frozenset = frozenset(),
                 skin_groups: set[str] | frozenset | None = None,
                 surface: set[str] | frozenset = frozenset()) -> list[tuple[int, int, int]]:
    ranges: list[tuple[int, int, int]] = []
    if model is None:
        return ranges
    cur = None
    for g in model.groups:
        if g.name not in visible:
            if cur is not None:
                ranges.append((cur[0], cur[1] - cur[0], cur[2]))
                cur = None
            continue
        if g.name in unskinned:
            mode = MODE_GLASS
        elif g.name in surface:
            mode = MODE_SURFACE
        elif g.name in plain:
            mode = MODE_PLAIN
        elif skin_groups is not None and g.name not in skin_groups:
            mode = MODE_PLAIN
        else:
            mode = MODE_SKIN
        if cur is not None and g.first == cur[1] and cur[2] == mode:
            cur[1] = g.first + g.count
        else:
            if cur is not None:
                ranges.append((cur[0], cur[1] - cur[0], cur[2]))
            cur = [g.first, g.first + g.count, mode]
    if cur is not None:
        ranges.append((cur[0], cur[1] - cur[0], cur[2]))
    return ranges


def build_surface_ranges(model, visible: set[str], unskinned: set[str],
                         assignments: dict[str, str]) -> dict[str, list[tuple[int, int]]]:
    out: dict[str, list[tuple[int, int]]] = {}
    if model is None or not assignments:
        return out
    cur = None

    def flush():
        if cur is not None:
            out.setdefault(cur[0], []).append((cur[1], cur[2] - cur[1]))

    for g in model.groups:
        key = assignments.get(g.name) if g.name in visible and g.name not in unskinned else None
        if key is None:
            flush()
            cur = None
        elif cur is not None and cur[0] == key and g.first == cur[2]:
            cur[2] = g.first + g.count
        else:
            flush()
            cur = [key, g.first, g.first + g.count]
    flush()
    return out


def compute_fit(model, bounds, visible: set[str]):
    if model is None:
        return None
    lows, highs = [], []
    for g, (lo, hi) in zip(model.groups, bounds):
        if g.name in visible and np.isfinite(lo).all() and np.isfinite(hi).all():
            lows.append(lo)
            highs.append(hi)
    if not lows:
        return None
    lows, highs = np.array(lows), np.array(highs)
    centers = (lows + highs) / 2.0
    dist = np.linalg.norm(centers - np.median(centers, axis=0), axis=1)
    keep = dist <= max(float(np.percentile(dist, 90)) * 3.0, 1e-6)
    lo = lows[keep].min(axis=0)
    hi = highs[keep].max(axis=0)
    center = (lo + hi) / 2.0
    radius = max(0.05, float(np.linalg.norm(hi - lo)) / 2.0)
    distance = radius / math.sin(math.radians(22.0)) * 1.05
    return center, radius, distance, hi - lo, int(keep.sum()), len(keep)
