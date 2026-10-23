"""Small synthetic regressions; real building validation remains outside this repository."""

import ezdxf
import pymupdf as fitz
import pytest
import yaml
from ezarch.geometry import build, generate_model
from ezarch.graphics import Canvas
from ezarch.project import Project, fingerprint, read_project
from ezarch.views import extract_view


def project(**changes):
    data = dict(name='Synthetic opening', materials={'wall': {'color': [.8, .8, .75]}},
                elements=[dict(id='wall', kind='wall', start=[0, 0], end=[6000, 0],
                               height=3000, thickness=300, material='wall',
                               openings=[dict(offset=2000, width=1000, height=2100)])],
                views=[dict(id='plan', kind='plan', cut_z=1200, scale=100),
                       dict(id='section', kind='section', axis='y', at=0, scale=100)],
                dimensions=[dict(id='width', p1=[0, 0], p2=[6000, 0], base=[0, -900], view='plan')])
    data.update(changes)
    return Project.model_validate(data)


def test_input_validation():
    for change in [{'units': 'm'}, {'views': [{'id': '../escape', 'scale': 100}]},
                   {'views': [{'id': 'bad', 'scale': 0}]},
                   {'elements': [dict(id='bad', kind='box', material='wall', origin=[0,0,float('nan')], size=[1,1,1])]}]:
        with pytest.raises(ValueError):
            project(**change)
    p = project().model_dump()
    p['elements'][0]['openings'][0]['width'] = 5000
    with pytest.raises(ValueError, match='exceeds wall'):
        Project.model_validate(p)


def test_dxf_to_model_to_step_and_source_change(tmp_path):
    pytest.importorskip('cadquery', reason='Legacy CadQuery compatibility only')
    source = tmp_path / 'outline.dxf'
    doc = ezdxf.new()
    doc.units = ezdxf.units.M
    doc.layers.new('BOUNDARY')
    doc.modelspace().add_lwpolyline([(0,0),(6,0),(6,4),(0,4)], close=True, dxfattribs={'layer': 'BOUNDARY'})
    doc.saveas(source)
    data = project(elements=[dict(id='from-plan', kind='dxf_extrusion', file='outline.dxf', layer='BOUNDARY', height=3000, material='wall')]).model_dump()
    config = tmp_path / 'project.yml'
    config.write_text(yaml.safe_dump(data))
    p = read_project(config)
    first_hash = fingerprint(p)
    shape = build(p)[0].shape
    assert shape.Volume() == pytest.approx(6000 * 4000 * 3000)
    generate_model(p, tmp_path / 'model')
    data['elements'] = [dict(id='from-step', kind='step', file='model/model.step', material='wall')]
    config.write_text(yaml.safe_dump(data))
    imported = read_project(config)
    assert build(imported)[0].shape.Volume() == pytest.approx(shape.Volume())
    assert extract_view(build(imported), imported.views[0])['cuts']
    doc.modelspace().query('LWPOLYLINE')[0].set_points([(0,0),(7,0),(7,4),(0,4)])
    doc.saveas(source)
    assert fingerprint(p) != first_hash
    assert build(p)[0].shape.Volume() == pytest.approx(7000 * 4000 * 3000)


def test_stair_risers_have_no_accidental_gaps():
    pytest.importorskip('cadquery', reason='Legacy CadQuery compatibility only')
    p = project(elements=[dict(id='stair', kind='stair', origin=[0,0,0], steps=12, rise=160, run=280, width=1200, material='wall')])
    shape = build(p)[0].shape
    assert len(shape.Solids()) == 12
    assert shape.BoundingBox().zmax == pytest.approx(1920)
    solids = sorted(shape.Solids(), key=lambda s: s.BoundingBox().xmin)
    for a,b in zip(solids, solids[1:]):
        assert a.BoundingBox().xmax == pytest.approx(b.BoundingBox().xmin, abs=.0001)


