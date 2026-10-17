import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from keystone.core import initialize

ROOT = Path(__file__).resolve().parents[1]
def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class SetupTests(unittest.TestCase):
    def test_existing_obsidian_is_not_reinstalled(self):
        setup = load_script('setup')
        with patch.object(setup, 'detect_obsidian', return_value='/Applications/Obsidian.app'), patch.object(setup.subprocess, 'run') as run:
            self.assertEqual(setup.install_obsidian(Path('/unused')), '/Applications/Obsidian.app')
            run.assert_not_called()
    def test_installer_uses_package_manager_only_when_absent(self):
        setup = load_script('setup')
        with patch.object(setup, 'detect_obsidian', side_effect=[None, '/Applications/Obsidian.app']), patch.object(setup.platform,'system',return_value='Darwin'), patch.object(setup.shutil,'which',return_value='/opt/homebrew/bin/brew'), patch.object(setup.subprocess,'run') as run:
            setup.install_obsidian(Path('/unused'))
            run.assert_called_once_with(['brew','install','--cask','obsidian'], check=True)
    def test_project_scoped_connections_preserve_other_servers(self):
        installer = load_script('install_agents')
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / 'project'
            project.mkdir()
            data = Path(temporary) / 'data'
            initialize(data)
            config = {'mcpServers':{'existing':{'command':'unchanged'}}}
            (project / '.mcp.json').write_text(json.dumps(config))
            installer.install_agents(project,data)
            changed = json.loads((project / '.mcp.json').read_text())
            self.assertEqual(changed['mcpServers']['existing'],config['mcpServers']['existing'])
            self.assertIn('keystone',changed['mcpServers'])
            self.assertTrue((project / '.agents/skills/keystone-recall/SKILL.md').exists())
            installer.install_agents(project,data)
            self.assertIn('[mcp_servers.keystone]',(project / '.codex/config.toml').read_text())
    def test_different_existing_connection_not_overwritten(self):
        installer = load_script('install_agents')
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / 'project'
            project.mkdir()
            data = Path(temporary) / 'data'
            initialize(data)
            original = json.dumps({'mcpServers':{'keystone':{'command':'existing'}}})
            (project / '.mcp.json').write_text(original)
            with self.assertRaises(ValueError):
                installer.install_agents(project,data)
            self.assertEqual((project / '.mcp.json').read_text(), original)
            self.assertFalse((project / '.codex/config.toml').exists())

if __name__ == '__main__': unittest.main()
