import zipfile

import pymupdf as fitz
import pytest
from ezarch import cad, delivery


def test_batch_failure_and_resume_are_per_file(tmp_path, monkeypatch):
    a, b = tmp_path / 'a.dxf', tmp_path / 'b.dxf'
    a.write_bytes(b'A')
    b.write_bytes(b'B')
    calls = []
    def convert(source, target, **kwargs):
        calls.append(source)
        if source == b:
            raise RuntimeError('synthetic converter failure')
        target = __import__('pathlib').Path(target)
        if target.exists():
            raise FileExistsError(target)
        target.write_bytes(source.read_bytes() + b'converted')
        return {'output_sha256': cad.sha256(target)}
    monkeypatch.setattr(cad, 'convert', convert)
    items = [{'source': a, 'target': tmp_path / 'a.dwg'}, {'source': b, 'target': tmp_path / 'b.dwg'}]
    first = delivery.convert_many(items)
    assert [row['state'] for row in first] == ['ready', 'failed']
    second = delivery.convert_many(items, previous=first)
    assert second[0]['reused'] and calls.count(a) == 1
    a.write_bytes(b'changed')
    third = delivery.convert_many(items, previous=second)
    assert third[0]['state'] == 'failed'
    assert (tmp_path / 'a.dwg').read_bytes() == b'Aconverted'


def test_pdf_order_dimensions_bookmarks_and_exact_zip(tmp_path):
    paths = []
    for index, (width, height) in enumerate([(120, 80), (80, 150)]):
        doc = fitz.open()
        page = doc.new_page(width=width, height=height)
        page.insert_text((10, 20), f'Page {index}')
        path = tmp_path / f'{index}.pdf'
        doc.save(path)
        doc.close()
        paths.append(path)
    result = delivery.combine_pdfs(paths[::-1], tmp_path / 'combined.pdf', bookmarks=[('First chosen', 1), ('Second chosen', 2)])
    assert result['pages'] == 2
    with fitz.open(result['file']) as doc:
        assert (doc[0].rect.width, doc[0].rect.height) == (80, 150)
        assert 'Page 1' in doc[0].get_text()
        assert len(doc.get_toc()) == 2
    (tmp_path / 'private-note.txt').write_text('not selected')
    archive = tmp_path / 'selected.zip'
    delivery.collect_outputs({'图册/组合.pdf': result['file']}, archive)
    with zipfile.ZipFile(archive) as zipped:
        assert zipped.namelist() == ['图册/组合.pdf']
    with pytest.raises(FileExistsError):
        delivery.combine_pdfs(paths, tmp_path / 'combined.pdf')
    with pytest.raises(ValueError):
        delivery.collect_outputs({'../escape.pdf': paths[0]}, tmp_path / 'unsafe.zip')
    assert not (tmp_path / 'unsafe.zip').exists()


def test_invalid_pdf_input_never_publishes_partial_file(tmp_path):
    broken = tmp_path / 'bad.pdf'
    broken.write_bytes(b'invalid')
    with pytest.raises(fitz.FileDataError):
        delivery.combine_pdfs([broken], tmp_path / 'output.pdf')
    assert not (tmp_path / 'output.pdf').exists()
