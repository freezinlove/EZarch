"""Package only declared release files, including from a GitHub source archive."""
import argparse
import hashlib
import json
import posixpath
import re
import subprocess
import tempfile
import tomllib
import zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit


def release_files(skill: Path, manifest: Path) -> list[tuple[str, Path]]:
    """Resolve an explicit allowlist without following file/directory links."""
    skill = skill.resolve()
    files = []
    seen = set()
    for line in manifest.read_text(encoding="utf-8").splitlines():
        name = line.strip()
        if not name or name.startswith("#"):
            continue
        relative = PurePosixPath(name)
        if (relative.is_absolute() or relative.as_posix() != name
                or any(part in {".", ".."} for part in relative.parts)
                or "\\" in name or ":" in name):
            raise ValueError(f"Unsafe release path: {name}")
        if name.casefold() in seen:
            raise ValueError(f"Duplicate release path: {name}")
        seen.add(name.casefold())
        path = skill
        for part in relative.parts:
            path = path / part
            if path.is_symlink() or path.is_junction():
                raise ValueError(f"Release files cannot use symlinks or junctions: {name}")
        if not path.is_file() or not path.resolve().is_relative_to(skill):
            raise ValueError(f"Missing or invalid release file: {name}")
        files.append((name, path))
    if not files:
        raise ValueError("Release file list is empty")
    return sorted(files)


def tracked_skill_files(skill: Path) -> set[str] | None:
    """Check committed AND staged additions without discovering private untracked files."""
    skill = skill.resolve()
    if not any((parent / '.git').exists() for parent in (skill, *skill.parents)):
        return None  # Source archives work without Git; link/build-input checks still apply.
    try:
        root = Path(subprocess.check_output(
            ['git', '-C', str(skill), 'rev-parse', '--show-toplevel'], stderr=subprocess.PIPE,
        ).decode('utf-8').strip()).resolve()
        prefix = skill.relative_to(root).as_posix()
        output = subprocess.check_output(
            ['git', '-C', str(root), 'ls-files', '--cached', '--full-name', '-z', '--', prefix],
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError('Cannot check tracked skill files in this Git checkout') from error
    base = PurePosixPath(prefix)
    return {PurePosixPath(name.decode('utf-8')).relative_to(base).as_posix()
            for name in output.split(b'\0') if name}


def markdown_targets(content: str):
    """Read inline/image and reference-definition destinations, ignoring code samples."""
    prose = []
    fence = None
    for line in content.splitlines(keepends=True):
        marker = re.match(r'^\s*(`{3,}|~{3,})(.*)$', line)
        if fence:
            if (marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence)
                    and not marker[2].strip()):
                fence = None
            continue
        if marker:
            fence = marker[1]
            continue
        # Indented code blocks are examples, not resource dependencies.
        if line.startswith(('    ', '\t')):
            continue
        prose.append(line)
    text = ''.join(prose)
    text = re.sub(r'(`+)(?!`).*?(?<!`)\1(?!`)', '', text, flags=re.DOTALL)
    patterns = (
        r'!?\[[^\]\n]*\]\(\s*(?:<([^>\n]+)>|((?:[^\s()]|\([^\s()]*\))+))',
        r'^ {0,3}\[[^\]\n]+\]:\s*(?:<([^>\n]+)>|(\S+))',
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.MULTILINE):
            yield match[1] or match[2]


