"""Publication boundaries: local project files never become skill payloads."""
import os
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

import pytest

from tools.package_skill import package, release_files, validate_release


@pytest.fixture
def release_tree(tmp_path):
    skill = tmp_path / "skill"
    skill.mkdir()
    (skill / "pyproject.toml").write_text('[project]\nversion = "1.2.3"\n', encoding="utf-8")
    (skill / "SKILL.md").write_text("Public skill", encoding="utf-8")
    manifest = tmp_path / "files.txt"
    manifest.write_text("pyproject.toml\nSKILL.md\n", encoding="utf-8")
    return skill, manifest


def test_package_ignores_unlisted_files_and_does_not_need_git(release_tree, tmp_path):
    skill, manifest = release_tree
    # Include a Python file and an asset-directory secret: extension/directory filters are insufficient.
    for name in [".env", "outputs/private.txt", "validation/notes.md", "assets/private.env",
                 "src/ezarch/private.py", ".venv/state.json"]:
        path = skill / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("SYNTHETIC_PRIVATE_SENTINEL", encoding="utf-8")
    archive, count, digest = package(skill, manifest, tmp_path / "dist")
    with zipfile.ZipFile(archive) as z:
        assert set(z.namelist()) == {"ezarch/pyproject.toml", "ezarch/SKILL.md", "ezarch/.ezarch-release.json"}
        assert all(b"SYNTHETIC_PRIVATE_SENTINEL" not in z.read(name) for name in z.namelist())
    assert count == 3
    assert archive.with_suffix(".zip.sha256").read_text(encoding="utf-8").startswith(digest)
    os.utime(skill / "SKILL.md", (1700000000, 1700000000))
    assert package(skill, manifest, tmp_path / "again")[2] == digest


@pytest.mark.parametrize("entry", ["../outside.txt", "/outside.txt", "C:/outside.txt", "a\\outside.txt"])
def test_manifest_rejects_escaping_paths(release_tree, entry):
    skill, manifest = release_tree
    manifest.write_text(entry, encoding="utf-8")
    with pytest.raises(ValueError, match="Unsafe release path"):
        release_files(skill, manifest)


@pytest.mark.parametrize("directory", [False, True])
def test_selected_symlink_is_rejected_and_unlisted_link_is_ignored(release_tree, tmp_path, directory):
    skill, manifest = release_tree
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("SYNTHETIC_PRIVATE_SENTINEL", encoding="utf-8")
    link = skill / "linked"
    try:
        link.symlink_to(outside if directory else outside / "secret.txt", target_is_directory=directory)
    except OSError:
        pytest.skip("Creating symlinks requires OS privileges on this host")
    package(skill, manifest, tmp_path / "safe")
    manifest.write_text("linked/secret.txt" if directory else "linked", encoding="utf-8")
    with pytest.raises(ValueError, match="symlinks or junctions"):
        package(skill, manifest, tmp_path / "unsafe")
    assert not (tmp_path / "unsafe").exists()


def test_missing_release_file_fails_before_replacing_archive(release_tree, tmp_path):
    skill, manifest = release_tree
    archive, _, _ = package(skill, manifest, tmp_path / "dist")
    original = archive.read_bytes()
    (skill / "SKILL.md").unlink()
    with pytest.raises(ValueError, match="Missing or invalid"):
        package(skill, manifest, tmp_path / "dist")
    assert archive.read_bytes() == original


def test_repository_release_list_resolves_and_includes_dependencies():
    root = Path(__file__).resolve().parents[1]
    names = dict(validate_release(root / "skills/ezarch", root / "tools/skill-files.txt"))
    assert {"LICENSE", "THIRD_PARTY_NOTICES.md", "SKILL.md", "pyproject.toml", "uv.lock",
            "assets/fonts/COPYING", "assets/fonts/FandolFang-Regular.otf",
            "assets/fonts/EZarchFang.ttf", "scripts/build_font.py"} <= names.keys()


