from privacy_fixture import allow_fixture
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from mnemos import core, privacy, note_history as history, library_answers as answers, documentation_health as health, workspace_backup as backup, skill_builder


class LibraryFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve(); self.data = self.root/'data'
        core.initialize(self.data, 'Engineer')
        shutil.rmtree(self.data/'vault'); (self.data/'vault').mkdir()
        self.one = core.save_document(self.data, {'id':'deploy', 'title':'Deployment recovery', 'type':'runbook',
            'body':'1. Restore the previous release after a failed deployment.\n2. Check the health endpoint before accepting traffic.', 'status':'verified'})
        self.two = core.save_document(self.data, {'id':'checks', 'title':'Deployment health checks', 'type':'troubleshooting',
            'body':'Wait until the health endpoint returns a successful response.\n\n## Open questions\n\n- Who owns the recovery check?'})


class HistoryTests(LibraryFixture):
    def test_edits_restore_draft_and_current_is_preserved(self):
        updated = core.save_document(self.data, {**self.one, 'body':'Updated deployment procedure — résumé 日本語.'})
        versions = history.overview(self.data, 'deploy')['versions']
        self.assertEqual({v['revision'] for v in versions}, {self.one['revision'],updated['revision']})
        payload = {'id':'deploy', 'revision':self.one['revision']}
        checked = history.preview(self.data,payload)
        self.assertIn('-Updated deployment',checked['diff'])
        with self.assertRaises(core.MnemosError): history.restore(self.data,{**payload,'review_revision':'stale'})
        restored = history.restore(self.data,{**payload,'review_revision':checked['review_revision']})['document']
        self.assertEqual(restored['body'],self.one['body']); self.assertEqual(restored['status'],'draft')
        self.assertFalse(core.get_document(self.data,'deploy')['privacy']['ai_approved'])
        self.assertIn(updated['revision'],{v['revision'] for v in history.overview(self.data,'deploy')['versions']})
    def test_external_edits_deletion_custom_properties_and_stale_restore(self):
        path = self.data/'vault'/self.one['path']
        raw = path.read_text('utf-8').replace('---\n\n','owner_team: "SRE"\n---\n\n',1) + '\nExternal edit — 日本語.\n'
        path.write_text(raw,encoding='utf-8')
        external = core.get_document(self.data,'deploy')
        self.assertIn(external['revision'],{v['revision'] for v in history.overview(self.data,'deploy')['versions']})
        payload = {'id':'deploy','revision':external['revision']}; checked=history.preview(self.data,payload)
        path.unlink()
        with self.assertRaises(core.MnemosError): history.restore(self.data,{**payload,'review_revision':checked['review_revision']})
        checked=history.preview(self.data,payload)
        restored=history.restore(self.data,{**payload,'review_revision':checked['review_revision']})['document']
        self.assertIn('External edit — 日本語.',restored['body'])
        self.assertEqual(core.parse_markdown((self.data/'vault'/restored['path']).read_text('utf-8'))[0]['owner_team'],'SRE')
    def test_history_corruption_traversal_and_symlinks_fail(self):
        with self.assertRaises(core.MnemosError):history.preview(self.data,{'id':'../config','revision':'a'*64})
        p=history._path(self.data,'deploy',self.one['revision']);record=json.loads(p.read_text('utf-8'));record['markdown']='tampered';p.write_text(json.dumps(record),encoding='utf-8')
        with self.assertRaises(core.MnemosError):history.preview(self.data,{'id':'deploy','revision':self.one['revision']})
        p.unlink();p.symlink_to(self.data/'config.json')
        with self.assertRaises(core.MnemosError):core.get_document(self.data,'deploy')
    def test_complete_backup_includes_private_history_but_vault_export_does_not(self):
        from mnemos.backup import snapshot_bytes
        import io, zipfile
        with zipfile.ZipFile(io.BytesIO(snapshot_bytes(core.vault_path(self.data))[0])) as archive:
            self.assertFalse(any(n.startswith('note-history/') for n in archive.namelist()))
        core.save_document(self.data,{**self.one,'body':'Replacement body'})
        record=backup.create(self.data,{'destination':str(self.root/'backups')})
        checked=backup.preview(self.data,{'archive':record['path'],'destination':str(self.root/'restored')})
        result=backup.restore(self.data,{'archive':record['path'],'destination':str(self.root/'restored'),'review_revision':checked['review_revision']})
        self.assertIn(self.one['revision'],{v['revision'] for v in history.overview(result['path'],'deploy')['versions']})


