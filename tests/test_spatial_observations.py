"""Evidence, scope and nonmutation tests, with no project layout fixtures."""
import copy
import math

import pytest
from shapely.affinity import affine_transform
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box
from shapely.ops import unary_union

from ezarch.annotations import Footprint, annotation_conflicts, text_footprint
from ezarch.diagnostics import geometry_location, issue_region
from ezarch.fonts import measure_text
from ezarch.measurements import measure_clear_width
from ezarch.project import skill_root
from ezarch.routing import reachable_targets


def test_annotation_relations_include_intentional_overlap_and_touch_without_verdict():
    data = {"a": box(0, 0, 4, 3), "b": box(3, 1, 5, 2), "c": box(4, 2, 6, 3)}
    before = {key: value.wkb for key, value in data.items()}
    result = annotation_conflicts(data, {"line": LineString([(1, -1), (1, 4)])}, unit_mm=2)
    pairs = {tuple(o["id"] for o in f["objects"]): f for f in result["findings"]}
    assert pairs[("a", "b")]["overlap_area_mm2"] == 4
    assert pairs[("a", "c")]["relation"] == "touches"
    assert pairs[("a", "line")]["intersection"].length == 3
    assert pairs[("a", "line")]["overlap_area_mm2"] == 0
    assert result["checked_pair_count"] == 6
    assert all(f["evidence"] == "candidate" for f in result["findings"])
    assert not {"passed", "score", "suggested_position"} & result.keys()
    assert before == {key: value.wkb for key, value in data.items()}
    assert issue_region(pairs[("a", "b")], padding=1) == (2, 0, 5, 3)


def test_clearance_uses_closest_points_and_strict_explicit_threshold():
    a, b = box(0, 0, 2, 2), box(3, 0, 5, 2)
    assert not annotation_conflicts({"a": a}, {"b": b}, unit_mm=1000, clearance_mm=1000)["findings"]
    r = annotation_conflicts({"a": a}, {"b": b}, unit_mm=1000, clearance_mm=1001)
    f, = r["findings"]
    assert f["relation"] == "within_clearance" and f["distance_mm"] == 1000
    assert f["geometry"].length == 1 and f["intersection"] is None
    assert f["location"]["precision"] == "supplied_footprint_relation"


def test_footprint_holes_and_input_groups_are_not_collapsed():
    ring = box(0, 0, 10, 10).difference(box(2, 2, 8, 8))
    r = annotation_conflicts({"same": ring}, {"same": box(3, 3, 4, 4)}, unit_mm=1)
    assert not r["findings"] and r["checked_pair_count"] == 1
    r = annotation_conflicts({"same": box(0, 0, 1, 1)}, {"same": box(0, 0, 1, 1)}, unit_mm=1)
    assert [o["group"] for o in r["findings"][0]["objects"]] == ["annotation", "obstacle"]


def test_partial_annotation_inputs_and_missing_ids_remain_visible():
    bow = Polygon([(0, 0), (2, 2), (0, 2), (2, 0)])
    inputs = {"ok": box(0, 0, 1, 1), "missing": None, "bad": bow, "empty": Polygon(),
              "z": Point(1, 2, 3), "font": Footprint(None, "ink", unavailable_reason="Missing glyphs")}
    r = annotation_conflicts(inputs, {"far": box(20, 20, 21, 21)}, unit_mm=1,
                             expected_annotation_ids=[*inputs, "absent"], expected_obstacle_ids=["far", "wall"])
    assert r["observation"] == "none_found" and r["coverage"] == "partial"
    assert r["checked_pair_count"] == 1
    assert sum(bool(item["reason"]) for item in r["inputs"]) == 5
    assert r["scope"]["missing_ids"] == {"annotation": ("absent",), "obstacle": ("wall",)}


@pytest.mark.parametrize("inputs,obstacles", [({}, {}), ({"a": box(0, 0, 1, 1)}, {}), ({}, {"o": box(0, 0, 1, 1)})])
def test_no_comparisons_is_not_a_clean_check(inputs, obstacles):
    r = annotation_conflicts(inputs, obstacles, unit_mm=1)
    assert r["coverage"] == "none" and r["observation"] == "not_assessed"


def test_real_font_rotated_envelope_and_missing_glyph_are_not_axis_aligned_or_silent():
    font = skill_root() / "assets/fonts/EZarchFang.ttf"
    measured = measure_text("文字", font, size_mm=4, rotation=37)
    footprint = text_footprint(measured, kind="ink")
    assert list(footprint.geometry.exterior.coords)[:4] == measured["ink"]["corners_mm"]
    assert footprint.geometry.area < box(*measured["ink"]["bbox_mm"]).area
    transformed = text_footprint(measured, kind="ink", transform=(.001, 0, 0, -.001, 10, 20))
    assert transformed.geometry.area == pytest.approx(footprint.geometry.area*1e-6)
    bad = text_footprint(measure_text("\U0010ffff", font, size_mm=4), kind="ink")
    assert bad.geometry is None and "Missing glyphs" in bad.unavailable_reason
    r = annotation_conflicts({"bad": bad, "ok": transformed}, {"far": box(40, 40, 41, 41)}, unit_mm=1000)
    assert r["coverage"] == "partial"
    for text in ("", "  "):
        absent = text_footprint(measure_text(text, font, size_mm=4), kind="ink")
        assert absent.unavailable_reason and absent.geometry is None
    spaces = text_footprint(measure_text("  ", font, size_mm=4), kind="metrics")
    assert spaces.geometry.area > 0


