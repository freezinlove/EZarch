
import unicodedata

import ezdxf
import pymupdf as fitz
import pytest
from ezarch.fonts import FontFace
from ezarch.graphics import Canvas
from ezarch.project import skill_root
from ezarch.site_symbols import canopy_symbol, direction_symbol, road_symbol, route_symbol
from ezarch.symbols import linework_style, place_symbol
from fontTools.ttLib import TTCollection, TTFont


def test_explicit_route_direction_and_road_geometry():
    symbol = route_symbol([(0, 0), (3000, 1000), (5000, 1000)], head_length=300, head_width=200)
    assert symbol.anchors['end'] == (5000, 1000)
    direction = direction_symbol((0, 2), length=1000, head_length=200, head_width=100)
    assert direction.anchors['end'] == (0, 1000)
    road = road_symbol([(0, 0), (10000, 0)], left_width=1000, right_width=2000, join='mitre', centerline=True)
    assert road.geometry_bounds() == pytest.approx((0, -2000, 10000, 1000))
    tree = canopy_symbol(radius=2000, trunk_radius=100, pit=[(-400,-400),(400,-400),(400,400),(-400,400)])
    doc = ezdxf.new('R2010')
    a = place_symbol(tree, doc.modelspace(), style=linework_style(), unit_mm=1, origin=(5000, 1000), rotation_deg=37)
    assert len(a.entities) == 3
    with pytest.raises(ValueError):
        direction_symbol((0, 0), length=100, head_length=20, head_width=10)


def test_per_text_font_collection_face_and_outline(tmp_path):
    font = skill_root() / 'assets/fonts/EZarchFang.ttf'
    collection = TTCollection()
    collection.fonts = [TTFont(font), TTFont(font)]
    path = tmp_path / 'fonts.ttc'
    collection.save(path)
    collection.close()
    canvas = Canvas(120, 70, font_roles={'notes': FontFace(path, 1)})
    canvas.text(10, 20, '建筑 ABC 123', size=5, font_role='notes')
    canvas.text_box(10, 30, 90, 30, 'Annotation with selected face', font=font)
    report = canvas.save(tmp_path / 'editable', formats={'pdf', 'svg'})
    assert report['font_faces'][0]['index'] == 1
    with fitz.open(tmp_path / 'editable.pdf') as doc:
        assert 'ABC 123' in unicodedata.normalize('NFKC', doc[0].get_text())
        assert doc[0].get_fonts()
    assert '<tspan font-family="EZFace' in (tmp_path / 'editable.svg').read_text()
    canvas.save(tmp_path / 'outlined', formats={'svg'}, svg_text='outline')
    assert '<text' not in (tmp_path / 'outlined.svg').read_text()


def test_shaped_text_and_svg_composition(tmp_path):
    canvas = Canvas(140, 100)
    canvas.rich_text(5, 5, 130, 70, '<p>建筑 — office ffi</p><p dir="rtl">مرحبا بالعالم</p>',
                     css='body{font-size:14pt;margin:0}')
    report = canvas.save(tmp_path / 'rich', formats={'pdf', 'svg'})
    assert report['rich_text'][0]['scale'] == 1
    with fitz.open(tmp_path / 'rich.pdf') as doc:
        assert 'office' in unicodedata.normalize('NFKC', doc[0].get_text())
    graphic = tmp_path / 'shape.svg'
    graphic.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><defs><clipPath id="clip"><circle cx="50" cy="50" r="40"/></clipPath></defs><rect width="100" height="100" fill="blue" clip-path="url(#clip)"/></svg>')
    canvas = Canvas(120, 70)
    canvas.svg(graphic, 5, 5, 50, 50)
    canvas.svg(graphic, 65, 5, 50, 50)
    canvas.save(tmp_path / 'combined', formats={'pdf', 'svg'})
    import re
    ids = re.findall(r'\bid="([^"]+)"', (tmp_path / 'combined.svg').read_text())
    assert len(ids) == len(set(ids))
    assert (tmp_path / 'combined.pdf').stat().st_size > 500


def test_rich_text_no_unrequested_shrink(tmp_path):
    canvas = Canvas(50, 50)
    canvas.rich_text(0, 0, 5, 2, '<p>Long text that cannot fit</p>', css='body{font-size:20pt}')
    with pytest.raises(ValueError, match='does not fit'):
        canvas.save(tmp_path / 'bad')
