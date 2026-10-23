"""Saved-format properties and topology, not architectural design prescriptions."""
import math
import re
import xml.etree.ElementTree as ET

import ezdxf
import pymupdf as fitz
import pytest
from ezarch.drafting import Drawing
from ezarch.graphics import PT, Canvas
from ezarch.project import skill_root
from ezdxf.addons.drawing.properties import RenderContext
from ezdxf.fonts.fonts import sideload_ttf
from ezdxf.lldxf.tagwriter import TagCollector


def svg_items(path, kind):
    return ET.parse(path).getroot().findall(f"{{http://www.w3.org/2000/svg}}{kind}")


def test_explicit_properties_reach_dxf_pdf_and_svg(tmp_path):
    drawing = Drawing((0, 0, 100, 100), scale=1, margin=0)
    line, = drawing.line((10, 20), (90, 20), color="#194fbe", width=.5, dash=[7, 2, 1, 2])
    circle, = drawing.circle((50, 60), 15, color="#a83219", width=.25, dash=[3, 2])
    text, = drawing.text((50, 90), "COLOR", color="#884422", size=4)
    drawing.save(tmp_path / "properties", view_source="canvas", formats=["dxf", "pdf", "svg"])
    saved = ezdxf.readfile(tmp_path / "properties.dxf")
    for entity, color in [(line, (25, 79, 190)), (circle, (168, 50, 25)), (text, (136, 68, 34))]:
        assert saved.entitydb[entity.dxf.handle].rgb == color
    assert saved.entitydb[line.dxf.handle].dxf.lineweight == 50
    assert saved.entitydb[circle.dxf.handle].dxf.lineweight == 25
    assert saved.linetypes.get(line.dxf.linetype).simplified_line_pattern() == (7, 2, 1, 2)
    svg_line, = svg_items(tmp_path / "properties.svg", "polyline")
    assert svg_line.attrib["stroke"] == "#194fbe"
    assert float(svg_line.attrib["stroke-width"]) == .5
    assert svg_line.attrib["stroke-dasharray"] == "7.0,2.0,1.0,2.0"
    svg_circle, = svg_items(tmp_path / "properties.svg", "circle")
    assert float(svg_circle.attrib["r"]) == 15
    assert svg_items(tmp_path / "properties.svg", "text")[0].attrib["fill"] == "#884422"
    with fitz.open(tmp_path / "properties.pdf") as pdf:
        paths = pdf[0].get_drawings()
        path, = [p for p in paths if p["color"] == pytest.approx((25/255, 79/255, 190/255))]
        assert path["width"] / PT == pytest.approx(.5)
        assert [float(v) / PT for v in re.findall(r"[\d.]+", path["dashes"])[:-1]] == pytest.approx([7, 2, 1, 2], abs=1e-5)
        circle_path, = [p for p in paths if p["color"] == pytest.approx((168/255, 50/255, 25/255))]
        assert circle_path["items"][0][0] == "c"
        assert tuple(circle_path["items"][0][1]) == pytest.approx((65*PT, 40*PT), abs=.001)
        assert pdf[0].get_text("dict")["blocks"][0]["lines"][0]["spans"][0]["color"] == 0x884422
    assert not saved.audit().has_errors


