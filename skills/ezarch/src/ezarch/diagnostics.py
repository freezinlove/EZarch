"""Small location helpers for optional observations; no inspection scheduler."""
from __future__ import annotations

import math
from collections.abc import Mapping


def _id_mapping(values, name):
    if not isinstance(values, Mapping):
        raise TypeError(f"{name} must map nonempty string IDs to values")
    result = dict(values)
    if any(not isinstance(key, str) or not key for key in result):
        raise ValueError(f"{name} requires nonempty string IDs")
    return result


def _expected_ids(values, name):
    if values is None:
        return None
    if isinstance(values, str):
        raise TypeError(f"{name} must be a collection of IDs, not one string")
    values = tuple(values)
    if any(not isinstance(key, str) or not key for key in values) or len(set(values)) != len(values):
        raise ValueError(f"{name} requires distinct nonempty string IDs")
    return values


def geometry_location(geometry, *, precision):
    """Locate supplied observation geometry, without claiming a physical defect.

    Empty/invalid/nonfinite observations cannot furnish a crop. Coordinates and
    precision describe the caller's evidence, not its architectural meaning.
    """
    from .wall_regions import _geometry

    _geometry(geometry, {"Point", "MultiPoint", "LineString", "LinearRing", "MultiLineString",
                         "Polygon", "MultiPolygon", "GeometryCollection"}, "location")
    if not isinstance(precision, str) or not precision:
        raise ValueError("precision must describe the observation location")
    point = geometry.representative_point()
    return {"bounds": tuple(geometry.bounds), "points": [(point.x, point.y)], "precision": precision}


def issue_region(finding: dict, *, padding: float) -> tuple[float, float, float, float]:
    """Return a crop bbox in the finding's input coordinates, without rendering.

    Padding is a positive length in those coordinates, not paper millimetres.
    A backend may only locate an invalid geometry to its whole object bounds;
    consult location.precision before treating a crop as an exact defect location.
    The returned region can be used with ezarch.cad.plot or another viewer.
    """
    padding = float(padding)
    if not math.isfinite(padding) or padding <= 0:
        raise ValueError("padding must be a positive finite input-coordinate length")
    bounds = tuple(float(v) for v in finding["location"]["bounds"])
    if len(bounds) != 4 or not all(math.isfinite(v) for v in bounds):
        raise ValueError("Finding needs four finite bounds")
    x0, y0, x1, y1 = bounds
    if x0 > x1 or y0 > y1:
        raise ValueError("Finding bounds are inverted")
    result = (x0 - padding, y0 - padding, x1 + padding, y1 + padding)
    if not all(math.isfinite(v) for v in result) or result[0] >= result[2] or result[1] >= result[3]:
        raise ValueError("Padding is outside representable coordinate precision")
    return result