def test_wheel_inputs_are_individual_declared_release_files():
    root = Path(__file__).resolve().parents[1]
    skill = root / "skills/ezarch"
    declared = dict(release_files(skill, root / "tools/skill-files.txt"))
    metadata = tomllib.loads((skill / "pyproject.toml").read_text(encoding="utf-8"))
    wheel = metadata["tool"]["hatch"]["build"]["targets"]["wheel"]
    names = {*wheel["only-include"], *wheel["force-include"], *metadata["project"]["license-files"]}
    assert names <= declared.keys()
    assert all((skill / name).is_file() for name in names)
    assert metadata["tool"]["hatch"]["build"]["hooks"]["custom"]["path"] in declared


@pytest.mark.parametrize('link', [
    '[知识](references/new.md)',
    '[知识][detail]\n\n[detail]: references/new.md "说明"',
    '![素材](references/new.md#detail)',
])
def test_unlisted_document_dependency_blocks_archive_replacement(release_tree, tmp_path, link):
    skill, manifest = release_tree
    archive, _, _ = package(skill, manifest, tmp_path / 'dist')
    previous = archive.read_bytes()
    (skill / 'references').mkdir()
    (skill / 'references/new.md').write_text('New knowledge', encoding='utf-8')
    (skill / 'SKILL.md').write_text(link, encoding='utf-8')
    with pytest.raises(ValueError, match=r'SKILL.md -> references/new.md'):
        package(skill, manifest, tmp_path / 'dist')
    assert archive.read_bytes() == previous
    with manifest.open('a', encoding='utf-8') as stream:
        stream.write('references/new.md\n')
    archive, _, _ = package(skill, manifest, tmp_path / 'fixed')
    with zipfile.ZipFile(archive) as z:
        assert z.read('ezarch/references/new.md').decode() == 'New knowledge'


def test_relative_assets_and_non_dependencies_in_markdown(release_tree, tmp_path):
    skill, manifest = release_tree
    (skill / 'references').mkdir()
    (skill / 'assets').mkdir()
    (skill / 'assets/素材 图.svg').write_text('<svg/>', encoding='utf-8')
    (skill / 'assets/plan(1).svg').write_text('<svg/>', encoding='utf-8')
    (skill / 'references/topic.md').write_text(
        '![素材](../assets/%E7%B4%A0%E6%9D%90%20%E5%9B%BE.svg)\n'
        '[素材](<../assets/素材 图.svg> "图")\n'
        '[括号](../assets/plan(1).svg)\n'
        '[目录](../)\n'
        '[返回](../SKILL.md#purpose)\n', encoding='utf-8')
    (skill / 'SKILL.md').write_text(
        '[专题](references/topic.md)\n'
        '[外网](https://example.invalid/no-download.md)\n'
        '[页内](#purpose)\n'
        '`[占位](missing.md)`\n'
        '```md\n[占位](missing.md)\n```\n'
        '~~~md\n![占位](missing.png)\n~~~\n'
        '    [占位](missing.md)\n', encoding='utf-8')
    with manifest.open('a', encoding='utf-8') as stream:
        stream.write('references/topic.md\nassets/素材 图.svg\nassets/plan(1).svg\n')
    package(skill, manifest, tmp_path / 'dist')


@pytest.mark.parametrize('link', ['../private.md', 'file:///tmp/private.md'])
def test_document_link_cannot_depend_on_file_outside_installation(release_tree, tmp_path, link):
    skill, manifest = release_tree
    (tmp_path / 'private.md').write_text('private', encoding='utf-8')
    (skill / 'SKILL.md').write_text(f'[Outside]({link})', encoding='utf-8')
    with pytest.raises(ValueError, match='Local link leaves release package'):
        package(skill, manifest, tmp_path / 'dist')
    assert not (tmp_path / 'dist').exists()


def test_git_staged_unlinked_capability_cannot_be_silently_omitted(release_tree, tmp_path):
    skill, manifest = release_tree
    subprocess.run(['git', 'init', '-q', str(skill)], check=True)
    module = skill / 'src/ezarch/new_tool.py'
    module.parent.mkdir(parents=True)
    module.write_text('VALUE = 42\n', encoding='utf-8')
    # An untracked project file is neither published nor made a dependency.
    (skill / 'private.txt').write_text('SYNTHETIC_PRIVATE_SENTINEL', encoding='utf-8')
    subprocess.run(['git', '-C', str(skill), 'add', 'src/ezarch/new_tool.py'], check=True)
    with pytest.raises(ValueError, match=r'Tracked skill files.*src/ezarch/new_tool.py'):
        package(skill, manifest, tmp_path / 'dist')
    with manifest.open('a', encoding='utf-8') as stream:
        stream.write('src/ezarch/new_tool.py\n')
    archive, _, _ = package(skill, manifest, tmp_path / 'dist')
    with zipfile.ZipFile(archive) as z:
        assert 'ezarch/src/ezarch/new_tool.py' in z.namelist()
        assert 'ezarch/private.txt' not in z.namelist()


