import http.client
import importlib.util
import io
import json
from pathlib import Path
import shlex
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from mnemos import core, onboarding
from mnemos.server import MnemosServer


class OnboardingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name).resolve()
        self.data = self.base / 'data'
        self.addCleanup(self.temporary.cleanup)
        detect = patch.object(onboarding, 'detect_obsidian', return_value=None)
        self.detect = detect.start()
        self.addCleanup(detect.stop)
        install = patch.object(onboarding, 'install_obsidian')
        self.install = install.start()
        self.addCleanup(install.stop)

    def server(self, **options):
        server = MnemosServer(('127.0.0.1', 0), self.data, **options)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def stop():
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        self.addCleanup(stop)
        return server

    def request(self, server, method='GET', path='/api/setup', payload=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', server.server_address[1], timeout=5)
        self.addCleanup(connection.close)
        request_headers = dict(headers or {})
        body = None
        if payload is not None:
            body = json.dumps(payload)
            request_headers.setdefault('Content-Type', 'application/json')
        connection.request(method, path, body, request_headers)
        response = connection.getresponse()
        raw = response.read()
        try:
            content = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            content = raw
        return response.status, content

    def payload(self, **extra):
        result = {'data_path': str(self.data), 'author': 'Engineer', 'assistant_mode': 'local',
                  'backup': {'provider': 'local', 'destination': str(self.data / 'backups'), 'remote': ''},
                  'install_obsidian': False}
        result.update(extra)
        return result

    def test_fresh_setup_is_read_only_until_apply_and_bootstraps_library(self):
        server = self.server()
        status, result = self.request(server)
        self.assertEqual(status, 200)
        self.assertFalse(result['initialized'])
        self.assertFalse(result['obsidian']['installed'])
        self.assertFalse(self.data.exists())
        self.assertEqual(self.request(server, path='/api/bootstrap')[0], 409)
        status, result = self.request(server, 'POST', payload=self.payload())
        self.assertEqual(status, 200)
        self.assertEqual(result['status'], 'ready')
        self.assertEqual(result['library_url'], '/')
        self.assertTrue(result['initialized'])
        self.assertEqual(core.load_config(self.data)['assistant_mode'], 'local')
        self.assertEqual(self.request(server, path='/api/bootstrap')[1]['session']['author'], 'Engineer')
        self.install.assert_not_called()

    def test_custom_location_switches_only_after_success_and_survives_default_launch(self):
        pointer = self.data / 'installation.json'
        server = self.server(installation_file=pointer)
        custom = self.base / 'my library'
        payload = self.payload(data_path=str(custom), backup={'provider': 'local', 'destination': str(custom / 'backups'), 'remote': ''})
        self.assertEqual(self.request(server, 'POST', payload=payload)[0], 200)
        self.assertEqual(server.data_path, custom)
        self.assertEqual(onboarding.load_selection(pointer, self.data), custom)
        self.assertFalse((self.data / 'config.json').exists())
        self.assertNotIn('tokens', pointer.read_text())

    def test_existing_update_preserves_documents_tokens_and_legacy_tunnel(self):
        core.initialize(self.data, 'Original')
        document = core.save_document(self.data, {'title': 'Keep me', 'body': 'Unchanged evidence'})
        token = core.issue_token(self.data, 'reader', 'Reader')
        original_tokens = core.load_config(self.data)['tokens']
        profile = self.data / 'connections/chatgpt/keystone.yaml'
        profile.parent.mkdir(parents=True)
        profile.write_text('existing profile')
        server = self.server()
        status, result = self.request(server, 'POST', payload=self.payload(assistant_mode='connected'))
        self.assertEqual(status, 200)
        config = core.load_config(self.data)
        self.assertEqual(config['tokens'], original_tokens)
        self.assertEqual(core.get_document(self.data, document['id'])['revision'], document['revision'])
        self.assertEqual(profile.read_text(), 'existing profile')
        self.assertEqual(config['assistant_mode'], 'connected')
        self.assertNotIn(token, json.dumps(result))
        self.assertEqual(result['connection_status'], 'not-checked')

    def test_rejects_unrelated_or_existing_vault_locations_without_mutation(self):
        server = self.server()
        unrelated = self.base / 'unrelated'
        unrelated.mkdir()
        (unrelated / 'keep.txt').write_text('keep')
        vault = self.base / 'existing-vault'
        (vault / '.obsidian').mkdir(parents=True)
        for target in [unrelated, vault, vault / 'nested-data']:
            with self.subTest(target=target):
                status, _ = self.request(server, 'POST', payload=self.payload(data_path=str(target)))
                self.assertEqual(status, 400)
                self.assertEqual(server.data_path, self.data)
                self.assertFalse((target / 'config.json').exists())
        self.assertEqual((unrelated / 'keep.txt').read_text(), 'keep')

    def test_rejects_symlinked_target_and_config(self):
        target = self.base / 'target'
        target.mkdir()
        link = self.base / 'linked'
        try:
            link.symlink_to(target, target_is_directory=True)
        except OSError:
            self.skipTest('Symlinks unavailable')
        with self.assertRaises(ValueError):
            onboarding.configure(self.data, self.payload(data_path=str(link)))
        outside = self.base / 'outside-config.json'
        outside.write_text('{"version":1}')
        (target / 'config.json').symlink_to(outside)
        with self.assertRaises(ValueError):
            onboarding.configure(self.data, self.payload(data_path=str(target)))
        self.assertEqual(outside.read_text(), '{"version":1}')

    def test_invalid_backup_or_modes_do_not_initialize(self):
        cases = [self.payload(backup={'provider': 'local', 'destination': str(self.data / 'vault/backups')}),
                 self.payload(backup={'provider': 'rclone', 'remote': 'https://user:secret@example.test'}),
                 self.payload(assistant_mode=['local']), self.payload(install_obsidian='true'),
                 self.payload(api_key='never-save-this')]
        for payload in cases:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                onboarding.configure(self.data, payload)
            self.assertFalse(self.data.exists())

    def test_setup_security_applies_before_initialization(self):
        server = self.server()
        for headers in [{'Host': 'attacker.example'}, {'Origin': 'https://attacker.example'},
                        {'Sec-Fetch-Site': 'cross-site'}, {'Authorization': 'Bearer invalid'}]:
            with self.subTest(headers=headers):
                self.assertEqual(self.request(server, 'POST', payload=self.payload(), headers=headers)[0], 403)
        self.assertEqual(self.request(server, 'POST', payload=self.payload(), headers={'Content-Type': 'text/plain'})[0], 415)
        self.assertEqual(self.request(server, headers={'Sec-Fetch-Site': 'cross-site'})[0], 403)
        self.assertFalse(self.data.exists())

    def test_authenticated_and_shared_servers_cannot_run_setup(self):
        core.initialize(self.data, 'Owner')
        token = core.issue_token(self.data, 'owner', 'Owner')
        for options in [{'require_auth': True}, {'public_hosts': ['internal.example']}]:
            server = self.server(**options)
            headers = {'Authorization': 'Bearer ' + token}
            self.assertEqual(self.request(server, headers=headers)[0], 403)
            self.assertEqual(self.request(server, 'POST', payload=self.payload(), headers=headers)[0], 403)
            self.assertEqual(self.request(server, path='/setup.html', headers=headers)[0], 403)

    def test_reader_token_does_not_inherit_local_setup_access(self):
        core.initialize(self.data, 'Owner')
        token = core.issue_token(self.data, 'reader', 'Reader')
        server = self.server()
        self.assertEqual(self.request(server, 'POST', payload=self.payload(), headers={'Authorization': 'Bearer ' + token})[0], 403)

    def test_uninitialized_shared_server_is_refused(self):
        with self.assertRaises(ValueError):
            MnemosServer(('127.0.0.1', 0), self.data, require_auth=True)

    def test_failed_optional_install_is_explicit_and_does_not_undo_library(self):
        self.install.side_effect = OSError('Installer failed')
        selected, result = onboarding.configure(self.data, self.payload(install_obsidian=True))
        self.assertEqual(selected, self.data)
        self.assertTrue(result['initialized'])
        self.assertEqual(result['obsidian']['status'], 'failed')
        self.assertFalse(result['obsidian']['installed'])
        self.assertTrue(result['warnings'])

    def test_install_result_is_detected_instead_of_assumed(self):
        self.install.return_value = '/claimed/path'
        _, result = onboarding.configure(self.data, self.payload(install_obsidian=True))
        self.assertFalse(result['obsidian']['installed'])
        self.detect.return_value = '/actual/Obsidian.app'
        _, result = onboarding.configure(self.data, self.payload(install_obsidian=True))
        self.assertTrue(result['obsidian']['installed'])

    def test_stale_pointer_does_not_override_new_default_installation(self):
        custom = self.base / 'custom'
        core.initialize(custom, 'Custom')
        pointer = self.data / 'installation.json'
        onboarding.save_selection(pointer, custom)
        core.initialize(self.data, 'New default')
        self.assertEqual(onboarding.load_selection(pointer, self.data), self.data)

    def test_copied_commands_quote_paths_and_shell_metacharacters_literally(self):
        arguments = [r'C:\Program Files\Python\python.exe', r"C:\Mnemos's Tools\scripts\install_agents.py",
                     '--data', r'C:\Notes\Engineer’s $(name); `cache']
        expected = (r"& 'C:\Program Files\Python\python.exe' 'C:\Mnemos''s Tools\scripts\install_agents.py' "
                    r"'--data' 'C:\Notes\Engineer’’s $(name); `cache'")
        self.assertEqual(onboarding._shell_command(arguments, 'powershell'), expected)
        self.assertEqual(shlex.split(onboarding._shell_command(arguments, 'posix')), arguments)
        self.assertEqual(onboarding._shell_command(["‘’‚‛"], 'powershell'), "& '‘‘’’‚‚‛‛'")

    def test_setup_commands_identify_and_use_the_platform_shell(self):
        for platform, expected in [('win32', 'powershell'), ('darwin', 'posix'), ('linux', 'posix')]:
            with self.subTest(platform=platform), patch.object(onboarding.sys, 'platform', platform):
                result = onboarding.choices(self.data)
                self.assertEqual(result['command_shell'], expected)
                self.assertEqual(set(result['commands']), {'codex', 'claude_code', 'claude_desktop', 'chatgpt'})
                for command in result['commands'].values():
                    self.assertEqual(command.startswith('& '), expected == 'powershell')
                if expected == 'posix':
                    self.assertEqual(shlex.split(result['commands']['codex'])[-2:], ['--data', str(self.data)])

    def test_launcher_opens_fresh_setup_without_terminal_questions(self):
        spec = importlib.util.spec_from_file_location('mnemos_launch_test', core.ROOT / 'scripts/launch.py')
        launcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(launcher)
        with patch.object(launcher, 'ROOT', self.base), patch.object(launcher.sys, 'argv', ['launch.py']), \
                patch.object(launcher, 'MnemosServer') as server, patch.object(launcher.threading, 'Timer') as timer, \
                patch.object(launcher.webbrowser, 'open') as browser, redirect_stdout(io.StringIO()):
            server.return_value.server_address = ('127.0.0.1', 4318)
            launcher.main()
            timer.call_args.args[1]()
            browser.assert_called_once_with('http://127.0.0.1:4318/setup.html')
        self.assertFalse(self.data.exists())

    def test_launcher_opens_existing_library(self):
        core.initialize(self.data, 'Existing')
        spec = importlib.util.spec_from_file_location('mnemos_launch_existing_test', core.ROOT / 'scripts/launch.py')
        launcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(launcher)
        with patch.object(launcher, 'ROOT', self.base), patch.object(launcher.sys, 'argv', ['launch.py']), \
                patch.object(launcher, 'MnemosServer') as server, patch.object(launcher.threading, 'Timer') as timer, \
                patch.object(launcher.webbrowser, 'open') as browser, redirect_stdout(io.StringIO()):
            server.return_value.server_address = ('127.0.0.1', 4318)
            launcher.main()
            timer.call_args.args[1]()
            browser.assert_called_once_with('http://127.0.0.1:4318')


if __name__ == '__main__':
    unittest.main()