def validate_release(skill: Path, manifest: Path) -> list[tuple[str, Path]]:
    """Fail on omissions; never add extra files to the public allowlist automatically."""
    files = release_files(skill, manifest)
    declared = dict(files)
    errors = []
    required = {'SKILL.md', 'pyproject.toml'} - declared.keys()
    if required:
        errors.append('Required release files missing: ' + ', '.join(sorted(required)))

    tracked = tracked_skill_files(skill)
    if tracked is not None and (missing := tracked - declared.keys()):
        errors.append('Tracked skill files missing from release manifest: ' + ', '.join(sorted(missing)))

    for name, path in files:
        if path.suffix.lower() != '.md':
            continue
        for target in markdown_targets(path.read_text(encoding='utf-8')):
            parsed = urlsplit(target)
            if parsed.scheme == 'file':
                errors.append(f'Local link leaves release package: {name} -> {target}')
                continue
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            relative = unquote(parsed.path)
            destination = posixpath.normpath(posixpath.join(posixpath.dirname(name), relative))
            if (relative.startswith('/') or '\\' in relative or destination == '..'
                    or destination.startswith('../')):
                errors.append(f'Local link leaves release package: {name} -> {target}')
            elif (destination != '.' and destination not in declared
                  and not any(item.startswith(destination.rstrip('/') + '/') for item in declared)):
                errors.append(f'Local link target missing from release manifest: {name} -> {target}')

    if project := declared.get('pyproject.toml'):
        metadata = tomllib.loads(project.read_text(encoding='utf-8'))
        build = metadata.get('tool', {}).get('hatch', {}).get('build', {})
        wheel = build.get('targets', {}).get('wheel', {})
        inputs = {*wheel.get('only-include', []), *wheel.get('force-include', {}),
                  *metadata.get('project', {}).get('license-files', [])}
        if custom := build.get('hooks', {}).get('custom', {}).get('path'):
            inputs.add(custom)
        if missing := inputs - declared.keys():
            errors.append('Build inputs missing from release manifest: ' + ', '.join(sorted(missing)))
        if wheel:
            modules = {name for name in declared if name.startswith('src/ezarch/') and name.endswith('.py')}
            if missing := modules - set(wheel.get('only-include', [])):
                errors.append('Runtime modules missing from wheel only-include: ' + ', '.join(sorted(missing)))

    if errors:
        raise ValueError('Release completeness check failed:\n- ' + '\n- '.join(sorted(set(errors)))
                         + '\nReview public files in tools/skill-files.txt; keep project/maintenance files outside the installable skill.')
    return files


def package(skill: Path, manifest: Path, out: Path) -> tuple[Path, int, str]:
    files = validate_release(skill, manifest)
    # Read metadata from the already validated files, not an unlisted/linked path.
    project = dict(files).get("pyproject.toml")
    if project is None:
        raise ValueError("Release file list must include pyproject.toml")
    version = tomllib.loads(project.read_text(encoding="utf-8"))["project"]["version"]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.+-]*", version):
        raise ValueError("Invalid release version")
    out.mkdir(parents=True, exist_ok=True)
    archive = out / f"ezarch-{version}-skill.zip"
    marker = {"version": version, "files": {name: hashlib.sha256(file.read_bytes()).hexdigest() for name, file in files}}
    with tempfile.NamedTemporaryFile(dir=out, suffix=".zip.tmp", delete=False) as stream:
        temporary = Path(stream.name)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as z:
            for name, file in files:
                # Stable timestamps/permissions make an identical source package reproducible.
                info = zipfile.ZipInfo(f"ezarch/{name}", date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, file.read_bytes())
            info = zipfile.ZipInfo("ezarch/.ezarch-release.json", date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            z.writestr(info, json.dumps(marker, sort_keys=True).encode())
        digest = hashlib.sha256(temporary.read_bytes()).hexdigest()
        temporary.replace(archive)
    finally:
        temporary.unlink(missing_ok=True)
    archive.with_suffix(".zip.sha256").write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    return archive, len(files) + 1, digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--check", action="store_true", help="Check release completeness without creating an archive")
    parser.add_argument("--base-url", help="HTTPS directory serving the versioned release ZIP")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.check:
        files = validate_release(root / 'skills/ezarch', root / 'tools/skill-files.txt')
        print(f'Release complete: {len(files)} declared files; local Markdown links and build inputs checked.')
        return
    if args.out is None:
        parser.error('Specify --out to package, or --check to validate only')
    archive, count, digest = package(root / "skills/ezarch", root / "tools/skill-files.txt", args.out)
    if args.base_url:
        if not args.base_url.startswith("https://"):
            parser.error("Release base URL must use HTTPS")
        version = tomllib.loads((root / "skills/ezarch/pyproject.toml").read_text())["project"]["version"]
        (args.out / "ezarch-release.json").write_text(json.dumps({"version": version, "url": args.base_url.rstrip("/") + "/" + archive.name, "sha256": digest}, indent=2))
    print(f"{archive}: {count} files, SHA256 {digest}")


if __name__ == "__main__":
    main()
