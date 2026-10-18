#!/usr/bin/env python3
"""Prepare and run a private OpenAI MCP tunnel without storing its runtime key."""
from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import warnings
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mnemos.core import load_config

TUNNEL_ID = re.compile(r'tunnel_(?:[a-z0-9]{4}_)?[a-z0-9]{32}\Z')
PROFILE = 'keystone'  # Stable runtime profile identity across the product rename.
ALLOWED_ENV = {
    'PATH', 'HOME', 'USERPROFILE', 'SystemRoot', 'SYSTEMROOT', 'WINDIR',
    'TEMP', 'TMP', 'TMPDIR', 'LANG', 'LC_ALL', 'LC_CTYPE',
    'HTTPS_PROXY', 'HTTP_PROXY', 'NO_PROXY', 'https_proxy', 'http_proxy', 'no_proxy',
    'SSL_CERT_FILE', 'SSL_CERT_DIR',
}


def child_environment(key=None):
    """Prevent unrelated tunnel settings and other API keys overriding the profile."""
    result = {name: value for name, value in os.environ.items() if name in ALLOWED_ENV}
    if key:
        result['CONTROL_PLANE_API_KEY'] = key
    return result


def executable(value):
    resolved = shutil.which(value) if not Path(value).is_absolute() else value
    if not resolved or not Path(resolved).is_file():
        raise ValueError('Install the official OpenAI tunnel-client and provide its executable with --binary.')
    return str(Path(resolved).resolve())


