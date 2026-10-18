#!/usr/bin/env python3
"""Test the Swift client against an isolated, real local Python service (macOS)."""
from pathlib import Path
import argparse
import os
import subprocess
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mnemos.server import MnemosServer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scratch-path', type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='mnemos-native-test-') as directory:
        root = Path(directory).resolve()
        server = MnemosServer(('127.0.0.1', 0), root / 'data', installation_file=root / 'data/installation.json')
        server.launcher_managed = True
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        env = dict(os.environ, MNEMOS_TEST_PORT=str(server.server_port), MNEMOS_TEST_ROOT=str(root))
        command = ['swift', 'test', '--package-path', str(ROOT / 'desktop')]
        if args.scratch_path:
            command += ['--scratch-path', str(args.scratch_path.resolve())]
        try:
            result = subprocess.run(command, env=env)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
