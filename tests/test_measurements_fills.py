"""Selected geometry measurements and independent expression, without project policy."""
import json
import subprocess
import sys

import pytest
from ezarch.diagrams import fill_regions, generate_diagrams
from ezarch.frames import paper_transform
from ezarch.graphics import Canvas
from ezarch.intake import brief
from ezarch.measurements import coverage, measure_area
from ezarch.project import Project
from shapely.affinity import rotate, scale, translate
from shapely.geometry import MultiPolygon, Polygon, box


@pytest.mark.parametrize("unit_mm", [1, 10, 1000])
@pytest.mark.parametrize("angle", [0, 37, -117])
def test_area_holes_overlapping_masks_and_unit_invariance(unit_mm, angle):
    boundary = Polygon([(0, 0), (10, 0), (10, 8), (0, 8)], holes=[[(1, 1), (2, 1), (2, 3), (1, 3)]])
    cuts = {"one": box(4, 0, 7, 4), "two": box(6, 0, 11, 4)}
    def transform(shape):
        return translate(rotate(scale(shape, 1000/unit_mm, 1000/unit_mm, origin=(0, 0)),
                                angle, origin=(0, 0)), 130.7, -83.2)
    source = {"object": ["caller-ID"]}
    result = measure_area(transform(boundary), unit_mm=unit_mm,
                          exclusions={k: transform(v) for k, v in cuts.items()},
                          basis="Caller definition", source=source)
    assert result["boundary_area_m2"] == pytest.approx(78)
    assert result["removed_area_m2"] == pytest.approx(24)
    assert result["area_m2"] == pytest.approx(54)
    assert result["outside_exclusions"]["two"].area*(unit_mm/1000)**2 == pytest.approx(4)
    assert sum(g.area for g in result["effects"].values()) > result["removed"].area
    source["object"].append("changed")
    assert result["source"] == {"object": ["caller-ID"]}
    # Floating overlays may split tiny edge slivers; the supplied hole remains absent.
    hole = transform(Polygon([(1, 1), (2, 1), (2, 3), (1, 3)]))
    assert result["geometry"].intersection(hole).area*(unit_mm/1000)**2 == pytest.approx(0, abs=1e-9)


def test_empty_result_multipart_concavity_and_no_input_mutation():
    region = MultiPolygon([Polygon([(0, 0), (4, 0), (4, 1), (1, 1), (1, 4), (0, 4)]), box(8, 0, 9, 2)])
    before = region.wkb
    result = measure_area(region, unit_mm=1000, exclusions={"all": box(-1, -1, 10, 10)})
    assert result["boundary_area_m2"] == 9 and result["area_m2"] == 0
    assert result["geometry"].is_empty and region.wkb == before
    assert measure_area(Polygon(), unit_mm=1)["area_m2"] == 0


@pytest.mark.parametrize("shape,unit", [(Polygon([(0, 0), (2, 2), (2, 0), (0, 2)]), 1),
                                      (Polygon([(0, 0, 1), (2, 0, 1), (2, 2, 1)]), 1),
                                      (box(0, 0, 1, 1), 0), (box(0, 0, 1, 1), float("nan"))])
def test_area_rejects_invalid_geometry_and_units(shape, unit):
    with pytest.raises(ValueError):
        measure_area(shape, unit_mm=unit)


def test_coverage_triple_overlap_clipping_and_intentional_blank():
    domain = box(0, 0, 10, 10)
    regions = {"a": box(-2, 0, 4, 4), "b": box(0, 0, 4, 4), "c": box(0, 0, 4, 4)}
    result = coverage(domain, regions, unit_mm=1000)
    assert result["covered_area_m2"] == 16 and result["uncovered_area_m2"] == 84
    assert result["overlap_area_m2"] == 16
    assert sum(p["area_m2"] for p in result["overlap_pairs"]) == 48
    assert result["outside_area_m2"] == {"a": 8, "b": 0, "c": 0}
    assert result["checked_ids"] == ("a", "b", "c") and result["pair_count"] == 3
    assert "passed" not in result and result["not_checked"]


def test_coverage_empty_selection_and_boundary_touch():
    domain = box(0, 0, 2, 1)
    empty = coverage(domain, {}, unit_mm=1000)
    assert empty["pair_count"] == 0 and empty["checked_ids"] == ()
    assert empty["uncovered"].equals(domain)
    result = coverage(domain, {"left": box(0, 0, 1, 1), "right": box(1, 0, 2, 1)}, unit_mm=1000)
    assert result["overlap_pairs"] == [] and result["uncovered"].is_empty


def test_fill_holes_multipart_explicit_mapping_and_single_format(tmp_path):
    hole = [(2, 2), (3, 2), (3, 3), (2, 3)]
    shape = MultiPolygon([Polygon([(0, 0), (4, 0), (4, 4), (0, 4)], holes=[hole]), box(5, 0, 6, 1)])
    canvas = Canvas(100, 100)
    items = fill_regions(canvas, {"arbitrary": shape}, colors={"arbitrary": "#42a1b7"},
                         transform=paper_transform((0, 0, 8, 8), 100, unit_mm=1000, margin=10))
    assert len(items["arbitrary"]) == 2 and len(items["arbitrary"][0]["holes"]) == 1
    assert items["arbitrary"][0] is canvas.items[1]
    # Geometry can be re-expressed without changing it or choosing a building type.
    other = Canvas(100, 100)
    fill_regions(other, {"arbitrary": shape}, colors={"arbitrary": "#000000"})
    assert shape.area == 16
    canvas.save(tmp_path/"only", formats=["svg"])
    svg = (tmp_path/"only.svg").read_text()
    assert 'fill-rule="evenodd"' in svg and "#42a1b7" in svg
    assert not (tmp_path/"only.pdf").exists() and not (tmp_path/"only.png").exists()


def test_fill_validates_selection_before_drawing_and_empty_is_noop():
    canvas = Canvas(100, 100)
    initial = len(canvas.items)
    with pytest.raises(KeyError):
        fill_regions(canvas, {"a": box(0, 0, 1, 1), "b": box(2, 0, 3, 1)}, colors={"a": "#123456"})
    assert len(canvas.items) == initial
    assert fill_regions(canvas, {}, colors={}) == {}


def test_legacy_diagram_selection_and_boundary_area_alias(tmp_path):
    project = Project(name="Area selection", materials={}, elements=[], rooms=[dict(id="r", name="空间", type="interior",
                      polygon=[[0, 0], [3000, 0], [3000, 2000], [0, 2000]])])
    result = generate_diagrams(project, tmp_path/"diagram", kinds=["areas"], formats=["svg"])
    assert set(result) == {"areas"}
    assert not (tmp_path/"diagram/program.svg").exists()
    assert "BOUNDARY AREAS" in (tmp_path/"diagram/areas.svg").read_text()
    report = brief(project, tmp_path/"brief")
    assert report["interior_boundary_area_m2"] == report["interior_net_area_m2"] == 6
    assert report["compatibility_fields"] and report["rooms"][0]["basis"]
    assert generate_diagrams(project, tmp_path/"none", kinds=[]) == {}
    assert not (tmp_path/"none").exists()


def test_new_geometry_and_fill_imports_do_not_load_project_or_renderer():
    code = "import sys,json; from ezarch import measurements,diagrams; print(json.dumps(sorted(sys.modules)))"
    modules = json.loads(subprocess.check_output([sys.executable, "-c", code], text=True))
    assert not {"ezarch.project", "ezarch.graphics", "pymupdf", "cadquery", "bpy"} & set(modules)
