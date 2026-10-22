"""Existing-document preservation and independent drawing in native target units."""
import os
from pathlib import Path
import subprocess
import sys

import ezdxf
from ezdxf.lldxf.tagwriter import TagCollector
import pytest

from ezarch.drafting import Drawing


def tags(entity):
    return list(TagCollector.dxftags(entity))


def source_document(tmp_path):
    doc = ezdxf.new("R2010")
    doc.units = ezdxf.units.M
    doc.header["$MEASUREMENT"] = 0
    doc.layers.new("A-ANNOTATION", dxfattribs={"color": 3, "lineweight": 50})
    doc.layers.new("A-VISIBLE", dxfattribs={"color": 2})
    doc.layers.get("A-VISIBLE").freeze()
    doc.linetypes.new("EZ-GRID", dxfattribs={"pattern": [3, 2, -1]})
    doc.styles.new("ProjectFont", dxfattribs={"font": "project-font.shx", "width": .8})
    ms = doc.modelspace()
    ms.add_spline(fit_points=[(0, 0), (3, 4), (8, 1)])
    ms.add_lwpolyline([(0, 0, 0, 0, .5), (4, 0, 0, 0, 0)], dxfattribs={"layer": "A-VISIBLE"})
    block = doc.blocks.new("ExistingPart")
    block.add_circle((2, 3), 1)
    ms.add_blockref(block.name, (10, 20), dxfattribs={"rotation": 31})
    doc.add_xref_def("reference.dxf", "Reference")
    ms.add_blockref("Reference", (100, 200))
    paper = doc.layouts.new("User Sheet")
    paper.add_text("Existing title", dxfattribs={"height": 5})
    paper.add_viewport(center=(80, 60), size=(90, 70), view_center_point=(15, 20), view_height=40)
    doc.set_modelspace_vport(height=800, center=(41, 27))
    path = tmp_path / "original.dxf"
    doc.saveas(path)
    return ezdxf.readfile(path)


@pytest.mark.parametrize("target", ["model", "paper", "block"])
def test_binding_roundtrip_preserves_existing_entities_resources_and_views(tmp_path, target):
    doc = source_document(tmp_path)
    all_entities = {e.dxf.handle: tags(e) for layout in [*doc.layouts, *doc.blocks] for e in layout}
    tables = {name: {e.dxf.name: tags(e) for e in getattr(doc, name)}
              for name in ("layers", "styles", "linetypes", "dimstyles")}
    vports = [tags(e) for e in doc.viewports]
    layouts = doc.layout_names()
    layout = {"model": doc.modelspace(), "paper": doc.layouts.get("User Sheet"),
              "block": doc.blocks.get("ExistingPart")}[target]
    count = len(doc.entitydb)
    unit_mm, scale = (1, 1) if target == "paper" else (1000, 100)
    d = Drawing.from_layout(layout, scale=scale, unit_mm=unit_mm, text_style="ProjectFont")
    assert len(doc.entitydb) == count  # Binding itself creates no resources or geometry.
    assert d.canvas is None
    text, = d.text((4, 2), "Added", rotation=37)
    dim, = d.dimension((0, 0), (7, 0), (0, -2))
    fill = d.poly([(0, 0), (3, 0), (3, 2)], close=True, fill="#cccccc", dash=[10, 2])
    assert [e.dxftype() for e in fill] == ["LWPOLYLINE", "HATCH"]
    assert tuple(d.entities) == (text, dim, *fill)
    assert text.dxf.height == pytest.approx(2.5 * scale / unit_mm)
    assert d.dimensions[0]["measured_mm"] == pytest.approx(7 * unit_mm)
    assert all(e.dxf.owner == layout.layout_key for e in d.entities)
    assert text.dxf.layer != "A-ANNOTATION"
    assert fill[0].dxf.linetype != "EZ-GRID"
    path = tmp_path / "edited.dxf"
    doc.saveas(path)
    saved = ezdxf.readfile(path)
    assert not saved.audit().has_errors
    assert saved.units == ezdxf.units.M and saved.header["$MEASUREMENT"] == 0
    assert saved.layout_names() == layouts
    assert [tags(e) for e in saved.viewports] == vports
    for handle, previous in all_entities.items():
        assert tags(saved.entitydb[handle]) == previous, handle
    for table, entries in tables.items():
        for name, previous in entries.items():
            assert tags(getattr(saved, table).get(name)) == previous, (table, name)
    assert saved.entitydb[text.dxf.handle].dxf.rotation == 37
    assert saved.entitydb[dim.dxf.handle].get_measurement() == 7
    assert saved.entitydb[dim.dxf.handle].override().get("dimlfac") == unit_mm
    before = len(doc.entitydb)
    doc.saveas(path)
    assert len(doc.entitydb) == before


