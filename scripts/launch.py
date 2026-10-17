#!/usr/bin/env python3
"""Start the local library and open its browser interface."""
import argparse
from pathlib import Path
import subprocess
import sys
import threading
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from keystone.server import KeystoneServer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', default=str(ROOT / 'data'))
    parser.add_argument('--port', type=int, default=4318)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    data = Path(args.data).expanduser().resolve()
    if not (data / 'config.json').exists():
        subprocess.run([sys.executable, str(ROOT / 'scripts' / 'setup.py'), '--data', str(data)], check=True)
    server = KeystoneServer(('127.0.0.1', args.port), data)
    url = f'http://127.0.0.1:{server.server_address[1]}'
    print(f'Keystone: {url}\nKeep this window open. Press Ctrl+C to stop.', flush=True)
    if not args.no_browser:
        timer = threading.Timer(0.3, lambda: webbrowser.open(url))
        timer.daemon = True
        timer.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'Could not start Keystone: {error}', file=sys.stderr)
        raise SystemExit(1)
