"""Area-operation contracts, without private project geometry or repair policy."""
import math

import ezdxf
import pytest
import shapely
from ezarch.symbols import Symbol, SymbolStyle, linework_style, place_symbol, polygon_symbol
from ezarch.wall_regions import compose_wall_regions, opening_region, wall_band, wall_region
from shapely import affinity
from shapely.geometry import LineString, MultiLineString, MultiPolygon, Polygon, box


@pytest.mark.parametrize("cap,area,bounds", [("flat", 20, (0, -1, 10, 1)),
                                            ("square", 24, (-1, -1, 11, 1))])
def test_full_width_and_explicit_end_cap(cap, area, bounds):
    wall = wall_region(LineString([(0, 0), (10, 0)]), width=2, cap=cap, join="mitre")
    assert wall.area == pytest.approx(area)
    assert wall.bounds == bounds


@pytest.mark.parametrize("points", [[(0, 4), (0, 0), (4, 0)],
                                    [(0, 0), (4, 0), (6, 3)]])
@pytest.mark.parametrize("join", ["mitre", "bevel"])
def test_corner_geometry_matches_explicit_buffer_and_rotates(points, join):
    path = LineString(points)
    before = path.wkb
    wall = wall_region(path, width=.3, cap="flat", join=join, mitre_limit=3)
    assert wall.equals(path.buffer(.15, cap_style="flat", join_style=join, mitre_limit=3))
    rotated = wall_region(affinity.rotate(path, 37, origin=(0, 0)), width=.3, cap="flat", join=join,
                          mitre_limit=3)
    assert affinity.rotate(wall, 37, origin=(0, 0)).symmetric_difference(rotated).area < 1e-12
    assert path.wkb == before


@pytest.mark.parametrize("vertical", [[(5, 0), (5, 4)], [(5, -4), (5, 4)]])
def test_t_and_x_intersections_are_area_unions(vertical):
    paths = MultiLineString([[(0, 0), (10, 0)], vertical])
    wall = wall_region(paths, width=2, cap="flat", join="mitre")
    separate = compose_wall_regions({str(i): wall_region(p, width=2, cap="flat", join="mitre")
                                     for i, p in enumerate(paths.geoms)})
    assert wall.equals(separate.geometry)
    assert wall.is_valid


def test_band_respects_holes_and_reports_consumed_inner_space():
    region = box(0, 0, 10, 8).difference(box(3, 3, 7, 5))
    band = wall_band(region, inside=.2, outside=.1, join="mitre")
    assert band.equals(region.buffer(.1, join_style=2).difference(region.buffer(-.2, join_style=2)))
    assert len(band.geoms) == 2
    assert wall_band(box(0, 0, 1, 1), inside=2, outside=0, join="mitre").equals(box(0, 0, 1, 1))


def test_opening_orientation_units_and_left_offset():
    opening = opening_region((0, 0), (4, 0), depth=2, offset=3)
    assert opening.equals(box(0, 2, 4, 4))
    assert opening_region((4, 0), (0, 0), depth=2, offset=3).equals(box(0, -4, 4, -2))
    diagonal = opening_region((0, 0), (3, 4), depth=2)
    assert diagonal.area == pytest.approx(10)
    assert diagonal.centroid.coords[0] == pytest.approx((1.5, 2))
    scaled = opening_region((0, 0), (3000, 4000), depth=2000)
    assert affinity.scale(diagonal, 1000, 1000, origin=(0, 0)).equals(scaled)


def test_composition_reports_actual_selection_overlaps_and_partial_cuts():
    sources = {"a": box(0, 0, 6, 2), "b": box(4, 0, 10, 2)}
    cuts = {"partial": box(1, 1, 2, 3), "same": box(1, 1, 2, 3),
            "touch": box(3, 2, 4, 3), "away": box(20, 20, 21, 21)}
    before = {k: v.wkb for k, v in (sources | cuts).items()}
    result = compose_wall_regions(sources, cuts=cuts, clip=box(0, -1, 8, 4))
    assert result.geometry.area == 15
    assert result.removed.area == 1  # Duplicate masks do not double-count removed area.
    assert result.clipped_out.area == 4
    assert result.cut_effects["partial"].area == result.cut_effects["same"].area == 1
    assert result.cut_effects["touch"].geom_type == "LineString"
    assert result.unused_cuts == ("touch", "away")
    assert sum(v.area for v in result.by_source.values()) == 19  # Attribution can overlap.
    assert before == {k: v.wkb for k, v in (sources | cuts).items()}


