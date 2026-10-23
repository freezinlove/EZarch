"""Prepare selected capabilities; keep successful capabilities usable after other failures."""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from ezarch import runtime  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument('--profile', choices=['core', 'model', 'draft', 'render', 'all', 'dev'], default='core')
parser.add_argument('--home', type=Path)
parser.add_argument('--install-blender', action='store_true')
parser.add_argument('--install-oda', action='store_true')
parser.add_argument('--install-font', action='store_true')
args = parser.parse_args()
if sys.platform not in ('win32', 'darwin'):
    raise SystemExit('EZarch releases support Windows and macOS only.')
if args.home:
    runtime.configure(args.home)
paths = runtime.locations(create=True)
previous = runtime.read_json(runtime.binding_file(root), {})
extras = set(previous.get('extras', []))
if args.profile in ('model', 'all', 'dev'):
    extras.add('model')
if args.profile == 'dev':
    extras.add('dev')
result = {'location': str(paths['home']), 'capabilities': {}}
try:
    installed = runtime.prepare(root, extras=extras, uv=os.environ.get('EZARCH_UV') or shutil.which('uv'))
    result['capabilities']['python'] = {'state': 'ready', **installed}
except Exception as error:
    result['capabilities']['python'] = {'state': 'failed', 'error': str(error)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(1) from error
python = installed['python']
env = runtime.process_env()
env['PYTHONPATH'] = str(root / 'src') + os.pathsep + env.get('PYTHONPATH', '')
for name, enabled in [('blender', args.install_blender or args.profile in ('model', 'render', 'all')),
                      ('oda', args.install_oda), ('font', args.install_font)]:
    if not enabled:
        continue
    call = subprocess.run([python, '-c', f'from ezarch.environment import install_{name}; print(install_{name}())'],
                          env=env, text=True, capture_output=True)
    result['capabilities'][name] = {'state': 'ready' if call.returncode == 0 else 'failed',
                                    'detail': (call.stdout + call.stderr)[-6000:]}
runtime.atomic_json(paths['state'] / 'last-install.json', result)
print(json.dumps(result, ensure_ascii=False, indent=2))
raise SystemExit(int(any(item['state'] == 'failed' for item in result['capabilities'].values())))
