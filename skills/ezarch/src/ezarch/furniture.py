"""Optional editable plan furniture, extracted from two completed drawing tasks.

These are geometry resources, not design rules or an exhaustive furniture catalog.
Local dimensions are mm; placement and appearance live independently in symbols.
Retained small construction details are resource-specific, not furniture standards.
"""
from __future__ import annotations

import math

from ezdxf import bbox

from .frames import _finite
from .symbols import Symbol, _positive

# Each entry is (required detail names, optional detail names).
_DETAILS = {
    "bed": ({"mattress", "pillows"}, set()),
    "sofa": ({"seats"}, {"arm_width"}), "lounge": ({"seats"}, {"arm_width"}),
    "bench": ({"seats"}, set()),
    "wardrobe": ({"modules"}, {"mirror", "fittings"}),
    "cabinet": ({"modules"}, {"mirror", "fittings"}),
    "counter": ({"modules"}, {"mirror", "fittings"}),
    "tv": ({"modules", "screen_width"}, {"mirror", "fittings"}),
    "shower": ({"opening"}, set()),
    **{name: (set(), set()) for name in (
        "dining_chair", "task_chair", "table", "coffee", "side_table", "nightstand",
        "fridge", "desk", "washer", "vanity", "wc", "bathtub")},
}

# Directions describe only the supplied geometry, not its intended room position.
# Symmetric/ambiguous resources have no inferred front or required approach side.
_RESOURCE_DIRECTIONS = {
    "bed": {"head": (0, 1), "foot": (0, -1)},
    "shower": {"opening": (0, 1)},
    **{kind: {"front": (0, 1), "back": (0, -1)} for kind in (
        "sofa", "lounge", "dining_chair", "task_chair", "wc", "nightstand",
        "wardrobe", "cabinet", "counter", "tv", "fridge", "washer", "vanity")},
}


def _count(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} requires a positive integer")
    return value


def _check_bounds(parts, bounds):
    extent = bbox.extents([part.entity for part in parts if not part.fill], fast=False)
    left, bottom, right, top = bounds
    if extent.has_data and (extent.extmin.x < left-0.1 or extent.extmin.y < bottom-0.1 or
                            extent.extmax.x > right+0.1 or extent.extmax.y > top+0.1):
        raise ValueError("Resource details extend beyond the supplied dimensions; edit the geometry or dimensions")


def _bounded(symbol, width, depth):
    _check_bounds(symbol.parts, (0, 0, width, depth))
    return symbol


def furniture_symbol(kind, width, depth, **details):
    """Build a supplied furniture resource once; no colors, layout or files implied.

    Bed requires mattress=(width,length) and pillows; seating requires seats;
    cabinets require modules; tv additionally requires screen_width; shower requires
    opening=(start,end) along local X. fittings are (sink/hob/dishwasher, local bounds).
    Unknown/irrelevant details fail rather than silently applying a different design.
    See references/editable-components.md for axes and retained construction details.
    """
    if kind not in _DETAILS:
        raise ValueError(f"No bundled geometry for {kind!r}; use Symbol/native entities or another resource")
    width, depth = _positive(width, "width"), _positive(depth, "depth")
    required, optional = _DETAILS[kind]
    missing, unknown = required-details.keys(), details.keys()-required-optional
    if missing or unknown:
        raise ValueError(f"{kind}: missing details {sorted(missing)}, unsupported details {sorted(unknown)}")
    details = dict(details)
    for key in ("pillows", "seats", "modules"):
        if key in details:
            _count(details[key], key)
    for key in ("arm_width", "screen_width"):
        if key in details:
            details[key] = _positive(details[key], key)
    if "mirror" in details and not isinstance(details["mirror"], bool):
        raise ValueError("mirror must be bool (mirror line on cabinet, not placement reflection)")
    if "mattress" in details:
        mw, ml = _finite(details["mattress"], 2, "mattress")
        details["mattress"] = (_positive(mw, "mattress width"), _positive(ml, "mattress length"))
    if "opening" in details:
        start, end = _finite(details["opening"], 2, "opening")
        if not 25 <= start < end <= width-25 or end-start < 90:
            raise ValueError("Opening does not fit sliding-panel geometry (25 mm ends, 90 mm overlap)")
        details["opening"] = start, end
    if "fittings" in details:
        fittings = []
        for name, bounds in details["fittings"]:
            if name not in ("sink", "hob", "dishwasher"):
                raise ValueError(f"No bundled fitting geometry for {name!r}")
            left, bottom, right, top = _finite(bounds, 4, "fitting bounds")
            if not (0 <= left < right <= width and 0 <= bottom < top <= depth):
                raise ValueError("Fitting bounds must lie inside the cabinet")
            fittings.append((name, (left, bottom, right, top)))
        details["fittings"] = fittings
    symbol = Symbol(nominal_bounds=(0, 0, width, depth),
                    anchors={"origin": (0, 0), "center": (width/2, depth/2)},
                    directions=_RESOURCE_DIRECTIONS.get(kind))
    _draw(symbol, kind, width, depth, details)
    return _bounded(symbol, width, depth)


