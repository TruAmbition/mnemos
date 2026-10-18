import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from mnemos import core, git_backup as gb, privacy


class GitBackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve(); self.data = self.root / 'data'
        core.initialize(self.data)
        shutil.rmtree(core.vault_path(self.data)); core.vault_path(self.data).mkdir()
        self.note = core.save_document(self.data, {'title': 'Recovery', 'body': 'Restart and verify the service.'})
        self.repo = self.root / 'docs'

    def configure(self, **changes):
        return gb.configure(self.data, {'create': True, 'parent': str(self.root), 'folder': 'docs', **changes})

    def allow(self):
        note = core.get_document(self.data, self.note['id'])
        privacy.update(self.data, {'id': note['id'], 'operation': 'policy', 'mode': 'team', 'fingerprint': note['privacy']['fingerprint']})

    def git(self, *args): return subprocess.check_output(['git', '-C', str(self.repo), *args], text=True).strip()

    def test_local_backup_preserves_notes_and_excludes_runtime(self):
        self.assertEqual(self.configure()['color'], 'amber')
        (core.vault_path(self.data) / '.obsidian').mkdir()
        (core.vault_path(self.data) / '.obsidian/workspace.json').write_text('personal settings')
        (self.data / 'privacy-approvals.json').write_text('{}')
        result = gb.sync(self.data)
        self.assertEqual(result['state'], 'local'); self.assertEqual(result['color'], 'amber')
        names = self.git('ls-tree', '-r', '--name-only', 'HEAD')
        self.assertIn('vault/', names); self.assertNotIn('.obsidian', names)
        self.assertNotIn('config.json', names); self.assertNotIn('privacy-approvals', names)
        head = self.git('rev-parse', 'HEAD'); gb.sync(self.data)
        self.assertEqual(head, self.git('rev-parse', 'HEAD'))
        core.save_document(self.data, {**self.note, 'body': 'New procedure'})
        self.assertEqual(gb.status(self.data)['state'], 'pending')
        gb.sync(self.data); self.assertNotEqual(head, self.git('rev-parse', 'HEAD'))
        self.assertEqual(self.git('status', '--porcelain'), '')

    def test_unicode_names_and_excluded_personal_files_do_not_break_commits(self):
        self.allow()
        note = core.get_document(self.data, self.note['id'])
        path = core.safe_path(core.vault_path(self.data), note['path'])
        path.rename(path.with_name('Recovery café.md'))
        personal = core.vault_path(self.data) / '.obsidian'
        personal.mkdir(); (personal / 'workspace.json').write_text('personal state')
        self.configure(); gb.sync(self.data)
        files = gb._files(self.data)
        gb._history_safe(self.data, self.repo, files)
        self.assertEqual(gb.status(self.data)['state'], 'local')

    def test_manual_changes_and_other_repositories_are_preserved(self):
        self.configure(); gb.sync(self.data)
        path = next((self.repo / 'vault').rglob('*.md')); path.write_text('Manual change')
        with self.assertRaises(core.MnemosError): gb.sync(self.data)
        self.assertEqual(path.read_text(), 'Manual change')
        self.assertEqual(gb.status(self.data)['color'], 'red')
        other = self.root / 'engineering'; other.mkdir(); subprocess.run(['git', 'init', str(other)], capture_output=True, check=True)
        (other / 'main.py').write_text('important')
        with self.assertRaises(core.MnemosError): gb.configure(self.data, {'path': str(other)})
        self.assertEqual((other / 'main.py').read_text(), 'important')

    def test_invalid_destination_and_secret_remote_rejected(self):
        for remote in ['https://token@example.com/repo', 'https://x/repo?token=abc', 'ext::command', '/tmp/remote', 'http://example.com/repo']:
            with self.assertRaises(core.MnemosError): self.configure(remote=remote)
        with self.assertRaises(core.MnemosError): self.configure(parent=str(self.data))
        with self.assertRaises(core.MnemosError): self.configure(auto_push=True)
        link = self.root / 'linked'; link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(core.MnemosError): self.configure(parent=str(link))

    def test_private_history_cannot_be_pushed_after_later_reclassification(self):
        self.configure(remote='https://example.com/docs.git', share_history=True)
        gb.sync(self.data); self.allow()
        with patch.object(gb, '_git', wraps=gb._git) as command:
            with self.assertRaisesRegex(core.MnemosError, 'local-only snapshot'): gb.sync(self.data, push=True)
            self.assertFalse(any('push' in call.args for call in command.call_args_list))
        self.assertEqual(gb.status(self.data)['color'], 'red')

    def test_push_green_only_after_success_and_new_changes_turn_red(self):
        self.allow(); self.configure(remote='https://example.com/docs.git', share_history=True)
        real = gb._git
        def transport(repo, *args, **kwargs):
            if args and args[0] == 'push':
                self.assertEqual(args[-1], 'HEAD:refs/heads/mnemos-backup')
                self.assertNotIn('--force', args)
                return subprocess.CompletedProcess(args, 0, b'', b'')
            return real(repo, *args, **kwargs)
        with patch.object(gb, '_git', side_effect=transport):
            result = gb.sync(self.data, push=True)
        self.assertEqual(result['color'], 'green'); self.assertTrue(result['last_push'])
        core.save_document(self.data, {**self.note, 'body': 'Updated procedure'})
        self.assertEqual(gb.status(self.data)['color'], 'amber')
        self.git('remote', 'set-url', 'origin', 'https://elsewhere.example/docs.git')
        with self.assertRaisesRegex(core.MnemosError, 'origin changed'): gb.sync(self.data, push=True)

    def test_push_failure_keeps_local_commit_and_safe_error(self):
        self.allow(); self.configure(remote='https://example.com/docs.git', share_history=True)
        real = gb._git
        def transport(repo, *args, **kwargs):
            if args and args[0] == 'push': raise core.MnemosError('Git operation failed. Check repository access.')
            return real(repo, *args, **kwargs)
        with patch.object(gb, '_git', side_effect=transport):
            with self.assertRaises(core.MnemosError): gb.sync(self.data, push=True)
        self.assertTrue(self.git('rev-parse', 'HEAD'))
        self.assertEqual(gb.status(self.data)['state'], 'error')
        self.assertFalse(gb.status(self.data)['last_push'])

    def test_secrets_and_removed_history_block_remote(self):
        self.allow(); self.configure(remote='https://example.com/docs.git', share_history=True); gb.sync(self.data)
        core.save_document(self.data, {**self.note, 'body': 'PASSWORD=reallysecretpassword'})
        with self.assertRaises(core.MnemosError): gb.sync(self.data, push=True)
        self.assertEqual(gb.status(self.data)['color'], 'red')

    def test_disable_preserves_files_and_stops_automatic(self):
        self.configure(automatic=True); gb.sync(self.data)
        result = gb.configure(self.data, {'enabled': False})
        self.assertEqual(result['state'], 'off'); self.assertTrue((self.repo / 'vault').exists())
        with self.assertRaises(core.MnemosError): gb.sync(self.data)

    def test_monitor_respects_opt_in_and_workspace(self):
        self.configure(automatic=True)
        server = SimpleNamespace(setup_enabled=True, stopping=False, workspace_lock=threading.RLock(), data_path=self.data, assert_selection_current=lambda: None)
        monitor = gb.GitBackupMonitor(server); monitor.scan_once()
        self.assertTrue(self.git('rev-parse', 'HEAD'))
        gb.configure(self.data, {'enabled': False})
        with patch.object(gb, 'sync') as sync:
            monitor.scan_once(); sync.assert_not_called()
        server.assert_selection_current = lambda: (_ for _ in ()).throw(ValueError('changed'))
        with patch.object(gb, 'sync') as sync:
            monitor.scan_once(); sync.assert_not_called()
