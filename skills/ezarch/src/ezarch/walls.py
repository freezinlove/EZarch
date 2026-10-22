"""Read-only observations on selected planar geometry, not architectural approval.

Lengths and reversal observations derive from real-task wall audits. Scope and
parameters are explicit; no project coordinates, repair, or design thresholds.
"""
from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping

import shapely
from shapely.geometry import LinearRing, LineString, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.validation import explain_validity

CHECKS = ("validity", "short_edges", "backtracks", "duplicates")
_SUPPORTED = {"Polygon", "MultiPolygon", "LineString", "LinearRing", "MultiLineString"}
_BOUNDARY = (
    "Only supplied planar straight geometry and explicitly selected checks; not design approval. "
    "No architectural semantics, gaps/misalignment, partial overlaps, near duplicates, "
    "openings, connectivity, visual quality or regulatory checks. "
    "No findings applies only to examined inputs; candidates may be intentional."
)


def _finite(value, name, *, positive=False):
    value = float(value)
    if not math.isfinite(value) or (value <= 0 if positive else value < 0):
        raise ValueError(f"{name} must be {'positive' if positive else 'nonnegative'} and finite")
    return value


def _parts(geometry):
    return list(geometry.geoms) if geometry.geom_type.startswith("Multi") else [geometry]


def _paths(geometry):
    for part_index, part in enumerate(_parts(geometry)):
        if part.geom_type == "Polygon":
            rings = [("exterior", part.exterior), *[(i, ring) for i, ring in enumerate(part.interiors)]]
        else:
            rings = [(None, part)]
        for ring_index, ring in rings:
            coords = [tuple(p) for p in ring.coords]
            closed = len(coords) > 1 and coords[0] == coords[-1]
            if closed:
                coords.pop()  # One closing endpoint, not a repair of repeated interior vertices.
            yield {"part": part_index, "ring": ring_index}, coords, closed


def _location(points, precision="segment"):
    points = [list(p) for p in points]
    xs, ys = zip(*points)
    return {"points": points, "bounds": [min(xs), min(ys), max(xs), max(ys)], "precision": precision}


def _finding(kind, objects, location, measurements, basis, *, evidence="candidate"):
    return {"kind": kind, "evidence": evidence, "objects": objects, "location": location,
            "measurements": measurements, "basis": basis}


def _validity(identity, geometry):
    # A closed line is assessed as a region only for this selected check.
    target = Polygon(geometry) if geometry.geom_type == "LinearRing" else geometry
    reason = explain_validity(target)
    if target.is_valid:
        return []
    location = {"bounds": list(target.bounds), "points": [], "precision": "object_bounds"}
    match = re.search(r"\[([^\[\]]+)\]$", reason)
    if match:
        try:
            point = [float(v) for v in match[1].split()]
            if len(point) == 2 and all(math.isfinite(v) for v in point):
                location = _location([point], "backend_point")
        except ValueError:
            pass
    return [_finding("invalid_region", [{"id": identity}], location, {"reason": reason},
                     "GEOS validity of this straight-edge planar region; reports one reason, not all defects",
                     evidence="representation_invalid")]