def test_resource_reuse_is_explicit_and_does_not_rewrite_definitions(tmp_path):
    doc = source_document(tmp_path)
    before = tags(doc.layers.get("A-VISIBLE")), tags(doc.linetypes.get("EZ-GRID"))
    d = Drawing.from_layout(doc.modelspace(), scale=100, unit_mm=1000, resource_policy="reuse")
    entity, = d.line((0, 0), (4, 0), dash=[10, 2])
    assert entity.dxf.layer == "A-VISIBLE" and entity.dxf.linetype == "EZ-GRID"
    assert (tags(doc.layers.get("A-VISIBLE")), tags(doc.linetypes.get("EZ-GRID"))) == before


def test_composite_returns_only_added_entities_and_no_automatic_export(tmp_path):
    doc = ezdxf.new()
    block = doc.blocks.new("Piece")
    d = Drawing.from_layout(block, scale=1, unit_mm=1, style={"excluded_axis_labels": []})
    circle, = d.circle((1, 2), 3)
    methods = [lambda: d.axis("I", "x", 0, 0, 40), lambda: d.chain([0, 10, 20], 0, -8),
               lambda: d.level((30, 30), 3400), lambda: d.north((10, 10), angle=41),
               lambda: d.section_mark((0, 0), (30, 20), "S"), lambda: d.index((0, 0), "D", "T"),
               lambda: d.leader([(0, 0), (10, 10)], "Note"),
               lambda: d.furniture("table", (0, 0), (20, 10), rotation=31)]
    for method in methods:
        count = len(block)
        entities = method()
        assert len(entities) == len(block) - count and entities
        assert circle not in entities
        assert all(e.dxf.owner == block.layout_key for e in entities)
    with pytest.raises(ValueError, match="doc.saveas"):
        d.save(tmp_path / "must-not-export")
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("options", [{"scale": 0}, {"unit_mm": 0}, {"scale": float("nan")},
                                     {"resource_policy": "overwrite"}, {"text_style": "missing"}])
def test_bad_binding_does_not_mutate_document(options):
    doc = ezdxf.new()
    before = len(doc.entitydb)
    with pytest.raises(ValueError):
        Drawing.from_layout(doc.modelspace(), **{"scale": 100, "unit_mm": 1, **options})
    assert len(doc.entitydb) == before


def test_cad_only_binding_does_not_load_rendering_or_project_dependencies(tmp_path):
    source = Path(__file__).resolve().parents[1] / "skills/ezarch/src"
    script = """
import sys, ezdxf
from ezarch.drafting import Drawing
doc = ezdxf.new()
d = Drawing.from_layout(doc.modelspace(), scale=100, unit_mm=1)
d.text((0, 0), 'test')
assert not {'ezarch.graphics', 'pymupdf', 'cadquery', 'bpy'} & sys.modules.keys()
"""
    env = {**os.environ, "PYTHONPATH": str(source), "PYTHONDONTWRITEBYTECODE": "1"}
    subprocess.run([sys.executable, "-c", script], cwd=tmp_path, env=env, check=True)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("unit_mm", [1, 1000])
def test_target_units_and_inherited_dimension_scale_do_not_distort_sizes(tmp_path, unit_mm):
    doc = ezdxf.new()
    doc.dimstyles.get("Standard").dxf.dimscale = 12
    previous = tags(doc.dimstyles.get("Standard"))
    d = Drawing.from_layout(doc.modelspace(), scale=100, unit_mm=unit_mm)
    dimension, = d.dimension((0, 0), (7000/unit_mm, 0), (0, -2000/unit_mm))
    cabinet = d.furniture("cabinet", (0, 0), (2400/unit_mm, 600/unit_mm))
    assert len(cabinet) == 4
    internal_x = [list(e.get_points("xy"))[0][0] * unit_mm for e in cabinet[1:]]
    assert internal_x == pytest.approx([600, 1200, 1800], abs=1e-9)
    d.axis("A", "x", 3000/unit_mm, 0, 6000/unit_mm)
    assert d.symbols[-1]["at_mm"] == 3000
    path = tmp_path / "unit-check.dxf"
    doc.saveas(path)
    saved = ezdxf.readfile(path)
    mtext, = [e for e in saved.entitydb[dimension.dxf.handle].virtual_entities() if e.dxftype() == "MTEXT"]
    assert mtext.dxf.char_height * unit_mm == pytest.approx(250)
    assert mtext.text == "7000"
    assert mtext.dxf.insert.y * unit_mm == pytest.approx(-2000 + 125 + 62.5)
    assert tags(saved.dimstyles.get("Standard")) == previous


def test_old_dxf_version_and_unattached_target_are_explicitly_unsupported():
    with pytest.raises(ValueError, match="R2000"):
        Drawing.from_layout(ezdxf.new("R12").modelspace(), scale=100, unit_mm=1)
    with pytest.raises(TypeError, match="attached"):
        Drawing.from_layout(None, scale=100, unit_mm=1)
