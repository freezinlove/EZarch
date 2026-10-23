"""Actual exported geometry, physical scale and edit propagation across view adapters."""
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import ezdxf
import numpy as np
import pymupdf as fitz
import pytest
import yaml
from ezarch.analysis import oriented_footprint, shadow_vector, solar_position, swing_envelope
from ezarch.annotations import text_footprint
from ezarch.board import compose
from ezarch.cad import plot
from ezarch.drafting import Drawing
from ezarch.fonts import measure_text
from ezarch.furniture import furniture_symbol
from ezarch.graphics import PT, Canvas
from ezarch.intake import brief
from ezarch.project import Project, skill_root
from ezarch.symbols import Symbol, color_style, linework_style
from shapely.geometry import Polygon


def pdf_pixels(path):
    with fitz.open(path) as doc:
        pix = doc[0].get_pixmap(dpi=254, alpha=False)
        return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3).copy()


def test_native_save_tracks_entities_layers_and_exact_page(tmp_path):
    d = Drawing((0, 0, 10000, 5000), scale=100)
    line, = d.line((1000, 1000), (9000, 1000), width=.25)
    d.save(tmp_path/'before', formats={'pdf'})
    line.translate(0, 2000, 0)
    d.doc.layers.get('A-VISIBLE').rgb = (255, 0, 0)
    d.ms.add_circle((2000, 2000), 500, dxfattribs={'true_color': 0x0000ff})
    report = d.save(tmp_path/'after', formats={'dxf', 'svg', 'pdf', 'png'})
    with fitz.open(tmp_path/'after.pdf') as doc:
        assert doc[0].rect.width / PT == pytest.approx(124, abs=.001)
        assert doc[0].rect.height / PT == pytest.approx(74, abs=.001)
        line_path, = [p for p in doc[0].get_drawings() if p['color'] == (1, 0, 0)]
        assert line_path['rect'].x0 / PT == pytest.approx(22, abs=.001)
        assert line_path['rect'].y0 / PT == pytest.approx(32, abs=.001)
        assert line_path['rect'].width / PT == pytest.approx(80, abs=.001)
        assert line_path['width'] / PT == pytest.approx(.25)
    assert report['view_source'] == 'native_cad' and not report['skipped']
    assert not np.array_equal(pdf_pixels(tmp_path/'before.pdf'), pdf_pixels(tmp_path/'after.pdf'))
    assert ET.parse(tmp_path/'after.svg').getroot().attrib['width'] == '124.0mm'
    assert ezdxf.readfile(tmp_path/'after.dxf').entitydb[line.dxf.handle].get_points("xy")[0][1] == 3000


@pytest.mark.parametrize('style_factory', [color_style, linework_style])
def test_drawing_and_canvas_share_component_geometry_and_live_edits(tmp_path, style_factory):
    symbol = furniture_symbol('wc', 400, 680)
    style = style_factory()
    d = Drawing((-1000, -1000, 2000, 2000), scale=20, margin=0)
    a = d.symbol(symbol, origin=(350, 500), rotation_deg=37, mirror_x=True, style=style)
    c = Canvas(150, 150)
    b = c.symbol(symbol, origin=(67.5, 75), scale=20, rotation_deg=37, mirror_x=True, style=style)
    d.save(tmp_path/'drawing', formats={'pdf'})
    c.save(tmp_path/'canvas', formats={'pdf', 'svg'})
    assert len(a.entities) == len(b.entities)
    # Same source curves and display backend, aligned through different coordinate systems.
    first = pdf_pixels(tmp_path/'drawing.pdf')
    second = pdf_pixels(tmp_path/'canvas.pdf')
    assert np.mean(np.abs(first.astype(float)-second.astype(float))) < .1
    for entity in a.entities:
        entity.translate(300, -100, 0)
    for entity in b.entities:
        entity.translate(300, -100, 0)
    d.save(tmp_path/'drawing-edit', formats={'pdf'})
    c.save(tmp_path/'canvas-edit', formats={'pdf'})
    assert not np.array_equal(first, pdf_pixels(tmp_path/'drawing-edit.pdf'))
    assert np.mean(np.abs(pdf_pixels(tmp_path/'drawing-edit.pdf').astype(float)
                         -pdf_pixels(tmp_path/'canvas-edit.pdf').astype(float))) < .1
    svg = (tmp_path/'canvas.svg').read_text()
    assert '<image' not in svg and '<path' in svg


def test_canvas_cad_preserves_origin_units_transparency_and_vector_text(tmp_path):
    doc = ezdxf.new()
    doc.units = ezdxf.units.M
    doc.modelspace().add_circle((2, 3), 1, dxfattribs={'true_color': 0xff0000, 'lineweight': 50})
    canvas = Canvas(100, 100, background='#00ff00')
    canvas.cad(doc, origin=(10, 70), scale=100)
    canvas.text(5, 90, 'editable text')
    canvas.save(tmp_path/'embedded', formats={'pdf', 'svg'})
    with fitz.open(tmp_path/'embedded.pdf') as pdf:
        assert 'editable text' in pdf[0].get_text()
        red, = [p for p in pdf[0].get_drawings() if p['color'] == (1, 0, 0)]
        assert tuple(v/PT for v in red['rect']) == pytest.approx((20, 30, 40, 50), abs=.01)
    pixels=pdf_pixels(tmp_path/'embedded.pdf')
    assert tuple(pixels[400, 300]) == (0, 255, 0)  # Hole/background, no white CAD rectangle.