def _path_findings(identity, geometry, check, unit_mm, threshold, min_edge_mm):
    findings, examined, excluded = [], 0, 0
    for reference, points, closed in _paths(geometry):
        count = len(points)
        edges = count if closed else count - 1
        if check == "short_edges":
            for i in range(edges):
                a, b = points[i], points[(i + 1) % count]
                length = math.dist(a, b) * unit_mm
                examined += 1
                if length < threshold:
                    findings.append(_finding("short_edge", [{"id": identity, **reference, "edge": i}],
                                             _location([a, b]), {"length_mm": length},
                                             "length_mm < short_edge_mm; short does not mean erroneous"))
        else:
            for i in range(0 if closed else 1, count if closed else count - 1):
                a, b, c = points[i - 1], points[i], points[(i + 1) % count]
                incoming = (b[0] - a[0], b[1] - a[1])
                outgoing = (c[0] - b[0], c[1] - b[1])
                first, second = math.hypot(*incoming), math.hypot(*outgoing)
                if min(first, second) * unit_mm <= min_edge_mm:
                    excluded += 1
                    continue
                cosine = sum((u / first) * (v / second) for u, v in zip(incoming, outgoing))
                deviation = math.degrees(math.acos(max(-1, min(1, -cosine))))
                examined += 1
                if deviation <= threshold:
                    findings.append(_finding("near_reversal", [{"id": identity, **reference, "vertex": i}],
                                             _location([a, b, c], "vertex_neighborhood"),
                                             {"vertex": list(b), "incoming_mm": first * unit_mm,
                                              "outgoing_mm": second * unit_mm,
                                              "deviation_from_reversal_deg": deviation},
                                             "deviation <= reversal_deviation_deg; no automatic repair"))
    return findings, examined, excluded


