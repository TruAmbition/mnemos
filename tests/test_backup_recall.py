from privacy_fixture import allow_fixture
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import patch
import zipfile
from mnemos.backup import create_backup, list_backups, restore_backup, snapshot_bytes
from mnemos.core import initialize, issue_token, save_document, update_settings
from mnemos.export import build_reader, vault_archive
from mnemos.recall import recall, recall_documents

class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.data = self.base / 'data'
        initialize(self.data, 'Tester')
        allow_fixture(self.data)
    def tearDown(self):
        self.temporary.cleanup()
    def test_roundtrip_and_no_auth_credentials(self):
        result = create_backup(self.data)
        archive = Path(result['path'])
        self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), result['sha256'])
        target = self.base / 'restored'
        restored = restore_backup(archive, target)
        self.assertTrue(restored['verified'])
        self.assertFalse((target / 'config.json').exists())
        self.assertGreater(restored['files'], 0)
        original = {p.relative_to(self.data / 'vault').as_posix(): p.read_bytes() for p in (self.data / 'vault').rglob('*') if p.is_file()}
        actual = {p.relative_to(target).as_posix(): p.read_bytes() for p in target.rglob('*') if p.is_file()}
        self.assertEqual(original, actual)
    def test_refuse_overwrite(self):
        result = create_backup(self.data)
        with self.assertRaises(ValueError):
            restore_backup(result['path'], self.data / 'vault')
    def test_tampering_detected_before_restore(self):
        raw, _ = snapshot_bytes(self.data / 'vault')
        poisoned = self.base / 'poison.zip'
        with zipfile.ZipFile(io.BytesIO(raw)) as source, zipfile.ZipFile(poisoned, 'w') as out:
            changed = False
            for name in source.namelist():
                body = source.read(name)
                if name.startswith('vault/') and not changed:
                    body += b'changed'
                    changed = True
                out.writestr(name, body)
        with self.assertRaises(ValueError):
            restore_backup(poisoned, self.base / 'restored')
        self.assertFalse((self.base / 'restored').exists())
    def test_traversal_and_symlinks_rejected(self):
        bad = self.base / 'bad.zip'
        with zipfile.ZipFile(bad, 'w') as out:
            out.writestr('keystone-manifest.json', json.dumps({'format':1, 'files':{'../outside':{'size':1,'sha256':hashlib.sha256(b'x').hexdigest()}}}))
            out.writestr('vault/../outside', b'x')
        with self.assertRaises(ValueError):
            restore_backup(bad, self.base / 'restore')
        if hasattr(Path, 'symlink_to'):
            try:
                (self.data / 'vault' / 'linked').symlink_to(self.data / 'config.json')
            except OSError:
                return
            with self.assertRaises(ValueError):
                create_backup(self.data)
    def test_cloud_failure_retains_local_snapshot_and_history(self):
        update_settings(self.data, {'backup': {'provider': 'rclone', 'destination': str(self.base / 'snapshots'), 'remote': 'encrypted:mnemos'}})
        with patch('mnemos.backup.shutil.which', return_value='/usr/bin/rclone'), patch('mnemos.backup.subprocess.run', side_effect=subprocess.CalledProcessError(1, ['rclone'])):
            with self.assertRaisesRegex(ValueError, 'Local snapshot retained'):
                create_backup(self.data)
        history = list_backups(self.data)
        self.assertEqual(history[0]['status'], 'cloud-failed')
        local = Path(history[0]['path'])
        self.assertTrue(local.exists())
        self.assertTrue(local.with_suffix('.zip.sha256').exists())
        self.assertEqual(hashlib.sha256(local.read_bytes()).hexdigest(), history[0]['sha256'])
        restore_backup(local, self.base / 'recovery')
    def test_cloud_arguments_do_not_invoke_a_shell(self):
        update_settings(self.data, {'backup': {'provider': 'rclone', 'destination': str(self.base / 'snapshots'), 'remote': 'encrypted:folder with spaces'}})
        with patch('mnemos.backup.shutil.which', return_value='/usr/bin/rclone'), patch('mnemos.backup.subprocess.run') as run:
            result = create_backup(self.data)
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(run.call_count, 2)
        for call in run.call_args_list:
            self.assertNotIn('shell', call.kwargs)
            self.assertIsInstance(call.args[0], list)
            self.assertTrue(call.args[0][3].startswith('encrypted:folder with spaces/'))
    def test_static_reader_only_contains_verified_documents_and_no_tokens(self):
        token = issue_token(self.data, 'reader', 'Viewer')
        save_document(self.data, {'id': 'private-context', 'title': 'Private context', 'body': 'PRIVATE_UNAPPROVED_CONTENT', 'status': 'draft'})
        save_document(self.data, {'id': 'public-context', 'title': 'Approved context', 'body': 'APPROVED_CONTENT', 'status': 'verified'})
        allow_fixture(self.data)
        output = self.base / 'reader'
        result = build_reader(self.data, output)
        payload = (output / 'data.json').read_text()
        self.assertIn('APPROVED_CONTENT', payload)
        self.assertNotIn('PRIVATE_UNAPPROVED_CONTENT', payload)
        self.assertNotIn(token, payload)
        self.assertNotIn('tokens', json.loads(payload)['settings'])
        self.assertEqual(json.loads(payload)['session']['role'], 'reader')
        self.assertTrue(result['documents'])
        with zipfile.ZipFile(io.BytesIO(vault_archive(self.data))) as archive:
            self.assertNotIn('config.json', archive.namelist())
            self.assertNotIn(token.encode(), b''.join(archive.read(name) for name in archive.namelist()))

