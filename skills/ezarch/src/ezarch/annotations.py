"""Read-only relationships of selected annotation footprints; no layout policy."""
from __future__ import annotations

import math
from copy import deepcopy
from dataclasses import dataclass
from itertools import chain, combinations, product

import shapely
from shapely.geometry import LineString, Polygon
from shapely.ops import nearest_points

from .diagnostics import _expected_ids, _id_mapping, geometry_location
from .frames import transform_geometry
from .wall_regions import _geometry, _number


@dataclass(frozen=True)
class Footprint:
    """Optional evidence wrapper. Raw Shapely geometry is also accepted."""

    geometry: object
    basis: str
    source: object = None
    unavailable_reason: str | None = None
    limitations: tuple[str, ...] = ()


def text_footprint(measurement, *, kind, transform=None):
    """Adapt measure_text's rotated corners in mm, including missing-glyph gaps.

    kind explicitly selects 'ink' or 'metrics'; both are envelopes, not glyph
    outlines. An optional affine maps mm to the caller's coordinate system.
    No renderer-specific layout or font substitution is inferred.
    """
    if kind not in {"ink", "metrics"}:
        raise ValueError("kind must select ink or metrics")
    source = deepcopy({key: measurement[key] for key in
                       ("text", "faces", "size_mm", "size_mode", "origin_mm", "rotation", "align", "valign", "method")})
    source["transform"] = deepcopy(transform)
    limitations = tuple(measurement["not_checked"]) + ("Envelope, not individual glyph ink",)
    if not measurement["glyph_coverage_complete"]:
        reason = "Missing glyphs: " + repr(measurement["missing_characters"])
        return Footprint(None, kind + "_envelope", source, reason, limitations)
    envelope = measurement[kind]
    if envelope is None:
        return Footprint(None, kind + "_envelope", source, "No envelope for this text and kind", limitations)
    geometry = Polygon(envelope["corners_mm"])
    if transform is not None:
        geometry = transform_geometry(geometry, transform)
    return Footprint(geometry, kind + "_envelope", source, limitations=limitations)


def annotation_conflicts(annotations, obstacles=None, *, unit_mm, clearance_mm=0,
                         expected_annotation_ids=None, expected_obstacle_ids=None):
    """Observe annotation pairs and annotation–obstacle pairs in one XY space.

    Inputs map IDs to Shapely geometries or Footprint records. Invalid inputs
    remain unassessed; other valid pairs are still compared. Touching and
    intersection are always observations; proximity uses distance < clearance.
    No implicit buffering, pen width, semantics, repair or object movement.
    """
    unit_mm = _number(unit_mm, "unit_mm", positive=True)
    clearance_mm = _number(clearance_mm, "clearance_mm")
    groups = {"annotation": _id_mapping(annotations, "annotations"),
              "obstacle": _id_mapping({} if obstacles is None else obstacles, "obstacles")}
    expected = {"annotation": _expected_ids(expected_annotation_ids, "expected_annotation_ids"),
                "obstacle": _expected_ids(expected_obstacle_ids, "expected_obstacle_ids")}
    inputs, valid = {}, {}
    for group, values in groups.items():
        for key, value in values.items():
            footprint = value if isinstance(value, Footprint) else Footprint(value, "supplied_geometry")
            record = {"group": group, "id": key, "basis": footprint.basis,
                      "source": deepcopy(footprint.source), "limitations": tuple(footprint.limitations),
                      "reason": footprint.unavailable_reason}
            token = (group, key)
            if not record["reason"]:
                try:
                    geometry = _geometry(footprint.geometry, {"Point", "MultiPoint", "LineString", "LinearRing",
                                                              "MultiLineString", "Polygon", "MultiPolygon"}, key)
                    valid[token] = geometry
                    record["bounds"] = tuple(geometry.bounds)
                except (TypeError, ValueError) as exc:
                    record["reason"] = str(exc)
            inputs[token] = record
    ann = [("annotation", key) for key in groups["annotation"]]
    obs = [("obstacle", key) for key in groups["obstacle"]]
    pair_count = len(ann)*(len(ann)-1)//2 + len(ann)*len(obs)
    pairs = chain(combinations(ann, 2), product(ann, obs))
    findings, pair_errors, checked = [], [], 0
    for left, right in pairs:
        if left not in valid or right not in valid:
            continue
        a, b = valid[left], valid[right]
        objects = [{"group": token[0], "id": token[1]} for token in (left, right)]
        try:
            distance_mm = a.distance(b)*unit_mm
            if not math.isfinite(distance_mm):
                raise ValueError("Pair distance exceeds representable range")
            if a.intersects(b):
                intersection = a.intersection(b)
                relation = "touches" if a.touches(b) else "intersects"
                area_mm2 = (intersection.area*unit_mm)*unit_mm
                if not math.isfinite(area_mm2):
                    raise ValueError("Intersection area exceeds representable range")
                evidence = intersection
            elif distance_mm < clearance_mm:
                intersection, area_mm2, relation = None, 0.0, "within_clearance"
                evidence = LineString([p.coords[0] for p in nearest_points(a, b)])
            else:
                checked += 1
                continue
            findings.append({"evidence": "candidate", "objects": objects, "relation": relation,
                             "distance_mm": distance_mm, "overlap_area_mm2": area_mm2,
                             "intersection": intersection, "geometry": evidence,
                             "location": geometry_location(evidence, precision="supplied_footprint_relation")})
            checked += 1
        except (ValueError, shapely.errors.GEOSException) as exc:
            pair_errors.append({"objects": objects, "reason": str(exc)})
    missing = {group: tuple(key for key in ids if key not in groups[group]) if ids is not None else ()
               for group, ids in expected.items()}
    gaps = any(record["reason"] for record in inputs.values()) or any(missing.values()) or pair_errors
    return {"inputs": list(inputs.values()), "findings": findings, "unassessed_pairs": pair_errors,
            "selected_pair_count": pair_count, "checked_pair_count": checked,
            "coverage": "none" if not checked else "partial" if gaps else "complete",
            "observation": "findings" if findings else "none_found" if checked else "not_assessed",
            "scope": {"input_ids": {g: tuple(v) for g, v in groups.items()}, "expected_ids": expected,
                      "missing_ids": missing, "unit_mm": unit_mm, "clearance_mm": clearance_mm,
                      "comparison": "annotation pairs and annotation-obstacle pairs only"},
            "not_checked": ["obstacle-obstacle pairs", "unselected or unrepresented objects",
                            "floor, units or coordinate-system correspondence", "rendered ink, pen width or occlusion",
                            "whether overlap is intentional", "visual quality, layout or architectural correctness"]}