def test_build_dependency_omission_is_caught_without_git(release_tree, tmp_path):
    skill, manifest = release_tree
    with (skill / 'pyproject.toml').open('a', encoding='utf-8') as stream:
        stream.write('\n[tool.hatch.build.targets.wheel]\nonly-include = ["src/new.py"]\n')
    (skill / 'src').mkdir()
    (skill / 'src/new.py').write_text('VALUE = 1\n', encoding='utf-8')
    with pytest.raises(ValueError, match=r'Build inputs.*src/new.py'):
        package(skill, manifest, tmp_path / 'dist')


def test_declared_runtime_module_must_also_be_in_wheel(release_tree, tmp_path):
    skill, manifest = release_tree
    (skill / 'src/ezarch').mkdir(parents=True)
    for name in ('__init__.py', 'new.py'):
        (skill / 'src/ezarch' / name).write_text('VALUE = 1\n', encoding='utf-8')
    with manifest.open('a', encoding='utf-8') as stream:
        stream.write('src/ezarch/__init__.py\nsrc/ezarch/new.py\n')
    project = skill / 'pyproject.toml'
    with project.open('a', encoding='utf-8') as stream:
        stream.write('\n[tool.hatch.build.targets.wheel]\nonly-include = ["src/ezarch/__init__.py"]\n')
    with pytest.raises(ValueError, match=r'Runtime modules missing from wheel.*src/ezarch/new.py'):
        package(skill, manifest, tmp_path / 'dist')
    project.write_text(project.read_text().replace(
        '["src/ezarch/__init__.py"]', '["src/ezarch/__init__.py", "src/ezarch/new.py"]'), encoding='utf-8')
    package(skill, manifest, tmp_path / 'fixed')


def test_real_package_installs_with_readable_references_and_runnable_code(tmp_path, monkeypatch):
    from ezarch import updates

    root = Path(__file__).resolve().parents[1]
    skill = root / 'skills/ezarch'
    monkeypatch.setenv('EZARCH_HOME', str(tmp_path / 'runtime'))
    monkeypatch.setenv('EZARCH_CONFIG', str(tmp_path / 'settings.json'))
    archive, _, sha = package(skill, root / 'tools/skill-files.txt', tmp_path / 'dist')
    version = tomllib.loads((skill / 'pyproject.toml').read_text())['project']['version']
    target = tmp_path / 'installed/ezarch'
    updates.install_release(target, {'version': version, 'url': archive.as_uri(), 'sha256': sha})
    for original in (skill / 'references').glob('*.md'):
        assert (target / 'references' / original.name).read_bytes() == original.read_bytes()
    assert not (target / '.venv').exists()
    environment = dict(os.environ, PYTHONPATH=str(target / 'src'), PYTHONNOUSERSITE='1')
    script = '''
import sys
from pathlib import Path
import ezarch
from ezarch.symbols import door_symbol
assert Path(ezarch.__file__).resolve().is_relative_to(Path(sys.argv[1]))
symbol = door_symbol(900, leaf_thickness=40, frame_width=40, frame_depth=100)
assert symbol.parts
'''
    subprocess.run([sys.executable, '-c', script, str(target)], env=environment, cwd=tmp_path,
                   check=True, timeout=30)


def test_model_runtime_excludes_known_vulnerable_vtk():
    from importlib.metadata import PackageNotFoundError, version

    from packaging.version import Version

    # PYSEC-2025-224/225/226 affect VTK's glTF reader through 9.5.0.
    try:
        installed = version("vtk")
    except PackageNotFoundError:
        return  # Default Blender runtime has no VTK dependency.
    assert Version(installed) >= Version("9.5.1")
