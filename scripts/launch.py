#!/usr/bin/env python3
"""Start the local library and open its browser interface."""
import argparse
from pathlib import Path
import sys
import threading
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mnemos.server import MnemosServer
from mnemos.onboarding import load_selection


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', help='Use this installation instead of the location selected in browser setup.')
    parser.add_argument('--port', type=int, default=4318)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    pointer = ROOT / 'data' / 'installation.json'
    if args.data:
        data = Path(args.data).expanduser().absolute()
        if data.is_symlink():
            raise ValueError('The Mnemos data folder must not be a symbolic link.')
        data = data.resolve()
    else:
        data = load_selection(pointer, ROOT / 'data')
    initialized = (data / 'config.json').exists()
    server = MnemosServer(('127.0.0.1', args.port), data, installation_file=None if args.data else pointer)
    url = f'http://127.0.0.1:{server.server_address[1]}' + ('' if initialized else '/setup.html')
    print(f'Mnemos: {url}\nKeep this window open. Press Ctrl+C to stop.', flush=True)
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
    except (OSError, ValueError) as error:
        print(f'Could not start Mnemos: {error}', file=sys.stderr)
        raise SystemExit(1)
