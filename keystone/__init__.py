"""Compatibility imports for installations created before the Mnemos rename."""
import importlib
import sys
from mnemos import __version__
for _name in ("core", "backup", "recall", "export", "server"):
    _module = importlib.import_module("mnemos." + _name)
    sys.modules[__name__ + "." + _name] = _module
    globals()[_name] = _module
