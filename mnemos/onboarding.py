"""Local installation choices; no assistant credentials or account changes."""
from __future__ import annotations

import importlib.util
import hashlib
import json
from pathlib import Path
import re
import shlex
import sys
import uuid

from . import core

MODES = {'local', 'handoff', 'connected'}


class SetupConflict(core.MnemosError):
    def __init__(self, message, code='workspace_changed', restart_required=False):
        super().__init__(message, 409)
        self.code = code
        self.restart_required = restart_required


def data_directory(value):
    if not isinstance(value, (str, Path)) or not str(value).strip():
        raise core.MnemosError('Choose a dedicated data folder.')
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise core.MnemosError('Choose an absolute path for the data folder.')
    path = path.absolute()
    for parent in [path, *path.parents]:
        if parent.is_symlink():
            raise core.MnemosError('Choose a data folder without symbolic links in its path.')
        if (parent / '.obsidian').exists() or (parent / '.obsidian').is_symlink():
            raise core.MnemosError('Choose a data folder outside every existing Obsidian vault.')
    if path.exists() and not path.is_dir():
        raise core.MnemosError('The data location must be a folder.')
    return path.resolve()


def initialized_config(data):
    if not (data / 'config.json').exists():
        return None
    config = core.load_config(data)
    if (not isinstance(config.get('owner'), str) or not isinstance(config.get('tokens'), list)
            or not isinstance(config.get('backup'), dict) or not (data / 'vault').is_dir()):
        raise core.MnemosError('This folder is not an initialized Mnemos installation. Choose a new folder.')
    return config


def validate_target(value):
    data = data_directory(value)
    config = initialized_config(data)
    if config is None and data.exists():
        remaining = [entry for entry in data.iterdir() if entry.name != '.DS_Store']
        # Apply can already hold the cross-process installation lock here.
        for entry in list(remaining):
            if entry.name == '.keystone.lock' and not entry.is_symlink() and entry.is_file() and entry.stat().st_size <= 1:
                remaining.remove(entry)
            elif entry.name == 'installation.json':
                load_selection(entry, data)
                remaining.remove(entry)
        if remaining:
            raise core.MnemosError('This data folder already contains unrelated files. Choose a new, empty folder.')
    return data, config