def test_canvas_handles_linear_component_and_invalid_scale(tmp_path):
    symbol=Symbol()
    symbol.line([(0,0), (1000,0)])
    c=Canvas(80,80)
    c.symbol(symbol, origin=(20,40), scale=25, style=linework_style())
    c.save(tmp_path/'line', formats={'pdf'})
    with fitz.open(tmp_path/'line.pdf') as pdf:
        black, = [p for p in pdf[0].get_drawings() if p['color'] == (0,0,0)]
        assert black['rect'].width/PT == pytest.approx(40, abs=.001)
    for scale in [0, -1, float('nan')]:
        with pytest.raises(ValueError):
            c.symbol(symbol, origin=(0,0), scale=scale, style=linework_style())


def test_native_fills_keep_holes_and_support_selection(tmp_path):
    d=Drawing((0,0,100,100), scale=1, margin=0)
    d.rect(0,0,100,100, color=None, fill='#00aa00')
    shapes=d.poly([(10,10),(90,10),(90,90),(10,90)], close=True,
                 holes=[[(30,30),(70,30),(70,70),(30,70)]], color=None, fill='#ee0000')
    d.save(tmp_path/'holes', formats={'pdf'})
    pixels=pdf_pixels(tmp_path/'holes.pdf')
    assert tuple(pixels[500,500]) == (0,170,0)
    assert tuple(pixels[200,200]) == (238,0,0)
    plot(d.doc, tmp_path/'selection', scale=1, handles=[shapes[0].dxf.handle],
         region=(0,0,100,100), formats={'svg'})
    assert (tmp_path/'selection.svg').is_file() and not (tmp_path/'selection.pdf').exists()


def test_direct_measurements_remain_available():
    sun=solar_position(0,0,datetime(2026,3,20,12,tzinfo=timezone.utc))
    assert sun['altitude_deg'] > 85
    assert shadow_vector(3000, {'altitude_deg':45, 'azimuth_deg':180})[1] == pytest.approx(3000)
    assert Polygon(swing_envelope((0,0),900,0)).area == pytest.approx(np.pi*900**2/4, rel=.001)
    assert Polygon(oriented_footprint((300,500),(400,100),37)).area == pytest.approx(150000)
    measurement=measure_text('Aa', skill_root()/'assets/fonts/EZarchFang.ttf', size_mm=3, rotation=37)
    footprint=text_footprint(measurement, kind='ink')
    assert list(footprint.geometry.exterior.coords)[:4] == pytest.approx(measurement['ink']['corners_mm'])


def test_board_allows_overlap_crop_and_reports_resolution(tmp_path):
    from PIL import Image
    Image.new('RGB',(20,20),'red').save(tmp_path/'image.png')
    items=[dict(type='image', file='image.png', x=-10,y=0,w=80,h=80),
           dict(type='image', file='image.png', x=10,y=10,w=80,h=80)]
    template=tmp_path/'board.yml'
    template.write_text(yaml.safe_dump({'sheets':[{'size_mm':[100,100], 'items':items}]}))
    result=compose(template,tmp_path/'board', formats={'pdf'})
    assert result['sheets'][0]['image_checks'][0]['effective_ppi'] < 10
    items[0]['minimum_ppi']=100
    template.write_text(yaml.safe_dump({'sheets':[{'size_mm':[100,100], 'items':items}]}))
    with pytest.raises(ValueError,match='resolution'):
        compose(template,tmp_path/'limited', formats={'pdf'})
    project=Project(name='Boundary sums', materials={}, elements=[], rooms=[dict(id=str(i),name=str(i),polygon=[(0,0),(1000,0),(1000,1000),(0,1000)]) for i in range(2)])
    assert brief(project,tmp_path/'areas')['interior_boundary_area_m2'] == 2


def test_native_text_uses_explicit_font_outlines_without_changing_dxf_style(tmp_path):
    from ezdxf.lldxf.tagwriter import TagCollector
    d = Drawing((0, 0, 100, 100), scale=1, margin=0)
    entity, = d.text((50, 50), "建筑 Aa", size=4, align="center", rotation=0)
    before = list(TagCollector.dxftags(entity))
    style_name = d.doc.styles.get(d.text_style).dxf.font
    d.save(tmp_path/'text-native', formats={'pdf'})
    assert list(TagCollector.dxftags(entity)) == before
    assert d.doc.styles.get(d.text_style).dxf.font == style_name
    with fitz.open(tmp_path/'text-native.pdf') as pdf:
        assert pdf[0].get_text() == ''  # CAD text is outlined in the current-entity view.
        bounds = fitz.Rect()
        for path in pdf[0].get_drawings():
            if path['fill'] != (1, 1, 1):
                bounds |= path['rect']
    measurement = measure_text("建筑 Aa", d.canvas.font_path, size_mm=4, origin=(50,50),
                               size_mode='cap', align='center', valign='middle', rotation=0)
    # Actual outlined glyph bounds must match the selected font, not a fallback.
    xmin,ymin,xmax,ymax = measurement['ink']['bbox_mm']
    assert tuple(v/PT for v in bounds) == pytest.approx((xmin, 100-ymax, xmax, 100-ymin), abs=.02)
