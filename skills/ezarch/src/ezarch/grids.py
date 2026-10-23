"""Independent axis geometry, paper-sized tags and directed offset measurements.

No axis layout, numbering, column placement, floor matching or design approval.
Drawing adapters reuse the caller's existing Drawing context and native entities.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from itertools import combinations

from .frames import _finite


def _length(value, name, *, positive=False):
    value, = _finite((value,), 1, name)
    if value < 0 or (positive and value == 0):
        raise ValueError(f"{name} must be {'positive' if positive else 'nonnegative'}")
    return value


def _axis(start, end):
    start, end = _finite(start, 2, "start"), _finite(end, 2, "end")
    length = _length(math.dist(start, end), "axis length", positive=True)
    direction = ((end[0]-start[0])/length, (end[1]-start[1])/length)
    return start, end, length, direction


def axis_segment(start, end, *, start_trim=0, end_trim=0):
    """Return two trimmed endpoints in the input unit; do not choose tag locations."""
    start, end, length, direction = _axis(start, end)
    first, last = _length(start_trim, "start_trim"), _length(end_trim, "end_trim")
    if first+last >= length:
        raise ValueError("End trims consume the entire axis segment")
    return (_finite((start[0]+direction[0]*first, start[1]+direction[1]*first), 2, "trimmed start"),
            _finite((end[0]-direction[0]*last, end[1]-direction[1]*last), 2, "trimmed end"))


def axis_offset(point, start, end, *, unit_mm):
    """Projection onto a directed infinite axis; positive offset is on its left.

    Inputs/projection use caller units; distances use mm. station_mm is measured
    from start, not the nearest endpoint. Outside-segment feet are not clamped.
    """
    point = _finite(point, 2, "point")
    start, end, length, (dx, dy) = _axis(start, end)
    unit_mm = _length(unit_mm, "unit_mm", positive=True)
    px, py = _finite((point[0]-start[0], point[1]-start[1]), 2, "relative point")
    station, offset = _finite((px*dx+py*dy, -px*dy+py*dx), 2, "projection distances")
    projection = _finite((start[0]+dx*station, start[1]+dy*station), 2, "projection")
    station_mm, offset_mm = _finite((station*unit_mm, offset*unit_mm), 2, "millimetre distances")
    return {"point": point, "axis": (start, end), "projection": projection,
            "station_mm": station_mm, "signed_offset_mm": offset_mm,
            "within_segment": 0 <= station <= length, "unit_mm": unit_mm}


def draw_axis(drawing, start, end, *, trim_start_mm=0, trim_end_mm=0,
              layer="A-GRID", color="BYLAYER", width=None, dash=None):
    """Draw one axis using explicit endpoints and optional paper-mm end trims.

    Coordinates are in the Drawing target unit, as with Drawing.line. The
    context supplies scale/unit conversion and drawing-resource behavior.
    No circles, names, intersections, columns or dimensions are added.
    """
    first, last = axis_segment(start, end,
                              start_trim=_length(trim_start_mm, "trim_start_mm")*drawing.scale,
                              end_trim=_length(trim_end_mm, "trim_end_mm")*drawing.scale)
    return drawing.line(first, last, layer=layer, color=color, width=width, dash=dash)


@dataclass
class AxisTag:
    entities: tuple
    center: tuple
    radius: float


def draw_axis_tag(drawing, center, label, *, diameter_mm, text_height_mm, rotation=0,
                  leader=(), layer="A-ANNOTATION", color="BYLAYER", width=None,
                  text_color="BYLAYER"):
    """A circular tag with independently supplied center and optional leader path.

    Diameter/text height are paper mm, rotation is CCW degrees in target XY.
    Leader vertices use target units and are drawn exactly as given; they are not
    routed or clipped. Text uses the Drawing's font/style; no fit/resize policy.
    Returned metadata describes construction, not later native edits.
    """
    center = _finite(center, 2, "center")
    radius = _length(_length(diameter_mm, "diameter_mm", positive=True)*drawing.scale/2,
                     "target radius", positive=True)
    height = _length(text_height_mm, "text_height_mm", positive=True)
    _length(height*drawing.scale, "target text height", positive=True)
    rotation, = _finite((rotation,), 1, "rotation")
    leader = tuple(_finite(point, 2, "leader point") for point in leader)
    if len(leader) == 1:
        raise ValueError("Leader needs at least two vertices, or an empty sequence")
    label = str(label)
    # Validate both appearances before drawing the first part of the tag.
    drawing._stroke(color, width, None, layer)
    if drawing._color(text_color, layer)[1] is None:
        raise ValueError("Tag text requires a color or BYLAYER")
    entities = []
    if leader:
        entities.extend(drawing.poly(leader, layer=layer, color=color, width=width))
    entities.extend(drawing.circle(center, radius, layer=layer, color=color, width=width))
    entities.extend(drawing.text(center, label, size=height, rotation=rotation, layer=layer, color=text_color))
    return AxisTag(tuple(entities), center, radius)


def axis_tag_spacing(circles, *, unit_mm):
    """Pairwise circle-envelope measurements, not label/layout validation.

    circles maps local IDs to (center, radius), all in the same coordinate unit.
    Negative circle_gap_mm means overlapping envelopes. Text, leaders and drawing
    content are not inspected. Empty/singleton inputs have zero measured pairs.
    """
    if not isinstance(circles, Mapping):
        raise TypeError("circles must map selected IDs to (center, radius)")
    unit_mm = _length(unit_mm, "unit_mm", positive=True)
    selected = {}
    for key, (center, radius) in circles.items():
        if not isinstance(key, str) or not key:
            raise ValueError("Circle IDs must be nonempty strings")
        selected[key] = (_finite(center, 2, "center"), _length(radius, "radius", positive=True))
    pairs = []
    for (a, (ca, ra)), (b, (cb, rb)) in combinations(selected.items(), 2):
        distance = math.dist(ca, cb)
        distance_mm, gap_mm = _finite((distance*unit_mm, (distance-ra-rb)*unit_mm), 2, "spacing")
        midpoint = _finite((ca[0]/2+cb[0]/2, ca[1]/2+cb[1]/2), 2, "midpoint")
        pairs.append({"ids": (a, b), "centers": (ca, cb), "midpoint": midpoint,
                      "center_distance_mm": distance_mm, "circle_gap_mm": gap_mm})
    return {"checked_ids": tuple(selected), "pair_count": len(pairs), "pairs": pairs, "unit_mm": unit_mm,
            "scope": "supplied circle envelopes in one coordinate space",
            "not_checked": ("text bounds", "leader intersections", "other drawing content",
                            "unselected markers", "design or drafting suitability")}