def _obsidian_tools():
    spec = importlib.util.spec_from_file_location('mnemos_desktop_setup', core.ROOT / 'scripts/setup.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def detect_obsidian(data):
    return _obsidian_tools().detect_obsidian(data)


def install_obsidian(data):
    return _obsidian_tools().install_obsidian(data)


def _shell_command(arguments, shell):
    """Format literal arguments for copying; never execute the resulting command."""
    if shell == 'powershell':
        # PowerShell recognizes straight and smart single quotes as delimiters.
        quoted = ["'" + re.sub("['\u2018-\u201b]", lambda match: match[0] * 2, value) + "'"
                  for value in arguments]
        return '& ' + ' '.join(quoted)
    return shlex.join(arguments)


def choices(data, config=None):
    data = Path(data).resolve()
    config = initialized_config(data) if config is None else config
    installed = detect_obsidian(data)
    command_shell = 'powershell' if sys.platform == 'win32' else 'posix'
    def command(script, *args):
        from .runtime import tool_command
        project_args = ['--project', str(Path.home() / 'path-to-your-project')] if getattr(sys, 'frozen', False) and script == 'install_agents.py' else []
        return _shell_command(tool_command(script, *args, *project_args, '--data', str(data)), command_shell)
    return {
        'initialized': config is not None, 'data_path': str(data),
        'author': config.get('owner', 'Local engineer') if config else 'Local engineer',
        'backup': dict(config['backup']) if config else {'provider': 'local', 'destination': str(data / 'backups'), 'remote': ''},
        'assistant_mode': config.get('assistant_mode', 'local') if config else 'local',
        'obsidian': {'installed': bool(installed), 'path': installed, 'status': 'installed' if installed else 'not-installed'},
        'skills': {'available': sorted(path.parent.name for path in (core.ROOT / 'skills').glob('*/SKILL.md')),
                   'guidance': 'Skills are included with Mnemos. Use an assistant setup command below to install them in a chosen project; browser setup does not change assistant settings.'},
        'commands': {'codex': command('install_agents.py', '--client', 'codex'),
                     'claude_code': command('install_agents.py', '--client', 'claude'),
                     'claude_desktop': command('install_claude_desktop.py', '--apply'),
                     'chatgpt': command('connect_chatgpt.py', 'connect')},
        'command_shell': command_shell,
        'packaged_app': bool(getattr(sys, 'frozen', False)),
        'connection_status': 'not-checked', 'library_url': '/',
    }


def _backup_settings(data, payload, existing):
    backup = payload.get('backup', existing.get('backup') if existing else None)
    if backup is None:
        backup = {'provider': 'local', 'destination': str(data / 'backups'), 'remote': ''}
    if (not isinstance(backup, dict) or not isinstance(backup.get('provider'), str)
            or backup.get('provider') not in {'local', 'rclone'}):
        raise core.MnemosError('Choose local or rclone backup storage.')
    if set(backup) - {'provider', 'destination', 'remote'}:
        raise core.MnemosError('Backup setup accepts a location and configured remote name, not credentials.')
    destination = backup.get('destination') or str(data / 'backups')
    remote = backup.get('remote', '')
    if not isinstance(destination, str) or len(destination) > 4096 or '\x00' in destination:
        raise core.MnemosError('Choose a valid backup folder.')
    target = Path(destination).expanduser()
    if not target.is_absolute():
        raise core.MnemosError('Choose an absolute path for the backup folder.')
    target = target.resolve()
    if target.is_relative_to(data / 'vault'):
        raise core.MnemosError('Store backups outside the vault.')
    if target.exists() and not target.is_dir():
        raise core.MnemosError('The backup location must be a folder.')
    if not isinstance(remote, str) or len(remote) > 1024:
        raise core.MnemosError('Use a configured rclone remote name and path.')
    if backup['provider'] == 'rclone':
        if (not re.fullmatch(r'[A-Za-z0-9_-]+:[^\x00-\x1f]*', remote)
                or '..' in remote.split(':', 1)[1].split('/') or '://' in remote):
            raise core.MnemosError('Cloud backup needs an existing rclone remote, for example drive:Mnemos. Configure credentials in rclone separately.')
    else:
        remote = ''
    return {'provider': backup['provider'], 'destination': str(target), 'remote': remote}


def configure(current_data, payload):
    if set(payload) - {'mode', 'data_path', 'author', 'backup', 'assistant_mode', 'install_obsidian', 'expected_target_settings_revision'}:
        raise core.MnemosError('Setup accepts installation choices only. Do not submit credentials.')
    action = payload.get('mode')
    if not isinstance(action, str) or action not in {'update', 'create', 'select'}:
        raise core.MnemosError('Choose update, create, or select explicitly.')
    data, existing = validate_target(payload.get('data_path', str(current_data)))
    current_data = Path(current_data).resolve()
    if action == 'update' and (data != current_data or existing is None):
        raise core.MnemosError('Update can change only the active workspace. Choose create or select to change folders.')
    if action == 'create' and existing is not None:
        raise core.MnemosError('This workspace already exists. Choose select to use its saved settings.')
    if action == 'select':
        if existing is None:
            raise core.MnemosError('Select an initialized Mnemos workspace, or choose create for a new folder.')
        if set(payload) - {'mode', 'data_path', 'expected_target_settings_revision'}:
            raise core.MnemosError('Selecting a workspace loads its own saved settings. Do not submit replacement settings.')
        with core.storage_lock(data):
            if payload.get('expected_target_settings_revision') != settings_revision(data):
                raise SetupConflict('The selected workspace settings changed. Inspect the folder again before activating it.', 'settings_changed')
            result = choices(data, core.load_config(data))
        result.update(status='ready', warnings=[])
        return data, result
    author = payload.get('author', existing.get('owner') if existing else 'Local engineer')
    if not isinstance(author, str) or not 1 <= len(author.strip()) <= 120 or any(ord(c) < 32 for c in author):
        raise core.MnemosError('Choose an author name between 1 and 120 characters.')
    mode = payload.get('assistant_mode', existing.get('assistant_mode', 'local') if existing else 'local')
    if not isinstance(mode, str) or mode not in MODES:
        raise core.MnemosError('Choose local, handoff, or connected assistant mode.')
    should_install = payload.get('install_obsidian', False)
    if not isinstance(should_install, bool):
        raise core.MnemosError('The Obsidian installation choice must be true or false.')
    backup = _backup_settings(data, payload, existing)
    with core.storage_lock(data):
        # Recheck after acquiring the storage lock; another process may have initialized it.
        existing = initialized_config(data)
        if action == 'create' and existing is not None:
            raise SetupConflict('This folder was initialized by another process. Inspect it before selecting it.', 'settings_changed')
        config = core.initialize(data, author.strip()) if existing is None else core.load_config(data)
        # Preserve credentials, metadata, documents, and connector profiles.
        config.update(owner=author.strip(), backup=backup, assistant_mode=mode)
        core.save_config(data, config)
    warning_messages = []
    installation_error = None
    if should_install:
        try:
            install_obsidian(data)
        except Exception:
            installation_error = 'Obsidian could not be installed. The library is ready; install Obsidian from https://obsidian.md/download and open the dedicated vault.'
            warning_messages.append(installation_error)
    result = choices(data, config)
    if installation_error and not result['obsidian']['installed']:
        result['obsidian'].update(status='failed', error=installation_error)
    if backup['provider'] == 'rclone':
        warning_messages.append('Cloud credentials are configured separately with rclone. This setup has not tested a cloud backup.')
    if mode == 'connected':
        warning_messages.append('Connection mode is selected. Follow the assistant setup instructions; no account connection has been created or verified by this form.')
    result.update(status='ready', warnings=warning_messages)
    return data, result


def load_selection(pointer, default):
    pointer = Path(pointer)
    data_directory(pointer.parent)
    if pointer.is_symlink():
        raise core.MnemosError('The installation selection must not be a symbolic link.')
    if not pointer.exists():
        return Path(default).expanduser().resolve()
    try:
        stored = json.loads(pointer.read_text('utf-8'))
        if not isinstance(stored, dict) or stored.get('format') != 'mnemos-installation-1':
            raise ValueError
        data = data_directory(stored['data_path'])
        if initialized_config(data) is None:
            raise ValueError
        return data
    except (OSError, ValueError, KeyError, TypeError):
        raise core.MnemosError('The saved installation location is unavailable. Start with --data pointing to your intended installation.') from None


def settings_revision(data):
    path = Path(data) / 'config.json'
    if path.is_symlink():
        raise core.MnemosError('Configuration must not be a symbolic link.')
    return hashlib.sha256(path.read_bytes() if path.exists() else b'').hexdigest()


def selection_fingerprint(pointer):
    pointer = Path(pointer)
    data_directory(pointer.parent)
    if pointer.is_symlink():
        raise core.MnemosError('The installation selection must not be a symbolic link.')
    return hashlib.sha256(pointer.read_bytes() if pointer.exists() else b'').hexdigest()


def selection_revision(pointer):
    pointer = Path(pointer)
    selection_fingerprint(pointer)
    if pointer.exists():
        value = json.loads(pointer.read_text('utf-8')).get('revision')
        if isinstance(value, str) and re.fullmatch(r'[0-9a-f]{32}', value):
            return value
    return uuid.uuid4().hex


def save_selection(pointer, data, revision=None):
    pointer = Path(pointer)
    # The pointer belongs to the launcher directory, never to the vault itself.
    data_directory(pointer.parent)
    source_config = pointer.parent / 'config.json'
    if source_config.is_symlink():
        raise core.MnemosError('Configuration must not be a symbolic link.')
    core.atomic_write(pointer, json.dumps({'format': 'mnemos-installation-1', 'data_path': str(data),
                                          'revision': revision or uuid.uuid4().hex}, indent=2) + '\n')
