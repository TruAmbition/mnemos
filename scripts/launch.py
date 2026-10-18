#!/usr/bin/env python3
"""Open Mnemos, reusing its local service or starting it in the background."""
import argparse
import html
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mnemos.server import MnemosServer
from mnemos.onboarding import load_selection
from mnemos.runtime import default_root, tool_command


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def running(port):
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open(f'http://127.0.0.1:{port}/api/runtime', timeout=.5) as response:
            value = json.loads(response.read(16384))
        return value if value.get('kind') == 'mnemos-local-runtime-v1' else None
    except (OSError, ValueError):
        return None


def same_runtime(status, pointer, data):
    return bool(status and not status.get('stopping') and status.get('installation') == (str(pointer) if pointer else None)
                and (pointer or status.get('data_path') == str(data)))


def failure_page(message, folder):
    folder.mkdir(parents=True, exist_ok=True)
    page = folder / 'launch-error.html'
    if page.is_symlink():
        return
    page.write_text('<!doctype html><meta charset="utf-8"><title>Mnemos · Start help</title>'
                    '<style>body{font:18px system-ui;max-width:680px;margin:12vh auto;padding:24px;line-height:1.6}'
                    'h1{color:#304a37}</style><h1>Mnemos could not start</h1><p>' + html.escape(message) +
                    '</p><p>Your notes have not been changed. If another Mnemos window is running, open its '
                    'Connections page and stop that local service, then reopen this app.</p>')
    webbrowser.open(page.as_uri())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument('--data', help='Pin this workspace instead of following the saved default.')
    selection.add_argument('--installation', type=Path, help='Follow this installation.json default selection (native manager).')
    parser.add_argument('--port', type=int, default=4318)
    parser.add_argument('--no-browser', action='store_true', help='Run in the foreground without a browser (automation).')
    parser.add_argument('--background', action='store_true', help='Start a detached service, also when --no-browser is supplied.')
    parser.add_argument('--foreground', action='store_true', help='Keep the service in this terminal for diagnostics.')
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        raise ValueError('Choose a port between 0 and 65535.')
    base = default_root() if getattr(sys, 'frozen', False) else ROOT / 'data'
    if args.installation:
        if not args.installation.is_absolute() or args.installation.name != 'installation.json':
            raise ValueError('Choose an absolute installation.json path.')
        base = args.installation.parent
    pointer = None if args.data else base / 'installation.json'
    data = Path(args.data).expanduser().absolute() if args.data else load_selection(pointer, base)
    if data.is_symlink():
        raise ValueError('The Mnemos data folder must not be a symbolic link.')
    data = data.resolve()
    foreground = args.foreground or (args.no_browser and not args.background)
    if not foreground and args.port == 0:
        raise ValueError('Use a fixed port for the desktop launcher.')
    if not foreground:
        status = running(args.port)
        for _ in range(50):
            if not status or not status.get('stopping'):
                break
            time.sleep(.1)
            status = running(args.port)
        if status and status.get('stopping'):
            raise ValueError('Mnemos is still stopping. Wait a moment, then reopen the app.')
        if status and not same_runtime(status, pointer, data):
            raise ValueError(f'Port {args.port} is already serving a different Mnemos installation. Stop it from its Connections page, or use a different --port.')
        if not status:
            logs = (pointer.parent if pointer else data).parent / '.mnemos-runtime'
            logs.mkdir(parents=True, exist_ok=True)
            if logs.is_symlink():
                raise ValueError('Runtime directory must not be a symbolic link.')
            log = logs / 'launcher.log'
            if log.is_symlink():
                raise ValueError('Runtime log must not be a symbolic link.')
            # Keep a bounded, private diagnostic log. No credentials are needed here.
            fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            os.chmod(log, 0o600)
            command = tool_command('launch', '--foreground', '--no-browser', '--port', args.port)
            if args.data:
                command += ['--data', str(data)]
            elif args.installation:
                command += ['--installation', str(pointer)]
            options = {'start_new_session': True} if os.name != 'nt' else {'creationflags': subprocess.CREATE_NO_WINDOW}
            with os.fdopen(fd, 'w') as output:
                child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=output, stderr=output,
                                         cwd=str(ROOT), close_fds=True, **options)
            for _ in range(200):
                status = running(args.port)
                if same_runtime(status, pointer, data):
                    break
                if child.poll() is not None:
                    raise ValueError(f'Mnemos could not open port {args.port}. Another app may be using it. Diagnostics: {log}')
                time.sleep(.1)
            else:
                raise ValueError(f'Mnemos is taking longer than expected to start. Diagnostics: {log}. Reopen the app to retry.')
        url = f'http://127.0.0.1:{args.port}' + ('' if status.get('initialized') else '/setup.html')
        if not args.no_browser:
            webbrowser.open(url)
        print(f'Mnemos is running at {url}. Stop it from Connections.', flush=True)
        return
    initialized = (data / 'config.json').exists()
    server = MnemosServer(('127.0.0.1', args.port), data, installation_file=pointer)
    server.launcher_managed = True
    url = f'http://127.0.0.1:{server.server_address[1]}' + ('' if initialized else '/setup.html')
    print(f'Mnemos: {url}\nStop from Connections or press Ctrl+C.', flush=True)
    if not args.no_browser:
        timer = threading.Timer(.3, lambda: webbrowser.open(url))
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
        if '--no-browser' not in sys.argv and '--foreground' not in sys.argv:
            try:
                failure_page(str(error), default_root().parent / '.mnemos-runtime')
            except OSError:
                pass
        raise SystemExit(1)
