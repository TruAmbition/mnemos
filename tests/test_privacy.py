"""Negative security tests use private fixtures; no permissive defaults or mocks."""
import http.client
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
from unittest.mock import patch
from mnemos import core, privacy, knowledge_projects as kp, skill_builder, backup, export
from mnemos.handoff import build_pack
from scripts import mcp_server


class PrivacyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.data = Path(self.temp.name) / 'data'; core.initialize(self.data)
        shutil.rmtree(core.vault_path(self.data)); core.vault_path(self.data).mkdir()

    def project(self, name, mode='local', repos=None):
        return kp.save(self.data, {'name': name, 'privacy': mode, 'repository_ids': repos or []})['knowledge_project']

    def note(self, name='Private procedure', project=None, **changes):
        return core.save_document(self.data, {'title': name, 'type': 'runbook', 'body': 'Inspect the service. Verify recovery.',
            'project_id': project['id'] if project else '', **changes})

    def policy(self, doc, mode):
        current = core.get_document(self.data, doc['id'])
        return privacy.update(self.data, {'id': doc['id'], 'fingerprint': current['privacy']['fingerprint'], 'operation': 'policy', 'mode': mode})

    def approve(self, doc):
        current = core.get_document(self.data, doc['id'])
        return privacy.update(self.data, {'id': doc['id'], 'fingerprint': current['privacy']['fingerprint'], 'operation': 'approve', 'reviewed': True})

    def tool(self, name, **args):
        return mcp_server.call_tool(self.data, name, args)

    def test_defaults_fail_closed_for_ai_team_handoff_and_export(self):
        group = self.project('Private system'); doc = self.note(project=group, status='verified')
        self.assertEqual(core.get_document(self.data, doc['id'])['privacy']['mode'], 'local')
        self.assertEqual(core.list_documents(self.data, 'reader'), [])
        self.assertEqual(self.tool('search_documents', query='Private'), [])
        self.assertFalse(self.tool('recall_context', query='service')['items'])
        for action in [lambda: self.tool('read_document', id=doc['id']), lambda: build_pack(self.data, 'service'), lambda: export.vault_archive(self.data), lambda: self.approve(doc)]:
            with self.assertRaises(ValueError): action()
        self.assertTrue(core.get_document(self.data, doc['id']))
        self.assertTrue(Path(backup.create_backup(self.data)['path']).exists())

    def test_ai_review_is_required_and_cannot_grant_team_access(self):
        doc = self.note(project=self.project('Review', 'reviewed-ai'), status='verified')
        self.assertEqual(self.tool('search_documents', query='Private'), [])
        current = core.get_document(self.data, doc['id'])
        with self.assertRaises(core.MnemosError):
            privacy.update(self.data, {'id': doc['id'], 'operation': 'approve', 'fingerprint': current['privacy']['fingerprint']})
        self.approve(doc)
        self.assertTrue(self.tool('read_document', id=doc['id']))
        self.assertTrue(build_pack(self.data, 'service')['documents'])
        self.assertEqual(core.list_documents(self.data, 'reader'), [])
        self.assertTrue(core.list_documents(self.data)[0]['privacy']['ai_approved'])

    def test_team_requires_verified_for_readers_and_separate_ai_approval(self):
        project = self.project('Team', 'team'); draft = self.note(project=project)
        verified = self.note('Verified procedure', project, status='verified')
        self.assertEqual([d['id'] for d in core.list_documents(self.data, 'reader')], [verified['id']])
        self.assertEqual(self.tool('search_documents', query='procedure'), [])
        self.approve(verified)
        self.assertEqual([d['id'] for d in self.tool('search_documents', query='procedure')], [verified['id']])
        with privacy.audience('team'):
            self.assertEqual(len(core.list_documents(self.data, 'author')), 2)

    def test_changed_source_policy_and_revocation_invalidate_approvals(self):
        project = self.project('Review', 'reviewed-ai'); source = self.note(project=project)
        derived = self.note('Derived flow', sources=[f"mnemos:{source['id']}@{source['revision']}"])
        self.approve(derived); self.assertTrue(self.tool('search_documents', query='Derived'))
        core.save_document(self.data, {**source, 'body': 'Changed source'})
        self.assertFalse(self.tool('search_documents', query='Derived'))
        self.approve(derived)
        kp.save(self.data, {**project, 'privacy': 'team'})
        self.assertFalse(self.tool('search_documents', query='Derived'))
        self.approve(derived)
        current = core.get_document(self.data, derived['id'])
        privacy.update(self.data, {'id': derived['id'], 'operation': 'revoke', 'fingerprint': current['privacy']['fingerprint']})
        self.assertFalse(self.tool('search_documents', query='Derived'))

    def test_mixed_sources_missing_sources_cycles_and_shared_repos(self):
        secret = self.note(); team = self.note('Team procedure', self.project('Team', 'team'))
        derived = self.note('Combined', sources=[f"mnemos:{secret['id']}@x", f"mnemos:{team['id']}@x"])
        self.assertEqual(core.get_document(self.data, derived['id'])['privacy']['mode'], 'local')
        missing = self.note('Missing', sources=['mnemos:missing@x'])
        self.assertEqual(core.get_document(self.data, missing['id'])['privacy']['mode'], 'local')
        a = self.note('Cycle A', related_ids=['cycle-b'], id='cycle-a')
        self.note('Cycle B', related_ids=['cycle-a'], id='cycle-b')
        self.assertEqual(core.get_document(self.data, a['id'])['privacy']['mode'], 'local')
        config = core.load_config(self.data); config['projects'] = [{'id': 'project-shared', 'name': 'Shared'}]; core.save_config(self.data, config)
        private_group = self.project('Private', 'local', ['project-shared']); self.project('Team shared', 'team', ['project-shared'])
        shared = self.note('Shared repo snapshot', repository_ids=['project-shared'])
        self.assertEqual(core.get_document(self.data, shared['id'])['privacy']['mode'], 'local')
        kp.remove(self.data, private_group)
        self.assertEqual(core.get_document(self.data, shared['id'])['privacy']['mode'], 'local')

    def test_removing_source_links_or_project_membership_cannot_declassify(self):
        private = self.project('Private'); doc = self.note(project=private)
        changed = core.save_document(self.data, {**doc, 'project_id': '', 'repository_ids': []})
        self.policy(changed, 'team')
        self.assertEqual(core.get_document(self.data, changed['id'])['privacy']['mode'], 'local')
        derived = self.note('Derived', related_ids=[doc['id']])
        changed = core.save_document(self.data, {**derived, 'related_ids': []})
        self.policy(changed, 'team')
        self.assertEqual(core.get_document(self.data, changed['id'])['privacy']['mode'], 'local')

    def test_secret_scans_metadata_json_and_saved_build_export(self):
        for value in ['AWS_SECRET_ACCESS_KEY = "abcdefgh123456789"', {'password': 'abcdefgh123456789'}, {'body': '\napi_key: abcdefgh123456789'}, 'Bearer ' + 'a'*30]:
            with self.assertRaises(core.MnemosError): privacy.scan(value)
        private = self.note(summary='api_key: abcdefgh123456789'); self.policy(private, 'reviewed-ai')
        with self.assertRaises(core.MnemosError): self.approve(private)
        doc = self.note('Safe procedure'); self.policy(doc, 'reviewed-ai'); self.approve(doc)
        candidate = next(c for c in skill_builder.candidates(self.data)['candidates'] if c['id'] == 'document:' + doc['id'])
        payload = {'candidate_id': candidate['id'], 'revision': candidate['revision'], 'target': 'claude'}
        built = skill_builder.prepare(self.data, payload)
        saved = skill_builder.save(self.data, {**payload, 'preview_revision': built['preview_revision']})
        self.assertTrue(skill_builder.read(self.data, saved['id']))
        self.policy(doc, 'local')
        with self.assertRaises(core.MnemosError): skill_builder.read(self.data, saved['id'])
        self.assertTrue(skill_builder.read(self.data, saved['id'], for_export=False))

    def test_cloud_backup_refuses_private_before_upload_and_local_still_works(self):
        self.note()
        core.update_settings(self.data, {'backup': {'provider': 'rclone', 'remote': 'test:private', 'destination': str(self.data / 'backups')}})
        with patch('mnemos.backup.subprocess.run') as upload:
            with self.assertRaises(core.MnemosError): backup.create_backup(self.data)
            upload.assert_not_called()
        core.update_settings(self.data, {'backup': {'provider': 'local', 'destination': str(self.data / 'backups'), 'remote': ''}})
        self.assertTrue(backup.create_backup(self.data)['files'])

    def test_cli_ai_scope_and_new_repository_snapshot_invalidate_approval(self):
        from contextlib import redirect_stdout
        import io
        from mnemos.__main__ import main
        config = core.load_config(self.data)
        config['projects'] = [{'id':'project-service', 'name':'Service', 'last_refresh':{'commit':'first','document_id':'snapshot-first'}}]
        core.save_config(self.data, config)
        project = self.project('Service', 'reviewed-ai', ['project-service'])
        doc = self.note(project=project)
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(['search','--data',str(self.data),'--audience','ai','Private']),0)
        self.assertEqual(json.loads(output.getvalue())['documents'],[])
        self.approve(doc)
        self.assertTrue(self.tool('search_documents',query='Private'))
        config['projects'][0]['last_refresh'] = {'commit':'second','document_id':'snapshot-second'}
        core.save_config(self.data,config)
        self.assertFalse(self.tool('search_documents',query='Private'))
        self.assertEqual(privacy.AUDIENCE.get(),'local')

    def test_mixed_workflow_is_hidden_and_old_approval_cannot_be_replayed(self):
        private = self.note()
        team = self.note('Team', self.project('Team','team'), status='verified')
        core.atomic_write(core.safe_path(core.vault_path(self.data),'Workflows/mixed.json'), json.dumps({
            'id':'mixed','title':'Sensitive mixed workflow','status':'verified','steps':[
                {'id':'one','document_id':team['id'],'depends_on':[]},
                {'id':'two','document_id':private['id'],'depends_on':['one']}]}))
        self.approve(team)
        with self.assertRaises(core.MnemosError): self.tool('plan_workflow',id='mixed')
        self.assertEqual(core.list_workflows(self.data,'reader'),[])
        previous = core.get_document(self.data,team['id'])
        core.save_document(self.data,{**team,'body':'Changed private details'})
        with self.assertRaises(core.MnemosError):
            privacy.update(self.data,{'id':team['id'],'fingerprint':previous['privacy']['fingerprint'],'operation':'approve','reviewed':True})

    def test_unknown_attachments_block_full_export_but_not_local_backup(self):
        self.note(project=self.project('Team','team'), status='verified')
        (core.vault_path(self.data)/'unclassified.txt').write_text('Confidential attachment with no credential pattern')
        with self.assertRaisesRegex(core.MnemosError,'classification'): export.vault_archive(self.data)
        self.assertTrue(backup.create_backup(self.data)['files'])

    def test_capture_receipt_does_not_expose_private_links_and_cannot_overwrite(self):
        private = self.note()
        receipt = self.tool('capture_document', document={'title': 'New work', 'body': 'Captured', 'related_ids': [private['id']]})
        self.assertEqual(set(receipt), {'id', 'status', 'saved', 'notice'})
        with self.assertRaises(core.MnemosError): self.tool('capture_document', document={**private, 'body': 'Overwrite'})
        self.assertFalse(self.tool('search_documents', query='New work'))

    def test_reader_export_omits_private_and_ai_only_content(self):
        self.note('Private marker', status='verified')
        self.note('AI marker', self.project('AI', 'reviewed-ai'), status='verified')
        team = self.note('Team marker', self.project('Team', 'team'), status='verified')
        out = self.data.parent / 'reader'; export.build_reader(self.data, out)
        payload = json.loads((out/'data.json').read_text())
        self.assertEqual([d['id'] for d in payload['documents']], [team['id']])
        self.assertNotIn('Private marker', json.dumps(payload))


