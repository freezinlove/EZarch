import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from ezarch import runtime


@pytest.fixture
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv('EZARCH_CONFIG', str(tmp_path / 'config.json'))
    monkeypatch.setenv('EZARCH_HOME', str(tmp_path / '中文 runtime'))
    return tmp_path


@pytest.mark.parametrize('parent_cache', [None, 'existing-parent-cache'])
def test_locations_preference_environment_and_child_cache(isolated, monkeypatch, parent_cache):
    if parent_cache is None:
        monkeypatch.delenv('UV_CACHE_DIR', raising=False)
    else:
        monkeypatch.setenv('UV_CACHE_DIR', parent_cache)
    runtime.configure(isolated / 'chosen')
    assert runtime.locations()['home'] == isolated / '中文 runtime'
    monkeypatch.delenv('EZARCH_HOME')
    assert runtime.locations()['home'] == isolated / 'chosen'
    child = runtime.process_env()
    assert Path(child['UV_CACHE_DIR']).is_relative_to(isolated / 'chosen')
    assert os.environ.get('UV_CACHE_DIR') == parent_cache


def test_download_integrity_retry_cache_and_old_file(isolated):
    import hashlib
    source, target = isolated / 'source', isolated / 'cached'
    source.write_bytes(b'new')
    target.write_bytes(b'old')
    with pytest.raises(ValueError, match='checksum'):
        runtime.download(source.as_uri(), target, sha256='0' * 64)
    assert target.read_bytes() == b'old'
    digest = hashlib.sha256(b'new').hexdigest()
    runtime.download(source.as_uri(), target, sha256=digest)
    source.unlink()
    runtime.download(source.as_uri(), target, sha256=digest)
    assert target.read_bytes() == b'new'


def test_lock_never_overwrites_other_owner(isolated):
    path = isolated / 'lock'
    with runtime.lock(path):
        with pytest.raises(RuntimeError, match='locked'):
            with runtime.lock(path):
                pass
    assert not path.exists()


def test_shared_dependencies_distinct_code_and_failed_upgrade(isolated, monkeypatch):
    first, second = isolated / 'skill1', isolated / 'skill2'
    for skill in (first, second):
        skill.mkdir()
        (skill / 'uv.lock').write_text('same lock')
    commands = []
    def run(command, **kwargs):
        commands.append(command)
        if 'sync' in command:
            python = runtime.python_at(kwargs['env']['UV_PROJECT_ENVIRONMENT'])
            python.parent.mkdir(parents=True, exist_ok=True)
            python.touch()
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(runtime.subprocess, 'run', run)
    a = runtime.prepare(first, uv='uv')
    b = runtime.prepare(second, uv='uv')
    assert a['python'] == b['python'] and b['reused']
    assert sum('sync' in call for call in commands) == 1
    (first / 'uv.lock').write_text('new lock')
    def fail(*args, **kwargs):
        raise OSError('synthetic disk full')
    monkeypatch.setattr(runtime.subprocess, 'run', fail)
    with pytest.raises(OSError):
        runtime.prepare(first, uv='uv')
    assert runtime.read_json(runtime.binding_file(first))['python'] == a['python']
    assert runtime.find_python(first) is None  # changed dependencies require preparation
    assert Path(a['python']).exists()


def test_code_only_release_reuses_dependency_identity(tmp_path):
    skill = tmp_path / 'skill'
    skill.mkdir()
    locked = '[[package]]\nname="ezarch"\nversion="0.6.0"\nsource={editable="."}\n\n[[package]]\nname="ezdxf"\nversion="1.4.4"\nsource={registry="https://pypi.org/simple"}\n'
    path = skill / 'uv.lock'
    path.write_text(locked)
    first = runtime.dependency_fingerprint(skill)
    path.write_text(locked.replace('0.6.0', '0.7.0'))
    assert runtime.dependency_fingerprint(skill) == first
    path.write_text(locked.replace('1.4.4', '1.4.5'))
    assert runtime.dependency_fingerprint(skill) != first


def test_registered_tool_shared_without_copying_and_deleted_path_not_reused(isolated):
    executable = isolated / 'existing software.exe'
    executable.write_bytes(b'synthetic path only')
    result = runtime.register_tool('oda', executable)
    assert result['state'] == 'registered_path'
    assert runtime.registered_tool('oda') == str(executable)
    assert list(runtime.locations()['tools'].iterdir()) == []
    executable.unlink()
    assert runtime.registered_tool('oda') is None
