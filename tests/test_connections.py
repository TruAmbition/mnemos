import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from mnemos import connections, core
from mnemos.runtime import tool_command


class ConnectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.active = self.root / 'active'
        self.old = self.root / 'old'
        core.initialize(self.active, 'Engineer')
        core.initialize(self.old, 'Engineer')
        self.project = self.root / 'project'
        self.project.mkdir()
        self.config = self.project / '.mcp.json'
        self.cache = {}
        home = patch.object(Path, 'home', return_value=self.root)
        home.start()
        self.addCleanup(home.stop)
        env = patch.dict('os.environ', {'CODEX_HOME': str(self.root / '.codex')})
        env.start()
        self.addCleanup(env.stop)

    def configure(self, data=None, **extra):
        command = tool_command('mcp_server', '--data', str(data or self.old))
        config = {'command': command[0], 'args': command[1:], **extra}
        self.config.write_text(json.dumps({'mcpServers': {'mnemos': config}}))

    def entry(self):
        value = connections.inventory(self.active, self.cache, self.project)
        return next(row for row in value['connections'] if row['id'] == 'claude-code')

    def test_identifies_pinned_mismatch_without_leaking_settings(self):
        self.configure(env={'PRIVATE_TOKEN': 'sentinel-never-return'})
        row = self.entry()
        self.assertEqual(row['status'], 'configured')
        self.assertEqual(row['workspace'], str(self.old))
        self.assertFalse(row['matches_active'])
        public = connections.public_inventory(connections.inventory(self.active, self.cache, self.project))
        self.assertNotIn('sentinel-never-return', json.dumps(public))
        self.assertNotIn('_fingerprint', json.dumps(public))

    def test_success_tests_local_tools_and_preserves_notes(self):
        self.configure()
        before = {p: p.read_bytes() for p in (self.old / 'vault').rglob('*') if p.is_file()}
        value = connections.check_connection(self.active, self.cache, 'claude-code', self.project)
        row = next(r for r in value['connections'] if r['id'] == 'claude-code')
        self.assertEqual(row['status'], 'tested')
        self.assertIn('does not prove', row['detail'])
        self.assertTrue(row['last_tested'])
        self.assertEqual(before, {p: p.read_bytes() for p in (self.old / 'vault').rglob('*') if p.is_file()})
        self.configure(self.active)
        self.assertEqual(self.entry()['status'], 'configured')
        self.assertIsNone(self.entry()['last_tested'])

    def test_arbitrary_command_is_never_executed(self):
        self.config.write_text(json.dumps({'mcpServers': {'mnemos': {'command': '/bin/sh', 'args': ['-c', 'touch forbidden']}}}))
        with patch.object(connections.subprocess, 'run') as run:
            with self.assertRaises(core.MnemosError):
                connections.check_connection(self.active, self.cache, 'claude-code', self.project)
            run.assert_not_called()
        self.assertEqual(self.entry()['status'], 'needs-attention')

    def test_missing_disabled_broken_and_malformed_configs(self):
        self.assertEqual(self.entry()['status'], 'disconnected')
        self.configure(enabled=False)
        self.assertEqual(self.entry()['status'], 'disconnected')
        self.configure(self.root / 'missing')
        self.assertEqual(self.entry()['status'], 'needs-attention')
        self.config.write_text('{"PRIVATE_TOKEN": "sentinel-never-return", invalid}')
        row = self.entry()
        self.assertEqual(row['status'], 'needs-attention')
        self.assertNotIn('sentinel-never-return', json.dumps(row))

    def test_symlink_config_is_not_followed(self):
        target = self.root / 'outside.json'
        target.write_text('{}')
        try:
            self.config.symlink_to(target)
        except OSError:
            self.skipTest('Symlinks not available')
        self.assertEqual(self.entry()['status'], 'needs-attention')

    def test_frozen_commands_use_bundled_dispatch(self):
        with patch.object(sys, 'frozen', True, create=True):
            self.assertEqual(tool_command('mcp_server', '--data', self.active),
                             [sys.executable, '--tool', 'mcp_server', '--data', str(self.active)])
        with self.assertRaises(ValueError):
            tool_command('../untrusted')

    def test_tunnel_health_is_not_account_verification(self):
        data = self.active
        folder = data / 'connections/chatgpt'
        folder.mkdir(parents=True)
        (folder / 'keystone-connection.json').write_text('{}')
        with patch('scripts.connect_chatgpt.read_receipt', return_value={'profile_sha256': 'safe-hash'}), \
                patch('scripts.connect_chatgpt.status', return_value={'healthy': True, 'ready': True}):
            rows = connections.inventory(data, self.cache, self.project)['connections']
            client = next(row['id'] for row in rows if row['id'].startswith('chatgpt-'))
            rows = connections.check_connection(data, self.cache, client, self.project)['connections']
            row = next(row for row in rows if row['id'] == client)
            self.assertEqual(row['status'], 'tested')
            self.assertIn('require a test from your chat', row['detail'])
        with patch('scripts.connect_chatgpt.read_receipt', return_value={'profile_sha256': 'safe-hash'}), \
                patch('scripts.connect_chatgpt.status', side_effect=ValueError()):
            rows = connections.check_connection(data, self.cache, client, self.project)['connections']
            self.assertEqual(next(r for r in rows if r['id'] == client)['status'], 'disconnected')