def test_font_has_required_chinese_glyphs():
    from ezarch.project import skill_root
    from fontTools.ttLib import TTFont
    font = TTFont(skill_root() / 'assets/fonts/EZarchFang.ttf')
    cmap = font.getBestCmap()
    assert all(ord(c) in cmap for c in '建筑平面剖面立面仿宋尺寸楼梯墙体')


def test_reference_pdf_vectors_and_calibration(tmp_path):
    from ezarch.intake import reference
    c = Canvas(120, 80)
    c.line(10, 20, 70, 20)
    c.circle(90, 45, 10)
    c.text(10, 60, '建筑参考', size=4)
    c.save(tmp_path / 'source')
    result = reference(tmp_path / 'source.pdf', tmp_path / 'reference')
    assert result['pages'][0]['vector_paths'] >= 3
    assert result['pages'][0]['width_mm'] == pytest.approx(120, abs=.001)
    assert '建筑参考' in (tmp_path / 'reference/page-001.txt').read_text(encoding="utf-8")
    result = reference(tmp_path / 'source.png', tmp_path / 'calibrated', known_mm=6000, pixel_distance=600)
    assert result['calibration']['mm_per_source_pixel'] == 10


def test_mixed_chinese_area_unit_uses_real_superscript(tmp_path):
    c = Canvas(100, 40)
    c.text(10, 20, '160.0 m² 室内面积', size=4)
    report = c.save(tmp_path / 'units')
    assert not report['text_overflow']
    with fitz.open(tmp_path / 'units.pdf') as doc:
        assert '²' in doc[0].get_text()
        assert '室内面积' in doc[0].get_text()


def test_opening_topology_and_units(tmp_path):
    pytest.importorskip('cadquery', reason='Legacy CadQuery compatibility only')
    from ezarch.views import generate_views
    p = project()
    parts = build(p)
    plan = extract_view(parts, p.views[0])
    section = extract_view(parts, p.views[1])
    assert sum(c['area_mm2'] for c in plan['cuts']) == pytest.approx(5000 * 300)
    assert sum(c['area_mm2'] for c in section['cuts']) == pytest.approx(6000 * 3000 - 1000 * 2100)
    assert len(plan['cuts']) == 2  # Door void separates the wall into two islands.
    assert len(section['cuts']) == 1  # The lintel connects both jambs.
    result = generate_model(p, tmp_path / 'model', formats=['step', 'scene', 'glb', '3dm', 'dae'])
    assert result['geometry_valid']
    generate_views(p, tmp_path / 'views')
    dxf = ezdxf.readfile(tmp_path / 'views/plan.dxf')
    assert dxf.units == 4
    assert list(dxf.modelspace().query('DIMENSION'))[0].get_measurement() == pytest.approx(6000)
    with fitz.open(tmp_path / 'views/plan.pdf') as doc:
        assert len(doc[0].get_images()) == 0
        assert len(doc[0].get_drawings()) > 10


def test_board_explicit_scale_and_font(tmp_path):
    from ezarch.board import compose
    c = Canvas(100, 70)
    c.text(10, 15, '仿宋：平面图、剖面图、立面图', size=3)
    c.line(10, 30, 70, 30)
    c.save(tmp_path / 'external')
    template = {'sheets': [{'size_mm': [210, 297], 'items': [dict(type='pdf', file='external.pdf', x=20,y=20,w=100,h=70,scale_lock=True)]}]}
    path = tmp_path / 'board.yml'
    path.write_text(yaml.safe_dump(template))
    assert compose(path, tmp_path / 'board')['pages'] == 1
    with fitz.open(tmp_path / 'board/presentation.pdf') as pdf:
        assert '平面图' in pdf[0].get_text()
        assert pdf[0].rect.width * 25.4 / 72 == pytest.approx(210, abs=.001)
    template['sheets'][0]['items'][0]['w'] = 90
    path.write_text(yaml.safe_dump(template))
    with pytest.raises(ValueError, match='change scale'):
        compose(path, tmp_path / 'fail-scale')
    template['sheets'][0]['items'][0]['w'] = 100
