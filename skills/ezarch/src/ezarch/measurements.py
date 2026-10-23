"""Measurements of caller-selected planar geometry, without project semantics."""
from __future__ import annotations

import math
from copy import deepcopy
from itertools import combinations

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from .frames import _finite
from .wall_regions import _area_parts, _geometry, _number, _region, _regions


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


def measure_clear_width(region, section, *, unit_mm, obstacles=None, source=None):
    """All interior intervals along an explicit finite straight section.

    A span clipped by a section endpoint inside free space has unknown full
    width (width_mm=None), while span_mm records its observed length. Section
    direction is not inferred to be perpendicular to a passage. No global
    minimum, human-body clearance, code threshold or automatic point selection.
    """
    region = _region(region, empty=True)
    section = _geometry(section, {"LineString"}, "section")
    if len(section.coords) != 2 or section.length == 0:
        raise ValueError("section requires exactly two distinct endpoints")
    unit_mm = _number(unit_mm, "unit_mm", positive=True)
    obstacles = _regions({} if obstacles is None else obstacles, "obstacles")
    masks = unary_union(list(obstacles.values())) if obstacles else Polygon()
    free = _region(region.difference(masks), "free space", empty=True)
    # One overlay preserves boundary nodes. Subtracting the boundary a second
    # time can manufacture microscopic intervals after rotated intersections.
    boundary_contact = section.intersection(free.boundary)
    observed = section.intersection(free)

    def lines(geometry):
        if geometry.geom_type == "LineString":
            yield geometry
        elif hasattr(geometry, "geoms"):
            for part in geometry.geoms:
                yield from lines(part)

    spans = []
    for line in lines(observed):
        if line.length == 0 or not line.relate_pattern(free, "1********"):
            continue
        endpoints = sorted((tuple(line.coords[0]), tuple(line.coords[-1])), key=lambda p: section.project(Point(p)))
        start, end = endpoints
        clipped = tuple(p in section.coords and free.contains(Point(p)) for p in endpoints)
        span_mm = math.dist(start, end)*unit_mm
        stations = tuple(section.project(Point(p))*unit_mm for p in endpoints)
        if not all(math.isfinite(v) for v in (span_mm, *stations)):
            raise ValueError("Section span exceeds representable range")
        spans.append({"start": start, "end": end, "span_mm": span_mm,
                      "width_mm": None if any(clipped) else span_mm, "truncated": clipped,
                      "stations_mm": stations, "geometry": LineString(endpoints),
                      "location": {"bounds": tuple(line.bounds), "points": [tuple(line.interpolate(.5, normalized=True).coords[0])],
                                   "precision": "section_interval"}})
    spans.sort(key=lambda span: span["stations_mm"][0])
    return {"intervals": spans, "region": region, "section": section, "free_space": free,
            "boundary_contact": boundary_contact, "obstacles": obstacles, "unit_mm": unit_mm,
            "obstacle_contacts": {key: section.intersection(mask) for key, mask in obstacles.items()},
            "observation": "intervals" if spans else "no_interior_interval" if not free.is_empty else "empty_free_space",
            "source": deepcopy(source), "scope": "Interior intervals on the supplied finite section only",
            "not_checked": ["section direction and position suitability", "global minimum or passage width",
                            "accuracy or completeness of selected surfaces and obstacles",
                            "human use, reachability and regulatory compliance"]}
