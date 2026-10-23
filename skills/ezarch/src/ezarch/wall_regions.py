"""Independent planar wall-region operations extracted from drawing revisions.

All coordinates and dimensions use the same caller-chosen unit. No classification,
snapping, gap closing, make_valid, source-file edits or architectural approval.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

import shapely
from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from shapely.validation import explain_validity


def _number(value, name, *, positive=False):
    value = float(value)
    if not math.isfinite(value) or (value <= 0 if positive else value < 0):
        raise ValueError(f"{name} must be {'positive' if positive else 'nonnegative'} and finite")
    return value


def _geometry(value, types, name, *, empty=False):
    if not isinstance(value, BaseGeometry) or value.geom_type not in types:
        raise TypeError(f"{name} requires {', '.join(sorted(types))}")
    if value.has_z or shapely.has_m(value):
        raise ValueError(f"{name} must be XY geometry; no projection is implicit")
    if value.is_empty and not empty:
        raise ValueError(f"{name} is empty")
    if any(not math.isfinite(float(v)) for p in shapely.get_coordinates(value) for v in p):
        raise ValueError(f"{name} contains nonfinite coordinates")
    if not value.is_valid:
        raise ValueError(f"{name} is invalid: {explain_validity(value)}; no repair performed")
    if not math.isfinite(value.area) or not math.isfinite(value.length):
        raise ValueError(f"{name} exceeds representable measurement range")
    return value


def _region(value, name="region", *, empty=False):
    return _geometry(value, {"Polygon", "MultiPolygon"}, name, empty=empty)


def _area_parts(value):
    """Keep area members of an overlay; a boundary contact is not wall material."""
    if value.geom_type in ("Polygon", "MultiPolygon"):
        return value
    polygons = []
    if hasattr(value, "geoms"):
        for part in value.geoms:
            area = _area_parts(part)
            if not area.is_empty:
                polygons.extend(area.geoms if area.geom_type == "MultiPolygon" else [area])
    return MultiPolygon(polygons) if polygons else Polygon()


def _join_options(join, mitre_limit):
    if join not in ("mitre", "bevel"):
        raise ValueError("This straight-edge helper supports join='mitre' or 'bevel'; native Shapely remains available")
    return {"join_style": join, "mitre_limit": _number(mitre_limit, "mitre_limit", positive=True)}


def wall_region(path, *, width, cap, join, mitre_limit=5):
    """Symmetric buffer of selected LineString/LinearRing/MultiLineString.

    width is full width. Flat/square ends and mitre/bevel joins retain straight
    edges. mitre_limit is GEOS's extension ratio, not a building standard.
    """
    path = _geometry(path, {"LineString", "LinearRing", "MultiLineString"}, "path")
    width = _number(width, "width", positive=True)
    if cap not in ("flat", "square"):
        raise ValueError("This straight-edge helper supports cap='flat' or 'square'")
    result = path.buffer(width/2, cap_style=cap, **_join_options(join, mitre_limit))
    return _region(result, "buffer result")


def wall_band(region, *, inside, outside, join, mitre_limit=5):
    """Offset band around all boundaries, including holes; no fixed wall thickness.

    An inward offset can consume a narrow region completely. The returned actual
    geometry records that result; an inner void is not invented or guaranteed.
    """
    region = _region(region)
    inside, outside = _number(inside, "inside"), _number(outside, "outside")
    if inside + outside == 0:
        raise ValueError("At least one offset must be positive")
    options = _join_options(join, mitre_limit)
    outer = region.buffer(outside, **options) if outside else region
    inner = region.buffer(-inside, **options) if inside else region
    return _region(outer.difference(inner), "band result")


def opening_region(start, end, *, depth, offset=0):
    """Oriented rectangular cut mask with flat ends, not a detected/approved door.

    start/end define the span; depth runs perpendicular to it. Positive offset
    shifts its center to the left of start→end. No automatic depth/clearance guess.
    """
    from .frames import _finite

    sx, sy = _finite(start, 2, "start")
    ex, ey = _finite(end, 2, "end")
    depth = _number(depth, "depth", positive=True)
    offset, = _finite((offset,), 1, "offset")
    length = math.hypot(ex-sx, ey-sy)
    if not math.isfinite(length) or length == 0:
        raise ValueError("Opening span must have positive finite length")
    nx, ny = -(ey-sy)/length, (ex-sx)/length
    low, high = offset-depth/2, offset+depth/2
    return _region(Polygon([(sx+nx*low, sy+ny*low), (ex+nx*low, ey+ny*low),
                            (ex+nx*high, ey+ny*high), (sx+nx*high, sy+ny*high)]), "opening")


@dataclass
class WallComposition:
    geometry: object
    by_source: dict
    cut_effects: dict
    removed: object
    clipped_out: object
    unused_cuts: tuple


def _regions(values, name):
    if not isinstance(values, Mapping):
        raise TypeError(f"{name} must map local source IDs to regions; no project schema required")
    result = dict(values)
    if any(not isinstance(key, str) or not key for key in result):
        raise ValueError(f"{name} requires nonempty string IDs")
    for key, geometry in result.items():
        _region(geometry, f"{name}[{key!r}]")
    return result


def compose_wall_regions(regions, *, cuts=None, clip=None):
    """Union only supplied regions, optionally clip, then subtract supplied masks.

    Returned by_source regions can overlap; their areas are not additive. Each
    cut_effect is the intersection with the union before cuts, so overlapping
    cuts are also nonadditive. removed is the actual union of removed material.
    Boundary-only contact has zero area and is included in unused_cuts. Partial
    cuts are retained as given, never announced as verified through-openings.
    """
    regions = _regions(regions, "regions")
    if not regions:
        raise ValueError("Select at least one source region")
    cuts = _regions({} if cuts is None else cuts, "cuts")
    if clip is not None:
        clip = _region(clip, "clip")
    combined = _region(unary_union(list(regions.values())), "union")
    selected = combined if clip is None else _area_parts(combined.intersection(clip))
    masks = unary_union(list(cuts.values())) if cuts else Polygon()
    result = _region(selected.difference(masks), "result", empty=True)
    by_source = {key: _area_parts((region if clip is None else region.intersection(clip)).difference(masks))
                 for key, region in regions.items()}
    effects = {key: selected.intersection(mask) for key, mask in cuts.items()}
    return WallComposition(
        result, by_source, effects, selected.difference(result), combined.difference(selected),
        tuple(key for key, effect in effects.items() if effect.area == 0),
    )
