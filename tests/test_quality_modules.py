import ezdxf
import pymupdf as fitz
import pytest
import yaml
from ezarch.diagrams import generate_diagrams
from ezarch.drafting import Drawing
from ezarch.geometry import build
from ezarch.graphics import Canvas
from ezarch.project import Project
from ezarch.views import extract_view, generate_views


def two_levels():
    return Project.model_validate(dict(name='Two unrelated floors', materials={'w':{}},
        levels=[{'id':'L0'},{'id':'L1'}],
        elements=[dict(id='low',kind='box',origin=[0,0,0],size=[3000,200,3000],material='w'),
                  dict(id='high',kind='box',origin=[1000,0,3500],size=[2000,200,3000],material='w')],
        rooms=[dict(id='a',name='甲',level='L0',polygon=[[0,0],[3000,0],[3000,3000],[0,3000]]),
               dict(id='b',name='乙',level='L1',polygon=[[0,0],[3000,0],[3000,3000],[0,3000]])],
        views=[dict(id='upper',kind='plan',level='L1',floor_z=3500,cut_z=4700,scale=50,
                    drafting=[],drawing_bounds=[-1000,-1000,5000,5000])]))


def test_multi_level_projection_and_diagram_scope(tmp_path):
    pytest.importorskip('cadquery', reason='Legacy CadQuery compatibility only')
    p=two_levels()
    upper=extract_view(build(p),p.views[0])
    assert min(pt[0] for line in upper['lines'] for pt in line)==pytest.approx(1000)
    assert {c['id'] for c in upper['cuts']}=={'high'}
    with pytest.raises(ValueError,match='--level'):
        generate_diagrams(p,tmp_path/'bad')
    r=generate_diagrams(p,tmp_path/'diagrams','L1')
    assert len(r['areas']['metadata']['areas'])==1
    assert r['areas']['metadata']['areas'][0]['id']=='b'
    generate_views(p,tmp_path/'views')
    with fitz.open(tmp_path/'views/upper.pdf') as pdf:
        assert '乙' in pdf[0].get_text() and '甲' not in pdf[0].get_text()


def test_annotation_scale_and_editability(tmp_path):
    d=Drawing([-3000,-3000,10000,10000],100,'规范符号','T01')
    d.axis('A','y',0,-1000,5000)
    d.dimension([0,0],[4000,0],[0,-1500])
    d.level([2000,2000],3400)
    d.north([7000,7000])
    d.index([6500,2000], '1', 'T02')
    d.section_mark([0,4000],[4000,4000],'1')
    d.furniture('bed',[0,5000],[1800,2100])
    r=d.save(tmp_path/'drawing', view_source='canvas')
    assert not r['text_overflow'] and not r['geometry_overflow']
    doc=ezdxf.readfile(tmp_path/'drawing.dxf')
    # Annotation geometry must not pollute the model-projection comparison layer.
    assert not list(doc.modelspace().query('*[layer=="A-VISIBLE"]'))
    assert list(doc.modelspace().query('DIMENSION'))[0].get_measurement()==4000
    assert any(c.dxf.radius==1200 for c in doc.modelspace().query('CIRCLE'))
    with fitz.open(tmp_path/'drawing.pdf') as pdf:
        assert '3.400' in pdf[0].get_text() and '+3.400' not in pdf[0].get_text()
    with pytest.raises(ValueError):
        d.axis('I','x',0,0,2000)


def test_text_box_wrap_and_overflow():
    c=Canvas(100,100)
    r=c.text_box(5,5,40,50,'方案设计 / A measured public interior with furniture and circulation.',size=3)
    assert r['lines']>1
    with pytest.raises(ValueError,match='overflow'):
        c.text_box(5,5,12,3,'This cannot fit in a single line.',size=3)


def test_gltf_buffer_changes_invalidate_fingerprint_portably(tmp_path):
    import json
    import shutil

    from ezarch.project import fingerprint, read_project
    root=tmp_path/'project'
    root.mkdir()
    (root/'chair.bin').write_bytes(b'original geometry')
    (root/'chair.gltf').write_text(json.dumps({'buffers':[{'uri':'chair.bin'}]}))
    data=two_levels().model_dump()
    data['render']={'asset_instances':[{'id':'chair','file':'chair.gltf'}]}
    (root/'project.yml').write_text(yaml.safe_dump(data))
    a=fingerprint(read_project(root/'project.yml'))
    relocated=tmp_path/'other path'
    shutil.copytree(root,relocated)
    assert fingerprint(read_project(relocated/'project.yml'))==a
    (root/'chair.bin').write_bytes(b'changed geometry')
    assert fingerprint(read_project(root/'project.yml'))!=a


def test_batched_vector_paths_preserve_painter_order(tmp_path):
    from PIL import Image

    c = Canvas(50, 50)
    c.rect(0, 0, 50, 50, fill="#ff0000", stroke=None)
    c.rect(10, 10, 10, 10, fill="#00ff00", stroke=None)
    c.text(20, 30, "X", size=10)
    c.rect(0, 20, 50, 20, fill="#0000ff", stroke=None)
    c.save(tmp_path / "paint", dpi=254)
    with Image.open(tmp_path / "paint.png") as image:
        assert image.getpixel((50, 50))[:3] == (255, 0, 0)
        assert image.getpixel((150, 150))[:3] == (0, 255, 0)
        assert image.getpixel((230, 260))[:3] == (0, 0, 255)
