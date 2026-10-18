#!/usr/bin/env python3
"""Connect a local Mnemos vault to Claude Desktop, preserving existing settings.

The default is a read-only preflight. Pass --apply to save the configuration.
This does not connect claude.ai, Cowork, or Claude Code, and never restarts Claude.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mnemos.core import load_config
from scripts.install_agents import matching_connection


def default_config_path():
    if platform.system() == 'Darwin':
        return Path.home() / 'Library/Application Support/Claude/claude_desktop_config.json'
    if platform.system() == 'Windows':
        roaming = os.environ.get('APPDATA')
        if not roaming:
            raise ValueError('APPDATA is missing. Supply the config path shown in Claude Developer settings.')
        return Path(roaming) / 'Claude/claude_desktop_config.json'
    raise ValueError('Use --config with the path shown in your Claude Desktop Developer settings.')


def connection_for(data):
    data = Path(data).expanduser().resolve()
    load_config(data)
    return {
        'command': str(Path(sys.executable).resolve()),
        'args': [str(ROOT / 'scripts/mcp_server.py'), '--data', str(data)],
    }


def probe_connection(connection):
    """Exercise the real stdio process without reading or changing any documents."""
    requests = [
        {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {
            'protocolVersion': '2025-03-26', 'capabilities': {},
            'clientInfo': {'name': 'mnemos-claude-setup', 'version': '0.2.0'}}},
        {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
        {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list', 'params': {}},
    ]
    try:
        result = subprocess.run(
            [connection['command'], *connection['args']],
            input=''.join(json.dumps(message) + '\n' for message in requests),
            text=True, capture_output=True, timeout=15, check=True,
        )
        responses = [json.loads(line) for line in result.stdout.splitlines()]
        initialized = next(item for item in responses if item.get('id') == 1)
        listed = next(item for item in responses if item.get('id') == 2)
        names = {item['name'] for item in listed['result']['tools']}
        if initialized['result']['serverInfo']['name'] != 'mnemos' or not {
            'search_documents', 'read_document', 'capture_document', 'recall_context'
        }.issubset(names):
            raise ValueError('Required Mnemos tools were not returned.')
        return sorted(names)
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, StopIteration, TypeError) as error:
        # Do not echo subprocess output or the user's existing settings.
        raise ValueError('Mnemos MCP preflight failed; Claude settings were not changed.') from error


def install_claude_desktop(data, config_path=None, apply=False):
    config_path = Path(config_path or default_config_path()).expanduser().absolute()
    if config_path.is_symlink() or config_path.parent.is_symlink():
        raise ValueError('Refusing a symlinked Claude config file or config directory.')
    original = config_path.read_bytes() if config_path.exists() else None
    try:
        config = json.loads(original) if original is not None else {}
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError('Existing Claude config is invalid JSON; it was left unchanged.') from error
    if not isinstance(config, dict):
        raise ValueError('Existing Claude config must be an object; it was left unchanged.')
    servers = config.get('mcpServers', {})
    if not isinstance(servers, dict):
        raise ValueError('Existing mcpServers must be an object; settings were left unchanged.')
    connection = connection_for(data)
    for name in ('mnemos', 'keystone'):
        if name in servers and not matching_connection(servers[name], connection):
            raise ValueError('Claude already has a different Mnemos or legacy Keystone connection. It was left unchanged.')
    if 'mnemos' in servers and 'keystone' in servers and servers['mnemos'] != servers['keystone']:
        raise ValueError('Mnemos and legacy Keystone settings differ. Resolve the duplicate before applying; nothing was changed.')
    tool_names = probe_connection(connection)
    legacy = 'keystone' in servers
    changed = 'mnemos' not in servers or legacy
    result = {
        'config': str(config_path), 'data': str(Path(data).expanduser().resolve()),
        'status': 'already-configured' if not changed else ('installed' if apply else 'ready'),
        'tools': tool_names, 'backup': None, 'migrates_legacy_name': legacy,
        'notice': 'Fully quit and reopen Claude Desktop to activate a new connection. This installer does not restart the app.',
    }
    if not apply or not changed:
        return result
    migrated = dict(servers)
    migrated['mnemos'] = migrated.get('mnemos', migrated.get('keystone', connection))
    migrated.pop('keystone', None)
    config['mcpServers'] = migrated
    content = (json.dumps(config, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    config_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix='.mnemos-claude-', suffix='.tmp', dir=config_path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        current = config_path.read_bytes() if config_path.exists() else None
        if current != original or config_path.is_symlink():
            raise ValueError('Claude settings changed during setup. Run setup again; nothing was overwritten.')
        if original is not None:
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            backup = config_path.with_name(config_path.name + f'.mnemos-backup-{stamp}-{uuid.uuid4().hex[:8]}')
            descriptor = os.open(backup, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(original)
                stream.flush()
                os.fsync(stream.fileno())
            result['backup'] = str(backup)
        os.replace(temporary, config_path)
    finally:
        temporary.unlink(missing_ok=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', required=True, help='Initialized Mnemos data directory.')
    parser.add_argument('--config', help='Override the Claude Desktop config path.')
    parser.add_argument('--apply', action='store_true', help='Save the connection after successful preflight.')
    args = parser.parse_args()
    print(json.dumps(install_claude_desktop(args.data, args.config, args.apply), indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as error:
        print(f'Claude Desktop setup could not finish: {error}', file=sys.stderr)
        raise SystemExit(1)
