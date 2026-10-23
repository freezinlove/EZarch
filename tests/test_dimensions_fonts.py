"""Actual endpoint measurements, native dimensions and explicit font evidence."""
import math

import ezdxf
import pymupdf as fitz
import pytest
from ezarch.drafting import Drawing
from ezarch.fonts import FontFace, cap_metrics, discover_fonts, font_info, measure_text
from ezarch.measurements import measure_span
from ezarch.project import skill_root
from fontTools.ttLib import TTCollection, TTFont

FONT = skill_root()/"assets/fonts/EZarchFang.ttf"
OTF = skill_root()/"assets/fonts/FandolFang-Regular.otf"


@pytest.mark.parametrize("unit_mm", [1, 1000])
@pytest.mark.parametrize("direction,expected", [(None, 5000), ((1, 0), 3000), ((0, -4), 4000), ((4, 3), 4800)])
@pytest.mark.parametrize("target", ["model", "paper", "block"])
def test_native_dimensions_measure_real_span_and_preserve_endpoints(tmp_path, unit_mm, direction, expected, target):
    doc = ezdxf.new()
    layout = {"model": doc.modelspace(), "paper": doc.layouts.new("Sheet"),
              "block": doc.blocks.new("Part")}[target]
    old = layout.add_circle((19, 29), 7)
    drawing = Drawing.from_layout(layout, scale=75, unit_mm=unit_mm)
    p1, p2 = (0, 0), (3000/unit_mm, 4000/unit_mm)
    source = {"ids": ["point-A", "point-B"], "revision": "chosen-by-caller"}
    entity, = drawing.dimension(p1, p2, (-1000/unit_mm, 6000/unit_mm),
                                 direction=direction, decimals=2, source=source)
    source["ids"].append("later-change")
    record = drawing.dimensions[0]
    assert record["measured_mm"] == pytest.approx(expected)
    assert record["endpoint_distance_mm"] == 5000
    assert record["source"]["ids"] == ["point-A", "point-B"]
    assert entity.dxf.owner == layout.layout_key
    assert entity.get_measurement()*unit_mm == pytest.approx(expected)
    assert tuple(entity.dxf.defpoint2)[:2] == p1
    assert tuple(entity.dxf.defpoint3)[:2] == p2
    assert old.is_alive and old.dxf.radius == 7
    path = tmp_path/"dimension.dxf"
    doc.saveas(path)
    read = ezdxf.readfile(path)
    saved = read.entitydb[entity.dxf.handle]
    assert not read.audit().has_errors
    label, = [e for e in saved.virtual_entities() if e.dxftype() == "MTEXT"]
    assert label.text == f"{expected:.2f}"
    assert saved.override().get("dimlfac") == unit_mm


def test_endpoint_change_and_literal_override_are_distinguishable():
    d = Drawing((-3000, -3000, 12000, 9000), scale=100)
    d.dimension((0, 0), (6000, 0), (0, -1000))
    e, = d.dimension((0, 0), (7200, 0), (0, -2000), text_override="chosen text")
    assert d.dimensions[1]["measured_mm"] - d.dimensions[0]["measured_mm"] == 1200
    assert e.get_measurement() == 7200 and d.dimensions[1]["text_override"] == "chosen text"
    assert [i["text"] for i in d.canvas.items if i["kind"] == "text"] == ["6000", "chosen text"]


def test_oblique_canvas_and_dxf_value_agree_after_save(tmp_path):
    d = Drawing((-4000, -4000, 10000, 9000), scale=100)
    dim, = d.dimension((0, 0), (3000, 4000), (0, -1200), decimals=1)
    assert d.save(tmp_path/"oblique", view_source="canvas", formats=["pdf", "svg", "dxf"])
    with fitz.open(tmp_path/"oblique.pdf") as pdf:
        assert "5000.0" in pdf[0].get_text()
        line = pdf[0].get_text("dict")["blocks"][0]["lines"][0]
        assert line["dir"] == pytest.approx((.6, -.8), abs=1e-6)
    assert ezdxf.readfile(tmp_path/"oblique.dxf").entitydb[dim.dxf.handle].get_measurement() == 5000


@pytest.mark.parametrize("kwargs", [{"direction": (0, 0)}, {"decimals": -1}, {"decimals": 1.2},
                                    {"text_override": "<>"}, {"text_override": "\\P"},
                                    {"text_override": "%%d"}, {"text_override": "A\u0000B"},
                                    {"text_size": float("inf")}])
def test_bad_dimension_input_does_not_partially_draw(kwargs):
    d = Drawing((0, 0, 5000, 5000))
    original = len(d.ms), len(d.canvas.items)
    with pytest.raises(ValueError):
        d.dimension((0, 0), (3000, 4000), (0, 1000), **kwargs)
    assert (len(d.ms), len(d.canvas.items)) == original


