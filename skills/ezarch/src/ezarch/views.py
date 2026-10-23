"""True solid sections and OCCT hidden-line projections, with architectural annotation."""
from __future__ import annotations

from math import atan2, cos, degrees, hypot, pi, sin
from pathlib import Path

import numpy as np

from .geometry import Part, box, build
from .graphics import Canvas
from .project import Project, fingerprint, skill_root, write_json


def edge_points(edge, tolerance=.5):
    if edge.geomType() == "LINE":
        return [edge.startPoint().toTuple(), edge.endPoint().toTuple()]
    return [v.toTuple() for v in edge.sample(float(tolerance))[0]]


def wire_points(wire):
    segments = [edge_points(e) for e in wire.Edges()]
    if not segments:
        return []
    result = segments.pop(0)
    while segments:
        found = False
        for i, pts in enumerate(segments):
            if np.linalg.norm(np.array(result[-1]) - pts[0]) < 0.01:
                result.extend(pts[1:])
            elif np.linalg.norm(np.array(result[-1]) - pts[-1]) < 0.01:
                result.extend(list(reversed(pts))[1:])
            else:
                continue
            segments.pop(i)
            found = True
            break
        if not found:
            raise ValueError("Section wire cannot be ordered without a geometry gap")
    return result


def projection_lines(shapes, normal, xdir, origin=(0, 0, 0)):
    import cadquery as cq
    from OCP.BRepLib import BRepLib
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
    from OCP.HLRAlgo import HLRAlgo_Projector
    from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape
    if not shapes:
        return []
    algo = HLRBRep_Algo()
    for shape in shapes:
        algo.Add(shape.wrapped)
    algo.Projector(HLRAlgo_Projector(gp_Ax2(gp_Pnt(*origin), gp_Dir(*normal), gp_Dir(*xdir))))
    algo.Update()
    algo.Hide()
    extracted = HLRBRep_HLRToShape(algo)
    paths, seen = [], set()
    for compound in [extracted.VCompound(), extracted.OutLineVCompound(), extracted.Rg1LineVCompound()]:
        if compound.IsNull():
            continue
        BRepLib.BuildCurves3d_s(compound, 1e-7)
        for edge in cq.Shape.cast(compound).Edges():
            pts = [[float(v[0]), float(v[1])] for v in edge_points(edge)]
            if len(pts) < 2:
                continue
            forward = tuple(tuple(round(c, 3) for c in p) for p in pts)
            key = min(forward, forward[::-1])
            if key not in seen:
                seen.add(key)
                paths.append(pts)
    return paths


