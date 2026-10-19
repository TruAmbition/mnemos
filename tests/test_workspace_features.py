from privacy_fixture import allow_fixture
import copy
import hashlib
import io
import json
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from mnemos import core, privacy, semantic, session_inbox as inbox, workspace_backup as backup
from mnemos.recall import recall


class WorkspaceFixture(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.data=self.root/'data';core.initialize(self.data,'Engineer')
        shutil.rmtree(self.data/'vault');(self.data/'vault').mkdir()
        self.one=core.save_document(self.data,{'id':'rotate','title':'Credential rotation','body':'Replace the expired certificate and restart the service.','type':'runbook','status':'verified'})
        self.two=core.save_document(self.data,{'id':'database','title':'Database backups','body':'Copy the database snapshot to a separate disk.','type':'runbook'})


class WorkspaceRecoveryTests(WorkspaceFixture):
    def archive(self):return backup.create(self.data,{'destination':str(self.root/'backups')})
    def test_complete_content_without_credentials_and_inactive_restore(self):
        token=core.issue_token(self.data,'owner','AI')
        for folder in ('skill-builds','skill-analysis','skill-proposals','session-inbox'):
            core.atomic_write(self.data/folder/'example.json','{}')
        core.atomic_write(self.data/'privacy-approvals.json','{"secret":"approval"}')
        core.atomic_write(self.data/'connections/key.json',token)
        core.atomic_write(self.data/'vault/.obsidian/plugins/private.json',token)
        core.atomic_write(self.data/'search-index.json','{"secret":"vectors"}')
        conf=core.load_config(self.data);conf['git_backup']={'enabled':True,'auto_push':True};core.save_config(self.data,conf)
        record=self.archive();raw=Path(record['path']).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),record['sha256'])
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            names=z.namelist();self.assertNotIn(token.encode(),b''.join(z.read(n) for n in names))
            self.assertNotIn('privacy-approvals.json',names);self.assertNotIn('search-index.json',names)
        payload={'archive':record['path'],'destination':str(self.root/'restored')}
        preview=backup.preview(self.data,payload);result=backup.restore(self.data,{**payload,'review_revision':preview['review_revision']})
        self.assertFalse(result['active']);restored=Path(result['path'])
        cfg=core.load_config(restored);self.assertEqual(cfg['tokens'],[]);self.assertFalse(cfg['semantic_search']['enabled']);self.assertNotIn('git_backup',cfg)
        for folder in ('skill-builds','skill-analysis','skill-proposals','session-inbox'):self.assertTrue((restored/folder/'example.json').exists())
        self.assertEqual(core.get_document(restored,'rotate')['body'],self.one['body'])
        self.assertEqual(core.authenticate(self.data,token)['role'],'owner')
    def test_preview_binding_empty_destination_and_archive_corruption(self):
        record=self.archive();payload={'archive':record['path'],'destination':str(self.root/'restored')}
        checked=backup.preview(self.data,payload)
        with self.assertRaises(core.MnemosError):backup.restore(self.data,{**payload,'review_revision':'old'})
        with self.assertRaises(core.MnemosError):backup.restore(self.data,{**payload,'destination':str(self.root/'other'),'review_revision':checked['review_revision']})
        dest=self.root/'restored';dest.mkdir();(dest/'precious').write_text('keep')
        with self.assertRaises(core.MnemosError):backup.preview(self.data,payload)
        self.assertEqual((dest/'precious').read_text(),'keep')
        Path(record['path']).write_bytes(b'bad zip')
        with self.assertRaises(core.MnemosError):backup.preview(self.data,{**payload,'destination':str(self.root/'new')})
    def test_symlinks_and_unsafe_archive_members_rejected(self):
        outside=self.root/'outside';outside.write_text('private');(self.data/'vault/link').symlink_to(outside)
        with self.assertRaises(core.MnemosError):self.archive()
        (self.data/'vault/link').unlink();record=self.archive()
        with zipfile.ZipFile(record['path'],'a') as z:z.writestr('../escape','bad')
        with self.assertRaises(core.MnemosError):backup.preview(self.data,{'archive':record['path'],'destination':str(self.root/'new')})
        self.assertFalse((self.root/'escape').exists())
    def test_repository_remap_preserves_identity_and_disables_refresh(self):
        checkout=self.root/'project';checkout.mkdir()
        subprocess.run(['git','init',str(checkout)],check=True,capture_output=True)
        config=core.load_config(self.data)
        config['projects']=[{'id':'project-one','name':'One','path':str(self.root/'old'),
            'auto_refresh':True,'include':['README.md'],'exclude':[]}]
        core.save_config(self.data,config)
        record=self.archive()
        request={'archive':record['path'],'destination':str(self.root/'recovered'), 'repository_paths':{'project-one':str(checkout)}}
        checked=backup.preview(self.data,request)
        self.assertTrue(checked['repositories'][0]['available'])
        result=backup.restore(self.data,{**request,'review_revision':checked['review_revision']})
        restored=core.load_config(result['path'])['projects'][0]
        self.assertEqual(restored['id'],'project-one');self.assertEqual(restored['path'],str(checkout));self.assertFalse(restored['auto_refresh'])
        with self.assertRaises(core.MnemosError):backup.preview(self.data,{**request,'destination':str(self.root/'unused'),'repository_paths':{'project-one':str(self.root/'missing')}})
    def test_portable_paths_and_content_checksums(self):
        for name in ['vault/NUL.txt','vault/space.','vault/../escape','vault/.obsidian/key.json']:
            self.assertFalse(backup._allowed(name))
        record=self.archive();path=Path(record['path'])
        with zipfile.ZipFile(path) as source:members={n:source.read(n) for n in source.namelist()}
        members['vault/Runbooks/rotate.md']=b'Changed data'
        with zipfile.ZipFile(path,'w') as target:
            for name,raw in members.items():target.writestr(name,raw)
        with self.assertRaises(core.MnemosError):backup.preview(self.data,{'archive':str(path),'destination':str(self.root/'new')})


