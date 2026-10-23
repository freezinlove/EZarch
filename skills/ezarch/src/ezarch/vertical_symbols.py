"""Composable stair marks and rectangular lift geometry from a real CAD revision.

Local millimetres; no storey policy, inferred riser count, equipment selection or
circulation layout. These resources can be combined with any native geometry.
"""
from __future__ import annotations

import itertools
import math

from shapely.geometry import box

from .frames import _finite
from .symbols import Symbol, _positive, polygon_symbol
from .wall_regions import compose_wall_regions, opening_region, wall_band


def _positions(values, run, name):
    result = tuple(_finite((value,), 1, name)[0] for value in values)
    if len(set(result)) != len(result) or any(not 0 <= value <= run for value in result):
        raise ValueError(f"{name} must be distinct positions within [0, run]")
    return result


def stair_flight_symbol(width, run, *, treads, overhead_treads=(), side_edges=False):
    """One flight's selected tread lines: X across width, Y along run.

    Locations are explicit, not inferred from run or floor height. An overhead
    role needs the caller's style entry; placement can map it to a native linetype.
    Side edges are independent of landings, wells, breaks and direction marks.
    """
    width, run = _positive(width, "width"), _positive(run, "run")
    if not isinstance(side_edges, bool):
        raise TypeError("side_edges must be bool")
    treads = _positions(treads, run, "treads")
    overhead = _positions(overhead_treads, run, "overhead_treads")
    if set(treads) & set(overhead):
        raise ValueError("A tread cannot be both ordinary and overhead in this component")
    symbol = Symbol(nominal_bounds=(0, 0, width, run),
                    anchors={"start": (width/2, 0), "end": (width/2, run)})
    for positions, role in ((treads, "outline"), (overhead, "overhead")):
        for y in positions:
            symbol.segment((0, y), (width, y), role)
    if side_edges:
        for x in (0, width):
            symbol.segment((x, 0), (x, run))
    return symbol


def stair_break_symbol(width, *, amplitude, notch_width):
    """Four-vertex break mark; the mark does not erase or clip other geometry."""
    width = _positive(width, "width")
    amplitude, notch = _positive(amplitude, "amplitude"), _positive(notch_width, "notch_width")
    if notch >= width:
        raise ValueError("notch_width must be less than width")
    symbol = Symbol(nominal_bounds=(0, -amplitude, width, amplitude),
                    anchors={"center": (width/2, 0)})
    symbol.path([(0, -amplitude), ((width-notch)/2, amplitude),
                 ((width+notch)/2, -amplitude), (width, amplitude)], "outline")
    return symbol


def direction_symbol(points, *, head_length, head_width):
    """Editable shaft and two arrowhead lines, using explicit local-mm lengths.

    The final segment determines direction. No up/down label or route semantics
    are inferred; this mark can also be used outside a staircase.
    """
    points = tuple(_finite(point, 2, "point") for point in points)
    length, width = _positive(head_length, "head_length"), _positive(head_width, "head_width")
    if len(points) < 2 or any(a == b for a, b in itertools.pairwise(points)):
        raise ValueError("Direction path needs at least two points and no zero-length segments")
    a, b = points[-2:]
    distance = math.dist(a, b)
    if not math.isfinite(distance) or distance == 0:
        raise ValueError("Direction segment must have positive finite length")
    dx, dy = (b[0]-a[0])/distance, (b[1]-a[1])/distance
    symbol = Symbol(anchors={"tail": points[0], "tip": b})
    symbol.path(points, "outline")
    for sign in (-1, 1):
        symbol.segment(b, (b[0]-dx*length+sign*dy*width/2, b[1]-dy*length-sign*dx*width/2))
    symbol.nominal_bounds = symbol.geometry_bounds()
    return symbol


def lift_symbol(width, depth, *, wall_thickness, car_bounds, entrance_side, entrance_span,
                panel_count, panel_depth, panel_inset, shaft=True, car=True, doors=True,
                shaft_fill=None):
    """Rectangular shaft, explicit car and equal door panels; no product defaults.

    entrance_side is a local bottom/top/left/right edge, not a compass direction.
    Span coordinates run along X on top/bottom and Y on left/right. panel_inset
    measures inward from that outer edge. car_bounds is local (xmin,ymin,xmax,ymax).
    Dimensions are schematic geometry inputs, not certified equipment clearances.
    """
    width, depth = _positive(width, "width"), _positive(depth, "depth")
    thickness = _positive(wall_thickness, "wall_thickness")
    if thickness*2 >= min(width, depth):
        raise ValueError("Wall thickness leaves no shaft interior")
    if entrance_side not in ("bottom", "top", "left", "right"):
        raise ValueError("entrance_side must be a local bottom/top/left/right edge")
    if any(not isinstance(value, bool) for value in (shaft, car, doors)):
        raise TypeError("shaft, car and doors must be bool")
    if isinstance(panel_count, bool) or not isinstance(panel_count, int) or panel_count < 1:
        raise ValueError("panel_count must be a positive integer")
    pd = _positive(panel_depth, "panel_depth")
    inset, = _finite((panel_inset,), 1, "panel_inset")
    if not 0 <= inset <= thickness-pd:
        raise ValueError("Door panel depth/inset must fit the wall band")
    left, bottom, right, top = _finite(car_bounds, 4, "car_bounds")
    if not (thickness <= left < right <= width-thickness and
            thickness <= bottom < top <= depth-thickness):
        raise ValueError("Car bounds must fit the shaft interior")
    low, high = _finite(entrance_span, 2, "entrance_span")
    horizontal = entrance_side in ("bottom", "top")
    edge_length = width if horizontal else depth
    if not thickness <= low < high <= edge_length-thickness:
        raise ValueError("Entrance span must fit between the shaft's side walls")
    if horizontal:
        edge = 0 if entrance_side == "bottom" else depth
        center = thickness/2 if entrance_side == "bottom" else depth-thickness/2
        start, end = (low, center), (high, center)
        entrance_start, entrance_end = (low, edge), (high, edge)
    else:
        edge = 0 if entrance_side == "left" else width
        center = thickness/2 if entrance_side == "left" else width-thickness/2
        start, end = (center, low), (center, high)
        entrance_start, entrance_end = (edge, low), (edge, high)
    walls = wall_band(box(0, 0, width, depth), inside=thickness, outside=0, join="mitre")
    walls = compose_wall_regions({"shaft": walls}, cuts={"entrance": opening_region(start, end, depth=thickness)})
    symbol = polygon_symbol(walls.geometry, unit_mm=1, fill=shaft_fill) if shaft else Symbol()
    symbol.nominal_bounds = (0, 0, width, depth)
    symbol.anchors = {"origin": (0, 0), "car_center": ((left+right)/2, (bottom+top)/2),
                      "entrance_start": entrance_start, "entrance_end": entrance_end,
                      "entrance_center": tuple((a+b)/2 for a, b in zip(entrance_start, entrance_end))}
    if car:
        symbol.rect((left, bottom, right, top))
    if doors:
        for index in range(panel_count):
            a = low+(high-low)*index/panel_count
            b = low+(high-low)*(index+1)/panel_count
            if entrance_side == "bottom":
                bounds = (a, inset, b, inset+pd)
            elif entrance_side == "top":
                bounds = (a, depth-inset-pd, b, depth-inset)
            elif entrance_side == "left":
                bounds = (inset, a, inset+pd, b)
            else:
                bounds = (width-inset-pd, a, width-inset, b)
            symbol.rect(bounds)
    return symbol
