"""Measurement, evidence and nonmutation invariants; no architectural recipes."""
import copy
import json
import math

import ezdxf
import pytest
from ezarch.diagnostics import issue_region
from ezarch.walls import inspect_dxf_entities, inspect_geometry
from ezdxf.lldxf.tagwriter import TagCollector
from shapely import from_wkt
from shapely.affinity import affine_transform
from shapely.geometry import LinearRing, LineString, MultiPolygon, Point, Polygon


def by_name(result, name):
    return next(c for c in result["checks"] if c["name"] == name)


def test_invalid_polygon_is_located_without_repair_and_holes_are_checked():
    crossing = Polygon([(0, 0), (4, 4), (0, 4), (4, 0)])
    bad_hole = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)],
                       [[(20, 20), (21, 20), (21, 21), (20, 21)]])
    original = crossing.wkb, bad_hole.wkb
    r = inspect_geometry({"cross": crossing, "hole": bad_hole}, checks=["validity"], unit_mm=1)
    check = r["checks"][0]
    assert check["coverage"] == "complete"
    assert check["observation"] == "findings"
    first, second = check["findings"]
    assert first["location"]["points"] == [[2, 2]]
    assert first["evidence"] == "representation_invalid"
    assert "outside" in second["measurements"]["reason"].lower()
    assert (crossing.wkb, bad_hole.wkb) == original
    assert not crossing.is_valid and not bad_hole.is_valid
    assert issue_region(first, padding=3) == (-1, -1, 5, 5)
    json.dumps(r, allow_nan=False)


@pytest.mark.parametrize("unit_mm", [0.001, 1, 1000])
@pytest.mark.parametrize("angle", [0, 31, 170])
@pytest.mark.parametrize("mirror", [1, -1])
def test_measurements_survive_unit_rotation_mirror_changes(unit_mm, angle, mirror):
    # An immediate reversal followed by a short segment; no design meaning.
    line = LineString([(0, 0), (10, 0), (3, 0), (3, .25), (10, 4)])
    a = math.radians(angle)
    transform = [math.cos(a)/unit_mm, -mirror*math.sin(a)/unit_mm,
                 math.sin(a)/unit_mm, mirror*math.cos(a)/unit_mm, 17/unit_mm, -23/unit_mm]
    transformed = affine_transform(line, transform)
    before = transformed.wkb
    r = inspect_geometry({"g": transformed}, checks=["short_edges", "backtracks"], unit_mm=unit_mm,
                         short_edge_mm=.5, reversal_deviation_deg=.01, min_edge_mm=.001)
    edge = by_name(r, "short_edges")["findings"][0]
    turn = by_name(r, "backtracks")["findings"][0]
    assert edge["objects"][0]["edge"] == 2
    assert edge["measurements"]["length_mm"] == pytest.approx(.25)
    assert turn["objects"][0]["vertex"] == 1
    assert turn["measurements"]["incoming_mm"] == pytest.approx(10)
    assert turn["measurements"]["outgoing_mm"] == pytest.approx(7)
    assert transformed.wkb == before
    json.dumps(r, allow_nan=False)


def test_short_detail_is_a_candidate_not_a_failed_design_and_threshold_is_explicit():
    p = Polygon([(0, 0), (5, 0), (5, 4), (4.95, 4), (4.95, 5), (0, 5)])
    assert p.is_valid
    r = inspect_geometry({"detail": p}, checks=["validity", "short_edges"], unit_mm=1, short_edge_mm=.1)
    assert by_name(r, "validity")["observation"] == "none_found"
    short = by_name(r, "short_edges")["findings"]
    assert len(short) == 1 and short[0]["evidence"] == "candidate"
    assert "passed" not in r and "score" not in r
    r = inspect_geometry({"detail": p}, checks=["short_edges"], unit_mm=1, short_edge_mm=.01)
    assert r["checks"][0]["observation"] == "none_found"


def test_short_edge_threshold_is_strict_and_backtrack_threshold_is_inclusive():
    line = LineString([(0, 0), (1, 0), (0, 0)])
    r = inspect_geometry({"g": line}, checks=["short_edges", "backtracks"], unit_mm=1,
                         short_edge_mm=1, reversal_deviation_deg=0)
    assert not by_name(r, "short_edges")["findings"]
    assert by_name(r, "backtracks")["findings"]