class SessionInboxTests(WorkspaceFixture):
    def collect(self,ids=None,text='Fixed expired credentials; validation is still pending.'):
        return inbox.create(self.data,{'title':'Daily work','start':'2026-10-18T00:00:00-07:00','end':'2026-10-18T18:00:00-07:00','source_ids':ids if ids is not None else ['rotate','database'],'context':text})
    def test_collection_handoff_privacy_and_local_only_starter(self):
        record=self.collect();self.assertEqual(len(core.list_documents(self.data)),2)
        with self.assertRaises(core.MnemosError):inbox.handoff(self.data,{'id':record['id'],'reviewed_context':True})
        # Approval after collection changes its fingerprint; recollect exact approved evidence.
        allow_fixture(self.data);record=self.collect()
        with self.assertRaises(core.MnemosError):inbox.handoff(self.data,{'id':record['id']})
        handoff=inbox.handoff(self.data,{'id':record['id'],'reviewed_context':True})
        self.assertIn('session-notes',handoff['prompt']);self.assertIn('complete replacement body',handoff['prompt'])
        self.assertEqual(len(core.list_documents(self.data)),2)
    def test_create_update_combine_review_idempotency_and_durable_resume(self):
        record=self.collect();proposal=copy.deepcopy(record['proposal'])
        proposal['items'][0].update(action='update',target_id='rotate',title='Credential rotation',body='Updated procedure, pending verification.')
        proposal['items'].append({**proposal['items'][0],'action':'combine','target_id':'','title':'Combined recovery','reason':'Recovery uses both procedures.'})
        checked=inbox.review(self.data,{'id':record['id'],'proposal':proposal})
        self.assertIn('-Replace',checked['items'][0]['diff']);self.assertEqual(len(core.list_documents(self.data)),2)
        payload={'id':record['id'],'index':0,'review_revision':checked['review_revision']}
        saved=inbox.accept(self.data,payload);self.assertEqual(saved['document']['id'],'rotate')
        self.assertTrue(inbox.accept(self.data,payload)['already_saved'])
        self.assertEqual(core.get_document(self.data,'rotate')['status'],'draft')
        combined=inbox.accept(self.data,{**payload,'index':1});self.assertEqual(len(core.list_documents(self.data)),3)
        self.assertEqual(set(core.get_document(self.data,combined['document']['id'])['related_ids']),{'rotate','database'})
        self.assertEqual(inbox.read(self.data,record['id'])['state'],'saved')
        inbox.review(self.data,{'id':record['id']})
        self.assertEqual(inbox.read(self.data,record['id'])['state'],'saved')
        inbox.remove(self.data,{'id':record['id']});self.assertEqual(len(core.list_documents(self.data)),3)
    def test_stale_sources_and_proposal_changes_rejected(self):
        record=self.collect();review=inbox.review(self.data,{'id':record['id']})
        with self.assertRaises(core.MnemosError):inbox.accept(self.data,{'id':record['id'],'index':0,'review_revision':'old'})
        core.save_document(self.data,{**self.one,'body':'Changed after collection'})
        with self.assertRaises(core.MnemosError) as error:inbox.accept(self.data,{'id':record['id'],'index':0,'review_revision':review['review_revision']})
        self.assertEqual(error.exception.status,409,str(error.exception));self.assertEqual(len(core.list_documents(self.data)),2)
    def test_unicode_evidence_survives_review_and_reopening(self):
        text='Résumé — 日本語 → ✅; preserve “decisions” and café.'
        record=self.collect(text=text)
        self.assertEqual(inbox.read(self.data,record['id'])['context'],text)
        checked=inbox.review(self.data,{'id':record['id']})
        reread=inbox.read(self.data,record['id'])
        self.assertEqual(reread['context'],text)
        self.assertIn(text,reread['proposal']['items'][0]['body'])
        saved=inbox.accept(self.data,{'id':record['id'],'index':0,'review_revision':checked['review_revision']})
        self.assertIn(text,core.get_document(self.data,saved['document']['id'])['body'])
    def test_invalid_citations_targets_secrets_and_shapes(self):
        record=self.collect()
        mutations=[lambda p:p['items'][0].update(source_ids=['invented']),lambda p:p['items'][0].update(action='update',target_id='missing'),lambda p:p['items'][0].update(body='api_key: test-credential-not-real'),lambda p:p.update(session_id='session-'+'a'*16),lambda p:p['items'][0].update(action='combine',source_ids=['session-notes'])]
        for mutate in mutations:
            proposal=copy.deepcopy(record['proposal']);mutate(proposal)
            with self.assertRaises(core.MnemosError):inbox.review(self.data,{'id':record['id'],'proposal':proposal})
        with self.assertRaises(core.MnemosError):inbox.read(self.data,'../config')
        self.assertEqual(len(core.list_documents(self.data)),2)
    def test_duplicate_titles_flagged_and_timezone_range_preserved(self):
        record=self.collect();proposal=record['proposal'];proposal['items'][0]['title']='Credential rotation'
        checked=inbox.review(self.data,{'id':record['id'],'proposal':proposal})
        self.assertEqual(checked['items'][0]['possible_matches'][0]['id'],'rotate')
        self.assertTrue(record['start'].endswith('-07:00'))


