from privacy_fixture import allow_fixture
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from mnemos import core, projects
from mnemos.handoff import build_pack
from mnemos.recall import recall


@unittest.skipUnless(shutil.which('git'), 'Git is required for local project tests')
class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.git('init')
        self.data = self.root / 'data'
        core.initialize(self.data, 'Owner')
        self.write('README.md', '# Nimbus\n\nStart with the documented build.\n')
        self.write('src/app.py', 'print("hello")\n')
        self.commit()

    def git(self, *args):
        env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
        env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1',
                   GIT_AUTHOR_NAME='Test', GIT_AUTHOR_EMAIL='test@example.invalid',
                   GIT_COMMITTER_NAME='Test', GIT_COMMITTER_EMAIL='test@example.invalid')
        return subprocess.check_output(['git', '-c', 'commit.gpgsign=false', '-C', str(self.repo), *args], stderr=subprocess.DEVNULL, env=env).decode().strip()

    def write(self, name, body):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)

    def commit(self):
        self.git('add', '.')
        self.git('commit', '-m', 'Fixture commit')
        return self.git('rev-parse', 'HEAD')

    def register(self, **kwargs):
        return projects.save_project(self.data, {'name': 'Nimbus', 'path': str(self.repo), **kwargs})['project']

    def test_committed_capture_recall_and_repository_unchanged(self):
        project = self.register()
        self.write('README.md', 'UNCOMMITTED CONTENT must not be imported')
        before = (self.repo / '.git/index').read_bytes()
        head = self.git('rev-parse', 'HEAD')
        result = projects.refresh_project(self.data, project)
        doc = result['document']
        self.assertEqual(doc['status'], 'draft')
        self.assertEqual(doc['project'], 'Nimbus')
        self.assertIn('documented build', doc['body'])
        self.assertNotIn('UNCOMMITTED', doc['body'])
        self.assertNotIn(str(self.repo), doc['body'])
        self.assertEqual(result['project']['last_refresh']['commit'], head)
        self.assertTrue(doc['sources'][0].startswith('git:' + project['id'] + '@'))
        self.assertEqual((self.repo / '.git/index').read_bytes(), before)
        self.assertEqual(self.git('rev-parse', 'HEAD'), head)
        self.assertIn(doc['id'], recall(self.data, 'Nimbus')['context'])
        self.assertNotIn(doc['id'], recall(self.data, 'Nimbus', role='reader')['context'])

    def test_new_commit_preserves_handwritten_notes_and_latest_recall(self):
        first = projects.refresh_project(self.data, self.register())
        note = core.save_document(self.data, {'title': 'Nimbus deployment decision', 'type': 'decision', 'body': 'A human decision.', 'status': 'verified'})
        # Manual edits to an older capture must also survive refresh.
        old = core.save_document(self.data, {**first['document'], 'body': first['document']['body'] + '\nHuman annotation.'})
        self.write('README.md', '# Nimbus\nUpdated build documentation.\n')
        self.write('src/app.py', 'print("new feature")\n')
        self.commit()
        second = projects.refresh_project(self.data, first['project'])
        self.assertNotEqual(first['document']['id'], second['document']['id'])
        self.assertIn('README.md', second['document']['body'])
        self.assertIn('src/app.py', second['document']['body'])
        self.assertEqual(second['project']['last_refresh']['changed_count'], 2)
        self.assertIn(first['document']['id'], second['document']['related_ids'])
        self.assertEqual(core.get_document(self.data, old['id'])['revision'], old['revision'])
        self.assertEqual(core.get_document(self.data, note['id'])['revision'], note['revision'])
        ids = [d['id'] for d in recall(self.data, 'Nimbus')['items']]
        self.assertIn(second['document']['id'], ids)
        self.assertNotIn(first['document']['id'], ids)
        self.assertIn(note['id'], ids)
        allow_fixture(self.data)
        pack = build_pack(self.data, 'Nimbus')
        self.assertNotIn(first['document']['id'], [d['id'] for d in pack['documents']])
        history = build_pack(self.data, 'Nimbus', document_ids=[first['document']['id']])
        self.assertEqual(history['documents'][0]['id'], first['document']['id'])

    def test_same_commit_is_idempotent_and_preserves_manual_edits(self):
        first = projects.refresh_project(self.data, self.register())
        edited = core.save_document(self.data, {**first['document'], 'body': 'Human correction'})
        again = projects.refresh_project(self.data, first['project'])
        self.assertTrue(again['unchanged'])
        self.assertEqual(again['document']['revision'], edited['revision'])

    def test_update_revision_settings_and_preserve_config(self):
        credential = core.issue_token(self.data, 'reader', 'Reader')
        first = projects.refresh_project(self.data, self.register())
        updated = projects.save_project(self.data, {**first['project'], 'include': ['src/*.py']})['project']
        self.assertTrue(updated['needs_refresh'])
        self.assertIsNotNone(core.authenticate(self.data, credential))
        with self.assertRaises(core.MnemosError) as error:
            projects.refresh_project(self.data, first['project'])
        self.assertEqual(error.exception.status, 409)
        second = projects.refresh_project(self.data, updated)
        self.assertFalse(second['project']['needs_refresh'])
        self.assertNotEqual(first['document']['id'], second['document']['id'])
        self.assertIn('print', second['document']['body'])

    def test_disconnect_preserves_notes_and_repository(self):
        first = projects.refresh_project(self.data, self.register())
        result = projects.remove_project(self.data, first['project'])
        self.assertTrue(result['notes_preserved'])
        self.assertEqual(projects.list_projects(self.data)['projects'], [])
        self.assertEqual(core.get_document(self.data, first['document']['id'])['revision'], first['document']['revision'])
        self.assertTrue((self.repo / 'README.md').is_file())

    def test_exclusions_secret_detection_and_no_symlink_reads(self):
        self.write('.env', 'PRIVATE ENVIRONMENT')
        self.write('credentials.json', 'PRIVATE CREDENTIAL')
        self.write('docs/private.md', 'api_key=example-credential-should-not-be-imported')
        self.write('docs/allowed.md', '# Nimbus approved\nUseful context')
        self.write('docs/exclude.md', 'EXCLUDED CONTENT')
        if os.name != 'nt':
            (self.repo / 'docs/link.md').symlink_to(self.repo / '.env')
        self.commit()
        result = projects.refresh_project(self.data, self.register(include=['**'], exclude=['docs/exclude.md']))
        body = result['document']['body']
        for forbidden in ('PRIVATE ENVIRONMENT', 'PRIVATE CREDENTIAL', 'example-credential-should-not-be-imported', 'EXCLUDED CONTENT'):
            self.assertNotIn(forbidden, body)
        self.assertIn('Useful context', body)
        self.assertIn('credential-like content detected', body)
        self.assertNotIn('link.md', body)

    def test_source_limits_binary_and_fences(self):
        self.write('README.md', '# Nimbus\n```\nsource data\n```\n' + 'x' * 7000)
        self.write('docs/huge.md', 'x' * 33000)
        self.write('docs/binary.md', '\0binary')
        self.commit()
        result = projects.refresh_project(self.data, self.register(include=['**/*.md', 'README.md']))
        body = result['document']['body']
        self.assertIn('````text', body)
        self.assertIn('excerpt truncated', body)
        self.assertIn('larger than 32,000', body)
        self.assertIn('binary content', body)
        self.assertLess(len(body), 70000)

    def test_source_count_no_match_and_empty_repository(self):
        project = self.register(include=['missing.md'])
        result = projects.refresh_project(self.data, project)
        self.assertIn('No eligible documentation matched', result['project']['last_refresh']['warnings'][0])
        for index in range(15):
            self.write(f'docs/file-{index:02}.md', f'Example {index}')
        self.commit()
        project = projects.save_project(self.data, {**result['project'], 'include': ['docs/*.md']})['project']
        result = projects.refresh_project(self.data, project)
        self.assertEqual(result['project']['last_refresh']['source_count'], 12)
        self.assertTrue(result['project']['last_refresh']['warnings'])
        empty = self.root / 'empty'
        empty.mkdir()
        subprocess.run(['git', 'init', str(empty)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        project = self.register(name='Empty', path=str(empty))
        with self.assertRaisesRegex(core.MnemosError, 'needs a locally available commit'):
            projects.refresh_project(self.data, project)

    def test_invalid_paths_patterns_and_duplicates(self):
        self.register()
        for values in ({}, {'name': 'Different'}, {'path': str(self.repo / 'src')}, {'path': 'relative'},
                       {'include': ['../private']}, {'include': ['/absolute']}, {'include': []}):
            with self.assertRaises(core.MnemosError):
                self.register(**values)
        if os.name != 'nt':
            link = self.root / 'link'
            link.symlink_to(self.repo)
            with self.assertRaisesRegex(core.MnemosError, 'symbolic'):
                self.register(name='Linked', path=str(link))

    def test_missing_repo_and_head_change_leave_prior_capture_intact(self):
        project = self.register()
        prior = core.load_config(self.data)
        head = self.git('rev-parse', 'HEAD')
        with patch.object(projects, '_head', side_effect=[head, 'a' * 40]):
            with self.assertRaises(core.MnemosError) as error:
                projects.refresh_project(self.data, project)
        self.assertEqual(error.exception.status, 409)
        self.assertEqual(core.load_config(self.data), prior)
        self.repo.rename(self.root / 'moved')
        with self.assertRaisesRegex(core.MnemosError, 'unavailable'):
            projects.refresh_project(self.data, project)
        self.assertEqual(core.load_config(self.data), prior)

    def test_git_never_executes_repository_fsmonitor(self):
        marker = self.root / 'executed'
        hook = self.root / 'monitor.sh'
        hook.write_text('#!/bin/sh\ntouch "' + str(marker) + '"\n')
        hook.chmod(0o755)
        self.git('config', 'core.fsmonitor', str(hook))
        result = projects.refresh_project(self.data, self.register())
        self.assertTrue(result['document'])
        self.assertFalse(marker.exists())

    def test_read_only_commands_suppress_network_and_external_environment(self):
        original = subprocess.run
        calls = []
        def recorded(command, **kwargs):
            calls.append((command, kwargs['env']))
            return original(command, **kwargs)
        with patch.dict(os.environ, {'GIT_DIR': '/not-the-repo', 'GIT_CONFIG_COUNT': '1'}), patch.object(projects.subprocess, 'run', side_effect=recorded):
            projects.refresh_project(self.data, self.register())
        self.assertTrue(calls)
        for command, env in calls:
            self.assertIn('protocol.allow=never', command)
            self.assertEqual(env['GIT_NO_LAZY_FETCH'], '1')
            self.assertEqual(env['GIT_TERMINAL_PROMPT'], '0')
            self.assertEqual(env['GIT_ALLOW_PROTOCOL'], '')
            self.assertEqual(env['GIT_NO_REPLACE_OBJECTS'], '1')
            self.assertNotIn('GIT_DIR', env)
            self.assertNotIn('GIT_CONFIG_COUNT', env)
            self.assertFalse(set(command) & {'fetch', 'pull', 'push', 'checkout', 'status', 'diff'})

    def test_replace_refs_cannot_falsify_captured_blob_provenance(self):
        original = self.git('rev-parse', 'HEAD:README.md')
        self.write('replacement.md', 'Replacement object is not the recorded source')
        replacement = self.git('hash-object', '-w', 'replacement.md')
        self.git('replace', original, replacement)
        result = projects.refresh_project(self.data, self.register())
        self.assertIn('documented build', result['document']['body'])
        self.assertNotIn('Replacement object', result['document']['body'])

    def test_worktree_checkout_is_supported(self):
        worktree = self.root / 'second checkout'
        self.git('worktree', 'add', '--detach', str(worktree), 'HEAD')
        result = projects.refresh_project(self.data, self.register(path=str(worktree)))
        self.assertIn('documented build', result['document']['body'])
        self.assertEqual(result['project']['last_refresh']['branch'], '(detached HEAD)')


if __name__ == '__main__':
    unittest.main()