class LocalAuthenticationTests(unittest.TestCase):
    def setUp(self):
        from mnemos.server import MnemosServer
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.data = Path(self.temp.name) / 'data'; core.initialize(self.data)
        self.server = MnemosServer(('127.0.0.1', 0), self.data)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(2)

    def request(self, path, method='GET', payload=None, headers=None):
        c = http.client.HTTPConnection('127.0.0.1', self.server.server_port); self.addCleanup(c.close)
        h = dict(headers or {})
        if payload is not None: h['Content-Type'] = 'application/json'
        c.request(method, path, json.dumps(payload) if payload is not None else None, h)
        response = c.getresponse(); body = response.read()
        return response.status, response.getheaders(), json.loads(body)

    def test_anonymous_loopback_cannot_read_manage_or_stop(self):
        status, _, content = self.request('/api/bootstrap')
        self.assertEqual(status, 200); self.assertEqual(content['documents'], [])
        self.assertEqual(content['session']['role'], 'anonymous')
        for path in ['/api/projects', '/api/privacy', '/api/setup', '/api/runtime', '/api/export']:
            self.assertIn(self.request(path)[0], {401,403})
        for path in ['/api/documents', '/api/runtime/stop', '/api/privacy']:
            self.assertIn(self.request(path, 'POST', {}, {'X-Mnemos-Workspace':self.server.workspace_id})[0], {401,403})

    def test_launch_key_exchange_origin_permissions_and_no_fallback(self):
        from mnemos.local_access import key_path
        p = key_path(self.data, self.server.server_port)
        if os.name != 'nt': self.assertEqual(p.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.request('/api/local-login', 'POST', {'key':'wrong'})[0], 401)
        self.assertEqual(self.request('/api/local-login', 'POST', {'key':self.server.local_key}, {'Origin':'https://evil.invalid'})[0],403)
        status, headers, _ = self.request('/api/local-login', 'POST', {'key':self.server.local_key})
        self.assertEqual(status,200)
        cookie = next(v for k,v in headers if k == 'Set-Cookie' and v.startswith(self.server.local_cookie+'='))
        self.assertIn('HttpOnly',cookie); self.assertIn('SameSite=Strict',cookie)
        h = {'Cookie':cookie.split(';')[0]}
        self.assertEqual(self.request('/api/privacy', headers=h)[0],200)
        self.assertEqual(self.request('/api/privacy', headers={**h, 'Authorization':'Bearer invalid'})[0],403)
        # A shared owner token still cannot change policies or access local configuration.
        owner = core.issue_token(self.data,'owner','Shared owner','team')
        self.assertEqual(self.request('/api/privacy',headers={'Authorization':'Bearer '+owner})[0],403)
        self.assertEqual(self.request('/api/bootstrap',headers={'Authorization':'Bearer '+owner})[2]['settings'],{})

    def test_team_token_cannot_bypass_ai_approval_handoff(self):
        from privacy_fixture import allow_fixture
        doc = core.save_document(self.data, {'title':'Team note','body':'safe','status':'verified'})
        allow_fixture(self.data, approve=False)
        token = core.issue_token(self.data,'reader','Reader','team')
        self.assertTrue(self.request('/api/documents',headers={'Authorization':'Bearer '+token})[2]['documents'])
        status,_,_ = self.request('/api/handoff?query=Team',headers={'Authorization':'Bearer '+token})
        self.assertEqual(status,403)


if __name__ == '__main__': unittest.main()
