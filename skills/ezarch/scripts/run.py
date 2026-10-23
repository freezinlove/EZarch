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
raise SystemExit(subprocess.call([str(python), '-m', 'ezarch.cli', *sys.argv[1:]], env=env))
