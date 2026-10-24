"""Opt-in release checks and transactional managed-file updates; no daemon."""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import shutil
import time
import urllib.request
import uuid
import zipfile
from pathlib import Path, PurePosixPath

from .runtime import atomic_json, download, locations, lock, read_json

SOURCE = 'https://github.com/freezinlove/EZarch/releases/latest/download/ezarch-release.json'
MARKER = '.ezarch-release.json'


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def safe_name(value):
    path = PurePosixPath(value)
    if not value or path.is_absolute() or path.as_posix() != value or any(p in {'.', '..'} for p in path.parts) or '\\' in value or ':' in value:
        raise ValueError(f'Unsafe release path: {value}')
    return value


def version(value):
    if not re.fullmatch(r'\d+\.\d+\.\d+', value):
        raise ValueError('Only explicit stable x.y.z releases are accepted')
    return tuple(map(int, value.split('.')))


def state_path(target):
    key = hashlib.sha256(str(Path(target).resolve()).encode()).hexdigest()[:24]
    return locations()['state'] / f'update-{key}.json'


@contextlib.contextmanager
def usage(target):
    """Multiple readers may run; activation waits until every known reader exits."""
    state = state_path(target)
    leases = state.with_suffix('.users')
    with lock(state.with_suffix('.active.lock')):
        if state.with_suffix('.transaction.json').exists():
            raise RuntimeError('Interrupted update: run update recover before using this installation')
        leases.mkdir(parents=True, exist_ok=True)
        lease = leases / f'{os.getpid()}-{uuid.uuid4().hex}'
        lease.write_text(str(os.getpid()))
    try:
        yield
    finally:
        lease.unlink(missing_ok=True)


def identity(target):
    target = Path(target).resolve()
    if any((parent / '.git').exists() for parent in (target, *target.parents)):
        raise ValueError('Source checkout: use explicit Git maintenance; managed updater will not replace it')
    marker = read_json(target / MARKER)
    if not marker or not isinstance(marker.get('files'), dict):
        raise ValueError('Installation has no release manifest; retain it and bootstrap from a verified release package')
    version(marker['version'])
    for name in marker['files']:
        safe_name(name)
    return target, marker


def preferences(target, *, auto=None, remind=None, skip=None, source=None):
    path = state_path(target)
    state = read_json(path, {})
    for key, value in {'auto': auto, 'remind': remind, 'skip': skip, 'source': source}.items():
        if value is not None:
            state[key] = value
    atomic_json(path, state)
    return state


def check(target, *, source=None, force=False, timeout=2, now=None):
    target, installed = identity(target)
    path = state_path(target)
    state = read_json(path, {})
    now = time.time() if now is None else now
    if not force and now - state.get('checked_at', 0) < 86400:
        return {**state.get('last_result', {'state': 'unavailable'}), 'notify': False, 'cached': True}
    source = source or state.get('source') or SOURCE
    if not source.startswith(('https://', 'file://')):
        raise ValueError('Use HTTPS release metadata, or an explicit local file fixture')
    try:
        with urllib.request.urlopen(source, timeout=timeout) as response:
            raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError('Release metadata exceeds 1 MiB')
        release = json.loads(raw)
        available = version(release['version']) > version(installed['version'])
        result = {'state': 'available' if available else 'current', 'installed': installed['version'],
                  'release': release, 'source': source, 'notify': bool(available and state.get('remind', True)
                    and release['version'] not in {state.get('notified'), state.get('skip')})}
        if result['notify']:
            state['notified'] = release['version']
    except Exception as error:
        result = {'state': 'unavailable', 'error': str(error), 'notify': False, 'source': source}
    state.update(checked_at=now, last_result=result)
    atomic_json(path, state)
    return result


def fetch_release(source=SOURCE, *, timeout=5):
    if not source.startswith(('https://', 'file://')):
        raise ValueError('Release metadata must use HTTPS or explicit local fixture')
    with urllib.request.urlopen(source, timeout=timeout) as response:
        raw = response.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise ValueError('Release metadata exceeds 1 MiB')
    result = json.loads(raw)
    version(result['version'])
    return result


