import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mnemos.core import initialize

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('install_claude_desktop', ROOT / 'scripts/install_claude_desktop.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class ClaudeDesktopTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name).resolve()
        self.data = self.base / 'data'
        initialize(self.data, 'Tester')
        self.config = self.base / 'Claude/claude_desktop_config.json'
        self.config.parent.mkdir()

    def tearDown(self):
        self.temporary.cleanup()

    def test_preflight_spawns_real_mcp_without_changing_settings(self):
        original = b'{"preferences":{"existing":true}}'
        self.config.write_bytes(original)
        result = installer.install_claude_desktop(self.data, self.config)
        self.assertEqual(result['status'], 'ready')
        self.assertIn('capture_document', result['tools'])
        self.assertIn('recall_context', result['tools'])
        self.assertEqual(self.config.read_bytes(), original)
        self.assertIsNone(result['backup'])

    def test_merge_preserves_settings_and_backup_and_is_idempotent(self):
        existing = {'preferences': {'theme': 'dark'}, 'coworkUserFilesPath': '/keep',
                    'mcpServers': {'other': {'command': 'existing', 'env': {'API_KEY': 'test-placeholder'}}}}
        original = json.dumps(existing).encode()
        self.config.write_bytes(original)
        result = installer.install_claude_desktop(self.data, self.config, apply=True)
        changed = json.loads(self.config.read_text())
        self.assertEqual(result['status'], 'installed')
        self.assertEqual(changed['preferences'], existing['preferences'])
        self.assertEqual(changed['coworkUserFilesPath'], existing['coworkUserFilesPath'])
        self.assertEqual(changed['mcpServers']['other'], existing['mcpServers']['other'])
        self.assertTrue(Path(changed['mcpServers']['mnemos']['command']).is_absolute())
        self.assertEqual(changed['mcpServers']['mnemos']['args'][-1], str(self.data))
        self.assertEqual(Path(result['backup']).read_bytes(), original)
        again = installer.install_claude_desktop(self.data, self.config, apply=True)
        self.assertEqual(again['status'], 'already-configured')
        self.assertIsNone(again['backup'])
        self.assertEqual(len(list(self.config.parent.glob('*.mnemos-backup-*'))), 1)

    def test_conflicting_mnemos_is_untouched(self):
        original = b'{"mcpServers":{"mnemos":{"command":"other"}}}'
        self.config.write_bytes(original)
        with self.assertRaisesRegex(ValueError, 'different Mnemos'):
            installer.install_claude_desktop(self.data, self.config, apply=True)
        self.assertEqual(self.config.read_bytes(), original)
        self.assertEqual(len(list(self.config.parent.iterdir())), 1)

    def test_malformed_config_is_untouched(self):
        for original in (b'not json', b'[]', b'{"mcpServers":[]}'):
            with self.subTest(original=original):
                self.config.write_bytes(original)
                with self.assertRaises(ValueError):
                    installer.install_claude_desktop(self.data, self.config, apply=True)
                self.assertEqual(self.config.read_bytes(), original)

    def test_failed_server_preflight_does_not_modify_config(self):
        original = b'{"preferences":{"keep":true}}'
        self.config.write_bytes(original)
        with patch.object(installer.subprocess, 'run', side_effect=OSError('broken runtime')):
            with self.assertRaisesRegex(ValueError, 'preflight failed'):
                installer.install_claude_desktop(self.data, self.config, apply=True)
        self.assertEqual(self.config.read_bytes(), original)
        self.assertEqual(len(list(self.config.parent.iterdir())), 1)

    def test_new_config_is_created_only_on_apply(self):
        result = installer.install_claude_desktop(self.data, self.config)
        self.assertEqual(result['status'], 'ready')
        self.assertFalse(self.config.exists())
        installer.install_claude_desktop(self.data, self.config, apply=True)
        self.assertIn('mnemos', json.loads(self.config.read_text())['mcpServers'])

    def test_symlinked_config_is_refused(self):
        target = self.base / 'other.json'
        target.write_text('{}')
        try:
            self.config.symlink_to(target)
        except OSError:
            self.skipTest('Creating symlinks is unavailable.')
        with self.assertRaisesRegex(ValueError, 'symlinked'):
            installer.install_claude_desktop(self.data, self.config, apply=True)
        self.assertEqual(target.read_text(), '{}')


    def test_matching_legacy_connection_migrates_only_on_apply_with_backup(self):
        connection = installer.connection_for(self.data)
        connection['env'] = {'KEEP_SETTING': 'non-secret-value'}
        original = json.dumps({'preferences': {'keep': True}, 'mcpServers': {'keystone': connection, 'other': {'command': 'keep'}}}).encode()
        self.config.write_bytes(original)
        preview = installer.install_claude_desktop(self.data, self.config)
        self.assertTrue(preview['migrates_legacy_name'])
        self.assertEqual(preview['status'], 'ready')
        self.assertEqual(self.config.read_bytes(), original)
        self.assertEqual(len(list(self.config.parent.iterdir())), 1)
        result = installer.install_claude_desktop(self.data, self.config, apply=True)
        changed = json.loads(self.config.read_text())
        self.assertNotIn('keystone', changed['mcpServers'])
        self.assertEqual(changed['mcpServers']['mnemos'], connection)
        self.assertEqual(changed['mcpServers']['other'], {'command': 'keep'})
        self.assertEqual(changed['preferences'], {'keep': True})
        self.assertEqual(Path(result['backup']).read_bytes(), original)

    def test_conflicting_legacy_connection_is_not_replaced(self):
        original = b'{"mcpServers":{"keystone":{"command":"different"}}}'
        self.config.write_bytes(original)
        with self.assertRaisesRegex(ValueError, 'different Mnemos'):
            installer.install_claude_desktop(self.data, self.config, apply=True)
        self.assertEqual(self.config.read_bytes(), original)
        self.assertEqual(len(list(self.config.parent.iterdir())), 1)

    def test_identical_duplicate_names_are_consolidated_on_apply(self):
        connection = installer.connection_for(self.data)
        original = json.dumps({'mcpServers': {'mnemos': connection, 'keystone': connection}}).encode()
        self.config.write_bytes(original)
        result = installer.install_claude_desktop(self.data, self.config, apply=True)
        self.assertEqual(set(json.loads(self.config.read_text())['mcpServers']), {'mnemos'})
        self.assertEqual(Path(result['backup']).read_bytes(), original)

if __name__ == '__main__':
    unittest.main()
