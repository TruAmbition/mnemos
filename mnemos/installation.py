"""Resolve the installation default once, preserving explicitly pinned paths."""
from pathlib import Path

from . import core


def resolve_data(value=None):
    """Use this checkout's saved selection only when no path was supplied."""
    if value is not None:
        # Leave symlinks intact so storage validation can reject them.
        return Path(value).expanduser().absolute()
    from .onboarding import load_selection
    default = core.ROOT / 'data'
    return load_selection(default / 'installation.json', default)