def inspect_geometry(geometries: Mapping[str, BaseGeometry], *, checks: Iterable[str], unit_mm: float,
                     short_edge_mm: float | None = None, reversal_deviation_deg: float | None = None,
                     min_edge_mm: float = 0, expected_ids: Iterable[str] | None = None) -> dict:
    """Observe selected 2D straight geometry; return JSON-compatible facts and scope.

    Input IDs are local to this call, coordinates remain in the caller's space,
    unit_mm is millimetres per input unit. Compare only compatible planes/scopes.
    Unknown/nonfinite/3D/empty geometry is reported, never silently dropped.
    Polygon validity uses GEOS exact floating-point topology (no snapping).
    Duplicates compare canonical coordinate sequences, not proximity or style.
    See references/geometry-diagnostics.md for supported representations/limits.
    """
    if not isinstance(geometries, Mapping) or any(not isinstance(k, str) or not k for k in geometries):
        raise ValueError("geometries must map nonempty string IDs to geometry")
    if isinstance(checks, str):
        raise TypeError("checks must be a collection of check names")
    checks = list(dict.fromkeys(checks))
    if not checks or set(checks) - set(CHECKS):
        raise ValueError(f"Select checks from {CHECKS}")
    unit_mm = _finite(unit_mm, "unit_mm", positive=True)
    min_edge_mm = _finite(min_edge_mm, "min_edge_mm")
    if "short_edges" in checks:
        if short_edge_mm is None:
            raise ValueError("short_edges needs explicit short_edge_mm")
        short_edge_mm = _finite(short_edge_mm, "short_edge_mm", positive=True)
    if "backtracks" in checks:
        if reversal_deviation_deg is None:
            raise ValueError("backtracks needs explicit reversal_deviation_deg")
        reversal_deviation_deg = _finite(reversal_deviation_deg, "reversal_deviation_deg")
        if reversal_deviation_deg >= 90:
            raise ValueError("reversal_deviation_deg must be below 90")
    if isinstance(expected_ids, str):
        raise TypeError("expected_ids must be a collection of IDs")
    expected = None if expected_ids is None else list(dict.fromkeys(expected_ids))
    if expected is not None and any(not isinstance(k, str) or not k for k in expected):
        raise ValueError("expected_ids must contain nonempty strings")
    missing = [] if expected is None else [k for k in expected if k not in geometries]
    available, inputs = {}, []
    for identity, geometry in geometries.items():
        item = {"id": identity, "geometry_type": getattr(geometry, "geom_type", None)}
        reason = None
        if not isinstance(geometry, BaseGeometry):
            reason = "not_shapely_geometry"
        elif geometry.is_empty:
            reason = "empty_geometry"
        elif geometry.has_z or shapely.has_m(geometry):
            reason = "non_2d_geometry"
        elif geometry.geom_type not in _SUPPORTED:
            reason = "unsupported_geometry_type"
        elif not all(math.isfinite(float(v)) for p in shapely.get_coordinates(geometry) for v in p):
            reason = "nonfinite_coordinates"
        else:
            bounds = list(geometry.bounds)
            span = max(bounds[2] - bounds[0], bounds[3] - bounds[1])
            if not math.isfinite(span * unit_mm * 2):
                reason = "unrepresentable_measurement_range"
            else:
                available[identity] = geometry
                item["bounds"] = bounds
        item["unavailable_reason"] = reason
        inputs.append(item)
    results = []
    unavailable = [{"id": item["id"], "reason": item["unavailable_reason"]}
                   for item in inputs if item["unavailable_reason"]]
    for name in checks:
        unexamined = [*unavailable, *[{"id": k, "reason": "expected_id_missing"} for k in missing]]
        examined_ids, findings = [], []
        result = {"name": name, "parameters": {}, "examined_ids": examined_ids,
                  "unexamined": unexamined, "findings": findings}
        if name == "duplicates":
            result["parameters"] = {"comparison": "canonical_exact_coordinates", "tolerance": 0}
            if len(available) < 2:
                unexamined.extend({"id": k, "reason": "needs_two_comparable_inputs"} for k in available)
                result["compared_pairs"] = 0
            else:
                groups = {}
                for identity, geometry in available.items():
                    target = Polygon(geometry) if geometry.geom_type == "LinearRing" else geometry
                    coordinates = shapely.get_coordinates(target)
                    coordinates[coordinates == 0] = 0.0  # +0 and -0 are equal coordinates, not distinct geometry.
                    target = shapely.set_coordinates(target, coordinates)
                    key = (geometry.geom_type, shapely.normalize(target).wkb)
                    groups.setdefault(key, []).append(identity)
                    examined_ids.append(identity)
                result["compared_pairs"] = len(available) * (len(available) - 1) // 2
                for ids in groups.values():
                    if len(ids) > 1:
                        findings.append(_finding("duplicate_geometry", [{"id": k} for k in ids],
                                                 {"bounds": list(available[ids[0]].bounds), "points": [],
                                                  "precision": "object_bounds"}, {"instances": len(ids)},
                                                 "same type and canonical coordinates; purpose/style not assessed"))
        else:
            result["examined_elements"] = 0
            result["excluded_degenerate_vertices"] = 0
            if name == "short_edges":
                result["parameters"] = {"short_edge_mm": short_edge_mm, "comparison": "strictly_less"}
            elif name == "backtracks":
                result["parameters"] = {"reversal_deviation_deg": reversal_deviation_deg,
                                        "min_edge_mm": min_edge_mm, "comparison": "less_or_equal"}
            else:
                result["parameters"] = {"backend": f"GEOS {shapely.geos_version_string}", "snapping": False}
            for identity, geometry in available.items():
                if name == "validity":
                    if geometry.geom_type not in {"Polygon", "MultiPolygon", "LinearRing"}:
                        unexamined.append({"id": identity, "reason": "not_a_region_or_ring"})
                        continue
                    findings.extend(_validity(identity, geometry))
                    result["examined_elements"] += 1
                else:
                    found, count, excluded = _path_findings(
                        identity, geometry, name, unit_mm,
                        short_edge_mm if name == "short_edges" else reversal_deviation_deg, min_edge_mm)
                    findings.extend(found)
                    result["examined_elements"] += count
                    result["excluded_degenerate_vertices"] += excluded
                    if excluded:
                        unexamined.append({"id": identity, "reason": "degenerate_adjacent_edges",
                                           "vertices": excluded})
                    if not count:
                        unexamined.append({"id": identity, "reason": "no_applicable_elements"})
                        continue
                examined_ids.append(identity)
        result["coverage"] = "none" if not examined_ids else "partial" if unexamined else "complete"
        result["observation"] = "findings" if findings else "none_found" if examined_ids else "not_assessed"
        results.append(result)
    return {"scope": {"input_ids": list(geometries), "expected_ids": expected, "missing_ids": missing,
                      "completeness": "unknown_beyond_supplied_inputs", "unit_mm": unit_mm,
                      "coordinates": "caller_supplied_xy", "selected_checks": checks,
                      "unselected_checks": [name for name in CHECKS if name not in checks]},
            "inputs": inputs, "checks": results, "interpretation": _BOUNDARY}