def _stage_release(release):
    version(release['version'])
    if not re.fullmatch(r'[0-9a-f]{64}', release.get('sha256', '')):
        raise ValueError('Release requires SHA-256')
    if not release['url'].startswith(('https://', 'file://')):
        raise ValueError('Release package must use HTTPS or explicit local fixture')
    root = locations(create=True)['home'] / 'updates' / uuid.uuid4().hex
    root.mkdir(parents=True)
    archive = download(release['url'], locations()['cache'] / (release['sha256'] + '.zip'), sha256=release['sha256'])
    stage = root / 'skill'
    stage.mkdir()
    with zipfile.ZipFile(archive) as zipped:
        infos = zipped.infolist()
        if len(infos) > 10000 or sum(i.file_size for i in infos) > 512 * 1024 ** 2:
            raise ValueError('Release archive exceeds size/count limits')
        names = set()
        for item in infos:
            if item.is_dir() or not item.filename.startswith('ezarch/'):
                raise ValueError('Release must contain individual ezarch/ files')
            name = safe_name(item.filename[len('ezarch/'):])
            if name.casefold() in names or (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('Duplicate path or symlink in release')
            names.add(name.casefold())
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(zipped.read(item))
    marker = read_json(stage / MARKER, {})
    files = marker.get('files', {})
    if marker.get('version') != release['version'] or not files or set(n.casefold() for n in [*files, MARKER]) != names:
        raise ValueError('Package manifest/version mismatch')
    for name, expected in files.items():
        if digest(stage / safe_name(name)) != expected:
            raise ValueError(f'Package file checksum mismatch: {name}')
        if name.endswith('.py'):
            compile((stage / name).read_bytes(), name, 'exec')
    if not (stage / 'SKILL.md').is_file() or not (stage / 'pyproject.toml').is_file():
        raise ValueError('Package missing skill entry or metadata')
    return root, stage


def install_release(destination, release):
    """First install into an unused location; keep unknown old installations untouched."""
    from .storage import output_path
    target = output_path(destination)
    if target.exists():
        raise FileExistsError('Choose an unused installation path; existing installation and contents are preserved')
    _, stage = _stage_release(release)
    with lock(state_path(target).with_suffix('.active.lock')):
        if target.exists():
            raise FileExistsError(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + '.install-' + uuid.uuid4().hex)
        try:
            shutil.copytree(stage, temporary)
            os.replace(temporary, target)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
    return {'state': 'installed_reload_required', 'target': str(target), 'version': release['version'],
            'runtime': 'prepare dependencies or reuse a compatible registered environment'}


def prepare(target, release):
    target, installed = identity(target)
    if version(release['version']) <= version(installed['version']):
        raise ValueError('Release is not newer than this installation')
    root, stage = _stage_release(release)
    atomic_json(root / 'prepared.json', {'target': str(target), 'stage': str(stage), 'version': release['version'],
                                        'from_version': installed['version']})
    return {'state': 'prepared', 'prepared': str(root / 'prepared.json'), 'version': release['version'],
            'activation': 'explicit safe activation; reload skill after activation'}


def recover(target):
    """Rollback an interrupted file transaction before any new activation."""
    journal = state_path(target).with_suffix('.transaction.json')
    transaction = read_json(journal)
    if not transaction:
        return False
    for name, existed in transaction['files'].items():
        destination = Path(target) / safe_name(name)
        if existed:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(transaction['backup']) / name, destination)
        else:
            destination.unlink(missing_ok=True)
    journal.unlink()
    return True


