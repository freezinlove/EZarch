"""Optional native Blender execution and exchange; no project schema required."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from .environment import find_blender, install_blender
from .project import skill_root, write_json


def execute(script, out, *, source=None, save=None, arguments=(), timeout=1800):
    """Run an arbitrary script using Blender's Python, optionally continuing a .blend.

    This is trusted user/agent code, not a sandbox. Embedded scripts in source files
    stay disabled. A failed script never triggers the optional save operation.
    """
    script, out = Path(script).resolve(), Path(out).resolve()
    if not script.is_file():
        raise FileNotFoundError(script)
    from .storage import output_path
    out = output_path(out)
    out.mkdir(parents=True, exist_ok=True)
    request = {'action': 'run', 'script': str(script), 'arguments': list(arguments),
               'source': str(Path(source).resolve()) if source else None,
               'save': str(output_path(save)) if save else None}
    return _worker(request, out, timeout)


def _worker(request, out, timeout=1800):
    out = Path(out).resolve()
    from .storage import output_path
    out = output_path(out)
    out.mkdir(parents=True, exist_ok=True)
    request_path, report = out / 'blender-request.json', out / 'blender-result.json'
    write_json(request_path, request)
    report.unlink(missing_ok=True)
    executable = find_blender() or install_blender()
    command = [executable, '--background', '--factory-startup', '--disable-autoexec',
               '--python-exit-code', '1', '--python',
               str(skill_root() / 'scripts/blender_bridge.py'), '--',
               '--request', str(request_path), '--report', str(report)]
    log = out / 'blender.log'
    try:
        with log.open('w', encoding='utf-8') as stream:
            result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT,
                                    timeout=timeout, check=False)
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f'Blender exceeded {timeout}s; inspect {log}') from error
    if result.returncode or not report.is_file():
        raise RuntimeError(f'Blender failed ({result.returncode}); inspect {log}')
    return json.loads(report.read_text(encoding='utf-8'))


def extract(source, out, *, objects=None, collections=None, unit_scale_m=None):
    """Evaluated viewport meshes, including instances, in world-space millimetres."""
    out = Path(out).resolve()
    return _worker({'action': 'extract', 'source': str(Path(source).resolve()),
                    'target': str(out / 'scene.json'), 'objects': objects,
                    'collections': collections, 'unit_scale_m': unit_scale_m}, out)


def export_blend(source, out, formats=('glb',), **selection):
    from .exchange import export_scene
    out = Path(out).resolve()
    formats = list(dict.fromkeys(formats))
    if not formats or set(formats) - {'glb', '3dm', 'dae'}:
        raise ValueError('Supported .blend exchange formats: glb, 3dm, dae')
    extracted = extract(source, out / 'geometry', **selection)
    scene = json.loads(Path(extracted['file']).read_text(encoding='utf-8'))
    reports = export_scene(scene, out, [f for f in formats if f != 'glb']) if set(formats) - {'glb'} else []
    if 'glb' in formats:
        result = _worker({'action': 'glb', 'source': str(Path(source).resolve()),
                          'target': str(out / 'model.glb'), **selection}, out / 'glb-export')
        import numpy as np
        import trimesh
        loaded = trimesh.load(out / 'model.glb', force='scene')
        basis = np.array([[1, 0, 0, 0], [0, 0, -1, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
        loaded.apply_transform(basis)
        if not loaded.geometry:
            raise RuntimeError('GLB re-read contains no geometry')
        actual = loaded.bounds * 1000
        boxes = np.array([o['bounds_mm'] for o in scene['objects']])
        expected = np.array([boxes[:, :3].min(0), boxes[:, 3:].max(0)])
        error = float(np.max(np.abs(actual - expected)))
        result.update(bounds_mm=actual.tolist(), maximum_bounds_error_mm=error)
        if not np.allclose(actual, expected, rtol=1e-6, atol=.05):
            raise RuntimeError(f'GLB geometry bounds differ by {error:g} mm; inspect selection/modifier/instance export')
        reports.append(result)
    write_json(out / 'exchange-report.json', {'source': str(source), 'files': reports,
               'geometry': extracted, 'notes': [
                   '3DM/DAE adapter exports evaluated meshes and basic colors, not NURBS or shader graphs.',
                   'GLB uses Blender native material/UV export; unsupported procedural shaders need explicit baking.',
                   'Keep the .blend master and external dependencies for continued editing.']})
    return reports


def main(argv=None):
    parser = argparse.ArgumentParser(prog='ezarch blender')
    sub = parser.add_subparsers(dest='action', required=True)
    run = sub.add_parser('run', help='Execute arbitrary bpy code; optionally continue an existing .blend')
    run.add_argument('script', type=Path)
    run.add_argument('--source', type=Path)
    run.add_argument('--save', type=Path)
    run.add_argument('--out', type=Path, required=True)
    run.add_argument('--timeout', type=float, default=1800)
    for name in ('extract', 'export', 'view'):
        p = sub.add_parser(name)
        p.add_argument('source', type=Path)
        p.add_argument('--out', type=Path, required=True)
        p.add_argument('--objects', nargs='+')
        p.add_argument('--collections', nargs='+')
        p.add_argument('--unit-scale-m', type=float)
        if name == 'export':
            p.add_argument('--formats', nargs='+', choices=['glb', '3dm', 'dae'], default=['glb'])
        if name == 'view':
            p.add_argument('--spec', type=Path, required=True, help='JSON view settings; see geometry-drawings.md')
            p.add_argument('--formats', nargs='+', choices=['dxf', 'svg', 'pdf', 'png'], default=['dxf', 'pdf'])
    # Arguments following -- belong to the caller's Python script.
    argv = list(argv or [])
    extra = argv[argv.index('--') + 1:] if '--' in argv else []
    args = parser.parse_args(argv[:argv.index('--')] if '--' in argv else argv)
    if extra and args.action != 'run':
        parser.error('Only run accepts script arguments after --')
    if args.action == 'run':
        result = execute(args.script, args.out, source=args.source, save=args.save,
                         arguments=extra, timeout=args.timeout)
    else:
        options = {k: getattr(args, k) for k in ('objects', 'collections', 'unit_scale_m')}
        if args.action == 'export':
            result = export_blend(args.source, args.out, args.formats, **options)
        else:
            result = extract(args.source, args.out / 'geometry', **options)
            if args.action == 'view':
                from .mesh_views import save_mesh_view
                scene = json.loads(Path(result['file']).read_text(encoding='utf-8'))
                spec = json.loads(args.spec.read_text(encoding='utf-8'))
                if spec.get('font'):
                    spec['font'] = str((args.spec.resolve().parent / spec['font']).resolve())
                result = save_mesh_view(scene, spec, args.out, args.formats)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
