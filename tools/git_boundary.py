"""Opt-in repository checks; inspect staged blobs or all incoming push commits."""
import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args])


def findings(root, *, commits=None, max_bytes=10 * 1024 ** 2):
    root = Path(root)
    allowed_file = root / '.ezarch-public-files.json'
    allowed = set(json.loads(allowed_file.read_text()) if allowed_file.exists() else [])
    rows = []
    revisions = list(commits) if commits is not None else [None]
    for revision in revisions:
        arguments = (['diff-tree', '-m', '--root', '--no-commit-id', '-r', '--name-only', '-z', '--diff-filter=ACMR', revision]
                     if revision else ['diff', '--cached', '--name-only', '-z', '--diff-filter=ACMR'])
        for raw in git(root, *arguments).split(b'\0'):
            if not raw:
                continue
            name = raw.decode('utf-8', 'surrogateescape')
            spec = f'{revision or ""}:{name}'
            size = int(git(root, 'cat-file', '-s', spec))
            parts = Path(name).parts
            reasons = []
            if size > max_bytes:
                reasons.append(f'{size} bytes exceeds configured {max_bytes}')
            if any(p in {'.venv', '.ezarch', 'sources', 'outputs', 'renders', 'validation'} for p in parts):
                reasons.append('runtime/project-output directory')
            if name not in allowed:
                if Path(name).suffix.lower() in {'.dwg', '.dxf', '.blend', '.3dm', '.pdf', '.png', '.jpg', '.zip'}:
                    reasons.append('project/media file without explicit public-file declaration')
                if parts[0] not in {'skills', 'tests', 'tools', '.github', 'AGENTS.md', 'README.md', 'CHANGELOG.md', 'LICENSE',
                                    '.gitignore', 'ruff.toml', '.ezarch-public-files.json', 'pyproject.toml'}:
                    reasons.append('path outside declared maintenance areas')
            if reasons:
                rows.append({'commit': revision, 'path': name, 'reasons': reasons})
    return rows


def install(root):
    root = Path(root).resolve()
    previous = subprocess.run(['git', '-C', str(root), 'config', '--get', 'core.hooksPath'],
                              capture_output=True, text=True).stdout.strip()
    hooks = Path(git(root, 'rev-parse', '--absolute-git-dir').decode().strip()) / 'ezarch-hooks'
    if previous and Path(previous).resolve() != hooks:
        raise ValueError(f'Existing hooksPath preserved: {previous}; integrate the check manually')
    standard = hooks.parent / 'hooks'
    if any((standard / n).exists() for n in ('pre-commit', 'pre-push')) and not previous:
        raise ValueError('Existing Git hooks preserved; integrate this check manually')
    hooks.mkdir(exist_ok=True)
    command = f'{shlex.quote(sys.executable)} {shlex.quote(str(Path(__file__).resolve()))}'
    for name, mode in [('pre-commit', 'staged'), ('pre-push', 'push')]:
        path = hooks / name
        path.write_text(f'#!/bin/sh\nexec {command} {mode} --root {shlex.quote(str(root))}\n')
        path.chmod(0o755)
    subprocess.run(['git', '-C', str(root), 'config', 'core.hooksPath', str(hooks)], check=True)
    return str(hooks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['staged', 'push', 'install', 'status'])
    parser.add_argument('--root', type=Path, default=Path.cwd())
    a = parser.parse_args()
    if a.mode == 'install':
        print(install(a.root))
        return 0
    if a.mode == 'status':
        print(subprocess.run(['git', '-C', str(a.root), 'config', '--get', 'core.hooksPath'], capture_output=True, text=True).stdout or 'not configured')
        return 0
    commits = None
    if a.mode == 'push':
        commits = set()
        for line in sys.stdin:
            _, new, _, old = line.split()
            if set(new) == {'0'}:
                continue
            arguments = [new, '--not', '--remotes'] if set(old) == {'0'} else [f'{old}..{new}']
            commits.update(git(a.root, 'rev-list', *arguments).decode().split())
    result = findings(a.root, commits=commits)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(bool(result))


if __name__ == '__main__':
    raise SystemExit(main())