def test_span_is_independent_and_keeps_projection_sign():
    result = measure_span((1, 2), (-2, -2), unit_mm=1000, direction=(1, 0))
    assert result["signed_mm"] == -3000 and result["measured_mm"] == 3000
    assert result["endpoint_distance_mm"] == 5000
    assert measure_span((1, 2), (1, 2), unit_mm=1)["measured_mm"] == 0
    assert measure_span((0, 0), (0, 1), unit_mm=1, direction=(1, 0))["measured_mm"] == 0


@pytest.fixture
def collection(tmp_path):
    # Two real supplied faces assembled only as a private test fixture.
    path = tmp_path/"faces.ttc"
    first, second = TTFont(FONT), TTFont(FONT)
    second["OS/2"].usWeightClass = 700
    second["name"].setName("Test Bold", 2, 3, 1, 0x409)
    c = TTCollection()
    c.fonts = [first, second]
    c.save(path)
    c.close()
    return path


def test_discovery_reads_real_faces_errors_and_exact_filters(collection, tmp_path):
    damaged = tmp_path/"misleading-Bold.ttf"
    damaged.write_bytes(b"not a font")
    result = discover_fonts([tmp_path, FONT], text="中文㎡")
    assert len(result["candidates"]) == 3 and len(result["errors"]) == 1
    assert len(discover_fonts([collection], weight=700)["candidates"]) == 1
    assert discover_fonts([collection], weight=600)["candidates"] == []
    assert discover_fonts([collection], family="Not Installed")["candidates"] == []
    candidate = discover_fonts([collection], weight=700)["candidates"][0]
    assert candidate["face"].index == 1
    assert "㎡" in font_info(FONT, text="㎡")["missing_characters"]
    assert discover_fonts([tmp_path/"absent.ttf"])["errors"]


@pytest.mark.parametrize("path", [FONT, OTF])
@pytest.mark.parametrize("rotation", [0, 43, -91])
def test_font_advance_matches_existing_mupdf_horizontal_text(path, rotation):
    text = "轴号 R-12 345"
    measured = measure_text(text, path, size_mm=3.7, rotation=rotation, origin=(20, 30), align="center")
    reference = fitz.Font(fontfile=str(path)).text_length(text, fontsize=3.7)
    assert measured["advance_mm"] == pytest.approx(reference, abs=1e-5)
    assert measured["glyph_coverage_complete"] and measured["ink"] and measured["metrics"]
    assert len(measured["ink"]["corners_mm"]) == 4
    left, bottom, right, top = measured["ink"]["bbox_mm"]
    assert left < right and bottom < top
    assert "passed" not in measured and measured["not_checked"]


def test_missing_glyph_does_not_produce_false_width_or_bounds(tmp_path):
    result = measure_text("中文㎡", FONT, size_mm=3)
    assert result["missing_characters"] == ("㎡",)
    assert result["advance_mm"] is None and result["ink"] is None and result["metrics"] is None
    assert not result["glyph_coverage_complete"]
    fallback = tmp_path/"fallback.ttf"
    with TTFont(FONT) as data:
        for table in data["cmap"].tables:
            if table.isUnicode():
                table.cmap[ord("㎡")] = data.getBestCmap()[ord("A")]
        data.save(fallback)
    completed = measure_text("中文㎡", FONT, size_mm=3, fallbacks=[fallback])
    assert completed["glyph_coverage_complete"]
    assert completed["glyphs"][-1]["face"].path == fallback.resolve()
    assert completed["advance_mm"] > 0


def test_collection_index_cap_height_spaces_and_empty_text(collection):
    face = FontFace(collection, 1)
    assert font_info(face)["weight"] == 700
    measured = measure_text("A", face, size_mm=7, size_mode="cap", valign="middle")
    box = measured["ink"]["bbox_mm"]
    assert box[3]-box[1] == pytest.approx(7, abs=.03)
    assert cap_metrics(face)[0] > 0
    empty = measure_text("", FONT, size_mm=3)
    assert empty["advance_mm"] == 0 and empty["ink"] is None
    spaces = measure_text("   ", FONT, size_mm=3)
    assert spaces["advance_mm"] > 0 and spaces["ink"] is None and spaces["metrics"]
    with pytest.raises(ValueError):
        font_info(FontFace(FONT, 1))


@pytest.mark.parametrize("kwargs", [{"size_mm": 0}, {"size_mm": float("nan")},
                                    {"size_mm": 3, "align": "justify"},
                                    {"size_mm": 3, "origin": (1, 2, 3)}])
def test_text_invalid_geometry_is_not_silently_coerced(kwargs):
    with pytest.raises(ValueError):
        measure_text("A", FONT, **kwargs)


def test_rotated_ink_envelope_transforms_from_unrotated_measurement():
    first = measure_text("中文 42", FONT, size_mm=4, align="right", valign="middle")
    second = measure_text("中文 42", FONT, size_mm=4, align="right", valign="middle", rotation=39, origin=(10, 20))
    theta = math.radians(39)
    for (x, y), point in zip(first["ink"]["corners_mm"], second["ink"]["corners_mm"]):
        assert point == pytest.approx((10+x*math.cos(theta)-y*math.sin(theta),
                                      20+x*math.sin(theta)+y*math.cos(theta)))