def test_width_keeps_all_intervals_holes_and_source_snapshot():
    area = box(0, 0, 12, 8).difference(box(4, 1, 6, 7))
    obstacles = {"selected": box(8, 0, 9, 8), "outside": box(30, 30, 31, 31)}
    section = LineString([(-1, 4), (13, 4)])
    source = {"selected": ["s1"]}
    before = area.wkb, section.wkb, [v.wkb for v in obstacles.values()]
    result = measure_clear_width(area, section, unit_mm=1000, obstacles=obstacles, source=source)
    source["selected"].append("later")
    assert result["source"] == {"selected": ["s1"]}
    assert [v["width_mm"] for v in result["intervals"]] == [4000, 2000, 3000]
    assert [v["start"] for v in result["intervals"]] == [(0, 4), (6, 4), (9, 4)]
    assert result["obstacle_contacts"]["outside"].is_empty
    assert "minimum_width" not in result
    assert before == (area.wkb, section.wkb, [v.wkb for v in obstacles.values()])


def test_truncated_sections_report_observed_span_not_full_width():
    area = box(0, 0, 10, 4)
    for ends, flags in [([(2, 2), (8, 2)], (True, True)), ([(-1, 2), (8, 2)], (False, True)),
                        ([(8, 2), (-1, 2)], (True, False))]:
        span, = measure_clear_width(area, LineString(ends), unit_mm=1)["intervals"]
        assert span["truncated"] == flags and span["width_mm"] is None
        assert span["span_mm"] > 0
        assert span["stations_mm"][0] < span["stations_mm"][1]


def test_boundary_only_empty_and_tangent_contacts_do_not_become_usable_width():
    area = box(0, 0, 5, 5)
    r = measure_clear_width(area, LineString([(-1, 0), (6, 0)]), unit_mm=1)
    assert not r["intervals"] and r["boundary_contact"].length == 5
    r = measure_clear_width(area, LineString([(-1, 2), (6, 2)]), unit_mm=1, obstacles={"all": area})
    assert r["observation"] == "empty_free_space" and not r["intervals"]
    hole = Polygon([(1, 2), (2, 3), (3, 2), (2, 1)])
    r = measure_clear_width(area, LineString([(-1, 3), (6, 3)]), unit_mm=1, obstacles={"diamond": hole})
    assert [x["width_mm"] for x in r["intervals"]] == [2, 3]
    step = Polygon([(0, 0), (3, 0), (3, -2), (8, -2), (8, 2), (0, 2)])
    r = measure_clear_width(step, LineString([(-1, 0), (9, 0)]), unit_mm=1)
    assert [x["width_mm"] for x in r["intervals"]] == [5]
    assert r["intervals"][0]["start"] == (3, 0)


@pytest.mark.parametrize("unit,angle,mirror", [(1, 0, 1), (1000, 37, -1), (.01, 143, 1)])
def test_width_annotation_and_connectivity_under_coordinate_changes(unit, angle, mirror):
    angle = math.radians(angle)
    transform = [math.cos(angle)/unit, -mirror*math.sin(angle)/unit,
                 math.sin(angle)/unit, mirror*math.cos(angle)/unit, 27/unit, -39/unit]
    def change(shape):
        return affine_transform(shape, transform)
    area = change(box(0, 0, 20, 10))
    span, = measure_clear_width(area, change(LineString([(-2, 5), (22, 5)])), unit_mm=unit)["intervals"]
    assert span["span_mm"] == pytest.approx(20)
    assert span["width_mm"] == pytest.approx(20)
    r = annotation_conflicts({"a": change(box(0, 0, 4, 4))}, {"b": change(box(2, 2, 6, 6))}, unit_mm=unit)
    assert r["findings"][0]["overlap_area_mm2"] == pytest.approx(4)
    r = reachable_targets(area, change(Point(1, 1)), {"t": change(Point(19, 9))}, unit_mm=unit)
    assert r["targets"]["t"]["status"] == "connected_in_supplied_space"


def test_connectivity_retains_coincident_targets_and_missing_information():
    area = MultiPolygon([box(0, 0, 4, 4), box(8, 0, 12, 4)])
    targets = {"a": (1, 1), "same": (1, 1), "other": (9, 1), "edge": (0, 2),
               "outside": (6, 1), "invalid": None, "z": (1, 1, 4)}
    original = copy.deepcopy(targets)
    r = reachable_targets(area, (2, 2), targets, unit_mm=1, expected_target_ids=[*targets, "missing"])
    assert r["targets"]["a"]["status"] == r["targets"]["same"]["status"] == "connected_in_supplied_space"
    assert r["targets"]["other"]["status"] == "disconnected_in_supplied_space"
    assert r["targets"]["edge"]["reason"] == "on_boundary"
    assert r["targets"]["outside"]["reason"] == "outside_supplied_free_space"
    assert r["targets"]["missing"]["reason"] == "missing_target"
    assert r["targets"]["outside"]["point"] == (6, 1)
    assert targets == original and len(r["targets"]) == 8
    assert r["coverage"] == "partial"


