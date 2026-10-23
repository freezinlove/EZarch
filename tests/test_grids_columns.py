"""Geometry contracts beyond the source projects; no architectural layout recipes."""
import math

import ezdxf
import pytest
from ezarch.drafting import Drawing
from ezarch.frames import transform_points
from ezarch.grids import axis_offset, axis_segment, axis_tag_spacing, draw_axis, draw_axis_tag
from ezarch.symbols import (
    SymbolStyle,
    circular_column_symbol,
    linework_style,
    place_symbol,
    polygon_symbol,
    rectangular_column_symbol,
)
from ezdxf.lldxf.tagwriter import TagCollector
from shapely.geometry import Polygon, box


@pytest.mark.parametrize("mirror", [False, True])
@pytest.mark.parametrize("unit", [1, 1000])
@pytest.mark.parametrize("shape", ["rectangle", "circle", "custom"])
def test_sections_are_native_editable_and_style_independent(tmp_path, mirror, unit, shape):
    if shape == "rectangle":
        symbol = rectangular_column_symbol(430, 710, fill="section")
        assert symbol.nominal_bounds == (-215, -355, 215, 355)
    elif shape == "circle":
        symbol = circular_column_symbol(295, fill="section")
        assert symbol.parts[-1].entity.dxftype() == "CIRCLE"
    else:
        profile = box(200, 300, 900, 1100).difference(box(350, 500, 550, 800))
        symbol = polygon_symbol(profile, unit_mm=1, fill="section")
        assert symbol.nominal_bounds == (200, 300, 900, 1100)  # No forced centering of custom profiles.
    before = [list(TagCollector.dxftags(p.entity)) for p in symbol.parts]
    doc = ezdxf.new()
    styles = [SymbolStyle({"outline": ("#332211", .35)}, {"section": "#bbaacc"}),
              linework_style(outline_mm=.35)]
    placed = [place_symbol(symbol, doc.blocks.new(name), style=style, unit_mm=unit,
                           origin=(7, -9), rotation_deg=38, mirror_x=mirror)
              for name, style in zip(("Filled", "Lines"), styles)]
    assert [p.entity.dxftype() for p in symbol.parts if not p.fill] == [e.dxftype() for e in placed[1].entities]
    def native_geometry(entities):
        return [[(t.code, t.value) for t in TagCollector.dxftags(e)
                 if t.code not in (5, 330, 62, 420, 370)] for e in entities if e.dxftype() != "HATCH"]
    assert native_geometry(placed[0].entities) == native_geometry(placed[1].entities)
    path = tmp_path / "sections.dxf"
    doc.saveas(path)
    restored = ezdxf.readfile(path)
    assert not restored.audit().has_errors
    if shape == "circle":
        circle = next(iter(restored.blocks.get("Lines")))
        assert circle.dxftype() == "CIRCLE" and circle.dxf.radius == pytest.approx(295/unit)
    assert before == [list(TagCollector.dxftags(p.entity)) for p in symbol.parts]


def test_concave_section_preserves_given_profile():
    section = Polygon([(0, 0), (800, 0), (800, 200), (250, 200), (250, 900), (0, 900)])
    symbol = polygon_symbol(section, unit_mm=1)
    assert Polygon(symbol.parts[0].entity.get_points('xy')).equals(section)


def test_axis_trims_and_signed_projection_are_not_endpoint_snapping():
    start, end = (5, 7), (11, 15)  # Direction 3/5, 4/5.
    first, last = axis_segment(start, end, start_trim=2, end_trim=3)
    assert first == pytest.approx((6.2, 8.6))
    assert last == pytest.approx((9.2, 12.6))
    result = axis_offset((10.6, 17.8), start, end, unit_mm=1000)
    assert result['projection'] == pytest.approx((12.2, 16.6))
    assert result['station_mm'] == pytest.approx(12000)
    assert result['signed_offset_mm'] == pytest.approx(2000)
    assert result['within_segment'] is False
    reverse = axis_offset((10.6, 17.8), end, start, unit_mm=1000)
    assert reverse['signed_offset_mm'] == pytest.approx(-2000)
    assert reverse['station_mm'] == pytest.approx(-2000)
    assert reverse['projection'] == pytest.approx(result['projection'])


@pytest.mark.parametrize("angle", [17, 126, 254])
@pytest.mark.parametrize("mirror", [False, True])
def test_projection_is_rigid_transform_and_unit_equivalent(angle, mirror):
    c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    sign = -1 if mirror else 1
    transform = (sign*c, -s, sign*s, c, 2300, -5700)
    a, b, p = transform_points([(0, 0), (9000, 0), (1300, 450)], transform)
    result = axis_offset(p, a, b, unit_mm=1)
    metres = axis_offset([v/1000 for v in p], [v/1000 for v in a], [v/1000 for v in b], unit_mm=1000)
    assert result['station_mm'] == pytest.approx(1300)
    assert result['signed_offset_mm'] == pytest.approx(sign*450)
    assert metres['station_mm'] == pytest.approx(result['station_mm'])
    assert metres['signed_offset_mm'] == pytest.approx(result['signed_offset_mm'])


