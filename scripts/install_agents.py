#!/usr/bin/env python3
"""Install project-scoped skills and MCP configuration without editing global agent settings."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def install_agents(project, data, clients='both'):
    project, data = Path(project).resolve(), Path(data).resolve()
    if not (data / 'config.json').is_file():
        raise ValueError('Initialize the Keystone data directory first.')
    connection = {'command': sys.executable, 'args': [str(ROOT / 'scripts' / 'mcp_server.py'), '--data', str(data)]}
    prepared = []
    destinations = []
    if clients in {'codex', 'both'}:
        config_file = project / '.codex' / 'config.toml'
        content = config_file.read_text() if config_file.exists() else ''
        config = tomllib.loads(content)
        existing = config.get('mcp_servers', {}).get('keystone')
        if existing is not None and existing != connection:
            raise ValueError('Project already has a different Keystone MCP connection. Existing settings were left unchanged.')
        if existing is None:
            content += '\n[mcp_servers.keystone]\ncommand = ' + json.dumps(connection['command']) + '\nargs = ' + json.dumps(connection['args']) + '\n'
            prepared.append((config_file, content))
        destinations.append(project / '.agents' / 'skills')
    if clients in {'claude', 'both'}:
        config_file = project / '.mcp.json'
        config = json.loads(config_file.read_text()) if config_file.exists() else {}
        servers = config.setdefault('mcpServers', {})
        existing = servers.get('keystone')
        if existing is not None and existing != connection:
            raise ValueError('Project already has a different Keystone MCP connection. Existing settings were left unchanged.')
        servers['keystone'] = connection
        prepared.append((config_file, json.dumps(config, indent=2) + '\n'))
        destinations.append(project / '.claude' / 'skills')
    copies = []
    for parent in destinations:
        for source in (ROOT / 'skills').rglob('*'):
            if not source.is_file():
                continue
            target = parent / source.relative_to(ROOT / 'skills')
            if target.is_symlink() or any(p.is_symlink() for p in target.parents if p != project.parent):
                raise ValueError('Agent installation refuses symlinked configuration folders.')
            if target.exists() and target.read_bytes() != source.read_bytes():
                raise ValueError(f'Existing skill differs: {target}. It was left unchanged.')
            if not target.exists():
                copies.append((source, target))
    for target, _ in prepared:
        if target.is_symlink() or any(p.is_symlink() for p in target.parents if p != project.parent):
            raise ValueError('Agent installation refuses symlinked configuration folders.')
    for target, content in prepared:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    for source, target in copies:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return {'project': str(project), 'clients': clients, 'skills_copied': len(copies),
            'notice': 'Restart/reload your agent and trust this project to activate its MCP server. Global settings were not changed.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', default=str(ROOT))
    parser.add_argument('--data', required=True)
    parser.add_argument('--client', choices=['codex', 'claude', 'both'], default='both')
    args = parser.parse_args()
    print(json.dumps(install_agents(args.project, args.data, args.client), indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError) as error:
        print(f'Agent setup could not finish: {error}', file=sys.stderr)
        raise SystemExit(1)
