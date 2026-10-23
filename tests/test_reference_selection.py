import json

import ezdxf
import pymupdf as fitz
import pytest
from ezarch import references, selection
from ezarch.cad import sha256


def source_pdf(path):
    doc = fitz.open()
    for _ in range(2):
        page = doc.new_page(width=300, height=200)
        shape = page.new_shape()
        shape.draw_bezier((20, 30), (50, 0), (90, 60), (120, 30))
        shape.finish(color=(0, 0, 0))
        shape.commit()
        page.draw_rect((40, 70, 100, 120), color=(0, 0, 0), fill=(.8, .9, .8))
        page.insert_text((20, 170), 'Reference page')
        page.draw_circle((250, 100), 20)
    doc.save(path)
    doc.close()


def test_selected_pdf_extraction_affine_and_native_paths(tmp_path):
    path = tmp_path / 'source.pdf'
    source_pdf(path)
    original = sha256(path)
    report = references.extract_reference(path, tmp_path / 'extract', pages=[2], region=(0, 0, 150, 190))
    assert not (tmp_path / 'extract/page-001.png').exists()
    with fitz.open(tmp_path / 'extract/page-002.pdf') as clipped:
        assert clipped[0].rect.width == 150
        assert any(i[0] == 'c' for p in clipped[0].get_drawings() for i in p['items'])
    paths = json.loads((tmp_path / 'extract/page-002.paths.json').read_text())
    assert paths and report['pages'][0]['page'] == 2
    transform = references.fit_reference_transform([(0, 0), (1, 0), (0, 1), (1, 1)], [(10, 20), (12, 20), (10, 18), (12, 18)])
    assert transform['transform'] == pytest.approx((2, 0, 0, -2, 10, 20))
    doc = ezdxf.new()
    with fitz.open(path) as source:
        mapped = references.map_reference_geometry(source[1].get_drawings(extended=True), doc.modelspace(), transform=transform['transform'])
    assert not mapped['skipped']
    assert len(doc.modelspace().query('SPLINE')) >= 1
    assert len(doc.modelspace().query('HATCH')) == 1
    assert sha256(path) == original
    other = tmp_path / 'duplicate.pdf'
    other.write_bytes(path.read_bytes())
    assert references.catalog_sources([path, other])[1]['duplicate_of'] == str(path)


def test_path_clipping_is_not_silently_dropped(tmp_path):
    path = tmp_path / 'source.pdf'
    source_pdf(path)
    with fitz.open(path) as source:
        paths = source[0].get_drawings(extended=True)
    doc = ezdxf.new()
    result = references.map_reference_geometry(paths, doc.modelspace(), transform=(1, 0, 0, -1, 0, 0), region=(0, 0, 10, 10))
    assert not result['entities'] and result['skipped']


def test_nested_selection_transforms_overrides_and_source_preservation(tmp_path):
    doc = ezdxf.new('R2018')
    doc.units = 4
    inner = doc.blocks.new('inner')
    line = inner.add_line((0, 0), (100, 0))
    outer = doc.blocks.new('outer')
    outer.add_blockref('inner', (10, 20), dxfattribs={'rotation': 90})
    instance = doc.modelspace().add_blockref('outer', (1000, 2000))
    selected = selection.select_entities(doc, nested=True)
    row = selected['selected'][0]
    assert row.source_handle == line.dxf.handle and instance.dxf.handle in row.instance_path
    assert tuple(row.entity.dxf.start) == pytest.approx((1010, 2020, 0))
    assert tuple(row.entity.dxf.end) == pytest.approx((1010, 2120, 0))
    doc.saveas(tmp_path / 'before.dxf')
    before = sha256(tmp_path / 'before.dxf')
    selection.render_view(doc, tmp_path / 'view', selection=selected, overrides={row.id: {'true_color': 0xCC3322}},
                          region=(900, 1900, 1200, 2300), scale=10)
    doc.saveas(tmp_path / 'after.dxf')
    # Source geometry and colors remain original; serialization metadata may differ.
    assert line.dxf.color == 256 and len(doc.modelspace()) == 1
    assert before == sha256(tmp_path / 'before.dxf')


def test_replacement_keeps_other_geometry_and_version_bound_patch(tmp_path):
    doc = ezdxf.new()
    doc.units = 4
    line = doc.modelspace().add_line((0, 0), (1000, 0))
    retained = doc.modelspace().add_circle((1000, 1000), 200)
    doc.layouts.new('Retained sheet')
    replacement = ezdxf.new().modelspace().add_line((0, 100), (1000, 100))
    result, info = selection.replace_selection(doc, [line.dxf.handle], [replacement])
    assert len(doc.modelspace()) == 2 and result.entitydb[retained.dxf.handle].dxf.radius == 200
    assert result.layouts.get('Retained sheet') is not None
    diff = selection.compare_documents(doc, result)
    assert line.dxf.handle in diff['removed'] and set(info['added']) <= set(diff['added'])
    preview = selection.preview_changes(doc, result, tmp_path / 'comparison', region=(-300, -300, 1500, 1500), scale=20)
    assert preview['before']['width_mm'] == preview['after']['width_mm']
    doc.saveas(tmp_path / 'source.dxf')
    with pytest.raises(ValueError, match='Source changed'):
        selection.patch_document(tmp_path / 'source.dxf', tmp_path / 'patch.dxf', [line.dxf.handle], [replacement], expected_sha256='wrong')
    assert not (tmp_path / 'patch.dxf').exists()


@pytest.mark.parametrize('rotation', [0, 90, 180, 270])
def test_rotated_pdf_crop_matches_original_pixels(tmp_path, rotation):
    from PIL import Image, ImageChops, ImageStat
    source_pdf(tmp_path / 'plain.pdf')
    with fitz.open(tmp_path / 'plain.pdf') as doc:
        doc[0].set_rotation(rotation)
        doc.save(tmp_path / 'rotated.pdf')
    references.extract_reference(tmp_path / 'rotated.pdf', tmp_path / 'crop', pages=[1], region=(10,10,160,180), dpi=144)
    with fitz.open(tmp_path / 'crop/page-001.pdf') as doc:
        pixmap = doc[0].get_pixmap(dpi=144, alpha=False)
    rendered = Image.frombytes('RGB', (pixmap.width, pixmap.height), pixmap.samples)
    original = Image.open(tmp_path / 'crop/page-001.png').convert('RGB')
    assert original.size == rendered.size
    assert max(ImageStat.Stat(ImageChops.difference(original, rendered)).mean) < .01