@pytest.mark.parametrize("unit,scale", [(1, 100), (1000, 100), (1, 1)])
@pytest.mark.parametrize("target", ["model", "paper", "block"])
def test_drawing_adapters_keep_paper_sizes_native_labels_and_resources(tmp_path, unit, scale, target):
    doc = ezdxf.new()
    doc.layers.new('Existing', dxfattribs={'color': 4})
    doc.layers.get('Existing').freeze()
    doc.styles.new('CustomText', dxfattribs={'font': 'custom-font.ttf'})
    doc.header['$LTSCALE'] = 2
    layout = {'model': doc.modelspace, 'paper': doc.paperspace,
              'block': lambda: doc.blocks.new('CustomBlock')}[target]()
    old = layout.add_circle((2, 3), 5)
    before = [list(TagCollector.dxftags(e)) for e in (old, doc.layers.get('Existing'), doc.styles.get('CustomText'))]
    draw = Drawing.from_layout(layout, scale=scale, unit_mm=unit, text_style='CustomText', resource_policy='reuse')
    a, b = (0, 0), (6000/unit, 8000/unit)
    lines = draw_axis(draw, a, b, trim_start_mm=4, trim_end_mm=2, layer='Existing',
                      color='#112233', width=.13, dash=(6, 2, 1, 2))
    first, last = list(lines[0].vertices_in_wcs())
    assert (first.x, first.y) == pytest.approx((.6*4*scale/unit, .8*4*scale/unit))
    assert (last.x, last.y) == pytest.approx((b[0]-.6*2*scale/unit, b[1]-.8*2*scale/unit))
    center = (3300/unit, -750/unit)
    leader = [(2200/unit, 1000/unit), (2200/unit, -750/unit), (center[0]-4*scale/unit, center[1])]
    tag = draw_axis_tag(draw, center, 'I-自定轴42', diameter_mm=8, text_height_mm=2.5,
                        rotation=31, leader=leader, layer='Existing', color='#334455', width=.18)
    assert tag.center == center and tag.radius == 4*scale/unit
    assert len(tag.entities) == 3
    text = tag.entities[-1]
    assert text.dxf.text == 'I-自定轴42'  # No project-specific naming exclusions or truncation.
    assert text.dxf.style == 'CustomText'
    assert text.dxf.height == 2.5*scale/unit and text.dxf.rotation == 31
    assert list(tag.entities[0].get_points('xy')) == leader
    assert before == [list(TagCollector.dxftags(e)) for e in (old, doc.layers.get('Existing'), doc.styles.get('CustomText'))]
    assert doc.header['$LTSCALE'] == 2
    path = tmp_path / 'grid.dxf'
    doc.saveas(path)
    saved = ezdxf.readfile(path)
    assert not saved.audit().has_errors
    assert saved.layers.get('Existing').is_frozen()


def test_circle_spacing_reports_actual_scope_not_text_fit():
    circles = {'wide-name': ((0, 0), 4), 'near': ((6, 0), 4), 'far': ((20, 0), 4)}
    result = axis_tag_spacing(circles, unit_mm=1)
    assert result['checked_ids'] == tuple(circles) and result['pair_count'] == 3
    assert result['pairs'][0]['circle_gap_mm'] == -2
    assert result['pairs'][0]['midpoint'] == (3, 0)
    assert result['pairs'][1]['circle_gap_mm'] == 12
    assert 'text bounds' in result['not_checked']
    assert not {'passed', 'score', 'layout_valid'} & result.keys()
    assert axis_tag_spacing({}, unit_mm=1)['pair_count'] == 0
    assert axis_tag_spacing({'only': ((0, 0), 4)}, unit_mm=1)['pairs'] == []
    scaled = {key: (tuple(v/1000 for v in center), radius/1000) for key, (center, radius) in circles.items()}
    assert axis_tag_spacing(scaled, unit_mm=1000)['pairs'][0]['circle_gap_mm'] == pytest.approx(-2)


@pytest.mark.parametrize('make', [
    lambda: rectangular_column_symbol(0, 500), lambda: rectangular_column_symbol(500, math.inf),
    lambda: circular_column_symbol(-2), lambda: circular_column_symbol(math.nan),
    lambda: axis_segment((0, 0), (0, 0)), lambda: axis_segment((0, 0, 1), (1, 1)),
    lambda: axis_segment((0, 0), (3, 4), start_trim=3, end_trim=2),
    lambda: axis_segment((0, 0), (3, 4), start_trim=-1),
    lambda: axis_offset((1, 2), (0, 0), (3, 4), unit_mm=0),
    lambda: axis_tag_spacing({'bad': ((0, 0), -1)}, unit_mm=1),
    lambda: axis_tag_spacing({'bad': ((0, math.nan), 1)}, unit_mm=1),
])
def test_invalid_inputs_are_not_replaced_by_design_defaults(make):
    with pytest.raises(ValueError):
        make()


@pytest.mark.parametrize('overrides', [{"diameter_mm": -1}, {"text_height_mm": 0},
                                      {"text_color": 'nonsense'}, {"leader": [(0, 0)]}])
def test_bad_tag_does_not_leave_partial_geometry(overrides):
    doc = ezdxf.new()
    draw = Drawing.from_layout(doc.modelspace(), scale=100, unit_mm=1)
    args = {'diameter_mm': 8, 'text_height_mm': 2.5} | overrides
    with pytest.raises(ValueError):
        draw_axis_tag(draw, (0, 0), 'A', **args)
    assert not list(doc.modelspace())


def test_new_drawing_canvas_and_cad_get_the_same_selected_elements(tmp_path):
    draw = Drawing((-1000, -1000, 9000, 9000), scale=100)
    draw_axis(draw, (0, 0), (6000, 8000), trim_start_mm=4, dash=(6, 2))
    tag = draw_axis_tag(draw, (0, 0), 'Q7', diameter_mm=8, text_height_mm=2.5)
    assert len(tag.entities) == 2 and len(draw.entities) == 3
    draw.save(tmp_path/'grid', formats=['dxf', 'svg'])
    svg = (tmp_path/'grid.svg').read_text()
    assert '<circle' in svg and 'Q7' in svg and 'stroke-dasharray' in svg