@pytest.mark.parametrize("unit_mm,scale", [(1, 1), (1, 100), (1000, 100), (25.4, 50)])
def test_dash_lengths_units_global_scale_reuse_and_roundtrip(tmp_path, unit_mm, scale):
    doc = ezdxf.new()
    doc.header["$LTSCALE"] = 2.5
    a = Drawing.from_layout(doc.modelspace(), unit_mm=unit_mm, scale=scale)
    first, = a.line((0, 0), (500, 0), dash=[5, 2, 1])
    b = Drawing.from_layout(doc.modelspace(), unit_mm=unit_mm, scale=scale)
    second, = b.line((0, 1), (500, 1), dash=[5, 2, 1])
    assert first.dxf.linetype == second.dxf.linetype
    source_count = len(doc.linetypes)
    path = tmp_path / "dash.dxf"
    doc.saveas(path)
    saved = ezdxf.readfile(path)
    entity = saved.entitydb[first.dxf.handle]
    props = RenderContext(saved).resolve_all(entity)
    assert props.linetype_scale == pytest.approx(1)
    effective = [v * props.linetype_scale * unit_mm / scale for v in props.linetype_pattern]
    assert effective == pytest.approx([5, 2, 1, 5, 2, 1])
    assert entity.dxf.flags & 128
    assert saved.header["$LTSCALE"] == 2.5
    c = Drawing.from_layout(saved.modelspace(), unit_mm=unit_mm, scale=scale)
    c.line((0, 2), (500, 2), dash=[5, 2, 1])
    assert len(saved.linetypes) == source_count


def test_conflicting_generated_linetype_is_not_overwritten_or_wrongly_reused():
    doc = ezdxf.new()
    d = Drawing.from_layout(doc.modelspace(), scale=1, unit_mm=1, resource_policy="reuse")
    original, = d.line((0, 0), (100, 0), dash=[3, 2])
    name = original.dxf.linetype
    doc.linetypes.remove(name)
    collision = doc.linetypes.new(name, dxfattribs={"pattern": [15, 10, -5]})
    tags = list(TagCollector.dxftags(collision))
    added, = d.line((0, 1), (100, 1), dash=[3, 2])
    assert added.dxf.linetype != name
    assert list(TagCollector.dxftags(collision)) == tags
    assert doc.linetypes.get(added.dxf.linetype).simplified_line_pattern() == (3, 2)


def test_inherited_properties_remain_editable_and_explicit_values_do_not_change_layer(tmp_path):
    d = Drawing((0, 0, 100, 100), scale=1)
    layer = d.doc.layers.get("A-VISIBLE")
    layer.rgb, layer.dxf.lineweight = (17, 34, 51), 70
    before = list(TagCollector.dxftags(layer))
    inherited, = d.line((10, 10), (90, 10))
    explicit, = d.line((10, 30), (90, 30), color=1, width=.13)
    d.save(tmp_path / "inherit", view_source="canvas", formats=["dxf", "svg"])
    saved = ezdxf.readfile(tmp_path / "inherit.dxf")
    assert list(TagCollector.dxftags(saved.layers.get(layer.dxf.name))) == before
    entity = saved.entitydb[inherited.dxf.handle]
    assert entity.dxf.color == 256 and entity.dxf.lineweight == -1
    assert not entity.dxf.hasattr("true_color")
    assert saved.entitydb[explicit.dxf.handle].dxf.color == 1
    lines = svg_items(tmp_path / "inherit.svg", "polyline")
    assert [(p.attrib["stroke"], p.attrib["stroke-width"]) for p in lines] == [("#112233", "0.7"), ("#ff0000", "0.13")]


def test_r2000_keeps_native_version_and_reports_unsupported_rgb_before_mutation(tmp_path):
    doc = ezdxf.new("R2000")
    d = Drawing.from_layout(doc.modelspace(), scale=100, unit_mm=1)
    before = len(doc.entitydb)
    with pytest.raises(ValueError, match="R2004"):
        d.line((0, 0), (10, 0), color="#123456")
    assert len(doc.entitydb) == before
    d.line((0, 0), (10, 0))
    text, = d.text((0, 0), "ACI", color=3)
    d.poly([(0, 0), (10, 0), (0, 10)], close=True, fill=4)
    doc.saveas(tmp_path / "r2000.dxf")
    saved = ezdxf.readfile(tmp_path / "r2000.dxf")
    assert saved.dxfversion == "AC1015"
    assert saved.entitydb[text.dxf.handle].dxf.color == 3
    assert not saved.audit().has_errors