def extract_view(parts: list[Part], view: dict):
    import cadquery as cq
    kind = view.get("kind", "plan")
    exclude = set(view.get("exclude", ["site", "water", "landscape"]))
    selected = [p for p in parts if p.category not in exclude and not (kind == "plan" and p.category == "door")]
    selected = [p for p in selected if p.id not in view.get("exclude_ids", [])]
    inf = 1e6
    if kind == "plan":
        at = float(view.get("cut_z", 1200))
        normal, xdir, origin = (0, 0, 1), (1, 0, 0), (0, 0, at)
        bottom = float(view.get("floor_z", -inf))
        if bottom >= at:
            raise ValueError("Plan floor_z must be below cut_z")
        clip = box((-inf, -inf, bottom), (2 * inf, 2 * inf, at - bottom))
    elif kind == "section":
        at = float(view.get("at", 0))
        axis = view.get("axis", "y")
        if axis == "y":
            normal, xdir, origin = (0, -1, 0), (1, 0, 0), (0, at, 0)
            clip = box((-inf, at, -inf), (2 * inf, inf, 2 * inf))
        elif axis == "x":
            normal, xdir, origin = (1, 0, 0), (0, 1, 0), (at, 0, 0)
            clip = box((-inf, -inf, -inf), (inf + at, 2 * inf, 2 * inf))
        else:
            raise ValueError("Section axis must be x or y")
    elif kind in ("elevation", "axon"):
        normal = tuple(view.get("normal", (0, -1, 0) if kind == "elevation" else (1, -1, 1)))
        xdir = tuple(view.get("xdir", (1, 0, 0) if kind == "elevation" else (1, 1, 0)))
        origin, clip = (0, 0, 0), None
    else:
        raise ValueError(f"Unsupported view kind {kind}")
    n = np.array(normal, dtype=float)
    n /= np.linalg.norm(n)
    x = np.array(xdir, dtype=float)
    x -= n * np.dot(x, n)
    x /= np.linalg.norm(x)
    y = np.cross(n, x)

    def project(point):
        p = np.asarray(point) - origin
        return [float(np.dot(p, x)), float(np.dot(p, y))]

    solids, cuts = [], []
    plane = cq.Face.makePlane(basePnt=origin, dir=normal) if clip else None
    for part in selected:
        shaped = part.shape.intersect(clip) if clip else part.shape
        if shaped.Volume() > .001:
            solids.append(shaped)
        if plane is not None and part.category not in {"glass", "furniture", "finish"}:
            section = part.shape.intersect(plane)
            for face in section.Faces():
                cuts.append({"id": part.id, "category": part.category,
                             "outer": [project(v) for v in wire_points(face.outerWire())],
                             "holes": [[project(v) for v in wire_points(w)] for w in face.innerWires()],
                             "area_mm2": face.Area()})
    # Conventional sections suppress projected geometry behind earth below datum;
    # genuine cut foundations/basins remain in `cuts`. Set null for basement views.
    projection_min_z = view.get("projection_min_z", 0 if kind in {"section", "elevation"} else None)
    if projection_min_z is not None:
        above = box((-inf, -inf, projection_min_z), (2 * inf, 2 * inf, inf))
        solids = [s.intersect(above) for s in solids]
        solids = [s for s in solids if s.Volume() > .001]
    return {"kind": kind, "lines": projection_lines(solids, normal, xdir, origin), "cuts": cuts,
            "normal": normal, "xdir": x.tolist(), "up": y.tolist(), "origin": origin}


