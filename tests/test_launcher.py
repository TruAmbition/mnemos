import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from mnemos import core
from mnemos.runtime import default_root

spec = importlib.util.spec_from_file_location('mnemos_launcher_tests', core.ROOT / 'scripts/launch.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class LauncherTests(unittest.TestCase):
    def test_matching_running_service_is_reused_without_spawning(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            status = {'kind': 'mnemos-local-runtime-v1', 'installation': str(root / 'data/installation.json'),
                      'data_path': str(root / 'another-default'), 'initialized': True}
            with patch.object(launcher, 'ROOT', root), patch.object(sys, 'argv', ['launch.py']), \
                    patch.object(launcher, 'running', return_value=status), \
                    patch.object(launcher.subprocess, 'Popen') as popen, patch.object(launcher.webbrowser, 'open') as browser:
                launcher.main()
                popen.assert_not_called()
                browser.assert_called_once_with('http://127.0.0.1:4318')

    def test_different_installation_is_never_stopped_or_reused(self):
        status = {'kind': 'mnemos-local-runtime-v1', 'installation': '/other/installation.json'}
        with patch.object(sys, 'argv', ['launch.py']), patch.object(launcher, 'running', return_value=status), \
                patch.object(launcher.subprocess, 'Popen') as popen, patch.object(launcher.webbrowser, 'open') as browser:
            with self.assertRaisesRegex(ValueError, 'different Mnemos installation'):
                launcher.main()
            popen.assert_not_called()
            browser.assert_not_called()

    def test_pinned_service_requires_same_data_folder(self):
        status = {'installation': None, 'data_path': str(Path('/one'))}
        self.assertTrue(launcher.same_runtime(status, None, Path('/one')))
        self.assertFalse(launcher.same_runtime(status, None, Path('/two')))
        self.assertFalse(launcher.same_runtime(status, Path('/one/installation.json'), Path('/one')))
        self.assertFalse(launcher.same_runtime({**status, 'stopping': True}, None, Path('/one')))

    def test_packaged_default_is_outside_bundle(self):
        with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'platform', 'darwin'), \
                patch.object(Path, 'home', return_value=Path('/example-user')):
            self.assertEqual(default_root(), Path('/example-user/Library/Application Support/Mnemos/data'))
        self.assertEqual(default_root(), core.ROOT / 'data')