def test_rings_holes_and_multipart_keep_indices_and_closure_is_not_a_zero_edge():
    p = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)],
                [[(2, 2), (2.1, 2), (2.1, 3), (2, 3)]])
    m = MultiPolygon([Polygon([(20, 20), (22, 20), (22, 22), (20, 22)]), p])
    r = inspect_geometry({"multi": m}, checks=["short_edges"], unit_mm=1, short_edge_mm=.2)
    c = r["checks"][0]
    assert c["examined_elements"] == 12
    assert len(c["findings"]) == 2
    assert all(f["objects"][0]["part"] == 1 and f["objects"][0]["ring"] == 0 for f in c["findings"])


def test_duplicates_keep_ids_and_ignore_ring_start_direction_but_not_segmentation():
    p = Polygon([(0, 0), (4, 0), (4, 4), (0, 4)])
    same = Polygon([(4, 4), (4, 0), (0, 0), (0, 4)])
    segmented = Polygon([(0, 0), (2, 0), (4, 0), (4, 4), (0, 4)])
    near = Polygon([(0, 0), (4.001, 0), (4, 4), (0, 4)])
    r = inspect_geometry({"a": p, "b": same, "split": segmented, "near": near},
                         checks=["duplicates"], unit_mm=1)
    c = r["checks"][0]
    assert c["compared_pairs"] == 6
    assert len(c["findings"]) == 1
    assert [o["id"] for o in c["findings"][0]["objects"]] == ["a", "b"]
    assert c["findings"][0]["evidence"] == "candidate"


def test_duplicate_ring_and_line_direction():
    r = inspect_geometry({"a": LinearRing([(0, 0), (4, 0), (4, 4)]),
                          "b": LinearRing([(4, 4), (4, 0), (0, 0)]),
                          "c": LineString([(0, 0), (1, 0)]), "d": LineString([(1, 0), (0, 0)])},
                         checks=["duplicates"], unit_mm=1)
    assert len(r["checks"][0]["findings"]) == 2


def test_signed_zero_is_not_a_distinct_coordinate_or_mutated_input():
    p = Polygon([(-0., 0), (1, 0), (1, 1)])
    before = p.wkb
    r = inspect_geometry({"a": p, "b": Polygon([(0., 0), (1, 0), (1, 1)])},
                         checks=["duplicates"], unit_mm=1)
    assert len(r["checks"][0]["findings"]) == 1
    assert p.wkb == before


def test_empty_missing_unsupported_and_inapplicable_are_not_assessed():
    r = inspect_geometry({}, checks=["validity", "duplicates"], unit_mm=1, expected_ids=["missing"])
    assert r["scope"]["missing_ids"] == ["missing"]
    assert all(c["coverage"] == "none" and c["observation"] == "not_assessed" for c in r["checks"])
    r = inspect_geometry({"empty": Polygon(), "point": Point(1, 2), "3d": LineString([(0, 0, 1), (1, 0, 1)]),
                          "bad": None, "open": LineString([(0, 0), (1, 0)])},
                         checks=["validity", "duplicates"], unit_mm=1)
    assert all(c["observation"] == "not_assessed" for c in r["checks"])
    assert len(r["checks"][0]["unexamined"]) == 5
    json.dumps(r, allow_nan=False)


def test_partial_coverage_survives_no_findings_and_nonfinite_input():
    with pytest.warns(RuntimeWarning):
        g = from_wkt("LINESTRING (0 0, NaN 1)")
    p = Polygon([(0, 0), (2, 0), (2, 2)])
    r = inspect_geometry({"p": p, "nan": g}, checks=["validity"], unit_mm=1, expected_ids=["p", "missing"])
    c = r["checks"][0]
    assert c["coverage"] == "partial" and c["observation"] == "none_found"
    assert len(c["unexamined"]) == 2
    assert r["scope"]["unselected_checks"] == ["short_edges", "backtracks", "duplicates"]
    json.dumps(r, allow_nan=False)


def test_degenerate_turns_are_excluded_with_counts_not_declared_clear():
    line = LineString([(0, 0), (0, 0), (1, 0)])
    r = inspect_geometry({"g": line}, checks=["backtracks"], unit_mm=1, reversal_deviation_deg=.1)
    c = r["checks"][0]
    assert c["excluded_degenerate_vertices"] == 1
    assert c["observation"] == "not_assessed"