def save_view(project: Project, data: dict, view: dict, stem: Path, formats=None):
    formats = set(["dxf", "pdf", "svg", "png"] if formats is None else formats)
    view = dict(view)
    if view.get("font"):
        view["font"] = str(project._base_dir / view["font"])
    if view.get("drafting") is not None:
        return save_annotated_view(project, data, view, stem, formats)
    import ezdxf
    from ezdxf.enums import TextEntityAlignment
    all_points = [p for line in data["lines"] for p in line] + [p for c in data["cuts"] for p in c["outer"]]
    if not all_points:
        raise ValueError(f"Empty view {view['id']}")
    xs, ys = zip(*all_points)
    minx, miny, maxx, maxy = min(xs), min(ys), max(xs), max(ys)
    scale = float(view.get("scale", 100))
    margin = float(view.get("margin", 22))
    width, height = (maxx - minx) / scale + 2 * margin, (maxy - miny) / scale + 2 * margin
    if view.get("paper_mm"):
        width, height = view["paper_mm"]
        if (maxx - minx) / scale + 2 * margin > width or (maxy - miny) / scale + 2 * margin > height:
            raise ValueError("Requested scale does not fit the paper; never silently shrink a scaled drawing")
    canvas = Canvas(width, height, font=view.get("font"))
    ox = (width - (maxx - minx) / scale) / 2
    oy = margin

    def paper(point):
        return [ox + (point[0] - minx) / scale, oy + (maxy - point[1]) / scale]

    doc = ezdxf.new("R2010")
    doc.units = ezdxf.units.MM
    doc.header["$INSUNITS"] = 4
    doc.header["$MEASUREMENT"] = 1
    for name, lw in [("A-VISIBLE", 18), ("A-CUT", 40), ("A-ANNOTATION", 13),
                     ("A-DIM", 13), ("A-FURNITURE", 13), ("A-LANDSCAPE", 13)]:
        doc.layers.new(name, dxfattribs={"color": 7, "lineweight": lw})
    doc.styles.new("EZARCH", dxfattribs={"font": canvas.font_path.name})
    ms = doc.modelspace()

    def path(points, layer="A-VISIBLE", weight=.14, color="#52564f", close=False, fill=None):
        if len(points) < 2:
            return
        canvas.poly([paper(p) for p in points], stroke=color, width=weight, close=close, fill=fill)
        ms.add_lwpolyline(points, close=close, dxfattribs={"layer": layer})

    def label(point, text, size=2.5, color="#656a62", rotation=0):
        px, py = paper(point)
        canvas.text(px, py, text, size=size, align="center", color=color, rotation=rotation)
        ms.add_text(str(text), dxfattribs={"height": size * scale, "style": "EZARCH", "layer": "A-ANNOTATION", "rotation": rotation}).set_placement(point, align=TextEntityAlignment.MIDDLE_CENTER)

    if data["kind"] == "plan":
        for room in project.rooms:
            if room.get("level") != view.get("level"):
                continue
            polygon = room["polygon"]
            canvas.poly([paper(p) for p in polygon], close=True, fill=room.get("fill", "#f7f6f1"), stroke=None)
            spacing = room.get("grid_mm")
            if spacing:
                from shapely.geometry import LineString, Polygon
                area = Polygon(polygon)
                bx0, by0, bx1, by1 = area.bounds
                for axis, start, end in [(0, bx0, bx1), (1, by0, by1)]:
                    value = start + spacing
                    while value < end:
                        line = LineString([(value, by0), (value, by1)] if axis == 0 else [(bx0, value), (bx1, value)])
                        clipped = line.intersection(area)
                        for segment in getattr(clipped, "geoms", [clipped]):
                            if segment.geom_type == "LineString":
                                path(list(segment.coords), "A-FURNITURE", .045, "#d5d3c8")
                        value += spacing
        for tree in project.landscape:
            if view.get("floor_z", 0) > 0:
                continue
            if tree.get("kind") != "tree":
                continue
            cx, cy = tree["position"][:2]
            radius = tree.get("crown_radius", 1200)
            points = []
            for i in range(96):
                a = i * 2 * pi / 96
                r = radius * (1 + .07 * sin(a * 13) + .04 * cos(a * 21))
                points.append([cx + r * cos(a), cy + r * sin(a)])
            path(points, "A-LANDSCAPE", .12, "#7f8a72", True, "#edf0e5")
            path([[cx - 90, cy], [cx + 90, cy]], "A-LANDSCAPE", .13)
            path([[cx, cy - 90], [cx, cy + 90]], "A-LANDSCAPE", .13)
    for line in data["lines"]:
        path(line)
    for cut in data["cuts"]:
        path(cut["outer"], "A-CUT", .3, "#343930", True, "#343930")
        hatch = ms.add_hatch(color=7, dxfattribs={"layer": "A-CUT"})
        hatch.paths.add_polyline_path(cut["outer"], is_closed=True, flags=1)
        for hole in cut["holes"]:
            path(hole, "A-CUT", .3, "#343930", True, "#ffffff")
            hatch.paths.add_polyline_path(hole, is_closed=True, flags=0)
    if data["kind"] == "plan":
        from shapely.geometry import Polygon
        # Door symbols are generated from the same opening records as the solids.
        for element in project.elements:
            if element["kind"] != "wall":
                continue
            start, end = np.array(element["start"]), np.array(element["end"])
            tangent = (end - start) / np.linalg.norm(end - start)
            left = np.array([-tangent[1], tangent[0]])
            for opening in element.get("openings", []):
                if opening.get("type") != "door" or not element.get("z", 0) + opening.get("sill", 0) <= view.get("cut_z", 1200) < element.get("z", 0) + opening.get("sill", 0) + opening["height"]:
                    continue
                frame = opening.get("frame", 42)
                radius = opening["width"] - 2 * frame
                hinge = start + tangent * (opening["offset"] + frame)
                side = opening.get("swing_side", 1)
                leaf = hinge + left * radius * side
                path([hinge.tolist(), leaf.tolist()], "A-ANNOTATION", .18)
                arc = [(hinge + radius * (tangent * cos(a) + left * side * sin(a))).tolist()
                       for a in np.linspace(0, pi / 2, 25)]
                path(arc, "A-ANNOTATION", .09, "#969b90")
        for i, room in enumerate(project.rooms):
            if room.get("level") != view.get("level"):
                continue
            if room.get("label", True) is False:
                continue
            centre = room.get("label_at") or list(Polygon(room["polygon"]).representative_point().coords)[0]
            label(centre, room.get("plan_name", room.get("name", room.get("id", str(i)))), 2.5)
            label([centre[0], centre[1] - 370], f"{Polygon(room['polygon']).area / 1e6:.1f} m²", 2.0)
        for ann in project.annotations:
            if ann.get("view", "plan") in ("plan", view["id"]):
                if "points" in ann:
                    path(ann["points"], "A-ANNOTATION", .12, "#6a7166")
                if "text" in ann:
                    label(ann["at"], ann["text"], ann.get("size", 2.5))
    # Actual DIMENSION entities; PDF dimensions derive from exactly the same endpoints.
    if data["kind"] in {"section", "elevation"}:
        for level in view.get("levels", []):
            path([[minx - 800, level], [minx - 150, level]], "A-ANNOTATION", .12)
            label([minx - 1100, level + 160], "±0.000" if level == 0 else f"{level / 1000:.3f}", 2.5)
    dims = []
    for d in project.dimensions:
        if d.get("view", "plan") not in (data["kind"], view["id"]):
            continue
        a, b, base = d["p1"], d["p2"], d["base"]
        angle = degrees(atan2(b[1] - a[1], b[0] - a[0]))
        value = hypot(b[0] - a[0], b[1] - a[1])
        dim = ms.add_linear_dim(base=base, p1=a, p2=b, angle=angle,
                               override={"dimtxt": 2.2 * scale, "dimasz": 1.5 * scale,
                                         "dimexo": 0.8 * scale, "dimexe": 1.2 * scale,
                                         "dimdec": 0, "dimtad": 1, "dimtxsty": "EZARCH"},
                               dxfattribs={"layer": "A-DIM"})
        dim.render()
        if abs(a[0] - b[0]) < .001:
            aa, bb = [base[0], a[1]], [base[0], b[1]]
            path([a, [base[0] - 100, a[1]]], "A-DIM", .09, "#969b90")
            path([b, [base[0] - 100, b[1]]], "A-DIM", .09, "#969b90")
            path([aa, bb], "A-DIM", .09, "#777f73")
            for x0, y0 in [aa, bb]:
                path([[x0 - 75, y0 - 75], [x0 + 75, y0 + 75]], "A-DIM", .16)
            label([aa[0] - 160, (aa[1] + bb[1]) / 2], f"{value:,.0f}", 2.1, rotation=90)
        elif abs(a[1] - b[1]) < .001:
            aa, bb = [a[0], base[1]], [b[0], base[1]]
            path([a, [a[0], base[1] + 100]], "A-DIM", .09, "#969b90")
            path([b, [b[0], base[1] + 100]], "A-DIM", .09, "#969b90")
            path([aa, bb], "A-DIM", .09, "#777f73")
            for x0, y0 in [aa, bb]:
                path([[x0 - 75, y0 - 75], [x0 + 75, y0 + 75]], "A-DIM", .16)
            label([(aa[0] + bb[0]) / 2, aa[1] + 160], f"{value:,.0f}", 2.1)
        else:
            raise ValueError("Dimension annotations currently support horizontal/vertical endpoints; use a custom vector annotation for oblique dimensions")
        dims.append({"id": d.get("id"), "measured_mm": value, "p1": a, "p2": b})
    meta = {"title": view.get("title", view["id"]), "project_hash": fingerprint(project),
            "scale": scale, "bounds_mm": [minx, miny, maxx, maxy],
            "paper_origin_mm": [ox, oy], "dimensions": dims, "formats": sorted(formats)}
    report = canvas.save(stem, metadata=meta, formats=formats - {"dxf"})
    doc.set_modelspace_vport(height=maxy - miny + 2 * margin * scale, center=((minx + maxx) / 2, (miny + maxy) / 2))
    if doc.audit().has_errors:
        raise RuntimeError("Generated DXF failed structural audit")
    if "dxf" in formats:
        doc.saveas(stem.with_suffix(".dxf"))
    write_json(stem.with_suffix(".geometry.json"), {**data, **meta})
    return report


