"""Regression checks for task-selected output and preservation of user choices."""
import math

import ezdxf
import pymupdf as fitz
import pytest
from ezarch.drafting import Drawing
from ezarch.graphics import Canvas
from ezarch.project import Project, skill_root


def simple_project():
    return Project(name='Export choice', materials={'a': {'color': [.5, .6, .7]}},
                   elements=[dict(id='part', kind='box', origin=[0, 0, 0], size=[4000, 2000, 3000], material='a')],
                   views=[dict(id='cut', kind='plan', cut_z=1200, scale=100)])


def test_drawing_without_frame_selected_formats_and_repeated_save(tmp_path):
    d = Drawing([0, 0, 10000, 5000], scale=100, title='Not a requested title')
    d.line([1000, 1000], [9000, 1000])
    d.save(tmp_path / 'plain', formats=['pdf'])
    assert not (tmp_path / 'plain.dxf').exists()
    assert not (tmp_path / 'plain.svg').exists()
    with fitz.open(tmp_path / 'plain.pdf') as pdf:
        assert pdf[0].get_text() == ''
        assert pdf[0].rect.height * 25.4 / 72 == pytest.approx(74, abs=.001)
        lengths = [abs(item[2].x - item[1].x) * 25.4 / 72
                   for path in pdf[0].get_drawings() for item in path['items'] if item[0] == 'l']
        assert any(abs(length - 80) < .001 for length in lengths)


def test_custom_font_and_oblique_text_remain_editable(tmp_path):
    c = Canvas(160, 100, font=skill_root() / 'assets/fonts/FandolFang-Regular.otf')
    c.text(40, 60, '倾斜标注 ABC', rotation=32, size=5)
    c.save(tmp_path / 'angle', formats=['pdf', 'svg'])
    with fitz.open(tmp_path / 'angle.pdf') as pdf:
        line = pdf[0].get_text('dict')['blocks'][0]['lines'][0]
        assert line['dir'] == pytest.approx([math.cos(math.radians(32)), -math.sin(math.radians(32))])
        assert '倾斜标注 ABC' in pdf[0].get_text().replace('\xa0', ' ')
        assert 'FandolFang' in line['spans'][0]['font']
    assert '<text ' in (tmp_path / 'angle.svg').read_text()
    assert not (tmp_path / 'angle.png').exists()


def test_symbol_parameters_reach_saved_geometry(tmp_path):
    d = Drawing([-2000, -2000, 12000, 12000], style={
        'axis_circle_diameter_mm': 10, 'index_circle_diameter_mm': 12,
        'north_circle_diameter_mm': 30, 'section_position_length_mm': 9,
        'section_direction_length_mm': 6, 'excluded_axis_labels': []})
    d.axis('I', 'x', 0, 0, 5000)
    d.index([4000, 4000], '1', '2')
    d.north([8000, 8000])
    d.section_mark([0, 8000], [4000, 8000], 'S')
    d.save(tmp_path / 'symbols', formats=['dxf'])
    ms = ezdxf.readfile(tmp_path / 'symbols.dxf').modelspace()
    assert sorted(c.dxf.radius for c in ms.query('CIRCLE')) == [500, 500, 600, 1500]
    lengths = [math.dist(*list(e.get_points('xy'))) for e in ms.query('LWPOLYLINE[layer=="A-CUT"]')]
    assert sorted(lengths) == [600, 600, 900, 900]


def test_selected_model_and_view_exports_without_siblings(tmp_path):
    pytest.importorskip('cadquery', reason='Legacy CadQuery compatibility only')
    from ezarch.geometry import generate_model
    from ezarch.views import generate_views
    p = simple_project()
    generate_model(p, tmp_path / 'model', formats=['scene', 'glb'])
    assert not (tmp_path / 'model/model.step').exists()
    assert not (tmp_path / 'model/model.dae').exists()
    import trimesh
    glb = trimesh.load(tmp_path / 'model/model.glb', force='scene')
    assert glb.metadata['ezarch_up_axis'] == 'Y'
    assert glb.bounds.tolist() == [[0, 0, -2], [4, 3, 0]]
    generate_views(p, tmp_path / 'views', formats=['pdf'])
    assert not (tmp_path / 'views/cut.dxf').exists()
