"""External vendor-converter integration using generated geometry, no user files."""
import os

import ezdxf
import pytest
from ezarch import cad


def test_cached_converter_discovery_does_not_scan_other_applications(tmp_path, monkeypatch):
    from pathlib import Path

    from ezarch import project
    executable = tmp_path / '.ezarch/tools/oda/ODAFileConverter.app/Contents/MacOS/ODAFileConverter'
    executable.parent.mkdir(parents=True)
    executable.touch()
    monkeypatch.setenv('EZARCH_HOME', str(tmp_path / 'runtime'))
    monkeypatch.setenv('EZARCH_CONFIG', str(tmp_path / 'settings.json'))
    monkeypatch.setattr(project, 'skill_root', lambda: tmp_path)
    monkeypatch.setattr(cad.shutil, 'which', lambda _: None)
    monkeypatch.delenv('EZARCH_ODA', raising=False)
    def no_scan(*args, **kwargs):
        raise AssertionError('A known cached converter must not trigger filesystem traversal')
    monkeypatch.setattr(Path, 'glob', no_scan)
    assert cad.find_oda() == str(executable.resolve())


def test_vendor_dwg_roundtrip_preserves_native_entities(tmp_path):
    if not cad.find_oda():
        if os.environ.get('EZARCH_TEST_ODA') == '1':
            pytest.fail('ODA required by this integration job')
        pytest.skip('Optional ODA converter is not installed')
    doc = ezdxf.new('R2018')
    doc.units = ezdxf.units.MM
    doc.layers.new('CURVES')
    block = doc.blocks.new('COMPONENT')
    block.add_circle((0,0),100)
    ref = doc.modelspace().add_blockref('COMPONENT',(3200,2500), dxfattribs={'rotation': 37})
    arc = doc.modelspace().add_arc((1000, 2000), 750, 15, 270, dxfattribs={'layer': 'CURVES'})
    label = doc.modelspace().add_text('Original', dxfattribs={'height': 100})
    hatch = doc.modelspace().add_hatch()
    hatch.paths.add_polyline_path([(0,0),(1200,0),(1200,800),(0,800)],is_closed=True)
    doc.layouts.new('Paper').add_line((0,0),(10,0))
    source = tmp_path / 'source.dxf'
    doc.saveas(source)
    original_hash = cad.sha256(source)
    cad.convert(source, tmp_path / 'source.dwg')
    cad.edit(tmp_path / 'source.dwg', tmp_path / 'edited.dwg', [label.dxf.handle], text='Changed')
    result, working = cad.read(tmp_path / 'edited.dwg', tmp_path / 'converted')
    assert result.units == doc.units and result.dxfversion == doc.dxfversion
    assert len(result.modelspace()) == 4 and len(result.layouts.get('Paper')) == 1
    assert result.entitydb[label.dxf.handle].dxf.text == 'Changed'
    assert result.entitydb[arc.dxf.handle].dxf.radius == pytest.approx(750, abs=1e-9)
    assert result.entitydb[ref.dxf.handle].dxf.rotation == pytest.approx(37)
    assert len(result.blocks['COMPONENT']) == 1
    assert len(result.entitydb[hatch.dxf.handle].paths) == 1
    assert cad.sha256(source) == original_hash
    working.write_bytes(working.read_bytes() + b'\n')
    with pytest.raises(ValueError, match='working copy changed'):
        cad.read(tmp_path / 'edited.dwg', tmp_path / 'converted')