class AnswerTests(LibraryFixture):
    def collect(self):return answers.create(self.data,{'question':'How does deployment recovery work?', 'source_ids':['deploy','checks']})
    def reply(self,record):
        return {'format':answers.FORMAT,'request_id':record['id'],'claims':[
            {'text':'Restore the previous release, then validate health.','kind':'inference','citations':[
                {'source_id':'deploy','quote':'Restore the previous release after a failed deployment.'},
                {'source_id':'checks','quote':'Wait until the health endpoint returns a successful response.'}]}],
            'unknowns':['The deployment platform and recovery owner are not established.']}
    def test_handoff_privacy_and_imported_citations_save_linked_draft(self):
        r=self.collect()
        with self.assertRaises(core.MnemosError):answers.handoff(self.data,{'id':r['id']})
        allow_fixture(self.data);r=self.collect()
        pack=answers.handoff(self.data,{'id':r['id']})
        self.assertIn('untrusted data',pack['prompt']);self.assertIn(r['id'],pack['prompt'])
        result=answers.accept(self.data,{'id':r['id'],'answer':self.reply(r)})
        self.assertEqual(result['answer']['claims'][0]['kind'],'inference')
        with self.assertRaises(core.MnemosError):answers.save_note(self.data,{'id':r['id'],'answer_revision':'wrong'})
        payload={'id':r['id'],'answer_revision':result['answer_revision']}
        saved=answers.save_note(self.data,payload)['document']
        self.assertEqual(saved['status'],'draft');self.assertEqual(set(saved['related_ids']),{'deploy','checks'})
        self.assertIn('mnemos:deploy@'+self.one['revision'],saved['sources'])
        self.assertTrue(answers.save_note(self.data,payload)['already_saved'])
        answers.remove(self.data,{'id':r['id']});self.assertEqual(core.get_document(self.data,saved['id'])['body'],saved['body'])
    def test_invented_quote_source_missing_citations_and_wrong_request_rejected(self):
        r=self.collect()
        mutations=[lambda a:a.update(request_id='answer-'+'a'*16),lambda a:a['claims'][0].update(citations=[]),
            lambda a:a['claims'][0]['citations'][0].update(source_id='unknown'),
            lambda a:a['claims'][0]['citations'][0].update(quote='An invented quote that is not in any document.'),
            lambda a:a['claims'][0].update(kind='verified')]
        for mutate in mutations:
            answer=self.reply(r);mutate(answer)
            with self.assertRaises(core.MnemosError):answers.accept(self.data,{'id':r['id'],'answer':answer})
    def test_source_changes_invalidate_answer_import_save_and_handoff(self):
        r=self.collect();result=answers.accept(self.data,{'id':r['id'],'answer':self.reply(r)})
        core.save_document(self.data,{**self.one,'body':'Changed procedure'})
        self.assertEqual(answers.read(self.data,r['id'])['changed_sources'],['deploy'])
        for operation,payload in [(answers.accept,{'answer':self.reply(r)}),(answers.save_note,{'answer_revision':result['answer_revision']}),(answers.handoff,{})]:
            with self.assertRaises(core.MnemosError) as e:operation(self.data,{'id':r['id'],**payload})
            self.assertEqual(e.exception.status,409)
    def test_no_evidence_and_insufficient_answer_are_explicit(self):
        empty=answers.create(self.data,{'question':'unrelated quasar dynamics'})
        self.assertEqual(empty['sources'],[])
        with self.assertRaises(core.MnemosError):answers.handoff(self.data,{'id':empty['id']})
        r=self.collect();reply={'format':answers.FORMAT,'request_id':r['id'],'claims':[],'unknowns':['No platform configuration is provided.']}
        self.assertEqual(answers.accept(self.data,{'id':r['id'],'answer':reply})['answer']['claims'],[])
    def test_local_generation_needs_no_cloud_approval_and_validates_response(self):
        r=self.collect();calls=[]
        def http(method,path,payload=None):
            calls.append((method,path,payload))
            if path=='/api/tags':return {'models':[{'name':'local-model:latest','digest':'local'},{'name':'cloud-model','digest':'remote','remote_host':'example.com'}]}
            if path=='/api/show':return {'capabilities':['completion']}
            return {'done':True,'message':{'content':json.dumps(self.reply(r))}}
        with patch.object(answers,'_http',side_effect=http):
            with self.assertRaises(core.MnemosError):answers.generate(self.data,{'id':r['id'],'model':'cloud-model'})
            result=answers.generate(self.data,{'id':r['id'],'model':'local-model:latest'})
        self.assertIn('Local Ollama',result['provider']);self.assertTrue(result['answer']['claims'])
        chat=next(c[2] for c in calls if c[1]=='/api/chat');self.assertNotIn('tools',chat);self.assertFalse(chat['stream'])
    def test_local_transport_rejects_redirects_and_generation_race(self):
        with patch('mnemos.library_answers.http.client.HTTPConnection') as conn:
            conn.return_value.getresponse.return_value.status=302;conn.return_value.getresponse.return_value.read.return_value=b'{}'
            with self.assertRaises(core.MnemosError):answers._http('GET','/api/tags')
            self.assertEqual(conn.call_args.args,('127.0.0.1',11434))
        r=self.collect()
        def http(method,path,payload=None):
            if path=='/api/tags':return {'models':[{'name':'local','digest':'local'}]}
            if path=='/api/show':return {'capabilities':['completion']}
            core.save_document(self.data,{**self.one,'body':'Changed during generation'})
            return {'done':True,'message':{'content':json.dumps(self.reply(r))}}
        with patch.object(answers,'_http',side_effect=http):
            with self.assertRaises(core.MnemosError) as e:answers.generate(self.data,{'id':r['id'],'model':'local'})
            self.assertEqual(e.exception.status,409)


