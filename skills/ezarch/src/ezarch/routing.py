"""Optional point connectivity evidence in explicitly supplied planar free space.

No grid, implicit snapping, buffering, path drawing or room-use assumptions.
"""
from __future__ import annotations

from copy import deepcopy

import shapely
from shapely.geometry import Point

from .diagnostics import _expected_ids, _id_mapping, geometry_location
from .frames import _finite
from .wall_regions import _area_parts, _number, _region


def reachable_targets(free_space, start, targets, *, unit_mm, allowed_space=None,
                      expected_target_ids=None, source=None):
    """Classify original points by interior-connected area components.

    free_space already represents selected obstacles/openings. allowed_space
    optionally intersects it with caller-specified permitted space. Boundary or
    outside points are unresolved, never moved. A connected result concerns a
    zero-size point in supplied geometry, not a walkable or permitted route in
    a real building. Returned component indices are local to this result.
    """
    free_space = _region(free_space, "free_space", empty=True)
    unit_mm = _number(unit_mm, "unit_mm", positive=True)
    targets = _id_mapping(targets, "targets")
    expected = _expected_ids(expected_target_ids, "expected_target_ids")
    if allowed_space is not None:
        allowed_space = _region(allowed_space, "allowed_space", empty=True)
    effective = free_space if allowed_space is None else _area_parts(free_space.intersection(allowed_space))
    effective = _region(effective, "effective space", empty=True)
    parts = [] if effective.is_empty else list(effective.geoms) if effective.geom_type == "MultiPolygon" else [effective]

    def locate(value):
        try:
            if isinstance(value, (str, bytes, dict)):
                raise TypeError("Point requires numeric XY coordinates")
            if isinstance(value, Point):
                if value.is_empty or value.has_z or shapely.has_m(value):
                    raise ValueError("Point must be nonempty XY")
                xy = _finite(value.coords[0], 2, "point")
            else:
                xy = _finite(value, 2, "point")
        except (TypeError, ValueError, OverflowError) as exc:
            return {"point": None, "component": None, "reason": str(exc), "location": None}
        point = Point(xy)
        index = next((i for i, part in enumerate(parts) if part.contains(point)), None)
        if index is not None:
            reason = None
        elif effective.is_empty:
            reason = "empty_effective_space"
        elif effective.covers(point):
            reason = "on_boundary"
        elif allowed_space is not None and free_space.contains(point):
            reason = "outside_allowed_space"
        else:
            reason = "outside_supplied_free_space"
        return {"point": xy, "component": index, "reason": reason,
                "location": geometry_location(point, precision="original_target_point")}

    origin, records = locate(start), {}
    for key, target in targets.items():
        record = locate(target)
        if record["reason"] is not None or origin["reason"] is not None:
            status = "unresolved"
        elif record["component"] == origin["component"]:
            status = "connected_in_supplied_space"
        else:
            status = "disconnected_in_supplied_space"
        records[key] = {**record, "status": status, "start_reason": origin["reason"]}
    missing = tuple(key for key in expected if key not in targets) if expected is not None else ()
    for key in missing:
        records[key] = {"point": None, "component": None, "reason": "missing_target",
                        "location": None, "status": "unresolved", "start_reason": origin["reason"]}
    resolved = sum(record["status"] != "unresolved" for record in records.values())
    return {"start": origin, "targets": records, "free_space": free_space, "allowed_space": allowed_space,
            "effective_space": effective, "components": tuple(parts),
            "coverage": "none" if not resolved else "complete" if resolved == len(records) else "partial",
            "scope": {"input_target_ids": tuple(targets), "expected_target_ids": expected,
                      "missing_target_ids": missing, "unit_mm": unit_mm,
                      "method": "interior-connected components of valid supplied XY area; no grid or snap"},
            "source": deepcopy(source),
            "not_checked": ["targets beyond the supplied or expected IDs", "route drawing or drawn-route coverage",
                            "human dimensions, turning space or minimum passage width", "doors, stairs and level transitions",
                            "space ownership or permission beyond supplied allowed_space", "input completeness or physical accuracy",
                            "regulatory compliance or architectural suitability"]}
