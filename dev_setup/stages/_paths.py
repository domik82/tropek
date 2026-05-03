"""Shared path utilities for dev_setup stages."""

from pathlib import Path


def find_project_root() -> Path:
    """Walk up from this file until we find the workspace-level pyproject.toml."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        candidate = current / 'pyproject.toml'
        if candidate.exists() and '[tool.uv.workspace]' in candidate.read_text():
            return current
        current = current.parent
    raise FileNotFoundError('could not find workspace root (pyproject.toml with [tool.uv.workspace])')


PROJECT_ROOT = find_project_root()