@pytest.mark.parametrize("options", [dict(width=.123), dict(width=-1), dict(dash=[2, 0]),
    dict(dash=[2, float("nan")]), dict(color="#xyzxyz"), dict(color=0),
    dict(holes=[[(0, 0), (1, 0), (0, 1)]]), dict(fill="#ff0000")])
def test_invalid_inputs_do_not_partially_draw(options):
    drawing = Drawing((0, 0, 100, 100), scale=1)
    before = len(drawing.doc.entitydb), len(drawing.canvas.items), len(drawing.entities)
    with pytest.raises(ValueError):
        drawing.poly([(10, 10), (80, 10), (80, 80), (10, 80)], **options)
    assert (len(drawing.doc.entitydb), len(drawing.canvas.items), len(drawing.entities)) == before


@pytest.mark.parametrize("reverse", [False, True])
def test_holes_are_real_boundaries_and_show_underlying_content(tmp_path, reverse):
    drawing = Drawing((0, 0, 100, 100), scale=1, margin=0)
    drawing.rect(0, 0, 100, 100, color=None, fill="#00aa00")
    outer = [(10, 10), (90, 10), (90, 90), (10, 90)]
    holes = [[(30, 30), (70, 30), (70, 70), (30, 70)],
             [(15, 15), (25, 15), (25, 25), (15, 25)]]
    if reverse:
        outer, holes = outer[::-1], [ring[::-1] for ring in holes]
    entities = drawing.poly(outer, holes=holes, close=True, fill="#ee0000", color="#0000ff", width=.25)
    hatch, = [e for e in entities if e.dxftype() == "HATCH"]
    assert len(entities) == 4
    drawing.save(tmp_path / "holes", view_source="canvas", dpi=127, formats=["dxf", "pdf", "svg"])
    saved = ezdxf.readfile(tmp_path / "holes.dxf")
    boundaries = saved.entitydb[hatch.dxf.handle].paths
    assert len(boundaries) == 3 and boundaries[0].path_type_flags & 1
    assert all(not (p.path_type_flags & 1) for p in list(boundaries)[1:])
    assert saved.entitydb[hatch.dxf.handle].rgb == (238, 0, 0)
    path, = svg_items(tmp_path / "holes.svg", "path")
    assert path.attrib["fill-rule"] == "evenodd" and path.attrib["d"].count("M ") == 3
    with fitz.open(tmp_path / "holes.pdf") as pdf:
        pix = pdf[0].get_pixmap(dpi=127, alpha=False)
        assert pix.pixel(250, 250) == (0, 170, 0)
        assert pix.pixel(100, 400) == (0, 170, 0)
        assert pix.pixel(100, 100) == (238, 0, 0)
    assert not saved.audit().has_errors
    count = len(drawing.doc.entitydb), len(drawing.canvas.items)
    drawing.save(tmp_path / "again", view_source="canvas", formats=["dxf"])
    assert (len(drawing.doc.entitydb), len(drawing.canvas.items)) == count


@pytest.mark.parametrize("hole", [[(90, 90), (110, 90), (110, 110), (90, 110)],
                                 [(30, 30), (70, 70), (30, 70), (70, 30)]])
def test_invalid_hole_is_reported_without_repair_or_mutation(hole):
    doc = ezdxf.new()
    drawing = Drawing.from_layout(doc.modelspace(), scale=1, unit_mm=1)
    before = len(doc.entitydb)
    with pytest.raises(ValueError, match="Invalid fill geometry"):
        drawing.poly([(10, 10), (90, 10), (90, 90), (10, 90)], holes=[hole], close=True, fill="#aa0000")
    assert len(doc.entitydb) == before