def activate(target, prepared):
    target = Path(target).resolve()
    state = state_path(target)
    with lock(state.with_suffix('.active.lock')):
        leases = state.with_suffix('.users')
        if leases.exists() and any(leases.iterdir()):
            raise RuntimeError('Installation is in use; activate after tasks exit. Inspect PIDs for stale leases.')
        recover(target)
        target, old = identity(target)
        record = read_json(prepared)
        if record['target'] != str(target) or record['from_version'] != old['version']:
            raise ValueError('Prepared update belongs to another installation/version')
        stage = Path(record['stage'])
        new = read_json(stage / MARKER)
        for name, expected in old['files'].items():
            path = target / name
            if not path.is_file() or path.is_symlink() or digest(path) != expected:
                raise ValueError(f'Local changes preserved; update stopped at {name}')
        names = set(old['files']) | set(new['files']) | {MARKER}
        for name in names:
            safe_name(name)
            destination = target / name
            for component in (destination, *destination.parents):
                if component == target:
                    break
                if component.is_symlink() or component.is_junction():
                    raise ValueError(f'Local linked path preserved: {component}')
            if not destination.resolve().is_relative_to(target):
                raise ValueError('Linked destination leaves installation')
            if name in new['files']:
                if digest(stage / name) != new['files'][name]:
                    raise ValueError('Prepared files changed')
                if name not in old['files'] and destination.exists():
                    raise ValueError(f'Unknown local file preserved: {name}')
        backup = locations(create=True)['home'] / 'updates' / ('backup-' + uuid.uuid4().hex)
        existed = {}
        for name in names:
            path = target / name
            existed[name] = path.exists()
            if existed[name]:
                saved = backup / name
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, saved)
        journal = state.with_suffix('.transaction.json')
        atomic_json(journal, {'backup': str(backup), 'files': existed})
        try:
            for name in sorted(names - {MARKER}) + [MARKER]:
                destination = target / name
                if name in new['files'] or name == MARKER:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    temp = destination.with_name(destination.name + '.update-' + uuid.uuid4().hex)
                    try:
                        shutil.copy2(stage / name, temp)
                        os.replace(temp, destination)
                    finally:
                        temp.unlink(missing_ok=True)
                else:
                    destination.unlink()
            journal.unlink()
        except Exception:
            recover(target)
            raise
        return {'state': 'activated_reload_required', 'version': new['version'], 'backup': str(backup),
                'target': str(target), 'runtime_may_need_preparation': old['files'].get('uv.lock') != new['files'].get('uv.lock')}


def rollback(target, backup):
    target, current = identity(target)
    backup = Path(backup).resolve()
    record = locations(create=True)['temp'] / ('rollback-' + uuid.uuid4().hex + '.json')
    atomic_json(record, {'target': str(target), 'stage': str(backup), 'from_version': current['version']})
    try:
        return activate(target, record)
    finally:
        record.unlink(missing_ok=True)


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['install', 'check', 'prepare', 'activate', 'rollback', 'preferences', 'recover'])
    parser.add_argument('target', type=Path)
    parser.add_argument('--source')
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--prepared', type=Path)
    parser.add_argument('--backup', type=Path)
    parser.add_argument('--auto', action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument('--remind', action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument('--skip')
    a = parser.parse_args(argv)
    if a.operation == 'install':
        result = install_release(a.target, fetch_release(a.source or SOURCE))
    elif a.operation == 'preferences':
        result = preferences(a.target, auto=a.auto, remind=a.remind, skip=a.skip, source=a.source)
    elif a.operation == 'rollback':
        if not a.backup:
            parser.error('--backup is required')
        result = rollback(a.target, a.backup)
    elif a.operation == 'activate':
        if not a.prepared:
            parser.error('--prepared is required')
        result = activate(a.target, a.prepared)
    elif a.operation == 'recover':
        with lock(state_path(a.target).with_suffix('.active.lock')):
            result = {'recovered': recover(a.target)}
    else:
        result = check(a.target, source=a.source, force=a.force)
        state = read_json(state_path(a.target), {})
        if result['state'] == 'available' and (a.operation == 'prepare' or state.get('auto')):
            if state.get('prepared', {}).get('version') == result['release']['version']:
                result = state['prepared']
            else:
                with lock(state_path(a.target).with_suffix('.prepare.lock')):
                    result = prepare(a.target, result['release'])
                    atomic_json(state_path(a.target), {**read_json(state_path(a.target), {}), 'prepared': result})
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(result.get('state') == 'unavailable')


if __name__ == '__main__':
    raise SystemExit(main())
