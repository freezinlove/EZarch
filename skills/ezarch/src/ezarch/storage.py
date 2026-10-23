"""Output boundary protection, independent of any project directory structure."""
import os
from pathlib import Path


def protected_roots():
    source = Path(__file__).resolve()
    roots = []
    for parent in source.parents:
        if (parent / 'SKILL.md').is_file() and (parent / 'src/ezarch').is_dir():
            roots.append(parent)
        if (parent / 'skills/ezarch/SKILL.md').is_file() and (parent / '.git').exists():
            roots.append(parent)
    return roots


def output_path(path, *, allow_tool_write=False, roots=None):
    target = Path(path).expanduser().resolve()
    if allow_tool_write or os.environ.get('EZARCH_ALLOW_TOOL_WRITES') == '1':
        return target
    for root in protected_roots() if roots is None else roots:
        root = Path(root).resolve()
        if target.is_relative_to(root):
            raise ValueError(f'Project output targets EZarch code: {target}. Choose your project directory outside {root}. '
                             'For intentional skill maintenance only, use allow_tool_write=True or EZARCH_ALLOW_TOOL_WRITES=1.')
    return target
