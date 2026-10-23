"""Editable, measured architectural diagrams from project geometry."""
from math import atan2, cos, sin
from pathlib import Path
from typing import TYPE_CHECKING

from shapely.geometry import Polygon

if TYPE_CHECKING:
    from .project import Project

PALETTE = {"interior": "#b7bca8", "courtyard": "#dfd5bc", "service": "#89998e", "water": "#b2c8c3"}


def fill_regions(canvas, regions, *, colors, transform=None, stroke=None, width=.18):
    """Add only selected polygon fills to an existing Canvas; return editable items.

    Coordinates after the optional affine transform are paper mm, Y down.
    colors maps the same local IDs to explicit colors; extra colors are ignored.
    Empty selections are allowed. No labels, statistics, classification or save.
    """
    from ._drawing import css_color, paper_width
    from .frames import transform_geometry
    from .wall_regions import _region, _regions

    regions = _regions(regions, "regions")
    stroke, width = css_color(stroke), paper_width(width)
    prepared = {}
    for key, region in regions.items():
        color = css_color(colors[key])
        if color is None:
            raise ValueError(f"Explicit fill color required for {key!r}")
        geometry = region if transform is None else transform_geometry(region, transform)
        prepared[key] = (_region(geometry, f"transformed {key!r}"), color)
    added = {}
    for key, (geometry, color) in prepared.items():
        start = len(canvas.items)
        for part in geometry.geoms if geometry.geom_type == "MultiPolygon" else [geometry]:
            canvas.poly(list(part.exterior.coords), holes=[list(r.coords) for r in part.interiors],
                        close=True, fill=color, stroke=stroke, width=width, tag=key)
        added[key] = tuple(canvas.items[start:])
    return added


def generate_diagrams(project: "Project", out: Path, level: str | None = None, *, kinds=None, formats=None):
    """Compatibility project renderer; independent geometry drawing uses fill_regions."""
    from .graphics import Canvas
    from .measurements import measure_area
    from .project import fingerprint, write_json

    kinds = ("program", "circulation", "solid-void", "areas") if kinds is None else tuple(kinds)
    if len(set(kinds)) != len(kinds) or set(kinds) - {"program", "circulation", "solid-void", "areas"}:
        raise ValueError("Unknown or repeated legacy diagram kind; use fill_regions for custom drawings")
    if not kinds:
        return {}
    level_ids = {r.get("level") for r in project.rooms}
    if len(level_ids) > 1 and level is None:
        raise ValueError("Multi-level diagrams require --level to avoid stacking floors")
    rooms = [r for r in project.rooms if level is None or r.get("level") == level]
    if not rooms:
        raise ValueError(f"No rooms for level: {level}")
    out.mkdir(parents=True, exist_ok=True)
    polygons = [Polygon(r["polygon"]) for r in rooms]
    measurements = [measure_area(poly, unit_mm=1) for poly in polygons]
    xmin, ymin = min(p.bounds[0] for p in polygons), min(p.bounds[1] for p in polygons)
    xmax, ymax = max(p.bounds[2] for p in polygons), max(p.bounds[3] for p in polygons)
    scale = max(xmax - xmin, ymax - ymin) / 135

    def point(p):
        return [17 + (p[0] - xmin) / scale, 20 + (ymax - p[1]) / scale]

    outputs = {}
    for kind, title in [("program", "01 / PROGRAM"), ("circulation", "02 / CONNECTIONS"),
                        ("solid-void", "03 / SOLID + VOID")]:
        if kind not in kinds:
            continue
        canvas = Canvas(170, 184)
        for room in rooms:
            rtype = room.get("type", "interior")
            color = room.get("diagram_color", PALETTE.get(rtype, "#c8c8bc"))
            if kind == "solid-void":
                color = "#f4f0e5" if rtype in {"courtyard", "water"} else "#586052"
            if kind == "circulation":
                color = "#eeede5" if rtype != "courtyard" else "#f8f6f0"
            fill_regions(canvas, {"region": Polygon([point(p) for p in room["polygon"]])},
                         colors={"region": color}, stroke="#ffffff", width=.7)
        if kind == "program":
            for n, room in enumerate(rooms, 1):
                centre = list(Polygon(room["polygon"]).representative_point().coords)[0]
                x, y = point(centre)
                canvas.text(x, y, f"{n:02}", size=3.2, align="center", color="#394135")
        if kind == "circulation":
            for route_spec in project.brief.get("routes", []):
                if isinstance(route_spec, dict):
                    if level is not None and route_spec.get("level") != level:
                        continue
                    route = route_spec["points"]
                else:
                    if len(level_ids) > 1:
                        raise ValueError("Multi-level circulation routes require level and points")
                    route = route_spec
                if len(route) < 2:
                    raise ValueError("Circulation route requires at least two points")
                points = [point(p) for p in route]
                canvas.poly(points, stroke="#9b7250", width=.8)
                a, b = points[-2:]
                angle = atan2(b[1] - a[1], b[0] - a[0])
                ends = [(b[0] - 3 * cos(angle - .45), b[1] - 3 * sin(angle - .45)), b,
                        (b[0] - 3 * cos(angle + .45), b[1] - 3 * sin(angle + .45))]
                canvas.poly(ends, stroke="#9b7250", width=.8)
        canvas.line(17, 163, 152, 163, stroke="#9ca38e", width=.16)
        canvas.text(17, 172, title, size=3.1, bold=True)
        captions = {"program": "Space allocation from measured polygons",
                    "circulation": "Conceptual circulation, not performance simulation",
                    "solid-void": "Enclosed rooms and open-air courts"}
        canvas.text(17, 179, captions[kind], size=1.8, color="#747c68")
        outputs[kind] = canvas.save(out / kind, formats=formats,
                                   metadata={"project_hash": fingerprint(project), "diagram": kind})
    if "areas" not in kinds:
        write_json(out / "diagrams-report.json", outputs)
        return outputs
    # Areas are actual polygon measurements, not percentages invented for the graphic.
    area_canvas = Canvas(220, max(80, 40 + len(rooms) * 12))
    area_canvas.text(15, 17, "SPACE SCHEDULE / BOUNDARY AREAS", size=4, bold=True)
    largest = max(p.area for p in polygons)
    areas = []
    for i, (room, poly, measured) in enumerate(zip(rooms, polygons, measurements)):
        y = 32 + i * 12
        area_canvas.text(15, y + 3, room.get("name", room.get("id", "")), size=2.8)
        area_canvas.rect(80, y - 1, 95 * poly.area / largest, 5,
                         fill=PALETTE.get(room.get("type", "interior"), "#c8c8bc"), stroke=None)
        area_canvas.text(202, y + 3, f"{measured['area_m2']:.1f} m²", size=2.5, align="right")
        areas.append({"id": room.get("id"), "area_m2": measured["area_m2"],
                      "basis": "Supplied room polygon; no additional deductions", "unit_mm": 1})
    outputs["areas"] = area_canvas.save(out / "areas", formats=formats,
                                       metadata={"project_hash": fingerprint(project), "areas": areas})
    write_json(out / "diagrams-report.json", outputs)
    return outputs
