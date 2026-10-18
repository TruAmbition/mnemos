#!/usr/bin/env python3
"""Standalone entry point: desktop launcher or an explicitly selected bundled tool."""
from pathlib import Path
import runpy
import sys

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(ROOT))

if __name__ == '__main__':
    from mnemos.runtime import TOOLS
    tool = 'launch'
    args = sys.argv[1:]
    if args[:1] == ['--tool']:
        if len(args) < 2 or args[1] not in TOOLS:
            raise SystemExit('Choose a supported Mnemos tool.')
        tool, args = args[1], args[2:]
    elif args[:1] == ['--cli']:
        from mnemos.__main__ import main
        raise SystemExit(main(args[1:]))
    sys.argv = [str(ROOT / 'scripts' / (tool + '.py')), *args]
    runpy.run_path(sys.argv[0], run_name='__main__')
