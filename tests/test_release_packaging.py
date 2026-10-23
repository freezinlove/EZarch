"""Publication boundaries: local project files never become skill payloads."""
import os
import tomllib
import zipfile
from pathlib import Path

import pytest

from tools.package_skill import package, release_files


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
    names = dict(release_files(root / "skills/ezarch", root / "tools/skill-files.txt"))
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


def test_model_runtime_excludes_known_vulnerable_vtk():
    from importlib.metadata import PackageNotFoundError, version

    from packaging.version import Version

    # PYSEC-2025-224/225/226 affect VTK's glTF reader through 9.5.0.
    try:
        installed = version("vtk")
    except PackageNotFoundError:
        return  # Default Blender runtime has no VTK dependency.
    assert Version(installed) >= Version("9.5.1")
