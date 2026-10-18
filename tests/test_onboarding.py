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
        server = MnemosServer(('127.0.0.1', 0), options.pop('data_path', self.data), **options)
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
        request_headers.setdefault('X-Mnemos-Workspace', server.workspace_id)
        body = None
        if payload is not None:
            payload = dict(payload)
            if path in {'/api/setup', '/api/setup/inspect'}:
                payload.setdefault('expected_workspace', server.active_workspace())
                payload.setdefault('expected_settings_revision', onboarding.settings_revision(server.data_path))
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
        result = {'mode': 'update' if (self.data / 'config.json').exists() else 'create',
                  'data_path': str(self.data), 'author': 'Engineer', 'assistant_mode': 'local',
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

    def test_explicit_server_and_launcher_reject_data_symlink_before_resolving(self):
        core.initialize(self.data, 'Owner')
        link = self.base / 'linked-data'
        try:
            link.symlink_to(self.data, target_is_directory=True)
        except OSError:
            self.skipTest('Symlinks unavailable')
        with self.assertRaisesRegex(ValueError, 'symbolic link'):
            MnemosServer(('127.0.0.1', 0), link)
        spec = importlib.util.spec_from_file_location('mnemos_launch_symlink_test', core.ROOT / 'scripts/launch.py')
        launcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(launcher)
        with patch.object(launcher.sys, 'argv', ['launch.py', '--data', str(link)]), \
                patch.object(launcher, 'MnemosServer') as server, self.assertRaisesRegex(ValueError, 'symbolic link'):
            launcher.main()
        server.assert_not_called()

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

    def test_explicit_selection_survives_default_and_selected_config_edits(self):
        custom = self.base / 'custom'
        core.initialize(custom, 'Custom')
        pointer = self.data / 'installation.json'
        onboarding.save_selection(pointer, custom)
        core.initialize(self.data, 'New default')
        self.assertEqual(onboarding.load_selection(pointer, self.data), custom)
        core.issue_token(custom, 'reader', 'Reader')
        self.assertEqual(onboarding.load_selection(pointer, self.data), custom)

    def test_create_new_default_preserves_previous_workspace_and_restarts_at_new_one(self):
        core.initialize(self.data, 'Original')
        note = core.save_document(self.data, {'title': 'Original only', 'body': 'Keep this evidence'})
        token = core.issue_token(self.data, 'reader', 'Original reader')
        profile = self.data / 'connections/chatgpt/keystone.yaml'
        profile.parent.mkdir(parents=True)
        profile.write_text('existing pinned profile')
        original_config = (self.data / 'config.json').read_bytes()
        pointer = self.data / 'installation.json'
        server = self.server(installation_file=pointer)
        old_id = server.workspace_id
        custom = self.base / 'new default'
        payload = self.payload(mode='create', data_path=str(custom), author='New author',
                               backup={'provider': 'local', 'destination': str(custom / 'backups'), 'remote': ''})
        status, result = self.request(server, 'POST', payload=payload)
        self.assertEqual(status, 200, result)
        self.assertNotEqual(result['workspace_id'], old_id)
        self.assertEqual(result['previous_workspace']['data_path'], str(self.data))
        self.assertEqual((self.data / 'config.json').read_bytes(), original_config)
        self.assertEqual(core.get_document(self.data, note['id'])['revision'], note['revision'])
        self.assertIsNotNone(core.authenticate(self.data, token))
        self.assertEqual(profile.read_text(), 'existing pinned profile')
        self.assertFalse((custom / 'connections').exists())
        self.assertEqual(core.load_config(custom)['owner'], 'New author')
        self.assertEqual(onboarding.load_selection(pointer, self.data), custom)
        core.issue_token(self.data, 'author', 'Changed inactive settings')
        core.issue_token(custom, 'reader', 'Changed active settings')
        self.assertEqual(onboarding.load_selection(pointer, self.data), custom)
        restarted = self.server(data_path=custom, installation_file=pointer)
        status, overview = self.request(restarted)
        self.assertEqual(status, 200)
        self.assertEqual(overview['workspace_id'], result['workspace_id'])
        self.assertEqual(overview['active_workspace']['data_path'], str(custom))
        self.assertEqual(overview['setup_modes'], ['update', 'create', 'select'])

    def test_inspect_is_read_only_and_select_uses_target_settings_without_overwriting(self):
        target = self.base / 'existing'
        core.initialize(target, 'Target author')
        core.update_settings(target, {'backup': {'provider': 'rclone', 'destination': str(target / 'copies'), 'remote': 'drive:existing'}})
        config = core.load_config(target)
        config['assistant_mode'] = 'handoff'
        core.save_config(target, config)
        note = core.save_document(target, {'title': 'Target content', 'body': 'Retain the target'})
        original = (target / 'config.json').read_bytes()
        pointer = self.data / 'installation.json'
        server = self.server(installation_file=pointer)
        status, inspected = self.request(server, 'POST', '/api/setup/inspect', {'data_path': str(target)})
        self.assertEqual(status, 200, inspected)
        self.assertFalse(self.data.exists())
        self.assertEqual(inspected['workspace']['author'], 'Target author')
        self.assertEqual((target / 'config.json').read_bytes(), original)
        status, result = self.request(server, 'POST', payload={'mode': 'select', 'data_path': str(target),
            'expected_target_settings_revision': inspected['workspace']['settings_revision']})
        self.assertEqual(status, 200, result)
        self.assertEqual(result['author'], 'Target author')
        self.assertEqual(result['assistant_mode'], 'handoff')
        self.assertEqual(result['backup']['remote'], 'drive:existing')
        self.assertEqual((target / 'config.json').read_bytes(), original)
        self.assertEqual(core.get_document(target, note['id'])['revision'], note['revision'])

    def test_modes_reject_accidental_overwrite_or_workspace_switch(self):
        core.initialize(self.data, 'Original')
        target = self.base / 'existing'
        core.initialize(target, 'Existing target')
        pointer = self.data / 'installation.json'
        server = self.server(installation_file=pointer)
        original = (target / 'config.json').read_bytes()
        payloads = [self.payload(mode='create', data_path=str(target)),
                    self.payload(mode='update', data_path=str(target)),
                    self.payload(mode='select', data_path=str(target)),
                    {'mode': 'select', 'data_path': str(self.base / 'missing'), 'expected_target_settings_revision': ''}]
        for payload in payloads:
            with self.subTest(mode=payload['mode']):
                status, result = self.request(server, 'POST', payload=payload)
                self.assertEqual(status, 400, result)
                self.assertEqual(server.data_path, self.data)
        self.assertEqual((target / 'config.json').read_bytes(), original)
        self.assertFalse(pointer.exists())

    def test_stale_workspace_rejects_browser_mutation_and_download(self):
        core.initialize(self.data, 'Original')
        pointer = self.data / 'installation.json'
        server = self.server(installation_file=pointer)
        _, old = self.request(server)
        target = self.base / 'new'
        status, result = self.request(server, 'POST', payload=self.payload(mode='create', data_path=str(target)))
        self.assertEqual(status, 200, result)
        stale_headers = {'X-Mnemos-Workspace': old['workspace_id']}
        status, result = self.request(server, 'POST', '/api/documents', {'title': 'Stale tab'}, stale_headers)
        self.assertEqual(status, 409)
        self.assertEqual(result['code'], 'workspace_changed')
        self.assertEqual(self.request(server, path='/api/export?workspace=' + old['workspace_id'])[0], 409)
        payload = self.payload(mode='update', data_path=str(target), expected_workspace=old['active_workspace'],
                               expected_settings_revision=old['settings_revision'])
        self.assertEqual(self.request(server, 'POST', payload=payload)[0], 409)
        self.assertFalse(any(doc['title'] == 'Stale tab' for doc in core.list_documents(target)))
        self.assertEqual(self.request(server, 'POST', '/api/documents', {'title': 'Missing scope'}, {'X-Mnemos-Workspace': ''})[0], 409)

    def test_stale_active_or_target_settings_are_rejected(self):
        core.initialize(self.data, 'Original')
        pointer = self.data / 'installation.json'
        server = self.server(installation_file=pointer)
        _, old = self.request(server)
        core.issue_token(self.data, 'reader', 'New reader')
        status, result = self.request(server, 'POST', payload=self.payload(expected_settings_revision=old['settings_revision']))
        self.assertEqual(status, 409)
        self.assertEqual(result['code'], 'settings_changed')
        target = self.base / 'existing'
        core.initialize(target, 'Target')
        _, inspected = self.request(server, 'POST', '/api/setup/inspect', {'data_path': str(target)})
        core.issue_token(target, 'reader', 'New target reader')
        status, result = self.request(server, 'POST', payload={'mode': 'select', 'data_path': str(target),
            'expected_target_settings_revision': inspected['workspace']['settings_revision']})
        self.assertEqual(status, 409)
        self.assertEqual(result['code'], 'settings_changed')
        self.assertEqual(server.data_path, self.data)

    def test_overview_pairs_displayed_settings_with_their_exact_revision(self):
        core.initialize(self.data, 'Original')
        server = self.server()
        original_choices = onboarding.choices
        changed = False
        def concurrent_edit(data, *args):
            nonlocal changed
            result = original_choices(data, *args)
            if not changed:
                changed = True
                config = core.load_config(data)
                config['owner'] = 'Concurrent author'
                core.save_config(data, config)
            return result
        with patch.object(onboarding, 'choices', side_effect=concurrent_edit):
            status, result = self.request(server)
        self.assertEqual(status, 200, result)
        self.assertEqual(result['author'], 'Concurrent author')
        self.assertEqual(result['settings_revision'], onboarding.settings_revision(self.data))

    def test_pointer_save_failure_keeps_previous_active_workspace(self):
        core.initialize(self.data, 'Original')
        pointer = self.data / 'installation.json'
        onboarding.save_selection(pointer, self.data)
        original_pointer = pointer.read_bytes()
        server = self.server(installation_file=pointer)
        old_id = server.workspace_id
        target = self.base / 'new'
        with patch.object(onboarding, 'save_selection', side_effect=OSError('Simulated disk failure')):
            status, result = self.request(server, 'POST', payload=self.payload(mode='create', data_path=str(target)))
        self.assertEqual(status, 500)
        self.assertIn('previous workspace remains active', result['error'])
        self.assertEqual(server.data_path, self.data)
        self.assertEqual(server.workspace_id, old_id)
        self.assertEqual(pointer.read_bytes(), original_pointer)
        self.assertEqual(onboarding.load_selection(pointer, self.data), self.data)
        self.assertEqual(self.request(server, path='/api/bootstrap')[1]['session']['author'], 'Original')

    def test_second_default_server_fails_closed_after_selection_changes(self):
        core.initialize(self.data, 'Original')
        pointer = self.data / 'installation.json'
        first = self.server(installation_file=pointer)
        second = self.server(installation_file=pointer)
        target = self.base / 'new'
        self.assertEqual(self.request(first, 'POST', payload=self.payload(mode='create', data_path=str(target)))[0], 200)
        for method, path, payload in [('GET', '/api/bootstrap', None), ('GET', '/api/setup', None),
                                      ('POST', '/api/documents', {'title': 'Stale server'}),
                                      ('POST', '/api/setup', self.payload())]:
            status, result = self.request(second, method, path, payload)
            self.assertEqual(status, 409, result)
            self.assertTrue(result['restart_required'])
        self.assertEqual(onboarding.load_selection(pointer, self.data), target)
        self.assertFalse(any(doc['title'] == 'Stale server' for doc in core.list_documents(self.data)))

    def test_in_flight_mutation_finishes_in_its_original_workspace_before_activation(self):
        core.initialize(self.data, 'Original')
        pointer = self.data / 'installation.json'
        server = self.server(installation_file=pointer)
        old_id = server.workspace_id
        target = self.base / 'next'
        entered, release, switch_finished = threading.Event(), threading.Event(), threading.Event()
        results = {}
        original_save = core.save_document
        def delayed_save(data, payload, *args):
            entered.set()
            if not release.wait(3):
                raise RuntimeError('Test failed to release the pending write')
            return original_save(data, payload, *args)
        def write():
            results['write'] = self.request(server, 'POST', '/api/documents', {'title': 'In-flight document'},
                                            {'X-Mnemos-Workspace': old_id})
        def switch():
            try:
                results['switch'] = self.request(server, 'POST', payload=self.payload(mode='create', data_path=str(target)))
            finally:
                switch_finished.set()
        with patch.object(core, 'save_document', side_effect=delayed_save):
            writer = threading.Thread(target=write)
            switcher = threading.Thread(target=switch)
            writer.start()
            try:
                self.assertTrue(entered.wait(3))
                switcher.start()
                self.assertFalse(switch_finished.wait(0.1))
            finally:
                release.set()
                writer.join(timeout=5)
                if switcher.ident is not None:
                    switcher.join(timeout=5)
        self.assertEqual(results['write'][0], 200, results)
        self.assertEqual(results['switch'][0], 200, results)
        self.assertTrue(any(doc['title'] == 'In-flight document' for doc in core.list_documents(self.data)))
        self.assertFalse(any(doc['title'] == 'In-flight document' for doc in core.list_documents(target)))

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
