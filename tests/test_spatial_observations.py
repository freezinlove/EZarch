"""Evidence, scope and nonmutation tests, with no project layout fixtures."""

from ezarch.measurements import measure_clear_width
from shapely.geometry import LineString, Polygon, box


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
