from privacy_fixture import allow_fixture
"""Default workspace selection never silently retargets pinned connections."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from mnemos import core, onboarding
from mnemos.__main__ import main as cli
from mnemos.installation import resolve_data
from scripts import backup, connect_chatgpt, export_reader, install_agents, install_claude_desktop, mcp_server, setup


class DefaultSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name).resolve()
        self.root = self.base / 'checkout'
        self.original = self.root / 'data'
        self.selected = self.base / 'selected'
        core.initialize(self.original, 'Original')
        core.initialize(self.selected, 'Selected')
        core.save_document(self.original, {'title': 'Unique original workspace', 'type': 'context', 'body': 'Original evidence.'})
        core.save_document(self.selected, {'title': 'Unique selected workspace', 'type': 'context', 'body': 'Selected evidence.'})
        allow_fixture(self.original)
        allow_fixture(self.selected)
        self.pointer = self.original / 'installation.json'
        onboarding.save_selection(self.pointer, self.selected)
        self.root_patch = patch.object(core, 'ROOT', self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.addCleanup(self.temporary.cleanup)

    def test_default_uses_saved_selection_and_explicit_path_stays_pinned(self):
        self.assertEqual(resolve_data(), self.selected)
        self.assertEqual(resolve_data(self.original), self.original)
        core.update_settings(self.original, {'backup': {'provider': 'local', 'destination': str(self.base / 'new-backups'), 'remote': ''}})
        self.assertEqual(resolve_data(), self.selected)

    def test_cli_omitted_path_follows_selection_and_explicit_path_bypasses_it(self):
        for arguments, expected in [(['search', 'Unique'], 'Unique selected workspace'),
                                    (['search', '--data', str(self.original), 'Unique'], 'Unique original workspace')]:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(cli(arguments), 0)
            self.assertEqual([doc['title'] for doc in json.loads(output.getvalue())['documents']], [expected])

    def test_default_serve_tracks_pointer_but_explicit_serve_does_not(self):
        with patch('mnemos.server.serve') as serve:
            self.assertEqual(cli(['serve']), 0)
            self.assertEqual(serve.call_args.args[0], self.selected)
            self.assertEqual(serve.call_args.kwargs['installation_file'], self.pointer)
            self.assertEqual(cli(['serve', '--data', str(self.original)]), 0)
            self.assertEqual(serve.call_args.args[0], self.original)
            self.assertIsNone(serve.call_args.kwargs['installation_file'])

    def test_helper_commands_share_default_and_explicit_path_resolution(self):
        for module, function, arguments in [(backup, 'create_backup', []),
                                             (export_reader, 'build_reader', ['--out', str(self.base / 'reader')]),
                                             (connect_chatgpt, 'status', ['status'])]:
            with self.subTest(helper=module.__name__), patch.object(module, function, return_value={'healthy': True, 'ready': True}) as work, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(module.main(arguments), 0)
                self.assertEqual(work.call_args.args[0], self.selected)
                self.assertEqual(module.main(arguments + ['--data', str(self.original)]), 0)
                self.assertEqual(work.call_args.args[0], self.original)

    def test_terminal_setup_uses_selection_without_changing_default(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(setup.main(['--yes', '--skip-obsidian']), 0)
            self.assertEqual(setup.main(['--data', str(self.original), '--yes', '--skip-obsidian']), 0)
        self.assertEqual(resolve_data(), self.selected)

    def test_new_project_connection_pins_selection_and_never_migrates_on_switch(self):
        project = self.base / 'project'
        install_agents.install_agents(project, clients='claude')
        config = project / '.mcp.json'
        original_config = config.read_bytes()
        self.assertEqual(json.loads(original_config)['mcpServers']['mnemos']['args'][-1], str(self.selected))
        onboarding.save_selection(self.pointer, self.original)
        with self.assertRaisesRegex(ValueError, 'different'):
            install_agents.install_agents(project, clients='claude')
        self.assertEqual(config.read_bytes(), original_config)
        install_agents.install_agents(project, self.selected, clients='claude')
        self.assertEqual(config.read_bytes(), original_config)

    def test_desktop_connection_uses_selected_path_and_refuses_automatic_retarget(self):
        config = self.base / 'claude.json'
        with patch.object(install_claude_desktop, 'probe_connection', return_value=['recall_context']):
            install_claude_desktop.install_claude_desktop(config_path=config, apply=True)
            content = config.read_bytes()
            self.assertEqual(json.loads(content)['mcpServers']['mnemos']['args'][-1], str(self.selected))
            onboarding.save_selection(self.pointer, self.original)
            with self.assertRaisesRegex(ValueError, 'different'):
                install_claude_desktop.install_claude_desktop(config_path=config, apply=True)
            self.assertEqual(config.read_bytes(), content)

    def test_mcp_omitted_path_and_explicit_path_read_the_intended_library(self):
        request = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                   'params': {'name': 'search_documents', 'arguments': {'query': 'Unique'}}}
        for args, expected in [([], 'Unique selected workspace'),
                               (['--data', str(self.original)], 'Unique original workspace')]:
            stream = SimpleNamespace(buffer=io.BytesIO((json.dumps(request) + '\n').encode()))
            output = io.StringIO()
            with patch.object(mcp_server.sys, 'stdin', stream), contextlib.redirect_stdout(output):
                self.assertEqual(mcp_server.main(args), 0)
            result = json.loads(json.loads(output.getvalue())['result']['content'][0]['text'])
            self.assertEqual([doc['title'] for doc in result], [expected])

    def test_default_mcp_stops_after_switch_but_explicit_mcp_stays_pinned(self):
        for args, expected_calls, expected_status in [([], 1, 1), (['--data', str(self.selected)], 2, 0)]:
            onboarding.save_selection(self.pointer, self.selected)
            calls = 0
            def readline(_limit):
                nonlocal calls
                calls += 1
                if calls == 2:
                    onboarding.save_selection(self.pointer, self.original)
                return b'{"jsonrpc":"2.0","id":1,"method":"ping"}\n' if calls <= 2 else b''
            stream = SimpleNamespace(buffer=SimpleNamespace(readline=readline))
            errors = io.StringIO()
            with patch.object(mcp_server.sys, 'stdin', stream), patch.object(mcp_server, 'handle', wraps=mcp_server.handle) as handle, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors):
                self.assertEqual(mcp_server.main(args), expected_status)
                self.assertEqual(handle.call_count, expected_calls)
            if not args:
                self.assertIn('Restart this MCP connection', errors.getvalue())

    def test_invalid_pointer_does_not_block_explicit_path_or_skills_only(self):
        self.pointer.write_text('invalid')
        with self.assertRaises(ValueError):
            resolve_data()
        self.assertEqual(resolve_data(self.selected), self.selected)
        install_agents.install_agents(self.base / 'skills-project', skills_only=True)
        with patch('mnemos.__main__.resolve_data', side_effect=AssertionError('Must not resolve a vault')), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli(['skills-export', '--output', str(self.base / 'skills.zip')]), 0)

    def test_explicit_symlink_is_not_hidden_from_storage_validation(self):
        link = self.base / 'linked-data'
        try:
            link.symlink_to(self.selected, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest('Symlink creation unavailable')
        self.assertEqual(resolve_data(link), link)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cli(['search', '--data', str(link), 'Unique']), 1)
        with self.assertRaisesRegex(ValueError, 'symbolic link'):
            mcp_server.main(['--data', str(link)])
        with self.assertRaisesRegex(ValueError, 'symbolic link'):
            install_agents.install_agents(self.base / 'linked-project', link)


if __name__ == '__main__':
    unittest.main()