class HealthTests(LibraryFixture):
    def test_changed_evidence_unverified_open_questions_and_due_verification(self):
        core.save_document(self.data,{'id':'explanation','title':'Recovery explanation','body':'Explanation', 'sources':['mnemos:deploy@'+self.one['revision']]})
        core.save_document(self.data,{**self.one,'body':'New procedure'})
        path=self.data/'vault'/self.one['path'];raw=path.read_text('utf-8');meta,body=core.parse_markdown(raw)
        meta['verified']=(datetime.now(timezone.utc)-timedelta(days=95)).isoformat()
        path.write_text('---\n'+'\n'.join(k+': '+json.dumps(v) for k,v in meta.items())+'\n---\n\n'+body,encoding='utf-8')
        result=health.overview(self.data);categories={i['category'] for i in result['items']}
        self.assertEqual(categories,{'changed-evidence','unverified','open-questions','review-due'})
        health.configure(self.data,{'review_days':180});self.assertNotIn('review-due',{i['category'] for i in health.overview(self.data)['items']})
        with self.assertRaises(core.MnemosError):health.configure(self.data,{'review_days':0})
    def test_snooze_reappears_on_change_and_resolved_findings_disappear(self):
        item=next(i for i in health.overview(self.data)['items'] if i['id']=='checks:unverified')
        payload={'id':item['id'],'fingerprint':item['fingerprint'],'days':7};health.snooze(self.data,payload)
        self.assertTrue(next(i for i in health.overview(self.data)['items'] if i['id']==item['id'])['snoozed'])
        core.save_document(self.data,{**self.two,'body':'New procedure'})
        self.assertFalse(next(i for i in health.overview(self.data)['items'] if i['id']==item['id'])['snoozed'])
        with self.assertRaises(core.MnemosError):health.snooze(self.data,payload)
        current=core.get_document(self.data,'checks');core.save_document(self.data,{**current,'status':'verified'})
        self.assertNotIn(item['id'],{i['id'] for i in health.overview(self.data)['items']})
    def test_examples_archived_notes_empty_sections_and_code_todos_excluded(self):
        core.save_document(self.data,{**self.two,'example':True})
        core.save_document(self.data,{'id':'old','title':'Old','status':'archived','type':'runbook','body':'TODO later'})
        result=health.overview(self.data);self.assertEqual(result['items'],[])
        self.assertEqual(health._questions('## Open questions\n\nNone.\n\n```\nTODO code example\n```\n<!-- mnemos:related:start -->'),[])
    def test_saved_skill_tracks_changed_sources(self):
        allow_fixture(self.data)
        candidate=next(c for c in skill_builder.candidates(self.data)['candidates'] if c['id']=='document:deploy')
        payload={'candidate_id':candidate['id'],'revision':candidate['revision'],'target':'claude','name':'recover-deployment','description':'Use for deployment recovery.'}
        prepared=skill_builder.prepare(self.data,payload)
        skill_builder.save(self.data,{**payload,'preview_revision':prepared['preview_revision']})
        self.assertFalse(any(i['category']=='skill-review' for i in health.overview(self.data)['items']))
        core.save_document(self.data,{**self.one,'body':'Changed recovery procedure'})
        self.assertTrue(any(i['category']=='skill-review' for i in health.overview(self.data)['items']))
