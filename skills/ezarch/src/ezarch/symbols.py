"""Editable local-mm component geometry, independent appearance and placement.

No wall cutting, labels, room model, arrangement or file export is implicit.
Native curves are retained. Nominal bounds describe dimensions, not occupied area.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import ezdxf
from ezdxf import bbox
from ezdxf.lldxf.const import VALID_DXF_LINEWEIGHTS
from ezdxf.math import Matrix44

from ._drawing import css_color, paper_width
from .frames import _finite, transform_points


def _positive(value, name):
    value, = _finite((value,), 1, name)
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


@dataclass
class Part:
    entity: object
    role: str
    fill: bool = False


@dataclass
class SymbolStyle:
    """Stroke roles map to (RGB color, paper mm); fill roles map to RGB color.

    Empty fills omits all filled faces. Missing stroke roles are errors.
    Nonempty fill mappings must cover every used fill role.
    """
    strokes: dict
    fills: dict


def color_style():
    """Editable palette extracted from the residential furniture presentation."""
    return SymbolStyle(
        {"outline": ("#68706d", .18), "detail": ("#979b94", .09),
         "seam": ("#bbbbb1", .05), "glass": ("#739da5", .13)},
        {"plain": "#fcfbf6", "cabinet": "#e3dfd1", "table": "#f0ebde",
         "upholstery": "#efede3", "upholstery_dark": "#dbddd2", "bedding": "#e8eae0",
         "fixture": "#fcfdfa", "metal": "#889996", "shower": "#f2f8f6"},
    )


def linework_style(*, outline_mm=.18, detail_mm=.09, seam_mm=.05, glass_mm=.13):
    """True black contours, with no HATCH or grey face; widths are paper mm."""
    return SymbolStyle({role: ("#000000", width) for role, width in
                        (("outline", outline_mm), ("detail", detail_mm),
                         ("seam", seam_mm), ("glass", glass_mm))}, {})


class Symbol:
    """A small editable geometry resource, not a required project representation.

    Parts contain detached native ezdxf entities in local mm. Anchors and nominal
    bounds are construction metadata: arbitrary later edits do not update them.
    Builder methods and add() can also be used independently of supplied factories.
    """

    def __init__(self, *, nominal_bounds=None, anchors=None):
        self.parts = []
        self.anchors = dict(anchors or {})
        self.nominal_bounds = (None if nominal_bounds is None else
                               _finite(nominal_bounds, 4, "nominal_bounds"))
        self._layout = ezdxf.new("R2010").modelspace()

    def add(self, entity, role="detail", *, fill=False):
        """Copy one planar primitive; no blocks, text, external resources or inserts.

        Caller-provided primitives must be finite XY geometry in local mm.
        HATCH is accepted as a solid fill only; stroke primitives retain curves.
        """
        if entity.dxftype() not in {"LINE", "LWPOLYLINE", "ARC", "CIRCLE", "ELLIPSE", "HATCH"}:
            raise ValueError("Expected LINE/LWPOLYLINE/ARC/CIRCLE/ELLIPSE or solid HATCH")
        if (entity.dxftype() == "HATCH") != bool(fill):
            raise ValueError("Only HATCH parts use fill=True")
        if fill and not entity.dxf.solid_fill:
            raise ValueError("Only solid HATCH is supported")
        copied = entity.copy()
        self.parts.append(Part(copied, role, bool(fill)))
        return copied

    def path(self, points, role="detail", closed=False, fill=None):
        vertices = []
        for point in points:
            values = tuple(point)
            if len(values) not in (2, 3):
                raise ValueError("Path vertices require x, y, optional bulge")
            vertices.append(_finite((*values, 0) if len(values) == 2 else values, 3, "vertex"))
        if len(vertices) < (3 if closed or fill else 2):
            raise ValueError("Insufficient path vertices")
        if fill:
            if not closed:
                raise ValueError("Filled paths must be closed")
            hatch = self._layout.add_hatch()
            hatch.paths.add_polyline_path(vertices, is_closed=True)
            self.add(hatch, fill, fill=True)
            self._layout.delete_entity(hatch)
        if role:
            entity = self._layout.add_lwpolyline(vertices, format="xyb", close=closed)
            result = self.add(entity, role)
            self._layout.delete_entity(entity)
            return result

    def rect(self, bounds, radius=0, role="outline", fill=None):
        left, bottom, right, top = _finite(bounds, 4, "rectangle")
        if right <= left or top <= bottom:
            raise ValueError(f"Detail rectangle does not fit: {bounds}")
        radius, = _finite((radius,), 1, "radius")
        if radius < 0:
            raise ValueError("radius must be nonnegative")
        radius = min(radius, (right-left)/2, (top-bottom)/2)
        if radius:
            bulge = math.tan(math.pi/8)
            points = [(left+radius, bottom), (right-radius, bottom, bulge),
                      (right, bottom+radius), (right, top-radius, bulge),
                      (right-radius, top), (left+radius, top, bulge),
                      (left, top-radius), (left, bottom+radius, bulge)]
        else:
            points = [(left, bottom), (right, bottom), (right, top), (left, top)]
        return self.path(points, role, True, fill)

    def line(self, points, role="detail"):
        return self.path(points, role)

    def segment(self, start, end, role="outline"):
        start, end = _finite(start, 2, "start"), _finite(end, 2, "end")
        entity = self._layout.add_line(start, end)
        result = self.add(entity, role)
        self._layout.delete_entity(entity)
        return result

    def ellipse(self, center, width, depth, role="detail", fill=None):
        center = _finite(center, 2, "center")
        width, depth = _positive(width, "ellipse width"), _positive(depth, "ellipse depth")
        major, ratio = ((width/2, 0), depth/width) if width >= depth else ((0, depth/2), width/depth)
        if fill:
            hatch = self._layout.add_hatch()
            hatch.paths.add_edge_path().add_ellipse(center, major, ratio)
            self.add(hatch, fill, fill=True)
            self._layout.delete_entity(hatch)
        if abs(width-depth) < 1e-7:
            entity = self._layout.add_circle(center, width/2)
        else:
            entity = self._layout.add_ellipse(center, major, ratio)
        result = self.add(entity, role)
        self._layout.delete_entity(entity)
        return result

    def geometry_bounds(self):
        """Native curve bounds via ezdxf; ellipse bounds use its Bezier approximation."""
        extent = bbox.extents([part.entity for part in self.parts if not part.fill], fast=False)
        if not extent.has_data:
            return None
        return extent.extmin.x, extent.extmin.y, extent.extmax.x, extent.extmax.y


@dataclass
class Placement:
    entities: tuple
    anchors: dict
    nominal_envelope: tuple | None
    transform: tuple


def place_symbol(symbol, layout, *, style, unit_mm, origin=(0, 0), rotation_deg=0,
                 mirror_x=False, layer="0"):
    """Copy local-mm geometry to an existing R2004+ layout/block, without exporting.

    origin is in target units; unit_mm is mm per target unit. Mirror negates local
    X before counterclockwise rotation. No nonuniform stretch or layout inference.
    Existing layer definitions are reused unchanged, including visibility state.
    """
    if layout.doc is None or layout.doc.dxfversion < "AC1018":
        raise ValueError("RGB component placement requires an attached R2004+ layout")
    if layer not in layout.doc.layers:
        raise ValueError("Target layer must already exist; no source resources are overwritten")
    unit_mm = _positive(unit_mm, "unit_mm")
    ox, oy = _finite(origin, 2, "origin")
    angle, = _finite((rotation_deg,), 1, "rotation_deg")
    if not isinstance(mirror_x, bool):
        raise TypeError("mirror_x must be bool")
    c, s = math.cos(math.radians(angle))/unit_mm, math.sin(math.radians(angle))/unit_mm
    sign = -1 if mirror_x else 1
    transform = (sign*c, -s, sign*s, c, ox, oy)
    a, b, d, e, _, _ = transform
    matrix = Matrix44([a, d, 0, 0, b, e, 0, 0, 0, 0, 1/unit_mm, 0, ox, oy, 0, 1])
    anchors = {key: transform_points([point], transform)[0] for key, point in symbol.anchors.items()}
    envelope = None
    if symbol.nominal_bounds is not None:
        left, bottom, right, top = symbol.nominal_bounds
        envelope = tuple(transform_points([(left, bottom), (right, bottom),
                                           (right, top), (left, top)], transform))
    # Complete validation/copy/transform before attaching anything to the target.
    entities = []
    for part in symbol.parts:
        if part.fill and not style.fills:
            continue
        if part.fill:
            color, width = style.fills[part.role], 0
        else:
            color, width = style.strokes[part.role]
        color = css_color(color)
        if color is None:
            raise ValueError("Component roles require RGB; omit fills with an empty fills mapping")
        width = paper_width(width)
        weight = round(width*100)
        if weight not in VALID_DXF_LINEWEIGHTS or not math.isclose(weight/100, width, abs_tol=1e-9):
            raise ValueError(f"Unsupported DXF paper line width: {width} mm")
        entity = part.entity.copy()
        entity.transform(matrix)
        entity.dxf.layer = layer
        entity.dxf.color = 7
        entity.dxf.true_color = int(color[1:], 16)
        entity.dxf.lineweight = weight
        entity.dxf.linetype = "CONTINUOUS"
        entity.dxf.discard("transparency")
        entities.append(entity)
    for entity in entities:
        layout.add_entity(entity)
    return Placement(tuple(entities), anchors, envelope, transform)


def door_symbol(width, *, leaf_thickness, frame_width, frame_depth, opening_angle_deg=90,
                frame=True, leaf=True, swing=True):
    """Single leaf; hinge=(0,0), closed end=(width,0); width is not clear passage.

    Frame rectangles are centered on both ends. No opening is cut in a wall.
    Frame/leaf/arc can be requested independently. Negative angle opens clockwise.
    """
    width = _positive(width, "width")
    thickness = _positive(leaf_thickness, "leaf_thickness")
    fw, fd = _positive(frame_width, "frame_width"), _positive(frame_depth, "frame_depth")
    angle, = _finite((opening_angle_deg,), 1, "opening_angle_deg")
    if not -180 <= angle <= 180:
        raise ValueError("opening_angle_deg must be between -180 and 180")
    tip = (width*math.cos(math.radians(angle)), width*math.sin(math.radians(angle)))
    symbol = Symbol(nominal_bounds=(0, -fd/2, width, fd/2),
                    anchors={"hinge": (0, 0), "closed_end": (width, 0), "leaf_end": tip})
    if frame:
        for x in (0, width):
            symbol.rect((x-fw/2, -fd/2, x+fw/2, fd/2))
    if leaf:
        entity = symbol.rect((0, -thickness/2, width, thickness/2))
        entity.transform(Matrix44.z_rotate(math.radians(angle)))
    if swing and angle:
        entity = symbol._layout.add_arc((0, 0), width, min(0, angle), max(0, angle))
        symbol.add(entity, "detail")
        symbol._layout.delete_entity(entity)
    return symbol


def window_symbol(length, *, frame_depth, end_inset, rail_inset, mullions=(),
                  mullion_width=0, inner_offsets=(), sill_offsets=()):
    """Linear frame resource: local X along opening, Y across wall, centered at Y=0.

    Explicit mullion stations; no length-to-division rule or wall-thickness guess.
    Sills extend full length; frame rails use rail_inset, end returns use end_inset.
    """
    length, depth = _positive(length, "length"), _positive(frame_depth, "frame_depth")
    end, rail, mw = _finite((end_inset, rail_inset, mullion_width), 3, "window details")
    stations = tuple(_finite((x,), 1, "mullion station")[0] for x in mullions)
    inner = tuple(_finite((y,), 1, "inner offset")[0] for y in inner_offsets)
    sills = tuple(_finite((y,), 1, "sill offset")[0] for y in sill_offsets)
    if not (0 <= end < length/2 and 0 <= rail < length/2 and mw >= 0):
        raise ValueError("Window insets or mullion width do not fit length")
    if stations and (mw <= 0 or any(not end < x-mw/2 < x+mw/2 < length-end for x in stations)):
        raise ValueError("Mullion pairs must fit strictly between end returns")
    if len(set(stations)) != len(stations) or any(b-a <= mw for a, b in zip(sorted(stations), sorted(stations)[1:])):
        raise ValueError("Mullions overlap or repeat")
    if any(abs(y) >= depth/2 for y in inner) or len(set(inner)) != len(inner):
        raise ValueError("Inner rails must be distinct and inside frame depth")
    symbol = Symbol(nominal_bounds=(0, -depth/2, length, depth/2),
                    anchors={"start": (0, 0), "end": (length, 0), "center": (length/2, 0)})
    for y in sills:
        symbol.segment((0, y), (length, y), "detail")
    for y in (-depth/2, depth/2, *inner):
        symbol.segment((rail, y), (length-rail, y))
    for x in (end, length-end):
        symbol.segment((x, -depth/2), (x, depth/2))
    for x in stations:
        for edge in (x-mw/2, x+mw/2):
            symbol.segment((edge, -depth/2), (edge, depth/2))
    return symbol
