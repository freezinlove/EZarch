"""Measurements of caller-selected planar geometry, without project semantics."""
from __future__ import annotations

import math
from copy import deepcopy
from itertools import combinations

from shapely.geometry import Polygon
from shapely.ops import unary_union

from .frames import _finite
from .wall_regions import _area_parts, _number, _region, _regions


def _area(geometry, unit_mm):
    value = geometry.area * (unit_mm / 1000) ** 2
    if not math.isfinite(value):
        raise ValueError("Area exceeds representable range")
    return value


def measure_area(boundary, *, unit_mm, exclusions=None, basis=None, source=None):
    """Subtract the union of explicit masks; holes are already absent material.

    Per-mask effects can overlap and are not additive. Output geometries use the
    input unit; numeric areas are unrounded square metres. basis/source are
    caller statements saved as snapshots, not certified measurement definitions.
    """
    boundary = _region(boundary, "boundary", empty=True)
    unit_mm = _number(unit_mm, "unit_mm", positive=True)
    masks = _regions({} if exclusions is None else exclusions, "exclusions")
    combined = unary_union(list(masks.values())) if masks else Polygon()
    removed = _area_parts(boundary.intersection(combined))
    result = _region(boundary.difference(combined), "result", empty=True)
    return {
        "boundary": boundary, "geometry": result, "removed": removed,
        "exclusions": masks,
        "effects": {key: _area_parts(boundary.intersection(mask)) for key, mask in masks.items()},
        "outside_exclusions": {key: _area_parts(mask.difference(boundary)) for key, mask in masks.items()},
        "boundary_area_m2": _area(boundary, unit_mm), "removed_area_m2": _area(removed, unit_mm),
        "area_m2": _area(result, unit_mm), "unit_mm": unit_mm,
        "basis": deepcopy(basis), "source": deepcopy(source),
        "not_checked": ["architectural or legal area definition", "accuracy of supplied boundaries",
                        "unselected deductions", "later edits to source geometry"],
    }


def coverage(domain, regions, *, unit_mm):
    """Observe selected area coverage within one explicit domain/coordinate space.

    Pair areas are not additive for triple overlaps. overlap is their union;
    outside reports each original region beyond domain, including domain holes.
    No classification, completion, repair or overall pass/fail is inferred.
    """
    domain = _region(domain, "domain", empty=True)
    regions = _regions(regions, "regions")
    unit_mm = _number(unit_mm, "unit_mm", positive=True)
    clipped = {key: _area_parts(region.intersection(domain)) for key, region in regions.items()}
    covered = _area_parts(unary_union(list(clipped.values())))
    missing = _area_parts(domain.difference(covered))
    pairs = []
    for left, right in combinations(clipped, 2):
        intersection = _area_parts(clipped[left].intersection(clipped[right]))
        if not intersection.is_empty:
            pairs.append({"ids": (left, right), "geometry": intersection,
                          "area_m2": _area(intersection, unit_mm)})
    overlap = _area_parts(unary_union([pair["geometry"] for pair in pairs]))
    outside = {key: _area_parts(region.difference(domain)) for key, region in regions.items()}
    return {
        "checked_ids": tuple(regions), "pair_count": len(regions) * (len(regions)-1) // 2,
        "domain": domain, "covered": covered, "uncovered": missing, "overlap": overlap,
        "overlap_pairs": pairs, "outside": outside, "unit_mm": unit_mm,
        "domain_area_m2": _area(domain, unit_mm), "covered_area_m2": _area(covered, unit_mm),
        "uncovered_area_m2": _area(missing, unit_mm), "overlap_area_m2": _area(overlap, unit_mm),
        "outside_area_m2": {key: _area(shape, unit_mm) for key, shape in outside.items()},
        "scope": "Selected regions within the supplied domain; boundary-only contact has zero area",
        "not_checked": ["whether blank space or overlap is intentional", "unselected objects",
                        "floor or coordinate-system correspondence", "functional classification"],
    }


def measure_span(p1, p2, *, unit_mm, direction=None, source=None):
    """Endpoint distance or absolute projection onto an explicit direction.

    Direction is normalized, not snapped. Also return signed projection so
    endpoint order remains observable. Coincident endpoints are measurable.
    """
    p1, p2 = _finite(p1, 2, "p1"), _finite(p2, 2, "p2")
    unit_mm = _number(unit_mm, "unit_mm", positive=True)
    delta = tuple(b-a for a, b in zip(p1, p2))
    length = math.hypot(*delta)
    if direction is None:
        axis = tuple(v/length for v in delta) if length else None
        signed, mode = length, "aligned"
    else:
        axis = _finite(direction, 2, "direction")
        norm = math.hypot(*axis)
        if norm == 0 or not math.isfinite(norm):
            raise ValueError("direction must have positive finite length")
        axis = tuple(v/norm for v in axis)
        signed, mode = sum(d*u for d, u in zip(delta, axis)), "projected"
    if not all(math.isfinite(v) for v in (length, signed, length*unit_mm, signed*unit_mm)):
        raise ValueError("Span exceeds representable range")
    return {"p1": p1, "p2": p2, "mode": mode, "direction": axis, "unit_mm": unit_mm,
            "measured_mm": abs(signed)*unit_mm, "signed_mm": signed*unit_mm,
            "endpoint_distance_mm": length*unit_mm, "source": deepcopy(source)}