def test_empty_and_mixed_dimension_overlays_remain_polygonal():
    source = box(0, 0, 2, 2)
    result = compose_wall_regions({"a": source}, clip=box(2, 0, 3, 2))
    assert result.geometry.is_empty and result.by_source["a"].is_empty
    assert result.geometry.geom_type == "Polygon"
    assert result.clipped_out.equals(source)
    result = compose_wall_regions({"a": source}, cuts={"all": source})
    assert result.geometry.is_empty and result.removed.equals(source)
    other = box(4, 0, 6, 2)
    result = compose_wall_regions({"a": MultiPolygon([source, other])}, clip=box(1, 0, 4, 2))
    assert result.geometry.equals(box(1, 0, 2, 2))
    assert result.by_source["a"].equals(result.geometry)


@pytest.mark.parametrize("make", [
    lambda: wall_region(LineString([(0, 0), (1, 1)]), width=0, cap="flat", join="mitre"),
    lambda: wall_region(LineString([(0, 0, 1), (1, 1, 1)]), width=1, cap="flat", join="mitre"),
    lambda: wall_region(shapely.from_wkt("LINESTRING M (0 0 1, 1 1 2)"), width=1, cap="flat", join="mitre"),
    lambda: wall_region(LineString([(0, 0), (1, 1)]), width=1, cap="round", join="mitre"),
    lambda: wall_region(LineString([(0, 0), (1, 1)]), width=1, cap="flat", join="round"),
    lambda: wall_band(box(0, 0, 1, 1), inside=0, outside=0, join="mitre"),
    lambda: wall_band(box(0, 0, 1, 1), inside=-1, outside=1, join="mitre"),
    lambda: wall_band(Polygon([(0, 0), (2, 2), (0, 2), (2, 0)]), inside=1, outside=0, join="mitre"),
    lambda: opening_region((0, 0), (0, 0), depth=2),
    lambda: opening_region((0, 0), (1, 1), depth=math.inf),
    lambda: opening_region((math.nan, 0), (1, 1), depth=2),
    lambda: compose_wall_regions({}),
    lambda: compose_wall_regions({"": box(0, 0, 1, 1)}),
    lambda: compose_wall_regions({"empty": Polygon()}),
])
def test_invalid_input_is_rejected_without_repair(make):
    with pytest.raises((ValueError, TypeError)):
        make()


def test_polygon_holes_shared_style_and_native_roundtrip(tmp_path):
    geometry = box(10, 20, 14, 24).difference(box(11, 21, 13, 23))
    symbol = polygon_symbol(geometry, unit_mm=1000, fill="wall")
    assert symbol.nominal_bounds == (10000, 20000, 14000, 24000)
    doc = ezdxf.new()
    kwargs = {"unit_mm": 1000, "origin": (4, 7), "rotation_deg": 29, "mirror_x": True}
    fill = place_symbol(symbol, doc.blocks.new("Filled"), style=SymbolStyle({"outline": ("#000000", .25)},
                                                                                 {"wall": "#dedede"}), **kwargs)
    lines = place_symbol(symbol, doc.blocks.new("Lines"), style=linework_style(outline_mm=.25), **kwargs)
    hatch = fill.entities[0]
    assert hatch.dxftype() == "HATCH" and len(hatch.paths) == 2
    assert [p.path_type_flags for p in hatch.paths] == [3, 18]
    assert len(lines.entities) == 2 and all(e.dxftype() == "LWPOLYLINE" for e in lines.entities)
    assert [list(e.get_points()) for e in fill.entities[1:]] == [list(e.get_points()) for e in lines.entities]
    path = tmp_path / "rings.dxf"
    doc.saveas(path)
    restored = ezdxf.readfile(path)
    assert not restored.audit().has_errors
    assert len(next(iter(restored.blocks.get("Filled"))).paths) == 2
    # Mirroring may invert OCS; compare world coordinates rather than forcing +Z.
    for saved, placed in zip(restored.blocks.get("Lines"), lines.entities):
        assert list(saved.vertices_in_wcs()) == list(placed.vertices_in_wcs())
    assert polygon_symbol(Polygon(), unit_mm=1).parts == []


def test_polygon_builder_rejects_outside_hole_without_partial_write():
    symbol = Symbol()
    with pytest.raises(ValueError):
        symbol.polygon(list(box(0, 0, 2, 2).exterior.coords),
                       holes=[list(box(4, 4, 5, 5).exterior.coords)], fill="wall")
    assert symbol.parts == []
