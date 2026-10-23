"""Explicit file-list conversion, PDF combination and packaging."""
from __future__ import annotations

import os
import tempfile
import zipfile
from pathlib import Path

from .cad import sha256
from .storage import output_path


def convert_many(items, *, previous=(), retries=0, timeout=180):
    """Each item supplies source/target and optional version/repair; failures remain local."""
    from .cad import convert
    if not isinstance(retries, int) or not 0 <= retries <= 3:
        raise ValueError('retries must be between 0 and 3')
    items = list(items)
    targets = [str(output_path(item['target'])) for item in items]
    if len(targets) != len(set(t.casefold() for t in targets)):
        raise ValueError('Duplicate output target')
    old = {row['target']: row for row in previous}
    results = []
    for item, target in zip(items, targets):
        source = Path(item['source']).resolve()
        version, repair = item.get('version', 'ACAD2018'), bool(item.get('repair', False))
        row = {'source': str(source), 'target': target, 'version': version, 'repair': repair}
        try:
            row['source_sha256'] = sha256(source)
            before = old.get(target, {})
            if (before.get('state') == 'ready' and Path(target).is_file()
                    and all(before.get(key) == value for key, value in row.items())
                    and sha256(target) == before.get('output_sha256')):
                results.append({**before, 'reused': True})
                continue
            for attempt in range(retries + 1):
                try:
                    result = convert(source, target, version=version, repair=repair, timeout=timeout)
                    row.update(state='ready', output_sha256=result['output_sha256'], attempts=attempt + 1, reused=False)
                    break
                except Exception:
                    if attempt == retries or Path(target).exists():
                        raise
            results.append(row)
        except Exception as error:
            results.append({**row, 'state': 'failed', 'error': type(error).__name__, 'detail': str(error)})
    return results


def combine_pdfs(items, output, *, bookmarks=()):
    """Ordered paths or {file, pages:[1-based...]}; bookmark tuples use output page numbers."""
    import pymupdf as fitz
    output = output_path(output)
    if output.exists():
        raise FileExistsError(output)
    final = fitz.open()
    sources = []
    try:
        for value in items:
            item = {'file': value} if isinstance(value, (str, Path)) else value
            source = Path(item['file']).resolve()
            with fitz.open(source) as document:
                pages = list(range(1, len(document) + 1)) if item.get('pages') is None else list(item['pages'])
                if any(not isinstance(n, int) or not 1 <= n <= len(document) for n in pages):
                    raise ValueError(f'Invalid selected page for {source}')
                first = len(final) + 1
                for page in pages:
                    final.insert_pdf(document, from_page=page - 1, to_page=page - 1)
                sources.append({'file': str(source), 'sha256': sha256(source), 'pages': pages, 'first_output_page': first})
        if not len(final):
            raise ValueError('No pages selected')
        toc = [[1, str(title), page] for title, page in bookmarks]
        if any(not isinstance(row[2], int) or not 1 <= row[2] <= len(final) for row in toc):
            raise ValueError('Bookmark page outside selected output')
        if toc:
            final.set_toc(toc)
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=output.parent, suffix='.pdf', delete=False) as stream:
            temporary = Path(stream.name)
        try:
            final.save(temporary, garbage=4, deflate=True)
            os.replace(temporary, output)
        finally:
            temporary.unlink(missing_ok=True)
        return {'file': str(output), 'pages': len(final), 'sources': sources, 'sha256': sha256(output)}
    finally:
        final.close()


def collect_outputs(items, output):
    """Package exactly {archive_relative_name: file}; no directory sweep or guessed latest version."""
    from .updates import safe_name
    output = output_path(output)
    if output.exists():
        raise FileExistsError(output)
    if not items or len(items) != len({name.casefold() for name in items}):
        raise ValueError('Explicit unique archive names required')
    files = [(safe_name(name), Path(path).resolve()) for name, path in items.items()]
    if any(not path.is_file() or path == output for _, path in files):
        raise ValueError('Every selected output must be an existing separate file')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=output.parent, suffix='.zip', delete=False) as stream:
        temporary = Path(stream.name)
    try:
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for name, path in files:
                archive.write(path, name)
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return {'file': str(output), 'sha256': sha256(output),
            'items': [{'name': name, 'source': str(path), 'sha256': sha256(path)} for name, path in files]}


def main(argv=None):
    import argparse
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['convert', 'combine', 'collect'])
    parser.add_argument('items', type=Path, help='JSON explicit item list/mapping')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--previous', type=Path)
    a = parser.parse_args(argv)
    items = json.loads(a.items.read_text(encoding='utf-8'))
    if a.operation == 'convert':
        previous = json.loads(a.previous.read_text()) if a.previous else []
        result = convert_many(items, previous=previous)
    else:
        if a.out is None:
            parser.error('--out is required')
        result = combine_pdfs(items, a.out) if a.operation == 'combine' else collect_outputs(items, a.out)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(isinstance(result, list) and any(row['state'] == 'failed' for row in result))
