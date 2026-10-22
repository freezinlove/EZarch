"""Small location helpers for optional observations; no inspection scheduler."""
from __future__ import annotations

import math


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
