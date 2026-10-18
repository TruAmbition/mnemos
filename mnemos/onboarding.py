"""Local installation choices; no assistant credentials or account changes."""
from __future__ import annotations

import importlib.util
import hashlib
import json
from pathlib import Path
import re
import shlex
import sys

from . import core

MODES = {'local', 'handoff', 'connected'}


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
        # A default launcher may contain only its own selected-installation pointer.
        if len(remaining) == 1 and remaining[0].name == 'installation.json':
            load_selection(remaining[0], data)
            remaining = []
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
        return _shell_command([sys.executable, str(core.ROOT / 'scripts' / script), *args, '--data', str(data)], command_shell)
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
    if set(payload) - {'data_path', 'author', 'backup', 'assistant_mode', 'install_obsidian'}:
        raise core.MnemosError('Setup accepts installation choices only. Do not submit credentials.')
    data, existing = validate_target(payload.get('data_path', str(current_data)))
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
        default_config = Path(default).expanduser().resolve() / 'config.json'
        if default_config.is_symlink():
            raise ValueError
        # An old selection must not override a default installation initialized
        # or changed after the user made that selection.
        if default_config.exists() and stored.get('source_config_sha256') != hashlib.sha256(default_config.read_bytes()).hexdigest():
            return data_directory(Path(default).expanduser().resolve())
        data = data_directory(stored['data_path'])
        if initialized_config(data) is None:
            raise ValueError
        return data
    except (OSError, ValueError, KeyError, TypeError):
        raise core.MnemosError('The saved installation location is unavailable. Start with --data pointing to your intended installation.') from None


def save_selection(pointer, data):
    pointer = Path(pointer)
    # The pointer belongs to the launcher directory, never to the vault itself.
    data_directory(pointer.parent)
    source_config = pointer.parent / 'config.json'
    if source_config.is_symlink():
        raise core.MnemosError('Configuration must not be a symbolic link.')
    source_hash = hashlib.sha256(source_config.read_bytes()).hexdigest() if source_config.exists() else None
    core.atomic_write(pointer, json.dumps({'format': 'mnemos-installation-1', 'data_path': str(data),
                                          'source_config_sha256': source_hash}, indent=2) + '\n')