class SemanticTests(WorkspaceFixture):
    def setUp(self):
        super().setUp();self.calls=[];self.digest='local-model-one'
        self.mock=patch.object(semantic,'_http',side_effect=self.http);self.mock.start();self.addCleanup(self.mock.stop)
        semantic.configure(self.data,{'enabled':True,'model':'embeddinggemma'})
    def http(self,method,path,payload=None):
        self.calls.append((method,path,payload))
        if path=='/api/tags':return {'models':[{'name':'embeddinggemma:latest','digest':self.digest}]}
        vectors=[]
        for text in payload['input']:
            # Deliberately disjoint query/document words exercise vector retrieval.
            vectors.append([1.,0.] if any(w in text.lower() for w in ('certificate','identity renewal')) else [0.,1.])
        return {'embeddings':vectors}
    def test_real_cosine_ranking_recall_and_reused_index(self):
        result=semantic.search(self.data,'identity renewal');self.assertEqual(result['documents'][0]['id'],'rotate')
        self.assertEqual(result['documents'][0]['similarity'],1.)
        embeds=len([c for c in self.calls if c[1]=='/api/embed'])
        found=recall(self.data,'identity renewal',method='semantic');self.assertEqual(found['items'][0]['id'],'rotate');self.assertEqual(found['method'],'local-embeddings-and-keywords')
        self.assertEqual(len([c for c in self.calls if c[1]=='/api/embed']),embeds+1)
    def test_changed_notes_model_digest_and_archive_invalidate(self):
        semantic.rebuild(self.data);before=len(self.calls)
        core.save_document(self.data,{**self.one,'body':'Replace the certificate, then validate.'})
        semantic.search(self.data,'identity renewal');self.assertGreater(len(self.calls),before+2)
        self.digest='local-model-two';semantic.search(self.data,'identity renewal')
        self.assertEqual(semantic._cache(self.data)['digest'],'local-model-two')
        current=core.get_document(self.data,'rotate');core.save_document(self.data,{**current,'status':'archived'})
        self.assertFalse(any(d['id']=='rotate' for d in semantic.search(self.data,'identity renewal')['documents']))
    def test_off_remote_audience_bad_vectors_and_model_failure(self):
        with privacy.audience('ai'):
            with self.assertRaises(core.MnemosError):semantic.search(self.data,'identity renewal')
        with self.assertRaises(core.MnemosError):semantic.configure(self.data,{'enabled':True,'model':'cloud-model'})
        for value in [[],[float('nan')],[0,0],['x']]:
            with self.assertRaises(core.MnemosError):semantic._vector(value)
        semantic.rebuild(self.data);semantic.configure(self.data,{'enabled':False,'model':'embeddinggemma'})
        self.assertFalse((self.data/semantic.CACHE).exists())
        with self.assertRaises(core.MnemosError):semantic.search(self.data,'identity renewal')
    def test_transport_fixed_loopback_and_redirects_fail_closed(self):
        self.mock.stop()
        with patch('mnemos.semantic.http.client.HTTPConnection') as conn:
            conn.return_value.getresponse.return_value.status=302
            conn.return_value.getresponse.return_value.read.return_value=b'{}'
            with self.assertRaises(core.MnemosError):semantic._http('GET','/api/tags')
            self.assertEqual(conn.call_args.args,('127.0.0.1',11434))
