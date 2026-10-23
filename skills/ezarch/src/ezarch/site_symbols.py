"""Explicit route and site geometry resources; no routing, planting or site planning."""
import math

from .frames import _finite
from .symbols import Symbol, _positive, polygon_symbol


def route_symbol(points, *, head_length, head_width, start_arrow=False, end_arrow=True, role='outline', fill=None):
    points = [_finite(p, 2, 'route point') for p in points]
    if len(points) < 2 or any(a == b for a, b in zip(points, points[1:])):
        raise ValueError('Route needs at least two points and nonzero segments')
    head_length, head_width = _positive(head_length, 'head length'), _positive(head_width, 'head width')
    symbol = Symbol(anchors={'start': points[0], 'end': points[-1]})
    symbol.path(points, role=role)
    def head(tip, previous):
        dx, dy = tip[0] - previous[0], tip[1] - previous[1]
        length = math.hypot(dx, dy)
        dx, dy = dx / length, dy / length
        back = tip[0] - dx * head_length, tip[1] - dy * head_length
        wings = [(back[0] - dy * head_width / 2, back[1] + dx * head_width / 2), tip,
                 (back[0] + dy * head_width / 2, back[1] - dx * head_width / 2)]
        symbol.path(wings, role=role, closed=bool(fill), fill=fill)
    if start_arrow:
        head(points[0], points[1])
    if end_arrow:
        head(points[-1], points[-2])
    return symbol


def direction_symbol(direction, *, length, head_length, head_width, **kwargs):
    dx, dy = _finite(direction, 2, 'direction')
    magnitude = math.hypot(dx, dy)
    if magnitude == 0:
        raise ValueError('Direction must be nonzero')
    length = _positive(length, 'length')
    return route_symbol([(0, 0), (length * dx / magnitude, length * dy / magnitude)],
                        head_length=head_length, head_width=head_width, **kwargs)


def road_symbol(points, *, left_width, right_width, join, fill=None, centerline=False):
    from shapely.geometry import LineString
    path = LineString([_finite(p, 2, 'road point') for p in points])
    left_width, right_width = _finite((left_width, right_width), 2, 'road widths')
    if min(left_width, right_width) < 0 or left_width + right_width <= 0 or path.length <= 0:
        raise ValueError('Nonnegative widths with positive sum and nonempty path required')
    if join not in {'mitre', 'bevel', 'round'}:
        raise ValueError('join: mitre, bevel, round')
    geometry = path.buffer(left_width, single_sided=True, join_style=join).union(
        path.buffer(-right_width, single_sided=True, join_style=join))
    symbol = polygon_symbol(geometry, unit_mm=1, fill=fill)
    if centerline:
        symbol.path(points, role='detail')
    return symbol


def canopy_symbol(*, radius=None, outline=None, trunk_radius=None, pit=None, fill=None):
    """Use a caller-chosen circle/polygon canopy; optional trunk and explicit pit outline."""
    if (radius is None) == (outline is None):
        raise ValueError('Specify exactly one of radius or outline')
    symbol = Symbol(anchors={'origin': (0, 0)})
    if radius is not None:
        radius = _positive(radius, 'canopy radius')
        symbol.ellipse((0, 0), radius * 2, radius * 2, role='outline', fill=fill)
    else:
        symbol.polygon(outline, role='outline', fill=fill)
    if trunk_radius is not None:
        trunk_radius = _positive(trunk_radius, 'trunk radius')
        symbol.ellipse((0, 0), trunk_radius * 2, trunk_radius * 2, role='detail')
    if pit is not None:
        symbol.polygon(pit, role='detail')
    return symbol
