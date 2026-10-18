import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from mnemos.core import initialize

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
            self.assertIn('mnemos',changed['mcpServers'])
            self.assertTrue((project / '.agents/skills/mnemos-recall/SKILL.md').exists())
            installer.install_agents(project,data)
            self.assertIn('[mcp_servers.mnemos]',(project / '.codex/config.toml').read_text())
    def test_different_existing_connection_not_overwritten(self):
        installer = load_script('install_agents')
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / 'project'
            project.mkdir()
            data = Path(temporary) / 'data'
            initialize(data)
            original = json.dumps({'mcpServers':{'mnemos':{'command':'existing'}}})
            (project / '.mcp.json').write_text(original)
            with self.assertRaises(ValueError):
                installer.install_agents(project,data)
            self.assertEqual((project / '.mcp.json').read_text(), original)
            self.assertFalse((project / '.codex/config.toml').exists())

    def test_skills_only_needs_no_vault_and_does_not_read_or_change_mcp_settings(self):
        installer = load_script('install_agents')
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            (project / '.codex').mkdir()
            (project / '.codex/config.toml').write_text('not valid toml = [')
            (project / '.mcp.json').write_text('not valid json')
            result = installer.install_agents(project, clients='both', skills_only=True)
            self.assertTrue(result['skills_only'])
            self.assertEqual(result['connections'], {})
            self.assertEqual((project / '.codex/config.toml').read_text(), 'not valid toml = [')
            self.assertEqual((project / '.mcp.json').read_text(), 'not valid json')
            self.assertTrue((project / '.agents/skills/mnemos-handoff/SKILL.md').is_file())
            self.assertTrue((project / '.claude/skills/mnemos-handoff/SKILL.md').is_file())
            self.assertFalse((project / 'data').exists())

    def test_skills_only_does_not_create_mcp_files(self):
        installer = load_script('install_agents')
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            installer.install_agents(project, clients='both', skills_only=True)
            self.assertFalse((project / '.codex/config.toml').exists())
            self.assertFalse((project / '.mcp.json').exists())

    def test_matching_legacy_connections_reused_without_duplicate_or_rewrite(self):
        installer = load_script('install_agents')
        with tempfile.TemporaryDirectory() as temporary:
            project, data = Path(temporary) / 'project', Path(temporary) / 'data'
            project.mkdir()
            initialize(data)
            connection = {'command': str(Path(installer.sys.executable).resolve()),
                          'args': [str(ROOT / 'scripts/mcp_server.py'), '--data', str(data.resolve())]}
            (project / '.codex').mkdir()
            toml = '[mcp_servers.keystone]\ncommand = ' + json.dumps(connection['command']) + '\nargs = ' + json.dumps(connection['args']) + '\nenabled = true\n'
            original = json.dumps({'preferences': {'keep': True}, 'mcpServers': {'keystone': connection, 'other': {'command': 'keep'}}})
            (project / '.codex/config.toml').write_text(toml)
            (project / '.mcp.json').write_text(original)
            result = installer.install_agents(project, data)
            self.assertEqual(result['connections'], {'codex': 'keystone', 'claude': 'keystone'})
            self.assertEqual((project / '.codex/config.toml').read_text(), toml)
            self.assertEqual((project / '.mcp.json').read_text(), original)

    def test_conflicting_legacy_connection_rejected_before_any_write(self):
        installer = load_script('install_agents')
        with tempfile.TemporaryDirectory() as temporary:
            project, data = Path(temporary) / 'project', Path(temporary) / 'data'
            project.mkdir()
            initialize(data)
            original = json.dumps({'mcpServers': {'keystone': {'command': 'different'}}})
            (project / '.mcp.json').write_text(original)
            with self.assertRaises(ValueError):
                installer.install_agents(project, data)
            self.assertEqual((project / '.mcp.json').read_text(), original)
            self.assertFalse((project / '.codex/config.toml').exists())
            self.assertFalse((project / '.agents').exists())

if __name__ == '__main__': unittest.main()
