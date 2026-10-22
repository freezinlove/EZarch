"""Editable architectural linework and paper-sized symbols, independent of 3D.

New drawings use world millimetres, Y up; bound drawings use explicit target
units. Pen widths, text and symbol sizes are paper millimetres. Helpers implement
a documented drawing convention, not code approval.
"""
from __future__ import annotations

import math
from functools import wraps
from pathlib import Path

import ezdxf
import yaml
from ezdxf.enums import TextEntityAlignment

from .frames import paper_transform, transform_points
from .project import skill_root, write_json

INK = "#26312e"
DEFAULT_STYLE = yaml.safe_load((skill_root() / "assets/drafting/china-conventions.yml").read_text(encoding="utf-8"))


def _draw_entities(method):
    """Return the native entities added by this call, including composed symbols."""
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        start = len(self.entities)
        method(self, *args, **kwargs)
        return tuple(self.entities[start:])
    return wrapped


class Drawing:
    def __init__(self, bounds, scale=100, title="", number="", margin=12, *,
                 style=None, font=None):
        from .graphics import Canvas

        if scale <= 0 or len(bounds) != 4 or bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
            raise ValueError("Positive scale and valid drawing bounds required")
        self.bounds, self.scale, self.margin = list(bounds), float(scale), float(margin)
        self.title, self.number = title, number
        self.style = {**DEFAULT_STYLE, **(style or {})}
        self.pens = {**DEFAULT_STYLE["pens_mm"], **(style or {}).get("pens_mm", {})}
        self.width = (bounds[2] - bounds[0]) / scale + margin * 2
        self.height = (bounds[3] - bounds[1]) / scale + margin * 2
        self.canvas = Canvas(self.width, self.height, font=font)
        self.doc = ezdxf.new("R2010")
        self.doc.units = ezdxf.units.MM
        self.doc.header["$MEASUREMENT"] = 1
        self.doc.styles.new("EZARCH", dxfattribs={"font": self.canvas.font_path.name})
        self.doc.linetypes.new("EZ-GRID", dxfattribs={"description": "Axis centre line",
                               "pattern": [16 * scale, 10 * scale, -2 * scale, 2 * scale, -2 * scale]})
        for name, pen in self.pens.items():
            self.doc.layers.new(name, dxfattribs={"color": 7, "lineweight": round(pen * 100)})
        self.ms = self.doc.modelspace()
        self.dimensions, self.symbols = [], []
        self.entities = []
        self._bound, self._unit_mm = False, 1.0
        self._layer_names = {name: name for name in self.pens}
        self._grid_name, self.text_style, self.dimstyle = "EZ-GRID", "EZARCH", "EZDXF"
        self._paper_matrix = paper_transform(bounds, scale, margin=margin)

    @classmethod
    def from_layout(cls, layout, *, scale, unit_mm, style=None,
                    text_style="Standard", dimstyle="Standard", resource_policy="rename"):
        """Bind a DXF modelspace, paperspace or block without changing it yet.

        Coordinates/radii use target units. unit_mm is mm per target unit;
        scale is the physical scale denominator (paper-sized targets use 1).
        No unit inference, Canvas, font copying, viewport changes or saving.
        Existing resource definitions are reused explicitly or left untouched
        with new names. Text/dimension styles must already exist in the doc.
        """
        from ezdxf.layouts import BaseLayout

        if not isinstance(layout, BaseLayout) or layout.doc is None:
            raise TypeError("An attached ezdxf modelspace, paperspace or block is required")
        if layout.doc.dxfversion < "AC1015":
            raise ValueError("Drawing requires DXF R2000 or newer; source was not changed")
        if not all(math.isfinite(v) and v > 0 for v in (scale, unit_mm)):
            raise ValueError("scale and unit_mm must be positive finite values")
        if resource_policy not in {"rename", "reuse"}:
            raise ValueError("resource_policy must be rename or reuse")
        if text_style not in layout.doc.styles or dimstyle not in layout.doc.dimstyles:
            raise ValueError("text_style and dimstyle must exist in the target document")
        self = cls.__new__(cls)
        self.doc, self.ms, self.canvas = layout.doc, layout, None
        self.scale, self._unit_mm = float(scale / unit_mm), float(unit_mm)
        if not math.isfinite(self.scale) or self.scale <= 0:
            raise ValueError("scale / unit_mm must be positive and finite")
        self.style = {**DEFAULT_STYLE, **(style or {})}
        self.pens = {**DEFAULT_STYLE["pens_mm"], **(style or {}).get("pens_mm", {})}
        self.text_style, self.dimstyle = text_style, dimstyle
        self.resource_policy, self._bound = resource_policy, True
        self._layer_names, self._grid_name = {}, None
        self.entities, self.dimensions, self.symbols = [], [], []
        return self

    def _resource_name(self, table, name):
        if name not in table or self.resource_policy == "reuse":
            return name
        index = 1
        while f"{name}-EZARCH-{index}" in table:
            index += 1
        return f"{name}-EZARCH-{index}"

    def _layer(self, role):
        if not self._bound:
            return role
        if role not in self._layer_names:
            name = self._resource_name(self.doc.layers, role)
            if name not in self.doc.layers:
                self.doc.layers.new(name, dxfattribs={
                    "color": 7, "lineweight": round(self.pens.get(role, .18) * 100)})
            self._layer_names[role] = name
        return self._layer_names[role]

    def _grid(self):
        if self._grid_name is None:
            name = self._resource_name(self.doc.linetypes, "EZ-GRID")
            if name not in self.doc.linetypes:
                s = self.scale
                self.doc.linetypes.new(name, dxfattribs={"description": "Axis centre line",
                    "pattern": [16*s, 10*s, -2*s, 2*s, -2*s]})
            self._grid_name = name
        return self._grid_name

    def paper(self, p):
        if self._bound:
            raise ValueError("Bound drawings have no paper projection; use frames explicitly")
        return list(transform_points([p], self._paper_matrix)[0])

    @_draw_entities
    def poly(self, points, layer="A-VISIBLE", close=False, fill=None, color=INK, width=None, dash=None):
        points = [list(p) for p in points]
        if len(points) < 2:
            return
        if self.canvas is not None:
            self.canvas.poly([self.paper(p) for p in points], close=close, fill=fill,
                             stroke=color, width=width if width is not None else self.pens[layer], dash=dash)
        attrs = {"layer": self._layer(layer)}
        if dash:
            attrs["linetype"] = self._grid()
        self.entities.append(self.ms.add_lwpolyline(points, close=close, dxfattribs=attrs))
        if fill and close:
            hatch = self.ms.add_hatch(color=7, dxfattribs={"layer": self._layer(layer)})
            hatch.paths.add_polyline_path(points, is_closed=True)
            self.entities.append(hatch)

    @_draw_entities
    def line(self, a, b, **kw):
        self.poly([a, b], **kw)

    @_draw_entities
    def rect(self, x, y, w, h, **kw):
        self.poly([[x, y], [x + w, y], [x + w, y + h], [x, y + h]], close=True, **kw)

    @_draw_entities
    def circle(self, centre, radius, layer="A-ANNOTATION", color=INK, width=None):
        if self.canvas is not None:
            x, y = self.paper(centre)
            self.canvas.circle(x, y, radius / self.scale, stroke=color, width=width or self.pens[layer])
        self.entities.append(self.ms.add_circle(centre, radius, dxfattribs={"layer": self._layer(layer)}))

    @_draw_entities
    def text(self, point, text, size=2.5, align="center", color=INK, rotation=0, layer="A-ANNOTATION"):
        if self.canvas is not None:
            x, y = self.paper(point)
            self.canvas.text(x, y + (size * .32 if not rotation else 0), text, size=size,
                             align=align, color=color, rotation=rotation)
        alignment = {"left": TextEntityAlignment.MIDDLE_LEFT, "center": TextEntityAlignment.MIDDLE_CENTER,
                     "right": TextEntityAlignment.MIDDLE_RIGHT}[align]
        entity = self.ms.add_text(str(text), dxfattribs={"height": size * self.scale, "style": self.text_style,
                         "layer": self._layer(layer), "rotation": rotation})
        entity.set_placement(point, align=alignment)
        self.entities.append(entity)

    @_draw_entities
    def axis(self, name, orientation, at, start, end, bubbles="both"):
        if str(name) in self.style["excluded_axis_labels"]:
            raise ValueError("I, O and Z are not used as Chinese drawing grid labels")
        s = self.scale
        if orientation == "x":  # constant x, vertical line
            a, b = [at, start], [at, end]
        elif orientation == "y":
            a, b = [start, at], [end, at]
        else:
            raise ValueError("Axis orientation x or y required")
        self.line(a, b, layer="A-GRID", color="#929996", dash=[10, 2, 2, 2])
        for p, end_name in [(a, "start"), (b, "end")]:
            if bubbles in ("both", end_name):
                self.circle(p, self.style["axis_circle_diameter_mm"] / 2 * s)
                self.text(p, name, 3.5)
        self.symbols.append({"kind": "axis", "name": name, "orientation": orientation,
                             "at_mm": at * self._unit_mm})

    @_draw_entities
    def dimension(self, a, b, base, text_size=2.5):
        s = self.scale
        if abs(a[1] - b[1]) * self._unit_mm < .001:
            angle, aa, bb = 0, [a[0], base[1]], [b[0], base[1]]
            text_at, rot = [(a[0] + b[0]) / 2, base[1] + 1.8 * s], 0
        elif abs(a[0] - b[0]) * self._unit_mm < .001:
            angle, aa, bb = 90, [base[0], a[1]], [base[0], b[1]]
            text_at, rot = [base[0] - 1.8 * s, (a[1] + b[1]) / 2], 90
        else:
            raise ValueError("Use ezdxf adapter for non-orthogonal dimensions")
        if self.canvas is not None:
            self._canvas_dimension(a, b, aa, bb, text_at, rot, text_size)
        overrides = {
            "dimtxt": text_size * s, "dimasz": 2 * s, "dimexo": 2 * s,
            "dimexe": 2 * s, "dimdec": 0, "dimtad": 1, "dimblk": "ARCHTICK", "dimtxsty": self.text_style,
            "dimlfac": self._unit_mm}
        if self._bound:
            # DXF scales all style lengths, including inherited text gaps. Keep
            # these values in paper mm so target units do not distort placement.
            overrides.update(dimtxt=text_size, dimasz=2, dimexo=2, dimexe=2, dimscale=s)
        dimension = self.ms.add_linear_dim(base=base, p1=a, p2=b, angle=angle, dimstyle=self.dimstyle,
            override=overrides, dxfattribs={"layer": self._layer("A-DIM")})
        dimension.render()
        self.entities.append(dimension.dimension)
        self.dimensions.append({"p1": a, "p2": b, "base": base,
                                "measured_mm": math.dist(a, b) * self._unit_mm})

    def _canvas_dimension(self, a, b, aa, bb, text_at, rot, text_size):
        s = self.scale
        for p, q in [(a, aa), (b, bb)]:
            v = [q[i] - p[i] for i in range(2)]
            length = math.hypot(*v)
            if length:
                unit = [c / length for c in v]
                self.canvas.poly([self.paper([p[i] + unit[i] * 2 * s for i in range(2)]),
                                  self.paper([q[i] + unit[i] * 2 * s for i in range(2)])], width=.13)
        self.canvas.poly([self.paper(aa), self.paper(bb)], width=.13)
        for p in [aa, bb]:
            self.canvas.poly([self.paper([p[0] - s, p[1] - s]), self.paper([p[0] + s, p[1] + s])], width=.25)
        value = math.dist(a, b)
        x, y = self.paper(text_at)
        self.canvas.text(x, y, f"{value:.0f}", size=text_size, align="center", rotation=rot)

    @_draw_entities
    def chain(self, values, fixed, base, orientation="x"):
        for a, b in zip(values, values[1:]):
            if orientation == "x":
                self.dimension([a, fixed], [b, fixed], [0, base])
            elif orientation == "y":
                self.dimension([fixed, a], [fixed, b], [base, 0])
            else:
                raise ValueError("Chain orientation x or y required")

    @_draw_entities
    def level(self, point, value_mm, size=3, label=None):
        x, y = point
        u = size * self.scale
        self.poly([[x, y], [x - u, y + u], [x + u, y + u]], close=True, layer="A-ANNOTATION")
        self.line([x - u, y + u], [x + 5 * u, y + u], layer="A-ANNOTATION")
        value = label or ("±0.000" if abs(value_mm) < .001 else f"{value_mm / 1000:.3f}")
        self.text([x + 2 * u, y + u + 1.8 * self.scale], value, 2.5)
        self.symbols.append({"kind": "level", "value_mm": value_mm, "at": point})

    @_draw_entities
    def north(self, point, angle=0):
        s = self.scale
        a = math.radians(angle)
        def p(x, y):
            return [point[0] + s * (x * math.cos(a) - y * math.sin(a)),
                    point[1] + s * (x * math.sin(a) + y * math.cos(a))]
        factor = self.style["north_circle_diameter_mm"] / 24
        self.circle(point, 12 * factor * s)
        self.poly([p(0, 12 * factor), p(-1.5 * factor, -9 * factor), p(0, -6 * factor)], close=True, fill=INK, layer="A-ANNOTATION")
        self.poly([p(0, 12 * factor), p(1.5 * factor, -9 * factor), p(0, -6 * factor)], close=True, layer="A-ANNOTATION")
        self.text(p(0, 16 * factor), "N", 3.5)
        self.symbols.append({"kind": "north", "angle": angle})

    @_draw_entities
    def section_mark(self, a, b, name, direction=1):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        if length <= 0:
            raise ValueError("Section endpoints must differ")
        t, n, s = [dx / length, dy / length], [-dy / length * direction, dx / length * direction], self.scale
        for p, sign in [(a, 1), (b, -1)]:
            self.line(p, [p[i] + t[i] * sign * self.style["section_position_length_mm"] * s for i in range(2)], layer="A-CUT")
            self.line(p, [p[i] + n[i] * self.style["section_direction_length_mm"] * s for i in range(2)], layer="A-CUT")
            self.text([p[i] + n[i] * 8 * s for i in range(2)], name, 3.5)
        self.symbols.append({"kind": "section", "name": name, "a": a, "b": b, "direction": direction})

    @_draw_entities
    def index(self, point, detail, sheet, radius=None):
        x, y = point
        radius = self.style["index_circle_diameter_mm"] / 2 if radius is None else radius
        r = radius * self.scale
        self.circle(point, r)
        self.line([x - r, y], [x + r, y], layer="A-ANNOTATION")
        self.text([x, y + r * .45], detail, 2.5)
        self.text([x, y - r * .45], sheet, 2.5)
        self.symbols.append({"kind": "index", "detail": detail, "sheet": sheet})

    @_draw_entities
    def leader(self, points, text, size=3):
        self.poly(points, layer="A-ANNOTATION")
        self.circle(points[0], .5 * self.scale, width=.2)
        self.text([points[-1][0], points[-1][1] + 1.8 * self.scale], text, size, align="left")

    @_draw_entities
    def furniture(self, kind, origin, size, rotation=0):
        """Ordinary simplified symbols, NOT prescribed national-standard furniture."""
        w, d = size
        if min(w, d) <= 0:
            raise ValueError("Furniture footprint must be positive")
        a = math.radians(rotation)
        def world(p):
            return [origin[0] + p[0] * math.cos(a) - p[1] * math.sin(a),
                    origin[1] + p[0] * math.sin(a) + p[1] * math.cos(a)]
        def line(pts, close=False):
            self.poly([world(p) for p in pts], layer="A-FURNITURE", close=close)
        def rect(x, y, ww, dd):
            line([[x, y], [x + ww, y], [x + ww, y + dd], [x, y + dd]], True)
        rect(0, 0, w, d)
        if kind in {"chair", "sofa"}:
            rect(w * .07, d * .07, w * .86, d * .67)
            line([[0, d * .8], [w, d * .8]])
            if kind == "sofa":
                for f in (1/3, 2/3):
                    line([[w * f, d * .08], [w * f, d * .74]])
        elif kind == "bed":
            rect(w * .07, d * .7, w * .38, d * .22)
            rect(w * .55, d * .7, w * .38, d * .22)
            line([[0, d * .62], [w, d * .62]])
        elif kind in {"cabinet", "shelf"}:
            for i in range(1, max(2, round(w * self._unit_mm / 600))):
                f = i / max(2, round(w * self._unit_mm / 600))
                line([[w * f, 0], [w * f, d]])
        elif kind in {"sink", "wc"}:
            line([[w * (.5 + .32 * math.cos(t)), d * (.5 + .36 * math.sin(t))]
                  for t in [i * math.tau / 48 for i in range(48)]], True)
            if kind == "wc":
                rect(w * .08, d * .77, w * .84, d * .2)
        elif kind == "shower":
            line([[0, 0], [w, d]])
            line([[w, 0], [0, d]])
        elif kind not in {"table", "counter", "equipment"}:
            raise ValueError(f"Unknown furniture symbol {kind}; add a project-local custom symbol")
        self.symbols.append({"kind": "furniture", "type": kind, "origin": origin,
                             "size": size, "rotation": rotation})

    def save(self, stem: Path, dpi=150, metadata=None, formats=None):
        import shutil
        if self._bound:
            raise ValueError("Bound Drawing does not export: save the full document with doc.saveas()")
        formats = set(["dxf", "svg", "pdf", "png"] if formats is None else formats)
        if not formats or formats - {"dxf", "svg", "pdf", "png"}:
            raise ValueError("Drawing formats: dxf, svg, pdf, png")
        if "dxf" in formats and not self.canvas.custom_font:
            font_dir = stem.parent / "fonts"
            font_dir.mkdir(parents=True, exist_ok=True)
            for filename in ["EZarchFang.ttf", "COPYING", "SOURCE.md"]:
                shutil.copy2(skill_root() / "assets/fonts" / filename, font_dir / filename)
        original_items = list(self.canvas.items)
        meta = {**(metadata or {}), "title": self.title, "scale": self.scale,
                "dimensions": self.dimensions, "symbols": self.symbols,
                "formats": sorted(formats)}
        try:
            report = self.canvas.save(stem, dpi=dpi, metadata=meta, formats=formats - {"dxf"})
        finally:
            self.canvas.items = original_items
        if "dxf" in formats:
            if self.doc.audit().has_errors:
                raise ValueError("Invalid DXF")
            self.doc.set_modelspace_vport(height=self.bounds[3] - self.bounds[1],
                center=((self.bounds[0] + self.bounds[2]) / 2, (self.bounds[1] + self.bounds[3]) / 2))
            self.doc.saveas(stem.with_suffix(".dxf"))
        write_json(stem.with_suffix(".draft.json"), meta)
        return report
