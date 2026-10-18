from privacy_fixture import allow_fixture
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from mnemos import core, projects, knowledge_projects as kp, recall, skill_builder, skill_analysis
from mnemos.backup import snapshot_bytes


class KnowledgeProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.data = self.root / 'data'
        core.initialize(self.data, 'Engineer')
        self.repo = self.root / 'orders'
        self.repo.mkdir()
        self.git('init')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        (self.repo / 'README.md').write_text('Orders accepts checkout requests and publishes order.created.\n')
        (self.repo / 'api.py').write_text('def checkout():\n    return "order.created"\n')
        self.commit()
        self.repository = projects.save_project(self.data, {'name': 'Orders service', 'path': str(self.repo),
            'responsibility': 'Owns order state', 'include': ['README.md', 'api.py']})['project']
        self.group = kp.save(self.data, {'name': 'Commerce platform', 'purpose': 'Accept and fulfill customer orders',
            'repository_ids': [self.repository['id']]})['knowledge_project']

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], stderr=subprocess.DEVNULL).decode().strip()

    def commit(self):
        self.git('add', '.'); self.git('commit', '-m', 'fixture')

    def capture(self):
        self.repository = projects.list_projects(self.data)['projects'][0]
        return projects.refresh_project(self.data, self.repository)['document']

    def test_membership_shared_repositories_legacy_notes_and_rename(self):
        before = core.load_config(self.data)['projects']
        legacy = core.save_document(self.data, {'title': 'Old repair', 'type': 'runbook', 'project': 'Orders service', 'body': 'Repair orders.'})
        other = kp.save(self.data, {'name': 'Admin console', 'repository_ids': [self.repository['id']]})['knowledge_project']
        doc = core.get_document(self.data, legacy['id'])
        self.assertEqual(set(doc['project_ids']), {self.group['id'], other['id']})
        self.assertEqual(doc['revision'], legacy['revision'])
        self.assertEqual(core.load_config(self.data)['projects'], before)
        unchanged = kp.save(self.data, self.group)['knowledge_project']
        self.assertEqual(unchanged['revision'], self.group['revision'])
        renamed = kp.save(self.data, {**self.group, 'name': 'Store platform'})['knowledge_project']
        self.assertEqual(renamed['id'], self.group['id'])
        self.assertTrue(core.list_documents(self.data, query='Store platform'))
        with self.assertRaises(core.MnemosError): kp.save(self.data, {**self.group, 'purpose': 'stale'})

    def test_scope_recall_and_skills_follow_membership(self):
        self.capture()
        doc = core.save_document(self.data, {'title': 'Repair checkout', 'type': 'runbook', 'project': 'Orders service', 'body': 'Repair the checkout queue.'})
        unrelated = kp.save(self.data, {'name': 'Unrelated system'})['knowledge_project']
        self.assertTrue(recall.recall(self.data, 'checkout', project_id=self.group['id'])['items'])
        self.assertFalse(recall.recall(self.data, 'checkout', project_id=unrelated['id'])['items'])
        suggestions = skill_builder.candidates(self.data, project_id=self.group['id'])['candidates']
        self.assertEqual([s['id'] for s in suggestions], ['document:' + doc['id']])
        self.assertFalse(skill_builder.candidates(self.data, project_id=unrelated['id'])['candidates'])
        with self.assertRaises(core.MnemosError):
            skill_analysis.request(self.data, {'goal': 'Repair', 'source_ids': [doc['id'], self.capture()['id']], 'project_id': unrelated['id']})

    def test_explicit_project_and_flow_repository_metadata_survive_edit(self):
        doc = core.save_document(self.data, {'title': 'Checkout flow', 'type': 'flow', 'project': 'Commerce platform',
            'project_id': self.group['id'], 'repository_ids': [self.repository['id']], 'body': '## Flow steps\n\n1. Request an order\n2. Publish an event'})
        updated = core.save_document(self.data, {'id': doc['id'], 'revision': doc['revision'], 'title': doc['title'], 'body': 'Edited explanation'})
        self.assertEqual(updated['project_id'], self.group['id'])
        self.assertEqual(updated['repository_ids'], [self.repository['id']])
        self.assertEqual(updated['type'], 'flow')
        self.assertTrue(updated['path'].startswith('Flows/'))

    def test_analysis_cites_code_and_excludes_local_paths_and_unselected_notes(self):
        snap = self.capture()
        other = core.save_document(self.data, {'title': 'Private unrelated', 'body': 'Unselected material'})
        allow_fixture(self.data)
        self.group = kp.overview(self.data)['knowledge_projects'][0]
        pack = kp.analysis(self.data, {**self.group, 'source_ids': [snap['id']]})
        self.assertIn('api.py', pack['prompt'])
        self.assertIn('order.created', pack['prompt'])
        self.assertIn(snap['revision'], pack['prompt'])
        self.assertNotIn(str(self.repo), pack['prompt'])
        self.assertNotIn(other['body'], pack['prompt'])
        with self.assertRaises(core.MnemosError): kp.analysis(self.data, {**self.group, 'source_ids': [other['id']]})
        bad = core.save_document(self.data, {'title': 'Secret', 'project_id': self.group['id'], 'body': 'api_key=not-to-export'})
        with self.assertRaises(core.MnemosError): kp.analysis(self.data, {**self.group, 'source_ids': [bad['id']]})

    def test_freshness_changes_when_new_snapshot_supersedes_old(self):
        snap = self.capture()
        explanation = core.save_document(self.data, {'title': 'System understanding', 'project_id': self.group['id'],
            'body': 'Orders publishes an event.', 'sources': [f'mnemos:{snap["id"]}@{snap["revision"]}', f'mnemos-project:{self.group["id"]}@{self.group["revision"]}']})
        self.assertFalse(kp.freshness(self.data, explanation)['changed'])
        (self.repo / 'README.md').write_text('Orders now publishes order.accepted.\n'); self.commit(); self.capture()
        self.assertIn(self.repository['id'], kp.freshness(self.data, explanation)['changed'])
        recalled = recall.recall(self.data, 'System understanding', project_id=self.group['id'])
        self.assertIn('SOURCE EVIDENCE CHANGED', recalled['context'])
        kp.save(self.data, {**self.group, 'purpose': 'Changed system purpose'})
        self.assertIn(self.group['id'], kp.freshness(self.data, explanation)['changed'])

    def test_map_and_backup_preserve_hierarchy_without_private_paths(self):
        snap = self.capture()
        result = kp.create_map(self.data, self.group)
        self.assertIn(snap['id'], result['document']['related_ids'])
        self.assertIn('[[Contexts/', result['document']['body'])
        canvas = json.loads((core.vault_path(self.data) / result['canvas_path']).read_text())
        self.assertTrue(any(e['label'] == 'contains' for e in canvas['edges'] if 'label' in e))
        self.assertTrue(any(n.get('file') == snap['path'] for n in canvas['nodes']))
        self.assertNotIn(str(self.repo), json.dumps(canvas))
        second = kp.create_map(self.data, self.group)
        self.assertNotEqual(result['canvas_path'], second['canvas_path'])
        import io, zipfile
        raw, _ = snapshot_bytes(core.vault_path(self.data))
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            self.assertIn('vault/Projects/projects.json', z.namelist())
            self.assertIn('vault/' + result['canvas_path'], z.namelist())
        kp.remove(self.data, self.group)
        self.assertTrue(core.get_document(self.data, snap['id']))
        self.assertTrue(projects.list_projects(self.data)['projects'])

    def test_relationship_validation_and_missing_registration_recovery(self):
        for relationship in ({'from': self.repository['id'], 'to': self.repository['id'], 'kind': 'calls'},
                             {'from': self.repository['id'], 'to': 'missing', 'kind': 'calls'}):
            with self.assertRaises(core.MnemosError): kp.save(self.data, {**self.group, 'relationships': [relationship]})
        projects.remove_project(self.data, self.repository)
        self.assertEqual(kp.overview(self.data)['knowledge_projects'][0]['missing_repository_ids'], [self.repository['id']])
        kp.save(self.data, {**self.group, 'purpose': 'Still useful after restore'})

    def test_reader_catalog_only_contains_projects_with_visible_notes(self):
        self.capture()
        self.assertEqual(kp.catalog(self.data, 'reader'), [])
        core.save_document(self.data, {'title': 'Verified explanation', 'body': 'Reviewed', 'status': 'verified', 'project_id': self.group['id']})
        allow_fixture(self.data)
        self.assertEqual(kp.catalog(self.data, 'reader'), [{'id': self.group['id'], 'name': self.group['name']}])


if __name__ == '__main__': unittest.main()