def _draw(symbol, kind, width, depth, details):
    if kind == "bed":
        symbol.rect((0, 0, width, depth), 30, fill="upholstery")
        symbol.rect((18, depth - 95, width - 18, depth - 18), 15, fill="upholstery_dark")
        mattress_width, mattress_length = details["mattress"]
        mattress_left = (width - mattress_width) / 2
        mattress_right = (width + mattress_width) / 2
        mattress_top = depth - 100
        mattress_bottom = mattress_top - mattress_length
        if mattress_left < 20 or mattress_bottom < 20:
            raise ValueError("Mattress needs at least 20 mm side/foot margin and 100 mm head margin")
        symbol.rect((mattress_left, mattress_bottom, mattress_right, mattress_top), 55, fill="plain")
        symbol.rect((mattress_left + 20, mattress_bottom + 25, mattress_right - 20, depth - 600), 42, "detail", "bedding")
        symbol.line([(mattress_left + 30, depth - 620), (width * 0.38, depth - 635), (width * 0.66, depth - 615), (mattress_right - 30, depth - 628)])
        symbol.line([(mattress_left + 35, mattress_bottom + 85), (mattress_right - 35, mattress_bottom + 85)], "seam")
        pillow_count = details["pillows"]
        pillow_width = (mattress_width - 80 - (pillow_count - 1) * 45) / pillow_count
        if pillow_width <= 80:
            raise ValueError("Pillow seams do not fit the requested count and mattress")
        for index in range(pillow_count):
            start = mattress_left + 40 + index * (pillow_width + 45)
            symbol.rect((start, depth - 530, start + pillow_width, depth - 180), 60, "detail", "plain")
            symbol.line([(start + 40, depth - 215), (start + pillow_width - 40, depth - 215)], "seam")
    elif kind in ["sofa", "lounge"]:
        symbol.rect((0, 0, width, depth), 105 if kind == "sofa" else 150, fill="upholstery")
        symbol.rect((30, 25, width - 30, 205), 65, "detail", "upholstery_dark")
        arm = details.get("arm_width", 125 if kind == "sofa" else 110)
        symbol.rect((25, 140, arm, depth - 50), 42, "detail", "upholstery_dark")
        symbol.rect((width - arm, 140, width - 25, depth - 50), 42, "detail", "upholstery_dark")
        seats = details["seats"]
        cushion_width = (width - arm * 2 - 24 - (seats - 1) * 18) / seats
        if cushion_width <= 70:
            raise ValueError("Seat cushions do not fit the requested count and arm width")
        for index in range(seats):
            start = arm + 12 + index * (cushion_width + 18)
            symbol.rect((start, 235, start + cushion_width, depth - 65), 55, "detail", "upholstery")
            symbol.line([(start + 35, depth - 102), (start + cushion_width - 35, depth - 102)], "seam")
    elif kind == "dining_chair":
        symbol.line([(45, 90), (45, depth - 25), (width - 45, depth - 25), (width - 45, 90)], "seam")
        symbol.rect((20, 0, width - 20, 105), 48, fill="upholstery_dark")
        symbol.rect((0, 115, width, depth), 75, fill="upholstery")
        symbol.line([(45, depth - 45), (width - 45, depth - 45)], "seam")
    elif kind == "task_chair":
        center = (width / 2, depth * 0.58)
        radius = min(width, depth) * 0.43
        for index in range(5):
            angle = index * 2 * math.pi / 5
            endpoint = (center[0] + radius * math.cos(angle), center[1] + radius * math.sin(angle))
            symbol.line([center, endpoint], "detail")
        symbol.rect((55, depth * 0.29, width - 55, depth - 25), 95, fill="upholstery")
        symbol.rect((45, 0, width - 45, depth * 0.23), 60, fill="upholstery_dark")
        symbol.rect((0, depth * 0.31, 40, depth * 0.72), 16, "detail", "upholstery_dark")
        symbol.rect((width - 40, depth * 0.31, width, depth * 0.72), 16, "detail", "upholstery_dark")
    elif kind == "bench":
        symbol.rect((0, 0, width, depth), 32, fill="cabinet")
        count = details["seats"]
        for index in range(count):
            symbol.rect((18 + index * width / count, 25, (index + 1) * width / count - 18, depth - 25), 36, "detail", "upholstery")
    elif kind in ["table", "coffee", "side_table", "nightstand"]:
        radius = 75 if kind in ["table", "coffee"] else 28
        symbol.rect((0, 0, width, depth), radius, fill="table" if kind in ["table", "coffee"] else "cabinet")
        symbol.rect((22, 22, width - 22, depth - 22), max(8, radius - 22), "seam")
        if kind == "table":
            for horizontal in [100, width - 160]:
                for vertical in [100, depth - 160]:
                    symbol.rect((horizontal, vertical, horizontal + 60, vertical + 60), 5, "seam")
        elif kind == "nightstand":
            symbol.line([(width * 0.36, depth - 42), (width * 0.64, depth - 42)])
    elif kind in ["wardrobe", "cabinet", "counter", "tv"]:
        symbol.rect((0, 0, width, depth), 0, fill="cabinet")
        symbol.line([(20, 22), (width - 20, 22)], "seam")
        module_count = details["modules"]
        if width / module_count <= 110:
            raise ValueError("Cabinet handles do not fit the requested module count")
        for index in range(1, module_count):
            location = index * width / module_count
            symbol.line([(location, 25 if kind == "wardrobe" else depth - 100), (location, depth - 15)])
        symbol.line([(15, depth - 25), (width - 15, depth - 25)])
        for index in range(module_count):
            center = (index + 0.5) * width / module_count
            symbol.line([(center - 55, depth - 62), (center + 55, depth - 62)])
        if kind == "tv":
            screen_width = details["screen_width"]
            if screen_width > width - 100:
                raise ValueError("Screen needs 50 mm side margins in this geometry resource")
            symbol.rect((width / 2 - 130, min(depth * 0.32, 120), width / 2 + 130, min(depth * 0.32, 120) + 55), 8, "detail")
            symbol.rect(((width - screen_width) / 2, 35, (width + screen_width) / 2, 72), 9, "outline", "metal")
        if details.get("mirror", False):
            symbol.line([(30, 42), (width - 30, 42)], "glass")
        for fitting, bounds in details.get("fittings", ()):
            first_part = len(symbol.parts)
            left, bottom, right, top = bounds
            fitting_width, fitting_depth = right - left, top - bottom
            symbol.rect((left, bottom, right, top), 18, "detail", "fixture")
            if fitting == "sink":
                symbol.rect((left + 45, bottom + 55, right - 45, top - 40), 62, "detail")
                symbol.ellipse(((left + right) / 2, (bottom + top) / 2), 44, 44)
                symbol.ellipse(((left + right) / 2, bottom + 22), 24, 24)
                symbol.line([((left + right) / 2, bottom + 22), ((left + right) / 2, bottom + 110)])
            elif fitting == "hob":
                for index_u, proportion_u in enumerate([0.27, 0.73]):
                    for index_v, proportion_v in enumerate([0.28, 0.67]):
                        center = (left + fitting_width * proportion_u, bottom + fitting_depth * proportion_v)
                        diameter = 155 if index_u == index_v else 125
                        symbol.ellipse(center, diameter, diameter)
                        symbol.ellipse(center, diameter * 0.57, diameter * 0.57, "seam")
                        symbol.line([(center[0] - diameter * 0.58, center[1]), (center[0] + diameter * 0.58, center[1])], "seam")
                for proportion in [0.25, 0.42, 0.59, 0.76]:
                    symbol.ellipse((left + fitting_width * proportion, top - 22), 15, 15)
            else:
                symbol.line([(left + 35, top - 60), (right - 35, top - 60)])
                symbol.line([((left + right) / 2 - 80, top - 35), ((left + right) / 2 + 80, top - 35)])
            _check_bounds(symbol.parts[first_part:], bounds)
    elif kind == "fridge":
        symbol.rect((0, 0, width, depth), 15, fill="fixture")
        symbol.rect((20, 25, width - 20, depth - 80), 12, "seam")
        symbol.line([(15, depth - 65), (width - 15, depth - 65)])
        symbol.line([(width / 2, depth - 65), (width / 2, depth - 15)])
        symbol.line([(width / 2 - 50, depth - 45), (width / 2 - 50, depth - 20)])
        symbol.line([(width / 2 + 50, depth - 45), (width / 2 + 50, depth - 20)])
    elif kind == "desk":
        symbol.rect((0, 0, width, depth), 18, fill="table")
        symbol.line([(20, depth - 25), (width - 20, depth - 25)])
        symbol.rect((20, depth - 100, width * 0.23, depth - 35), 3, "detail")
        symbol.line([(width * 0.08, depth - 65), (width * 0.18, depth - 65)])
        center = width * 0.61
        symbol.rect((center - 145, depth * 0.30, center + 145, depth * 0.72), 8, "detail", "fixture")
        symbol.rect((center - 138, depth * 0.31, center + 138, depth * 0.36), 3, "detail", "metal")
        symbol.line([(center - 105, depth * 0.64), (center + 105, depth * 0.64)], "seam")
    elif kind == "washer":
        symbol.rect((0, 0, width, depth), 15, fill="fixture")
        symbol.rect((25, 25, width - 25, depth - 105), 12, "seam")
        symbol.line([(20, depth - 90), (width - 20, depth - 90)])
        symbol.rect((width * 0.12, depth - 70, width * 0.43, depth - 28), 5, "detail")
        symbol.ellipse((width * 0.79, depth - 49), 34, 34)
        symbol.line([(width * 0.36, depth - 12), (width * 0.64, depth - 12)])
    elif kind == "vanity":
        symbol.rect((0, 0, width, depth), 0, fill="cabinet")
        symbol.rect((65, 105, width - 65, depth - 65), 75, "detail", "fixture")
        symbol.rect((90, 130, width - 90, depth - 88), 58, "seam")
        symbol.ellipse((width / 2, depth * 0.59), 34, 34)
        symbol.ellipse((width / 2, 47), 26, 26)
        symbol.line([(width / 2, 47), (width / 2, 155)])
        symbol.line([(25, depth - 20), (width - 25, depth - 20)], "seam")
    elif kind == "wc":
        symbol.rect((width * 0.17, 0, width * 0.83, depth * 0.24), 38, fill="fixture")
        symbol.line([(width * 0.24, 32), (width * 0.76, 32)], "seam")
        symbol.ellipse((width / 2, depth * 0.11), 45, 28)
        symbol.rect((width * 0.29, depth * 0.19, width * 0.71, depth * 0.54), 55, "detail", "fixture")
        symbol.ellipse((width / 2, depth * 0.59), width * 0.58, depth * 0.76, "outline", "fixture")
        symbol.ellipse((width / 2, depth * 0.60), width * 0.43, depth * 0.57)
        symbol.ellipse((width / 2, depth * 0.60), width * 0.30, depth * 0.44, "seam")
    elif kind == "shower":
        symbol.rect((0, 0, width, depth), 0, "detail", "shower")
        symbol.rect((20, 20, width - 20, depth - 20), 8, "seam")
        symbol.rect((width - 150, 55, width - 80, 125), 5, "detail")
        symbol.line([(width - 140, 72), (width - 90, 72)], "seam")
        symbol.line([(width * 0.5, 25), (width * 0.5, 150)])
        symbol.ellipse((width * 0.5, 170), 100, 100)
        symbol.line([(width * 0.43, 45), (width * 0.57, 45)])
        start, end = details["opening"]
        middle = (start + end) / 2
        symbol.line([(0, depth - 18), (start, depth - 18)], "glass")
        symbol.line([(end, depth - 18), (width, depth - 18)], "glass")
        symbol.line([(start, depth - 25), (middle + 45, depth - 25)], "glass")
        symbol.line([(middle - 45, depth - 50), (end, depth - 50)], "glass")
        symbol.line([(middle + 15, depth - 25), (middle + 15, depth - 95)], "glass")
        symbol.line([(middle - 15, depth - 50), (middle - 15, depth - 120)], "glass")
    elif kind == "bathtub":
        symbol.rect((0, 0, width, depth), 100, fill="fixture")
        symbol.rect((70, 75, width - 70, depth - 75), 250, "detail")
        symbol.line([(260, 155), (260, depth - 155)], "seam")
        symbol.ellipse((width - 240, depth / 2), 48, 48)
        symbol.ellipse((width - 145, depth / 2), 25, 25, "seam")
        symbol.ellipse((width * 0.36, 36), 28, 28)
        symbol.line([(width * 0.36, 36), (width * 0.36, 155)])
    else:
        raise ValueError(kind)


