"""Run this installation's code in a compatible prepared runtime."""
import os
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from ezarch.runtime import find_python, process_env  # noqa: E402

python = find_python(root)
if not python:
    raise SystemExit('No prepared runtime: use bootstrap, or python -m ezarch.cli in a compatible environment.')
env = process_env()
env['PYTHONPATH'] = str(root / 'src') + os.pathsep + env.get('PYTHONPATH', '')
from ezarch.runtime import read_json  # noqa: E402
from ezarch.updates import MARKER, check, state_path, usage  # noqa: E402

if (root / MARKER).is_file():
    try:
        result = check(root)
        if result.get('notify'):
            print(f"EZarch {result['release']['version']} is available; update can be requested at any time.", file=sys.stderr)
        state = read_json(state_path(root), {})
        if state.get('auto') and result['state'] == 'available' and state.get('prepared', {}).get('version') != result['release']['version']:
            with state_path(root).with_suffix('.log').open('a') as log:
                subprocess.Popen([str(python), str(root / 'scripts/update.py'), 'prepare', str(root)],
                                 env=env, stdout=log, stderr=log)
    except Exception as error:
        # Updating is optional and must never prevent the requested drawing operation.
        print(f"EZarch update check unavailable: {error}", file=sys.stderr)
with usage(root):
    raise SystemExit(subprocess.call([str(python), '-m', 'ezarch.cli', *sys.argv[1:]], env=env))
