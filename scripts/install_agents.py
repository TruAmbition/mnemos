#!/usr/bin/env python3
"""Install project-scoped Mnemos skills, optionally with a local MCP connection."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mnemos.installation import resolve_data
from mnemos.core import load_config


def matching_connection(existing, expected):
    """Compare the executable and launch arguments, preserving client-specific extras."""
    if not isinstance(existing, dict) or existing.get('args') != expected['args']:
        return False
    command = existing.get('command')
    if not isinstance(command, str):
        return False
    resolved = shutil.which(command)
    return bool(resolved and Path(resolved).resolve() == Path(expected['command']).resolve())


def _connection_name(servers, connection):
    if not isinstance(servers, dict):
        raise ValueError('Existing MCP server settings must be an object; nothing was changed.')
    names = [name for name in ('mnemos', 'keystone') if name in servers]
    for name in names:
        if not matching_connection(servers[name], connection):
            raise ValueError(f'Project already has a different {name} MCP connection. Existing settings were left unchanged.')
    if len(names) > 1:
        raise ValueError('Both Mnemos and legacy Keystone connections already exist. Keep one matching connection before installing; nothing was changed.')
    return names[0] if names else None


def _check_target(target, project):
    for candidate in (target, *target.parents):
        if candidate == project.parent:
            break
        if candidate.is_symlink():
            raise ValueError('Agent installation refuses symlinked configuration folders.')


def install_agents(project, data=None, clients='both', skills_only=False):
    project = Path(project).expanduser().resolve()
    if clients not in {'codex', 'claude', 'both'}:
        raise ValueError('Choose codex, claude, or both.')
    if project.exists() and not project.is_dir():
        raise ValueError('The project must be a directory.')
    connection = None
    if not skills_only:
        data = resolve_data(data)
        if not (data / 'config.json').is_file():
            raise ValueError('Initialize the Mnemos data directory first, or use --skills-only.')
        load_config(data)
        data = data.resolve()
        connection = {'command': str(Path(sys.executable).resolve()), 'args': [str(ROOT / 'scripts' / 'mcp_server.py'), '--data', str(data)]}
    prepared, destinations, connections = [], [], {}
    if clients in {'codex', 'both'}:
        destinations.append(project / '.agents' / 'skills')
        if not skills_only:
            config_file = project / '.codex' / 'config.toml'
            _check_target(config_file, project)
            content = config_file.read_text() if config_file.exists() else ''
            config = tomllib.loads(content)
            name = _connection_name(config.get('mcp_servers', {}), connection)
            if name is None:
                name = 'mnemos'
                content += '\n[mcp_servers.mnemos]\ncommand = ' + json.dumps(connection['command']) + '\nargs = ' + json.dumps(connection['args']) + '\n'
                prepared.append((config_file, content))
            connections['codex'] = name
    if clients in {'claude', 'both'}:
        destinations.append(project / '.claude' / 'skills')
        if not skills_only:
            config_file = project / '.mcp.json'
            _check_target(config_file, project)
            config = json.loads(config_file.read_text()) if config_file.exists() else {}
            if not isinstance(config, dict):
                raise ValueError('Existing Claude Code settings must be an object; nothing was changed.')
            servers = config.setdefault('mcpServers', {})
            name = _connection_name(servers, connection)
            if name is None:
                name = 'mnemos'
                servers[name] = connection
                prepared.append((config_file, json.dumps(config, indent=2) + '\n'))
            connections['claude'] = name
    copies = []
    for parent in destinations:
        for source in (ROOT / 'skills').rglob('*'):
            if not source.is_file():
                continue
            if source.is_symlink():
                raise ValueError('Bundled skill files must not be symlinks.')
            target = parent / source.relative_to(ROOT / 'skills')
            _check_target(target, project)
            if target.exists() and (not target.is_file() or target.read_bytes() != source.read_bytes()):
                raise ValueError(f'Existing skill differs: {target}. It was left unchanged.')
            if not target.exists():
                copies.append((source, target))
    # Complete the preflight before writing any settings or copying any skills.
    for target, content in prepared:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    for source, target in copies:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return {'project': str(project), 'clients': clients, 'skills_only': skills_only,
            'skills_copied': len(copies), 'connections': connections,
            'notice': ('Skills installed without an MCP connection. Use supplied files for cloud handoffs; no vault access is implied.'
                       if skills_only else 'Restart/reload your agent and trust this project to activate its local MCP server. Matching legacy Keystone entries are reused without duplicates.')
                      + ' Global settings were not changed.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', default=str(ROOT))
    parser.add_argument('--data', help='Pin an initialized data directory; omitted uses the selected default. Unused with --skills-only.')
    parser.add_argument('--client', choices=['codex', 'claude', 'both'], default='both')
    parser.add_argument('--skills-only', action='store_true', help='Copy portable skills without reading or adding MCP settings or requiring a vault.')
    args = parser.parse_args()
    print(json.dumps(install_agents(args.project, args.data, args.client, args.skills_only), indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError) as error:
        print(f'Agent setup could not finish: {error}', file=sys.stderr)
        raise SystemExit(1)