def _dxf_geometry(entity):
    """Deliberately narrow conversion; never flatten curves or infer wall roles."""
    kind = entity.dxftype()
    if kind not in {"LINE", "LWPOLYLINE", "HATCH"}:
        raise ValueError("unsupported_entity_type; blocks and curves are not expanded")
    if tuple(entity.dxf.get("extrusion", (0, 0, 1))) != (0, 0, 1):
        raise ValueError("non_default_ocs")
    if kind != "HATCH" and entity.dxf.get("thickness", 0) != 0:
        raise ValueError("nonzero_thickness")
    if kind == "LINE":
        a, b = entity.dxf.start, entity.dxf.end
        if a.z != 0 or b.z != 0:
            raise ValueError("nonzero_elevation")
        return LineString([(a.x, a.y), (b.x, b.y)])
    if kind == "LWPOLYLINE":
        if entity.dxf.elevation != 0:
            raise ValueError("nonzero_elevation")
        if entity.has_arc:
            raise ValueError("curved_polyline")
        points = list(entity.get_points("xy"))
        return LinearRing(points) if entity.closed else LineString(points)
    if entity.dxf.elevation.z != 0:
        raise ValueError("nonzero_elevation")
    if entity.dxf.hatch_style != 0:
        raise ValueError("unsupported_hatch_style")
    paths = list(entity.paths)
    if not paths or any(not hasattr(path, "vertices") for path in paths):
        raise ValueError("hatch_requires_straight_polyline_paths")
    if any(not path.is_closed or any(v[2] != 0 for v in path.vertices) for path in paths):
        raise ValueError("open_or_curved_hatch_path")
    outer = [path for path in paths if path.path_type_flags & 1]
    if len(outer) != 1 or any(not path.path_type_flags & 16 for path in paths if path not in outer):
        raise ValueError("ambiguous_hatch_roles; needs one external shell and outermost holes")
    return Polygon([(v[0], v[1]) for v in outer[0].vertices],
                   [[(v[0], v[1]) for v in path.vertices] for path in paths if path not in outer])


def inspect_dxf_entities(entities: Iterable, **options) -> dict:
    """Inspect an explicit selection; options are those of inspect_geometry.

    Modelspace, paper space and block coordinates are distinct; select one plane
    and layout per call. Handles identify supplied entities; unbound entities get
    selection:N IDs. This function never writes the drawing or follows INSERTs.
    Native widths, layers and styles do not change the measured centerline/path.
    """
    geometries, sources, failures = {}, {}, {}
    for index, entity in enumerate(entities):
        handle = entity.dxf.get("handle")
        identity = handle or f"selection:{index}"
        if identity in geometries:
            raise ValueError(f"Duplicate selection ID {identity}; select one document/layout or use explicit IDs")
        layout = entity.get_layout()
        sources[identity] = {"handle": handle, "entity_type": entity.dxftype(), "layer": entity.dxf.layer,
                             "layout": layout.name if layout else None}
        try:
            geometries[identity] = _dxf_geometry(entity)
        except (ValueError, TypeError, shapely.errors.GEOSException) as exc:
            geometries[identity] = None
            failures[identity] = str(exc)
    result = inspect_geometry(geometries, **options)
    for item in result["inputs"]:
        item["source"] = sources[item["id"]]
        if item["id"] in failures:
            item["unavailable_reason"] = failures[item["id"]]
    for check in result["checks"]:
        for item in check["unexamined"]:
            if item["id"] in failures:
                item["reason"] = failures[item["id"]]
        for finding in check["findings"]:
            for obj in finding["objects"]:
                obj["source"] = sources[obj["id"]]
    return result
