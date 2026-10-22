"""Independent 2D affine calculations; no project data or file operations.

Coefficients follow Shapely: (a, b, d, e, xoff, yoff), mapping
(x, y) to (a*x + b*y + xoff, d*x + e*y + yoff).
Unit changes are explicit coefficients; directions omit translation.
"""
from __future__ import annotations

import math


def _finite(values, count, name):
    result = tuple(float(value) for value in values)
    if len(result) != count or not all(math.isfinite(value) for value in result):
        raise ValueError(f"{name} requires {count} finite values")
    return result


def affine_from_axes(origin, x_axis, y_axis):
    """Map local coordinates using caller-supplied basis vectors, including scale."""
    ox, oy = _finite(origin, 2, "origin")
    xx, xy = _finite(x_axis, 2, "x_axis")
    yx, yy = _finite(y_axis, 2, "y_axis")
    return xx, yx, xy, yy, ox, oy


def transform_points(points, transform):
    """Return new 2D coordinate tuples; never modify input or discard Z silently."""
    a, b, d, e, ox, oy = _finite(transform, 6, "transform")
    result = []
    for point in points:
        x, y = _finite(point, 2, "point")
        result.append(_finite((a*x + b*y + ox, d*x + e*y + oy), 2, "result"))
    return result


def transform_direction(direction, transform):
    """Apply the linear part only; magnitude is preserved only by rigid transforms."""
    a, b, d, e, _, _ = _finite(transform, 6, "transform")
    x, y = _finite(direction, 2, "direction")
    return _finite((a*x + b*y, d*x + e*y), 2, "result")


def affine_determinant(transform):
    """Signed area factor: negative reverses orientation, zero collapses area."""
    a, b, d, e, _, _ = _finite(transform, 6, "transform")
    determinant = a*e - b*d
    if not math.isfinite(determinant):
        raise ValueError("Non-finite determinant")
    return determinant


def inverse_affine(transform):
    """Return inverse coefficients; a singular transform has no inverse."""
    a, b, d, e, ox, oy = _finite(transform, 6, "transform")
    determinant = affine_determinant((a, b, d, e, ox, oy))
    if determinant == 0:
        raise ValueError("Singular transform has no inverse")
    ia, ib, id_, ie = e/determinant, -b/determinant, -d/determinant, a/determinant
    return _finite((ia, ib, id_, ie, -ia*ox - ib*oy, -id_*ox - ie*oy), 6, "inverse")


def transform_geometry(geometry, transform):
    """Transform a 2D Shapely geometry, preserving rings and component structure.

    Does not repair geometry, infer architecture, or adapt native CAD curves/OCS.
    Shapely is imported only by this operation.
    """
    from shapely.affinity import affine_transform
    from shapely.geometry.base import BaseGeometry

    coefficients = _finite(transform, 6, "transform")
    if not isinstance(geometry, BaseGeometry):
        raise TypeError("Expected a 2D Shapely geometry")
    if geometry.has_z or getattr(geometry, "has_m", False):
        raise ValueError("Only 2D geometry is supported; Z/M are not adapted")
    return affine_transform(geometry, coefficients)


def paper_transform(bounds, scale, *, unit_mm=1, margin=0):
    """Map Y-up model coordinates to Y-down paper mm, without fitting/resizing.

    bounds is (xmin, ymin, xmax, ymax) in source units. scale is the physical
    scale denominator, unit_mm is mm per source unit, margin is paper mm.
    Text/pen sizes are separate inputs to the drawing backend.
    """
    left, bottom, right, top = _finite(bounds, 4, "bounds")
    scale, unit_mm, margin = _finite((scale, unit_mm, margin), 3, "paper parameters")
    if right <= left or top <= bottom or scale <= 0 or unit_mm <= 0:
        raise ValueError("Positive scale/unit_mm and non-empty bounds required")
    factor = unit_mm / scale
    return _finite((factor, 0, 0, -factor, margin-left*factor, margin+top*factor), 6, "transform")
