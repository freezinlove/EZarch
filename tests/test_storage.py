import subprocess

import pytest
from ezarch.storage import output_path

from tools.git_boundary import findings


def test_resolved_output_rejects_link_into_tool_tree(tmp_path, monkeypatch):
    monkeypatch.delenv('EZARCH_ALLOW_TOOL_WRITES', raising=False)
    tool = tmp_path / 'tool'
    tool.mkdir()
    linked = tmp_path / 'link'
    linked.symlink_to(tool, target_is_directory=True)
    with pytest.raises(ValueError, match='Project output'):
        output_path(linked / 'drawing.pdf', roots=[tool])
    assert output_path(tool / 'fixture.dxf', roots=[tool], allow_tool_write=True) == tool / 'fixture.dxf'
    assert output_path(tmp_path / 'project/out.pdf', roots=[tool]) == tmp_path / 'project/out.pdf'


def test_git_staged_and_deleted_in_later_commit(tmp_path):
    def git(*args):
        return subprocess.check_output(['git', '-C', str(tmp_path), *args]).decode().strip()
    git('init', '-q')
    git('config', 'user.name', 'Test')
    git('config', 'user.email', 'test@example.invalid')
    (tmp_path / '私人图纸.dxf').write_text('synthetic fixture')
    git('add', '.')
    assert findings(tmp_path)[0]['path'] == '私人图纸.dxf'
    git('commit', '-qm', 'add synthetic')
    first = git('rev-parse', 'HEAD')
    git('rm', '私人图纸.dxf')
    git('commit', '-qm', 'delete synthetic')
    assert not findings(tmp_path)
    assert findings(tmp_path, commits=[first, git('rev-parse', 'HEAD')])
