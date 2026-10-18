"""Read-only connection inventory. Never execute commands from assistant settings."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib

from . import core
from .runtime import default_root, tool_command


def _read(path):
    if path.is_symlink() or path.stat().st_size > 2_000_000:
        raise ValueError('Configuration is a symbolic link or exceeds the inspection limit.')
    text = path.read_text(encoding='utf-8')
    value = tomllib.loads(text) if path.suffix == '.toml' else json.loads(text)
    if not isinstance(value, dict):
        raise ValueError('Configuration must be an object.')
    return value


def _entry(client, label, path, active, cache):
    result = {'id': client, 'name': label, 'config_path': str(path), 'status': 'disconnected',
              'detail': 'No Mnemos connection is configured here.', 'testable': False,
              'workspace': None, 'matches_active': None, 'last_tested': None}
    if not path.exists():
        return result
    try:
        settings = _read(path)
        servers = settings.get('mcp_servers' if path.suffix == '.toml' else 'mcpServers', {})
        if not isinstance(servers, dict):
            raise ValueError('MCP server settings must be an object.')
        names = [name for name in ('mnemos', 'keystone') if name in servers]
        if not names:
            return result
        if len(names) != 1:
            raise ValueError('Both Mnemos and Keystone are configured. Review the duplicate connections in this assistant.')
        entry = servers[names[0]]
        if not isinstance(entry, dict):
            raise ValueError('The Mnemos connection is malformed.')
        if entry.get('enabled') is False or entry.get('disabled') is True:
            result['detail'] = 'This connection is disabled in the assistant’s configuration.'
            return result
        command, args = entry.get('command'), entry.get('args', [])
        if not isinstance(command, str) or not isinstance(args, list) or any(not isinstance(a, str) for a in args):
            raise ValueError('This configuration is not a supported local Mnemos command. Review it in the assistant.')
        # Only recognize known command shapes; shell wrappers and remote URLs are not interpreted.
        frozen = args[:2] == ['--tool', 'mcp_server']
        source = bool(args and Path(args[0]).name == 'mcp_server.py' and Path(args[0]).is_absolute())
        if not frozen and not source:
            raise ValueError('This connection uses an unrecognized command. Review it in the assistant.')
        tail = args[2:] if frozen else args[1:]
        if tail and (len(tail) != 2 or tail[0] != '--data' or not Path(tail[1]).is_absolute()):
            raise ValueError('The configured workspace cannot be identified safely.')
        if not tail:
            # Only the running installation's executable/script has a known default.
            own = tool_command('mcp_server')
            actual = [command, *args]
            if actual != own:
                raise ValueError('This connection follows another installation’s default. Its active workspace is unknown here.')
            from .installation import resolve_data
            target = resolve_data()
        else:
            target = Path(tail[1]).expanduser().resolve()
        result.update(workspace=str(target), matches_active=target == active,
                      binding='Pinned workspace' if tail else 'Default at assistant startup')
        resolved = shutil.which(command)
        if not resolved or (source and not Path(args[0]).is_file()):
            raise ValueError('The configured launcher is missing. Reinstall this assistant connection from Workspace setup.')
        core.load_config(target)
        result.update(status='configured', testable=True,
                      detail='Configuration found. The assistant has not been contacted; restart or reload it after changes.')
        fingerprint = hashlib.sha256(json.dumps(entry, sort_keys=True).encode()).hexdigest()
        result['_fingerprint'] = fingerprint + ':' + str(target)
        checked = cache.get(client)
        if checked and checked['fingerprint'] == result['_fingerprint']:
            result.update(status=checked['status'], detail=checked['detail'], last_tested=checked['at'])
    except (OSError, ValueError, TypeError, core.MnemosError):
        # Do not return parser text or arbitrary config values: they may contain credentials.
        result.update(status='needs-attention', detail='The configuration, launcher, or workspace could not be validated. Check the configuration location and workspace shown here.')
    return result


def inventory(active, cache, project=None):
    active = Path(active).resolve()
    if project:
        project = Path(project).expanduser()
        if not project.is_absolute() or not project.is_dir():
            raise core.MnemosError('Choose an existing, absolute project folder.')
        project = project.resolve()
    elif not getattr(sys, 'frozen', False):
        project = core.ROOT

    home = Path.home()
    codex_home = Path(os.environ.get('CODEX_HOME', home / '.codex'))
    specs = [('codex-global', 'Codex · user settings', codex_home / 'config.toml')]
    if project:
        specs += [('codex-project', 'Codex · project', project / '.codex/config.toml'),
                  ('claude-code', 'Claude Code · project', project / '.mcp.json')]
    if sys.platform == 'darwin':
        desktop = home / 'Library/Application Support/Claude/claude_desktop_config.json'
    elif sys.platform == 'win32':
        desktop = Path(os.environ.get('APPDATA', home / 'AppData/Roaming')) / 'Claude/claude_desktop_config.json'
    else:
        desktop = None
    if desktop:
        specs.append(('claude-desktop', 'Claude Desktop', desktop))
    entries = [_entry(client, label, path, active, cache) for client, label, path in specs]
    # Only inspect explicitly known workspaces; never crawl the user's home or vaults.
    workspaces = list(dict.fromkeys([active, default_root().resolve(),
                                    *(Path(e['workspace']) for e in entries if e.get('workspace'))]))
    from scripts.connect_chatgpt import read_receipt
    profiles = []
    for data in workspaces:
        profile = data / 'connections/chatgpt/keystone-connection.json'
        if not profile.exists():
            continue
        row = {'id': 'chatgpt-' + hashlib.sha256(str(data).encode()).hexdigest()[:16],
               'name': 'ChatGPT · private tunnel', 'workspace': str(data), 'matches_active': data == active,
               'binding': 'Pinned workspace', 'config_path': str(profile), 'status': 'configured',
               'detail': 'Prepared profile found. Test to check the local tunnel client.', 'testable': True,
               'last_tested': None}
        try:
            receipt = read_receipt(data)
            row['_fingerprint'] = receipt['profile_sha256'] + ':' + str(data)
            checked = cache.get(row['id'])
            if checked and checked['fingerprint'] == row['_fingerprint']:
                row.update(status=checked['status'], detail=checked['detail'], last_tested=checked['at'])
        except (OSError, ValueError, KeyError, core.MnemosError):
            row.update(status='needs-attention', testable=False, detail='The prepared tunnel profile is missing or changed. Review it before reconnecting.')
        profiles.append(row)
    if not profiles:
        profiles.append({'id': 'chatgpt', 'name': 'ChatGPT · private tunnel', 'status': 'disconnected',
                         'detail': 'No prepared tunnel found in the inspected workspaces. Cloud handoff works without one.',
                         'workspace': None, 'matches_active': None, 'testable': False, 'last_tested': None})
    return {'project': str(project) if project else '', 'active_workspace': str(active),
            'connections': entries + profiles, 'scope': 'User Codex settings, Claude Desktop where supported, the selected project, and tunnel profiles in these known workspaces. Other projects and cloud account settings are not inspected.'}


def public_inventory(value):
    return {**value, 'connections': [{k: v for k, v in row.items() if not k.startswith('_')}
                                    for row in value['connections']]}


def check_connection(active, cache, client, project=None):
    value = inventory(active, cache, project)
    row = next((item for item in value['connections'] if item['id'] == client), None)
    if not row or not row['testable']:
        raise core.MnemosError('This connection cannot be tested. Refresh and review its configuration first.')
    status, detail = 'needs-attention', 'The local test failed. Check the workspace and restart the assistant after correcting its configuration.'
    if client.startswith('chatgpt-'):
        from scripts.connect_chatgpt import status as tunnel_status
        try:
            health = tunnel_status(Path(row['workspace']))
            if health.get('healthy') and health.get('ready'):
                status, detail = 'tested', 'Local tunnel client is healthy and ready. ChatGPT account access and tool use still require a test from your chat.'
            else:
                status, detail = 'disconnected', 'The local tunnel client is not ready. Start its connection launcher, then test again.'
        except (OSError, ValueError):
            status, detail = 'disconnected', 'No responding local tunnel client was found. Start its connection launcher, then test again.'
    else:
        # Use our own trusted runtime, never commands, environment, or URLs from configuration.
        messages = [{'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {
            'protocolVersion': '2025-03-26', 'capabilities': {}, 'clientInfo': {'name': 'mnemos-dashboard', 'version': '1'}}},
            {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
            {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list', 'params': {}}]
        try:
            result = subprocess.run(tool_command('mcp_server', '--data', row['workspace']),
                                    input=''.join(json.dumps(m) + '\n' for m in messages),
                                    text=True, capture_output=True, timeout=15,
                                    **({'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}))
            replies = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
            names = {tool['name'] for reply in replies if reply.get('id') == 2 for tool in reply['result']['tools']}
            if result.returncode == 0 and {'capture_document', 'recall_context'} <= names:
                status, detail = 'tested', 'The workspace opens and Mnemos exposes capture and recall tools. This tests the local vault with this app’s runtime; it does not prove the assistant is connected.'
        except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired):
            pass
    cache[client] = {'fingerprint': row['_fingerprint'], 'status': status, 'detail': detail,
                     'at': datetime.now(timezone.utc).isoformat(timespec='seconds')}
    return public_inventory(inventory(active, cache, project))