def test_allowed_space_can_forbid_an_intermediate_connection_without_moving_targets():
    area = box(0, 0, 10, 4)
    allowed = MultiPolygon([box(0, 0, 4, 4), box(6, 0, 10, 4)])
    r = reachable_targets(area, (1, 1), {"far": (9, 1), "middle": (5, 1)}, unit_mm=1, allowed_space=allowed)
    assert r["targets"]["far"]["status"] == "disconnected_in_supplied_space"
    assert r["targets"]["middle"]["reason"] == "outside_allowed_space"
    assert area.area == 40 and r["effective_space"].area == 32
    assert r["targets"]["far"]["location"]["points"] == [(9, 1)]


def test_holes_point_contacts_and_narrow_positive_connection():
    ring = box(0, 0, 8, 8).difference(box(2, 2, 6, 6))
    r = reachable_targets(ring, (1, 4), {"across": (7, 4), "hole": (4, 4)}, unit_mm=1)
    assert r["targets"]["across"]["status"] == "connected_in_supplied_space"
    assert r["targets"]["hole"]["status"] == "unresolved"
    touching = MultiPolygon([box(0, 0, 2, 2), box(2, 2, 4, 4)])
    r = reachable_targets(touching, (1, 1), {"across": (3, 3)}, unit_mm=1)
    assert r["targets"]["across"]["status"] == "disconnected_in_supplied_space"
    thin = unary_union([box(0, 0, 2, 2), box(4, 0, 6, 2), box(1, .999, 5, 1.001)])
    r = reachable_targets(thin, (1, 1), {"across": (5, 1)}, unit_mm=1)
    assert r["targets"]["across"]["status"] == "connected_in_supplied_space"
    assert "passed" not in r  # A point connection does not imply human passage.


@pytest.mark.parametrize("area,start,targets", [(Polygon(), (1, 1), {"t": (1, 1)}),
                                             (box(0, 0, 4, 4), (0, 2), {"t": (1, 1)}),
                                             (box(0, 0, 4, 4), (1, 1), {})])
def test_empty_input_or_unresolved_start_never_gives_success(area, start, targets):
    r = reachable_targets(area, start, targets, unit_mm=1)
    assert r["coverage"] == "none"
    assert all(t["status"] == "unresolved" for t in r["targets"].values())


@pytest.mark.parametrize("unit", [0, -1, float("inf"), float("nan")])
def test_bad_units_do_not_produce_measurements(unit):
    area = box(0, 0, 5, 5)
    with pytest.raises(ValueError):
        annotation_conflicts({"a": area}, unit_mm=unit)
    with pytest.raises(ValueError):
        measure_clear_width(area, LineString([(-1, 2), (6, 2)]), unit_mm=unit)
    with pytest.raises(ValueError):
        reachable_targets(area, (1, 1), {"a": (2, 2)}, unit_mm=unit)


def test_invalid_sections_and_domains_fail_explicitly_without_repair():
    area = box(0, 0, 5, 5)
    bad = Polygon([(0, 0), (2, 2), (0, 2), (2, 0)])
    for line in (LineString([(1, 1), (1, 1)]), LineString([(0, 0), (1, 1), (2, 2)])):
        with pytest.raises(ValueError):
            measure_clear_width(area, line, unit_mm=1)
    with pytest.raises(ValueError):
        reachable_targets(bad, (1, 1), {}, unit_mm=1)
    with pytest.raises(ValueError):
        reachable_targets(area, (1, 1), {}, unit_mm=1, expected_target_ids=["a", "a"])
    with pytest.raises(TypeError):
        annotation_conflicts({}, unit_mm=1, expected_annotation_ids="a")
    with pytest.raises(ValueError):
        geometry_location(Polygon(), precision="empty")


@pytest.mark.parametrize("bad_point", ["12", {1: "x", 2: "y"}, Point(1, 2, 3), (float("nan"), 1)])
def test_unusable_point_stays_unresolved(bad_point):
    r = reachable_targets(box(0, 0, 5, 5), (1, 1), {"bad": bad_point}, unit_mm=1)
    assert r["targets"]["bad"]["status"] == "unresolved" and r["coverage"] == "none"


def test_unrepresentable_pair_measurement_is_not_a_clean_result():
    r = annotation_conflicts({"a": box(0, 0, 2, 2)}, {"b": box(1, 1, 3, 3)}, unit_mm=1e200)
    assert r["coverage"] == "none" and r["unassessed_pairs"]
    assert r["observation"] == "not_assessed"