@pytest.mark.parametrize("options", [
    {"checks": []}, {"checks": ["all"]}, {"checks": "validity"}, {"unit_mm": 0},
    {"unit_mm": math.inf}, {"checks": ["short_edges"]}, {"checks": ["backtracks"]},
    {"checks": ["backtracks"], "reversal_deviation_deg": 90}, {"min_edge_mm": -1},
    {"expected_ids": "x"},
])
def test_bad_options_raise_instead_of_success(options):
    with pytest.raises((ValueError, TypeError)):
        inspect_geometry({}, **({"checks": ["validity"], "unit_mm": 1} | options))


def test_dxf_selection_is_read_only_and_locates_original_entities(tmp_path):
    doc = ezdxf.new()
    m = doc.modelspace()
    ring = m.add_lwpolyline([(0, 0), (5, 0), (2, 0), (2, 3), (0, 3)], close=True)
    duplicate = m.add_lwpolyline([(2, 3), (2, 0), (5, 0), (0, 0), (0, 3)], close=True)
    hatch = m.add_hatch()
    hatch.paths.add_polyline_path([(0, 0), (4, 4), (0, 4), (4, 0)], is_closed=True, flags=1)
    curve = m.add_lwpolyline([(0, 0, 1), (4, 0, 0)], format="xyb")
    circle = m.add_circle((0, 0), 4)
    before = {e.dxf.handle: list(TagCollector.dxftags(e)) for e in m}
    path = tmp_path / "source.dxf"
    doc.saveas(path)
    data = path.read_bytes()
    r = inspect_dxf_entities(m, checks=["validity", "short_edges", "backtracks", "duplicates"],
                             unit_mm=1, short_edge_mm=.1, reversal_deviation_deg=.1)
    turns = by_name(r, "backtracks")["findings"]
    assert turns and turns[0]["objects"][0]["source"]["handle"] == ring.dxf.handle
    assert turns[0]["objects"][0]["source"]["layout"] == "Model"
    dups = by_name(r, "duplicates")["findings"]
    assert {o["id"] for o in dups[0]["objects"]} == {ring.dxf.handle, duplicate.dxf.handle}
    invalid = by_name(r, "validity")["findings"]
    assert hatch.dxf.handle in [f["objects"][0]["id"] for f in invalid]
    skipped = {i["id"]: i["unavailable_reason"] for i in r["inputs"]}
    assert skipped[curve.dxf.handle] == "curved_polyline"
    assert "unsupported" in skipped[circle.dxf.handle]
    assert before == {e.dxf.handle: list(TagCollector.dxftags(e)) for e in m}
    assert path.read_bytes() == data
    json.dumps(r, allow_nan=False)


def test_hatch_role_ambiguity_and_non_xy_geometry_are_explicit():
    doc = ezdxf.new()
    m = doc.modelspace()
    h = m.add_hatch()
    h.paths.add_polyline_path([(0, 0), (5, 0), (5, 5), (0, 5)], flags=1)
    h.paths.add_polyline_path([(1, 1), (2, 1), (2, 2), (1, 2)], flags=16)
    ambiguous = m.add_hatch()
    ambiguous.paths.add_polyline_path([(0, 0), (2, 0), (2, 2)], flags=0)
    high = m.add_line((0, 0, 4), (1, 0, 4))
    ocs = m.add_lwpolyline([(0, 0), (2, 0)], dxfattribs={"extrusion": (0, 0, -1)})
    r = inspect_dxf_entities(m, checks=["validity"], unit_mm=1)
    assert r["checks"][0]["examined_ids"] == [h.dxf.handle]
    assert r["checks"][0]["coverage"] == "partial"
    reasons = {s["id"]: s["reason"] for s in r["checks"][0]["unexamined"]}
    assert "ambiguous" in reasons[ambiguous.dxf.handle]
    assert reasons[high.dxf.handle] == "nonzero_elevation"
    assert reasons[ocs.dxf.handle] == "non_default_ocs"


def test_crop_and_input_parameters_are_not_mutated():
    r = inspect_geometry({"g": LineString([(0, 0), (.1, 0)])},
                         checks=["short_edges"], unit_mm=1, short_edge_mm=1)
    f = r["checks"][0]["findings"][0]
    before = copy.deepcopy(f)
    assert issue_region(f, padding=2) == (-2, -2, 2.1, 2)
    assert f == before
    for padding in [0, -1, math.nan, math.inf]:
        with pytest.raises(ValueError):
            issue_region(f, padding=padding)