def preflight(data):
    load_config(data)
    command = [sys.executable, str(ROOT / 'scripts/mcp_server.py'), '--data', str(data)]
    requests = [
        {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {
            'protocolVersion': '2025-03-26', 'clientInfo': {'name': 'mnemos-tunnel-check', 'version': '1'},
            'capabilities': {}}},
        {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
        {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
    ]
    result = subprocess.run(command, input=''.join(json.dumps(item) + '\n' for item in requests),
                            text=True, capture_output=True, timeout=20, env=child_environment())
    try:
        replies = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        listed = next(item['result']['tools'] for item in replies if item.get('id') == 2)
        tools = {item['name'] for item in listed}
    except (ValueError, KeyError, StopIteration, TypeError):
        raise ValueError('Mnemos MCP preflight failed. Check the data path and Python installation.') from None
    if result.returncode or not {'recall_context', 'capture_document'} <= tools:
        raise ValueError('Mnemos MCP preflight failed to expose capture and recall tools.')
    # tunnel-client parses a command string; shlex quotes spaces and special characters.
    return shlex.join(command)


def profile_location(data):
    path = data / 'connections' / 'chatgpt'
    for candidate in (data, data / 'connections', path):
        if candidate.is_symlink():
            raise ValueError('The connection directory must not be a symbolic link.')
    return path


def prepare(data, binary, tunnel_id):
    if not TUNNEL_ID.fullmatch(tunnel_id):
        raise ValueError('Use the complete tunnel ID supplied by OpenAI Platform.')
    data = Path(data).absolute()
    profile_dir = profile_location(data)
    command = preflight(data.resolve())
    expected = {'tunnel_id': tunnel_id, 'data': str(data.resolve()), 'mcp_command': command}
    receipt_path = profile_dir / 'keystone-connection.json'
    profile_path = profile_dir / 'keystone.yaml'
    if profile_dir.exists():
        receipt = read_receipt(data)
        if {name: receipt.get(name) for name in expected} != expected:
            raise ValueError('This installation already has a different ChatGPT connection. Preserve or move its connection directory before preparing another.')
        return {'status': 'already-prepared', 'profile': str(profile_path)}
    profile_dir.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(prefix='.chatgpt-prepare-', dir=profile_dir.parent) as temporary:
        pending = Path(temporary) / 'profile'
        pending.mkdir(mode=0o700)
        result = subprocess.run([
            binary, 'init', '--sample', 'sample_mcp_stdio_local', '--profile', PROFILE,
            '--profile-dir', str(pending), '--tunnel-id', tunnel_id,
            '--mcp-command', command, '--health-listen-addr', '127.0.0.1:0',
            '--control-plane-api-key-ref', 'env:CONTROL_PLANE_API_KEY',
        ], text=True, capture_output=True, timeout=20, env=child_environment())
        created = pending / 'keystone.yaml'
        if result.returncode or not created.is_file():
            raise ValueError('The official client could not prepare the profile: ' + result.stderr.strip())
        created.chmod(0o600)
        expected['profile_sha256'] = hashlib.sha256(created.read_bytes()).hexdigest()
        with (pending / receipt_path.name).open('x', encoding='utf-8') as file:
            json.dump(expected, file, indent=2)
            file.write('\n')
        (pending / receipt_path.name).chmod(0o600)
        pending.rename(profile_dir)
    return {'status': 'prepared', 'profile': str(profile_path)}


def read_receipt(data):
    profile_dir = profile_location(Path(data).absolute())
    receipt_path = profile_dir / 'keystone-connection.json'
    profile_path = profile_dir / 'keystone.yaml'
    if receipt_path.is_symlink() or profile_path.is_symlink():
        raise ValueError('Connection files must not be symbolic links.')
    try:
        receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
        valid = (isinstance(receipt, dict)
                 and receipt.get('data') == str(Path(data).resolve())
                 and hashlib.sha256(profile_path.read_bytes()).hexdigest() == receipt.get('profile_sha256'))
    except (OSError, ValueError):
        valid = False
    if not valid:
        raise ValueError('No intact prepared profile was found. Run prepare first; preserve changed profiles before replacing them.')
    return receipt


def runtime_key():
    key = os.environ.get('MNEMOS_TUNNEL_API_KEY') or os.environ.get('KEYSTONE_TUNNEL_API_KEY') or os.environ.get('CONTROL_PLANE_API_KEY')
    if not key:
        if not sys.stdin.isatty():
            raise ValueError('Run in a terminal for hidden key entry, or provide MNEMOS_TUNNEL_API_KEY through a secure environment.')
        with warnings.catch_warnings():
            warnings.simplefilter('error', getpass.GetPassWarning)
            try:
                key = getpass.getpass('OpenAI tunnel runtime key (hidden; never saved): ')
            except getpass.GetPassWarning:
                raise ValueError('Secure terminal input is unavailable; no credential was read.') from None
    if not key or any(character.isspace() for character in key) or key.startswith('sk-admin-'):
        raise ValueError('Provide a runtime key with Tunnels Read + Use, not an admin key.')
    return key


def command_for(data, binary, action):
    read_receipt(data)
    profile_dir = profile_location(Path(data).absolute())
    command = [binary, action, '--profile', PROFILE, '--profile-dir', str(profile_dir),
               '--control-plane.api-key', 'env:CONTROL_PLANE_API_KEY',
               '--control-plane.base-url', 'https://api.openai.com',
               '--health.listen-addr', '127.0.0.1:0', '--log.http-raw-unsafe=false']
    if action == 'doctor':
        command.append('--explain')
    else:
        command.extend(['--health.url-file', str(profile_dir / 'health.url'), '--log.level', 'info'])
    return command


def run_command(command, key):
    # A foreground process intentionally remains attached to this terminal. Never
    # persist the key, pass it in argv, or put it into a shell command/history.
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, env=child_environment(key), bufsize=1)
    try:
        for line in process.stdout:
            print(line.replace(key, '[REDACTED]'), end='', flush=True)
        return process.wait()
    except KeyboardInterrupt:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        return 130


def run_connected(data, binary, action):
    command = command_for(data, binary, action)
    return run_command(command, runtime_key())


def check_and_run(data, binary):
    doctor = command_for(data, binary, 'doctor')
    run = command_for(data, binary, 'run')
    key = runtime_key()
    print('Checking the Mnemos connection...', flush=True)
    result = run_command(doctor, key)
    if result:
        return result
    print('Starting Mnemos for ChatGPT. Keep this terminal open; press Control-C to disconnect.', flush=True)
    return run_command(run, key)


def default_binary(data):
    local = Path(data).absolute() / 'tools' / ('tunnel-client.exe' if os.name == 'nt' else 'tunnel-client')
    return str(local) if local.is_file() else 'tunnel-client'


def status(data):
    read_receipt(data)
    path = profile_location(Path(data).absolute()) / 'health.url'
    if path.is_symlink():
        raise ValueError('Health URL must not be a symbolic link.')
    try:
        url = path.read_text(encoding='utf-8').strip()
    except OSError:
        raise ValueError('No running-client health address exists yet. Start run in a terminal.') from None
    parsed = urlsplit(url)
    if (parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or not parsed.port
            or parsed.username or parsed.password or parsed.path not in ('', '/')
            or parsed.query or parsed.fragment):
        raise ValueError('Unexpected health address; only the local tunnel listener is allowed.')
    # Bypass outbound proxy settings when querying this loopback-only listener.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, request, file, code, message, headers, newurl):
            return None
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    result = {}
    for label, endpoint in [('healthy', '/healthz'), ('ready', '/readyz')]:
        try:
            with opener.open(url.rstrip('/') + endpoint, timeout=5) as response:
                result[label] = response.status == 200
        except OSError:
            result[label] = False
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'doctor', 'run', 'connect', 'status'])
    parser.add_argument('--data', type=Path, default=ROOT / 'data')
    parser.add_argument('--binary', default=os.environ.get('MNEMOS_TUNNEL_CLIENT') or os.environ.get('KEYSTONE_TUNNEL_CLIENT'),
                        help='Official executable; defaults to data/tools/tunnel-client or PATH.')
    parser.add_argument('--tunnel-id', help='Nonsecret tunnel ID; required for prepare.')
    args = parser.parse_args()
    try:
        if args.action == 'status':
            result = status(args.data)
        else:
            binary = executable(args.binary or default_binary(args.data))
            if args.action == 'prepare':
                if not args.tunnel_id:
                    parser.error('prepare requires --tunnel-id')
                result = prepare(args.data, binary, args.tunnel_id)
            elif args.action == 'connect':
                return check_and_run(args.data, binary)
            else:
                return run_connected(args.data, binary, args.action)
        print(json.dumps(result, indent=2))
        return 0 if args.action != 'status' or result['healthy'] and result['ready'] else 1
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        print('Mnemos connection: ' + str(error), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('\nMnemos connection cancelled.', file=sys.stderr)
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