@pytest.mark.parametrize("angle", [0, .01, 37, 90, -113, 180])
@pytest.mark.parametrize("align", ["left", "center", "right"])
def test_text_anchor_cap_height_and_rotation_match_saved_native_semantics(tmp_path, angle, align):
    drawing = Drawing((0, 0, 100, 100), scale=1, margin=0)
    text, = drawing.text((50, 50), "Aa 中文", size=4, align=align, rotation=angle)
    drawing.save(tmp_path / "text", view_source="canvas", formats=["dxf", "pdf", "svg"])
    saved = ezdxf.readfile(tmp_path / "text.dxf")
    entity = saved.entitydb[text.dxf.handle]
    assert tuple(entity.get_placement()[1]) == (50, 50, 0)
    assert entity.dxf.height == 4 and entity.dxf.rotation == angle
    font_path = skill_root() / "assets/fonts/EZarchFang.ttf"
    native_font = sideload_ttf(font_path, 4)
    length = native_font.text_width("Aa 中文")
    offset = {"left": 0, "center": length / 2, "right": length}[align]
    theta = math.radians(angle)
    # Baseline is half the cap height below the middle anchor, in local text coordinates.
    expected = (50 - offset * math.cos(theta) + 2 * math.sin(theta),
                50 + offset * math.sin(theta) + 2 * math.cos(theta))
    with fitz.open(tmp_path / "text.pdf") as pdf:
        line, = pdf[0].get_text("dict")["blocks"][0]["lines"]
        # PDF affine coefficients are serialized to about five decimal places.
        assert line["dir"] == pytest.approx((math.cos(theta), -math.sin(theta)), abs=1e-5)
        assert [v / PT for v in line["spans"][0]["origin"]] == pytest.approx(expected, abs=.002)
        assert "中文" in pdf[0].get_text()
    svg, = svg_items(tmp_path / "text.svg", "text")
    assert float(svg.attrib["x"]) == pytest.approx(50 + 2 * math.sin(theta), abs=.002)
    assert float(svg.attrib["y"]) == pytest.approx(50 + 2 * math.cos(theta), abs=.002)


def test_standalone_canvas_keeps_em_baseline_and_arbitrary_widths(tmp_path):
    canvas = Canvas(100, 100)
    canvas.line(10, 10, 90, 10, width=.123, stroke="#2468ab")
    canvas.text(20, 50, "Baseline", size=5)
    canvas.save(tmp_path / "canvas", formats=["pdf"])
    with fitz.open(tmp_path / "canvas.pdf") as pdf:
        span = pdf[0].get_text("dict")["blocks"][0]["lines"][0]["spans"][0]
        assert span["size"] / PT == pytest.approx(5)
        assert [v / PT for v in span["origin"]] == pytest.approx([20, 50], abs=.001)
        assert pdf[0].get_drawings()[1]["width"] / PT == pytest.approx(.123)


def test_zero_width_is_not_replaced_by_default_pen(tmp_path):
    drawing = Drawing((0, 0, 100, 100), scale=1)
    circle, = drawing.circle((50, 50), 10, width=0)
    drawing.save(tmp_path / "hairline", view_source="canvas", formats=["dxf", "pdf", "svg"])
    assert ezdxf.readfile(tmp_path / "hairline.dxf").entitydb[circle.dxf.handle].dxf.lineweight == 0
    svg, = svg_items(tmp_path / "hairline.svg", "circle")
    assert svg.attrib["vector-effect"] == "non-scaling-stroke"
    with fitz.open(tmp_path / "hairline.pdf") as pdf:
        assert pdf[0].get_drawings()[1]["width"] == 0


def test_no_stroke_and_no_fill_produces_no_phantom_pdf_line(tmp_path):
    canvas = Canvas(30, 30)
    canvas.line(5, 5, 25, 25, stroke=None)
    canvas.circle(15, 15, 5, stroke=None)
    canvas.save(tmp_path / "invisible", formats=["pdf", "svg"])
    with fitz.open(tmp_path / "invisible.pdf") as pdf:
        assert len(pdf[0].get_drawings()) == 1  # Only the declared background.
    assert not svg_items(tmp_path / "invisible.svg", "polyline")
    assert not svg_items(tmp_path / "invisible.svg", "circle")
