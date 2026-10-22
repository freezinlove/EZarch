"""Shared value validation for the optional vector drawing helpers."""
from __future__ import annotations

import math
import re


def css_color(value):
    """Normalize RGB, without assigning design meaning to any color."""
    if value is None or (isinstance(value, str) and value == "none"):
        return None
    if isinstance(value, str):
        if not re.fullmatch(r"#?[0-9a-fA-F]{6}", value):
            raise ValueError("Color requires #RRGGBB or a normalized RGB triple")
        return "#" + value.lstrip("#").lower()
    values = tuple(value)
    if len(values) != 3 or not all(math.isfinite(v) and 0 <= v <= 1 for v in values):
        raise ValueError("RGB components must be finite and in [0, 1]")
    return "#" + "".join(f"{round(v * 255):02x}" for v in values)


def dash_pattern(value):
    """Alternating positive dash/gap lengths; odd arrays repeat as in SVG/PDF."""
    if value is None:
        return ()
    values = tuple(float(v) for v in value)
    if not all(math.isfinite(v) and v > 0 for v in values):
        raise ValueError("Dash and gap lengths must be positive finite paper millimetres")
    return values * 2 if len(values) % 2 else values


def points_2d(points):
    result = [tuple(float(v) for v in p) for p in points]
    if any(len(p) != 2 or not all(math.isfinite(v) for v in p) for p in result):
        raise ValueError("Drawing points must be finite 2D coordinates")
    return result


def polygon_rings(points, holes, close, fill):
    """Validate supplied topology only; never repair or reinterpret it."""
    outer = points_2d(points)
    inner = [points_2d(ring) for ring in holes]
    if inner and not close:
        raise ValueError("Holes require close=True")
    if fill is not None and not close:
        raise ValueError("Fill requires close=True")
    if inner or fill is not None:
        from shapely.geometry import Polygon
        from shapely.validation import explain_validity

        if any(len(set(ring)) < 3 for ring in [outer, *inner]):
            raise ValueError("Filled rings require at least three distinct points")
        region = Polygon(outer, inner)
        if region.is_empty or not region.is_valid or region.area <= 0:
            raise ValueError(f"Invalid fill geometry: {explain_validity(region)}")
    return outer, inner


def paper_width(value):
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError("Line width must be nonnegative finite paper millimetres")
    return value