def chair_symbol(width, depth, *, back_inset):
    """Keep the original +Y back geometry; query directions['front'] for facing."""
    width, depth = _positive(width, "width"), _positive(depth, "depth")
    inset = _positive(back_inset, "back_inset")
    if inset >= depth:
        raise ValueError("Back inset must be less than depth")
    symbol = Symbol(nominal_bounds=(0, 0, width, depth),
                    anchors={"origin": (0, 0), "center": (width/2, depth/2), "back": (width/2, depth)},
                    directions={"front": (0, -1), "back": (0, 1)})
    symbol.rect((0, 0, width, depth), fill="upholstery")
    symbol.segment((0, depth-inset), (width, depth-inset), "detail")
    return symbol


def desk_symbol(width, depth, *, computer=False):
    """Plain rectangular desktop, optional monitor/stand; never adds chairs."""
    width, depth = _positive(width, "width"), _positive(depth, "depth")
    if not isinstance(computer, bool):
        raise TypeError("computer must be bool")
    symbol = Symbol(nominal_bounds=(0, 0, width, depth),
                    anchors={"origin": (0, 0), "center": (width/2, depth/2)},
                    directions={"use_side": (0, 1)} if computer else None)
    symbol.rect((0, 0, width, depth), fill="table")
    if computer:
        symbol.rect((width*.22, depth*.15, width*.78, depth*.15+90), role="detail")
        symbol.segment((width*.5, depth*.15), (width*.5, depth*.5), "detail")
    return _bounded(symbol, width, depth)


def shelf_symbol(width, depth, *, divisions, axis):
    """Explicit division count and X/Y axis; no inference from aspect ratio."""
    width, depth = _positive(width, "width"), _positive(depth, "depth")
    count = _count(divisions, "divisions")
    if axis not in ("x", "y"):
        raise ValueError("axis must be x or y")
    symbol = Symbol(nominal_bounds=(0, 0, width, depth),
                    anchors={"origin": (0, 0), "center": (width/2, depth/2)})
    symbol.rect((0, 0, width, depth), fill="cabinet")
    if axis == "x":
        symbol.segment((0, depth/2), (width, depth/2), "detail")
        for index in range(1, count):
            symbol.segment((width*index/count, 0), (width*index/count, depth), "detail")
    else:
        symbol.segment((width/2, 0), (width/2, depth), "detail")
        for index in range(1, count):
            symbol.segment((0, depth*index/count), (width, depth*index/count), "detail")
    return symbol
