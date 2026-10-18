import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import warnings
from contextlib import redirect_stdout
from unittest.mock import Mock, patch

from keystone.core import initialize

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('connect_chatgpt', ROOT / 'scripts/connect_chatgpt.py')
connector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(connector)
TUNNEL = 'tunnel_0123456789abcdef0123456789abcdef'


class ChatGPTTunnelTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.data = Path(self.temporary.name) / 'data with spaces'
        initialize(self.data, 'Tester')

    def tearDown(self):
        self.temporary.cleanup()

    def fake_init(self, arguments, **kwargs):
        self.assertEqual(arguments[1], 'init')
        self.assertNotIn('CONTROL_PLANE_API_KEY', kwargs['env'])
        self.assertNotIn('--force', arguments)
        self.assertIn('env:CONTROL_PLANE_API_KEY', arguments)
        path = Path(arguments[arguments.index('--profile-dir') + 1]) / 'keystone.yaml'
        path.write_text('api_key: "env:CONTROL_PLANE_API_KEY"\n', encoding='utf-8')
        return subprocess.CompletedProcess(arguments, 0, '', '')

    def prepare(self):
        with patch.object(connector, 'preflight', return_value='quoted python command'), \
                patch.object(connector.subprocess, 'run', side_effect=self.fake_init):
            return connector.prepare(self.data, '/tunnel-client', TUNNEL)

    def test_real_mcp_preflight_exposes_capture_and_recall(self):
        command = connector.preflight(self.data)
        self.assertIn(str(self.data), command)
        self.assertIn('mcp_server.py', command)

    def test_prepare_is_isolated_no_secret_and_idempotent(self):
        with patch.dict(os.environ, {'CONTROL_PLANE_API_KEY': 'test-secret-do-not-save'}):
            result = self.prepare()
        self.assertEqual(result['status'], 'prepared')
        profile = Path(result['profile'])
        self.assertTrue(profile.is_relative_to(self.data))
        receipt = connector.read_receipt(self.data)
        self.assertEqual(receipt['tunnel_id'], TUNNEL)
        self.assertNotIn('test-secret-do-not-save', ''.join(p.read_text() for p in profile.parent.iterdir()))
        self.assertEqual(self.prepare()['status'], 'already-prepared')

    def test_different_connection_and_modified_profile_refused(self):
        result = self.prepare()
        with patch.object(connector, 'preflight', return_value='quoted python command'):
            with self.assertRaisesRegex(ValueError, 'different ChatGPT connection'):
                connector.prepare(self.data, '/tunnel-client', TUNNEL.replace('0', 'a'))
        profile = Path(result['profile'])
        profile.write_text('changed')
        with self.assertRaisesRegex(ValueError, 'intact'):
            connector.command_for(self.data, '/tunnel-client', 'run')
        self.assertEqual(profile.read_text(), 'changed')

    def test_failed_init_leaves_retry_possible(self):
        with patch.object(connector, 'preflight', return_value='python'), \
                patch.object(connector.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '', 'bad install')):
            with self.assertRaisesRegex(ValueError, 'bad install'):
                connector.prepare(self.data, '/tunnel-client', TUNNEL)
        self.assertFalse((self.data / 'connections/chatgpt').exists())
        self.assertEqual(self.prepare()['status'], 'prepared')

    def test_environment_and_command_do_not_leak_or_override_settings(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'unrelated', 'OPENAI_ADMIN_KEY': 'admin',
                                    'MCP_COMMAND': 'unwanted', 'CONTROL_PLANE_BASE_URL': 'https://unwanted.example'}):
            environment = connector.child_environment('runtime-test')
        self.assertEqual(environment['CONTROL_PLANE_API_KEY'], 'runtime-test')
        for name in ('OPENAI_API_KEY', 'OPENAI_ADMIN_KEY', 'MCP_COMMAND', 'CONTROL_PLANE_BASE_URL'):
            self.assertNotIn(name, environment)
        self.prepare()
        command = connector.command_for(self.data, '/tunnel-client', 'run')
        self.assertNotIn('runtime-test', ' '.join(command))
        self.assertIn('127.0.0.1:0', command)
        self.assertIn('--log.http-raw-unsafe=false', command)

    def test_noninteractive_missing_key_does_not_read_or_echo_input(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(connector.sys.stdin, 'isatty', return_value=False), \
                patch.object(connector.getpass, 'getpass') as prompt:
            with self.assertRaisesRegex(ValueError, 'terminal'):
                connector.runtime_key()
        prompt.assert_not_called()

    def test_unsafe_terminal_fallback_is_rejected(self):
        def fallback(*args):
            warnings.warn('terminal cannot disable echo', connector.getpass.GetPassWarning)
            self.fail('The hidden input warning must stop credential entry.')
        with patch.dict(os.environ, {}, clear=True), patch.object(connector.sys.stdin, 'isatty', return_value=True), \
                patch.object(connector.getpass, 'getpass', side_effect=fallback):
            with self.assertRaisesRegex(ValueError, 'Secure terminal input'):
                connector.runtime_key()

    def test_runtime_key_only_in_child_environment_and_output_redacted(self):
        self.prepare()
        secret = 'runtime-placeholder-secret'
        process = Mock(stdout=iter(['unexpected output ' + secret + '\n']))
        process.wait.return_value = 0
        output = io.StringIO()
        with patch.dict(os.environ, {'KEYSTONE_TUNNEL_API_KEY': secret}), \
                patch.object(connector.subprocess, 'Popen', return_value=process) as launch, redirect_stdout(output):
            self.assertEqual(connector.run_connected(self.data, '/tunnel-client', 'doctor'), 0)
        args, kwargs = launch.call_args
        self.assertNotIn(secret, ' '.join(args[0]))
        self.assertEqual(kwargs['env']['CONTROL_PLANE_API_KEY'], secret)
        self.assertNotIn(secret, output.getvalue())
        self.assertIn('[REDACTED]', output.getvalue())

    def test_connect_asks_once_and_runs_only_after_successful_doctor(self):
        self.prepare()
        with patch.object(connector, 'runtime_key', return_value='ephemeral-test') as prompt, \
                patch.object(connector, 'run_command', side_effect=[0, 0]) as run, redirect_stdout(io.StringIO()):
            self.assertEqual(connector.check_and_run(self.data, '/tunnel-client'), 0)
        prompt.assert_called_once()
        self.assertEqual([call.args[0][1] for call in run.call_args_list], ['doctor', 'run'])
        self.assertEqual([call.args[1] for call in run.call_args_list], ['ephemeral-test', 'ephemeral-test'])

    def test_failed_doctor_does_not_start_connection(self):
        self.prepare()
        with patch.object(connector, 'runtime_key', return_value='ephemeral-test'), \
                patch.object(connector, 'run_command', return_value=1) as run, redirect_stdout(io.StringIO()):
            self.assertEqual(connector.check_and_run(self.data, '/tunnel-client'), 1)
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0][1], 'doctor')

    def test_local_binary_preferred_to_path(self):
        self.assertEqual(connector.default_binary(self.data), 'tunnel-client')
        local = self.data / 'tools' / ('tunnel-client.exe' if os.name == 'nt' else 'tunnel-client')
        local.parent.mkdir()
        local.touch()
        self.assertEqual(connector.default_binary(self.data), str(local))

    def test_status_refuses_nonloopback_health_address(self):
        self.prepare()
        health = self.data / 'connections/chatgpt/health.url'
        for address in ['https://example.com', 'http://127.0.0.1:8000@evil.example', 'http://127.0.0.1:8000/path']:
            health.write_text(address)
            with self.subTest(address=address), self.assertRaisesRegex(ValueError, 'Unexpected health'):
                connector.status(self.data)

    def test_invalid_id_is_rejected_before_file_changes(self):
        with self.assertRaisesRegex(ValueError, 'complete tunnel ID'):
            connector.prepare(self.data, '/tunnel-client', 'anything')
        self.assertFalse((self.data / 'connections').exists())


if __name__ == '__main__':
    unittest.main()
