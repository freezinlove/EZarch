"""Standalone standard-library updater, usable before the drawing runtime exists."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from ezarch.updates import main  # noqa: E402

raise SystemExit(main())