class RecallTests(unittest.TestCase):
    def test_budget_source_and_relevance(self):
        docs = [{'id':str(i),'title':'Deployment recovery','type':'context','status':'verified','body':'A safe deployment uses staged verification.\n' * 200,
                 'summary':'Deployment decisions','revision':'abcdef123456789','tags':['deployment']} for i in range(20)]
        result = recall_documents(docs, 'deployment', 3000)
        self.assertLessEqual(len(result['context']), 3000)
        self.assertTrue(result['items'])
        self.assertIn('abcdef123456', result['context'])
        self.assertEqual(recall_documents(docs, 'unrelated widgets')['items'], [])
    def test_reader_cannot_recall_drafts(self):
        with tempfile.TemporaryDirectory() as temporary:
            initialize(temporary)
            save_document(temporary, {'title':'Private quasar incident','type':'context','body':'secret quasar fix','status':'draft'})
            self.assertFalse(recall(temporary,'quasar', role='reader')['items'])
            self.assertTrue(recall(temporary,'quasar', role='owner')['items'])
    def test_excerpt_keeps_match_near_end_of_long_document(self):
        body = ('Unrelated historical detail.\n' * 300) + 'The frobnicator requires a recovery token.\n'
        result = recall_documents([{'id': 'recovery', 'title': 'Recovery', 'status': 'verified', 'body': body}], 'frobnicator', 1000)
        self.assertTrue(result['items'])
        self.assertIn('frobnicator', result['items'][0]['excerpt'])
    def test_small_budget_with_long_summary_still_returns_source(self):
        result = recall_documents([{'id': 'recovery', 'title': 'Recovery ' * 20, 'summary': 'Helpful overview. ' * 100,
                                    'status': 'verified', 'body': 'The frobnicator requires a recovery token.'}], 'frobnicator', 500)
        self.assertTrue(result['items'])
        self.assertLessEqual(len(result['context']), 500)
        self.assertIn('frobnicator', result['context'])
    def test_context_recall_preserves_complete_handoff_when_it_fits(self):
        body = '\n\n'.join(['# Retry configuration handoff', '## Goal\nResume retry work.',
                            '## Current state\nRetry count changed from 3 to 5.',
                            '## Constraints\nStaging deployment has not run.',
                            '## Decisions\nPreserve unit-test evidence; do not assume staging success.',
                            '## Next actions\nRequest deployment authorization, then verify staging.'])
        docs = [{'id': 'retry-handoff', 'title': 'Retry handoff', 'type': 'context',
                 'status': 'draft', 'body': body, 'summary': 'Resume documented retry work.'}]
        result = recall_documents(docs, 'retry', 6000)
        self.assertEqual(result['items'][0]['excerpt'], body)
        self.assertIn('## Decisions', result['context'])
        self.assertIn('## Next actions', result['context'])
    def test_context_recall_marks_truncation_and_respects_budget(self):
        docs = [{'id': 'retry-handoff', 'title': 'Retry handoff', 'type': 'context',
                 'status': 'draft', 'body': '# Retry handoff\n' + 'Documented details.\n' * 500}]
        result = recall_documents(docs, 'retry', 700)
        self.assertTrue(result['items'])
        self.assertIn('[context truncated]', result['context'])
        self.assertLessEqual(len(result['context']), 700)

class MCPTests(unittest.TestCase):
    def test_capture_recall_protocol(self):
        path = Path(__file__).resolve().parents[1] / 'scripts/mcp_server.py'
        spec = importlib.util.spec_from_file_location('mnemos_mcp', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temporary:
            initialize(temporary)
            def call(method, params):
                return module.handle(temporary, {'jsonrpc':'2.0','id':1,'method':method,'params':params})['result']
            initialized = call('initialize', {'protocolVersion':'2025-03-26'})
            self.assertIn('tools', initialized['capabilities'])
            captured = call('tools/call', {'name':'capture_document','arguments':{'document':{'title':'Nebula context','type':'context','body':'We chose local disk for the nebula project.','status':'verified'}}})
            self.assertFalse(captured['isError'])
            document = json.loads(captured['content'][0]['text'])
            self.assertEqual(document['status'], 'draft')
            allow_fixture(temporary)
            recalled = call('tools/call', {'name':'recall_context','arguments':{'query':'nebula'}})
            self.assertIn('Nebula context', recalled['content'][0]['text'])
            packed = json.loads(recalled['content'][0]['text'])
            self.assertTrue(packed['items'])
            self.assertNotIn('excerpt', packed['items'][0])
            self.assertIsNone(module.handle(temporary, {'jsonrpc':'2.0','method':'notifications/initialized'}))

if __name__ == '__main__':
    unittest.main()
