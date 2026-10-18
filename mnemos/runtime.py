"""Commands and writable locations shared by source and standalone distributions."""
import os
from pathlib import Path
import sys

from . import core

TOOLS = {'launch', 'mcp_server', 'install_agents', 'install_claude_desktop',
         'connect_chatgpt', 'setup', 'backup', 'restore', 'export_reader'}


def default_root():
    if not getattr(sys, 'frozen', False):
        return core.ROOT / 'data'
    if sys.platform == 'darwin':
        return Path.home() / 'Library/Application Support/Mnemos/data'
    if sys.platform == 'win32':
        return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'Mnemos/data'
    return Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'mnemos/data'


def tool_command(tool, *args):
    name = tool.removesuffix('.py')
    if name not in TOOLS:
        raise ValueError('Unknown Mnemos tool.')
    if getattr(sys, 'frozen', False):
        return [sys.executable, '--tool', name, *map(str, args)]
    return [sys.executable, str(core.ROOT / 'scripts' / (name + '.py')), *map(str, args)]


def mcp_connection(data):
    command = tool_command('mcp_server', '--data', Path(data).resolve())
    return {'command': command[0], 'args': command[1:]}