def save_annotated_view(project: Project, data: dict, view: dict, stem: Path, formats=None):
    """Rich drawing adapter; commands are explicit project-selected annotations."""
    from shapely.geometry import Polygon

    from .drafting import Drawing
    points = [p for line in data["lines"] for p in line] + [p for cut in data["cuts"] for p in cut["outer"]]
    if not points:
        raise ValueError(f"Empty view {view['id']}")
    xs, ys = zip(*points)
    bounds = [min(xs), min(ys), max(xs), max(ys)]
    scale = view.get("scale", 100)
    frame = view.get("drawing_bounds", [bounds[0] - 25 * scale, bounds[1] - 25 * scale,
                                        bounds[2] + 25 * scale, bounds[3] + 25 * scale])
    drawing = Drawing(frame, scale, view.get("title", view["id"]), view.get("number", ""),
                      view.get("margin", 8),
                      style=view.get("style"), font=view.get("font"))
    if view.get("paper_mm") and (drawing.width > view["paper_mm"][0] or drawing.height > view["paper_mm"][1]):
        raise ValueError("Requested drawing scale does not fit paper")
    rooms = [r for r in project.rooms if r.get("level") == view.get("level")]
    if data["kind"] == "plan":
        for room in rooms:
            drawing.canvas.poly([drawing.paper(p) for p in room["polygon"]], close=True,
                                fill=room.get("fill", "#faf9f5"), stroke=None)
    for line in data["lines"]:
        drawing.poly(line, color="#46534d")
    for cut in data["cuts"]:
        drawing.canvas.poly([drawing.paper(p) for p in cut["outer"]], close=True, fill="#26312e", width=.35)
        drawing.ms.add_lwpolyline(cut["outer"], close=True, dxfattribs={"layer": "A-CUT"})
        hatch = drawing.ms.add_hatch(color=7, dxfattribs={"layer": "A-CUT"})
        hatch.paths.add_polyline_path(cut["outer"], is_closed=True, flags=1)
        for hole in cut["holes"]:
            drawing.canvas.poly([drawing.paper(p) for p in hole], close=True, fill="#ffffff", width=.35)
            hatch.paths.add_polyline_path(hole, is_closed=True, flags=0)
    if data["kind"] == "plan":
        for e in project.elements:
            if e["kind"] != "wall":
                continue
            start, end = np.array(e["start"]), np.array(e["end"])
            t = (end - start) / np.linalg.norm(end - start)
            n = np.array([-t[1], t[0]])
            for op in e.get("openings", []):
                bottom = e.get("z", 0) + op.get("sill", 0)
                if op.get("type") not in {"door", "glass_door"} or not bottom <= view.get("cut_z", 1200) < bottom + op["height"]:
                    continue
                f, side = op.get("frame", 42), op.get("swing_side", 1)
                if op.get("operation") == "sliding":
                    a = start + t * (op["offset"] + f)
                    b = start + t * (op["offset"] + op["width"] - f)
                    middle = (a + b) / 2
                    drawing.poly([a, b], layer="A-ANNOTATION")
                    for sign in (-1, 1):
                        tip = middle + t * sign * op["width"] * .3 + n * 1.5 * scale
                        drawing.poly([middle + n * 1.5 * scale, tip], layer="A-ANNOTATION")
                        drawing.poly([tip - t * sign * scale + n * scale, tip,
                                      tip - t * sign * scale - n * scale], layer="A-ANNOTATION")
                    continue
                leaves = op.get("leaves", min(2, op.get("panels", 1)))
                radius = (op["width"] - 2 * f) / leaves
                for leaf in range(leaves):
                    reverse = -1 if leaf == 1 else 1
                    offset = op["offset"] + (op["width"] - f if leaf == 1 else f)
                    hinge = start + t * offset
                    drawing.poly([hinge, hinge + n * radius * side], layer="A-ANNOTATION")
                    drawing.poly([hinge + radius * (t * reverse * cos(a) + n * side * sin(a))
                                  for a in np.linspace(0, pi / 2, 25)], layer="A-ANNOTATION", width=.13)
        for room in rooms:
            if not room.get("label", True):
                continue
            label_style = view.get("room_labels", {}).get(room["id"], {})
            p = label_style.get("position") or room.get("label_at") or list(Polygon(room["polygon"]).representative_point().coords)[0]
            drawing.text(p, label_style.get("text", room.get("plan_name", room.get("name", room["id"]))), 3)
            drawing.text([p[0], p[1] - 4 * scale], f"{Polygon(room['polygon']).area / 1e6:.1f} m²", 2.5)
    for d in project.dimensions:
        if d.get("view", "plan") in (data["kind"], view["id"]):
            drawing.dimension(d["p1"], d["p2"], d["base"])
    allowed = {"axis", "dimension", "chain", "level", "north", "section_mark", "index", "leader",
               "furniture", "text", "poly", "rect", "line", "circle"}
    for command in view["drafting"]:
        command = dict(command)
        op = command.pop("op")
        if op not in allowed:
            raise ValueError(f"Unknown drafting command {op}")
        # Custom annotation linework must not enter model projection alignment layer.
        if op in {"poly", "rect", "line", "circle"}:
            command.setdefault("layer", "A-ANNOTATION")
        getattr(drawing, op)(**command)
    report = drawing.save(stem, view_source="canvas", metadata={"project_hash": fingerprint(project), "bounds_mm": bounds}, formats=formats)
    write_json(stem.with_suffix(".geometry.json"), {**data, **report["metadata"], "scale_bar_segments": 4,
                                                  "scale_bar_height_mm": 1})
    return report


def generate_views(project: Project, out: Path, only=None, formats=None):
    import shutil
    formats = set(["dxf", "pdf", "svg", "png"] if formats is None else formats)
    if not formats or formats - {"dxf", "pdf", "svg", "png"}:
        raise ValueError("View formats: dxf, pdf, svg, png")
    parts = build(project)
    out.mkdir(parents=True, exist_ok=True)
    for font_file in (["EZarchFang.ttf", "COPYING", "SOURCE.md"] if "dxf" in formats else []):
        font_dir = out / "fonts"
        font_dir.mkdir(exist_ok=True)
        shutil.copy2(skill_root() / "assets/fonts" / font_file, font_dir / font_file)
    reports = {}
    views = project.views or [{"id": "plan", "kind": "plan", "scale": 100, "cut_z": 1200}]
    for view in views:
        if only and view["id"] not in only:
            continue
        data = extract_view(parts, view)
        reports[view["id"]] = save_view(project, data, view, out / view["id"], formats)
    if not reports:
        raise ValueError("No requested views matched the project")
    write_json(out / "views-report.json", reports)
    return reports
