import hashlib
import json
import shutil
import zipfile
from pathlib import Path

import pytest
from ezarch import updates

from tools.package_skill import package


@pytest.fixture
def releases(tmp_path, monkeypatch):
    monkeypatch.setenv('EZARCH_HOME', str(tmp_path / 'runtime'))
    monkeypatch.setenv('EZARCH_CONFIG', str(tmp_path / 'settings.json'))
    root = tmp_path / 'source'
    root.mkdir()
    (root / 'SKILL.md').write_text('old content')
    (root / 'pyproject.toml').write_text('[project]\nversion="1.0.0"')
    manifest = tmp_path / 'files.txt'
    manifest.write_text('SKILL.md\npyproject.toml\n')
    old, _, _ = package(root, manifest, tmp_path / 'dist')
    with zipfile.ZipFile(old) as z:
        z.extractall(tmp_path / 'installed')
    target = tmp_path / 'installed/ezarch'
    (root / 'SKILL.md').write_text('new content')
    (root / 'pyproject.toml').write_text('[project]\nversion="1.1.0"')
    archive, _, sha = package(root, manifest, tmp_path / 'dist')
    release = {'version': '1.1.0', 'url': archive.as_uri(), 'sha256': sha}
    metadata = tmp_path / 'release.json'
    metadata.write_text(json.dumps(release))
    return target, release, metadata


def test_check_limits_notices_and_offline_is_not_current(releases):
    target, _, metadata = releases
    first = updates.check(target, source=metadata.as_uri(), now=100000)
    assert first['notify'] and first['state'] == 'available'
    assert not updates.check(target, source=metadata.as_uri(), now=100001)['notify']
    assert not updates.check(target, source=metadata.as_uri(), now=200000)['notify']
    metadata.unlink()
    assert updates.check(target, source=metadata.as_uri(), force=True)['state'] == 'unavailable'


def test_prepare_activate_preserves_extra_and_backup(releases):
    target, release, _ = releases
    (target / 'my-notes.txt').write_text('user content')
    ready = updates.prepare(target, release)
    assert (target / 'SKILL.md').read_text() == 'old content'
    result = updates.activate(target, ready['prepared'])
    assert result['state'] == 'activated_reload_required'
    assert (target / 'SKILL.md').read_text() == 'new content'
    assert (target / 'my-notes.txt').read_text() == 'user content'
    assert (Path(result['backup']) / 'SKILL.md').read_text() == 'old content'


def test_local_changes_and_corrupt_download_preserved(releases):
    target, release, _ = releases
    with pytest.raises(ValueError, match='checksum'):
        updates.prepare(target, {**release, 'sha256': '0' * 64})
    ready = updates.prepare(target, release)
    (target / 'SKILL.md').write_text('local edit')
    with pytest.raises(ValueError, match='Local changes'):
        updates.activate(target, ready['prepared'])
    assert (target / 'SKILL.md').read_text() == 'local edit'


def test_activation_failure_rolls_back(releases, monkeypatch):
    target, release, _ = releases
    ready = updates.prepare(target, release)
    real = updates.os.replace
    def fail(source, destination):
        if Path(destination) == target / 'pyproject.toml':
            raise OSError('synthetic write failure')
        return real(source, destination)
    monkeypatch.setattr(updates.os, 'replace', fail)
    with pytest.raises(OSError):
        updates.activate(target, ready['prepared'])
    assert (target / 'SKILL.md').read_text() == 'old content'
    assert updates.identity(target)[1]['version'] == '1.0.0'


def test_zip_traversal_rejected(releases, tmp_path):
    target, release, _ = releases
    archive = tmp_path / 'malicious.zip'
    with zipfile.ZipFile(archive, 'w') as z:
        z.writestr('ezarch/../escaped', 'bad')
    with pytest.raises(ValueError, match='Unsafe'):
        updates.prepare(target, {**release, 'url': archive.as_uri(), 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()})
    assert not (tmp_path / 'escaped').exists()


def test_wrong_installation_and_checkout_rejected(releases, tmp_path):
    target, release, _ = releases
    ready = updates.prepare(target, release)
    other = tmp_path / 'other'
    shutil.copytree(target, other)
    with pytest.raises(ValueError, match='another'):
        updates.activate(other, ready['prepared'])
    (other / '.git').mkdir()
    with pytest.raises(ValueError, match='Source checkout'):
        updates.check(other)


def test_active_task_blocks_update_then_rollback(releases):
    target, release, _ = releases
    ready = updates.prepare(target, release)
    with updates.usage(target):
        with updates.usage(target):
            with pytest.raises(RuntimeError, match='in use'):
                updates.activate(target, ready['prepared'])
    applied = updates.activate(target, ready['prepared'])
    updates.rollback(target, applied['backup'])
    assert updates.identity(target)[1]['version'] == '1.0.0'
