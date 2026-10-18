from privacy_fixture import allow_fixture
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from unittest.mock import patch
from mnemos import core, skill_builder as skills
from mnemos.__main__ import main


class SkillBuilderTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.data=Path(self.temp.name)/'data';core.initialize(self.data,'Engineer')
        self.doc=core.save_document(self.data,{'id':'cache-repair','title':'Repair a local cache','type':'runbook','project':'Nimbus','status':'verified',
            'body':'## Prerequisites\nA disposable local cache.\n\n## Steps\n1. Inspect its current state.\n2. Use the documented rebuild command for this environment.\n\n## Validation\nConfirm the expected cache entries.\n'})
        allow_fixture(self.data)
        self.candidate=next(c for c in skills.candidates(self.data)['candidates'] if c['id']=='document:cache-repair')
        self.payload={'candidate_id':self.candidate['id'],'revision':self.candidate['revision'],'target':'claude','name':'repair-local-cache','description':'Repair the Nimbus local cache when asked to recover its documented state.'}

    def saved(self):
        preview=skills.prepare(self.data,self.payload)
        return skills.save(self.data,{**self.payload,'preview_revision':preview['preview_revision']})

    def test_candidates_distinguish_examples_drafts_and_procedures(self):
        draft=core.save_document(self.data,{'id':'draft-repair','title':'Another procedure','type':'troubleshooting','body':'Investigate the symptom.'})
        core.save_document(self.data,{'id':'ordinary-context','title':'Context only','type':'context','body':'We discussed options.'})
        core.save_document(self.data,{'id':'archived-procedure','title':'Old steps','type':'runbook','status':'archived','body':'Old.'})
        result=skills.candidates(self.data)['candidates']
        self.assertEqual(result[0]['readiness'],'verified-sources')
        self.assertFalse(any(c['example'] for c in result))
        self.assertTrue(any(c['id']=='document:'+draft['id'] and c['readiness']=='review-needed' for c in result))
        self.assertFalse(any(c['id'] in {'document:ordinary-context','document:archived-procedure'} for c in result))
        self.assertEqual(len(skills.candidates(self.data,'Nimbus cache')['candidates']),1)
        self.assertTrue(any(c['example'] and c['readiness']=='example' for c in skills.candidates(self.data,include_examples=True)['candidates']))

    def test_preview_has_exact_sources_without_writes_or_scripts(self):
        before=len(core.list_documents(self.data))
        preview=skills.prepare(self.data,self.payload)
        self.assertFalse((self.data/'skill-builds').exists())
        self.assertEqual(len(core.list_documents(self.data)),before)
        self.assertIn(self.doc['body'],preview['files']['references/source-01.md'])
        self.assertIn(self.doc['revision'],preview['files']['references/sources.md'])
        self.assertNotIn(str(self.data),json.dumps(preview))
        self.assertFalse(any(k.startswith('scripts/') for k in preview['files']))
        self.assertNotIn('tokens',preview['files'])
        self.assertTrue(preview['files']['SKILL.md'].startswith('---\nname: repair-local-cache\n'))

    def test_preview_save_revision_and_stale_source_conflicts(self):
        with self.assertRaises(core.MnemosError):skills.save(self.data,self.payload)
        preview=skills.prepare(self.data,self.payload)
        with self.assertRaises(core.MnemosError):skills.save(self.data,{**self.payload,'name':'different-name','preview_revision':preview['preview_revision']})
        self.doc=core.save_document(self.data,{**self.doc,'body':self.doc['body']+'\nA new check.\n'})
        with self.assertRaises(core.MnemosError) as raised:skills.save(self.data,{**self.payload,'preview_revision':preview['preview_revision']})
        self.assertEqual(raised.exception.status,409)
        self.assertFalse((self.data/'skill-builds').exists())

    def test_build_is_immutable_and_freshness_tracks_changed_sources(self):
        built=self.saved();other=self.saved()
        self.assertNotEqual(built['id'],other['id'])
        self.assertTrue(all(b['freshness']=='current' for b in skills.list_builds(self.data)))
        self.doc=core.save_document(self.data,{**self.doc,'body':'A changed procedure.'})
        self.assertTrue(all(b['freshness']=='changed' for b in skills.list_builds(self.data)))
        self.assertEqual(skills.read(self.data,built['id'], for_export=False)['files'],built['files'])
        with self.assertRaises(core.MnemosError): skills.read(self.data,built['id'])
        core.save_document(self.data,{**self.doc,'status':'archived'})
        self.assertTrue(all(b['freshness']=='unavailable' for b in skills.list_builds(self.data)))

    def test_external_source_edit_during_resolution_is_rejected(self):
        with patch.object(core,'get_document',return_value={**self.doc,'revision':'changed-outside-server'}):
            with self.assertRaises(core.MnemosError) as raised:skills.prepare(self.data,self.payload)
        self.assertEqual(raised.exception.status,409)
        self.assertFalse((self.data/'skill-builds').exists())

    def test_archive_exact_files_and_path_validation(self):
        built=self.saved()
        with zipfile.ZipFile(io.BytesIO(skills.archive(built))) as archive:
            self.assertEqual(set(archive.namelist()),{built['name']+'/'+f for f in built['files']})
            for name in archive.namelist():self.assertFalse(name.startswith('/') or '..' in name.split('/'))
        for value in ['../outside','UPPER','two--dashes','a'*64]:
            with self.assertRaises(core.MnemosError):skills.prepare(self.data,{**self.payload,'name':value})
        with self.assertRaises(core.MnemosError):skills.read(self.data,'../config')
        with self.assertRaises(core.MnemosError):skills.archive({**built,'files':{'../outside':'bad'}})

    def test_target_guidance_and_sensitive_sources(self):
        for target in ['chatgpt','claude']:
            built=skills.prepare(self.data,{**self.payload,'target':target})
            self.assertEqual(built['provenance']['target'],target)
            self.assertIn(skills.OPENAI_GUIDE if target=='chatgpt' else skills.CLAUDE_GUIDE,built['guidance'])
            self.assertIn('no live Mnemos access',built['files']['SKILL.md'])
        with self.assertRaises(core.MnemosError):skills.prepare(self.data,{**self.payload,'target':'unknown'})
        self.doc=core.save_document(self.data,{**self.doc,'body':'Procedure\napi_key: this-is-a-test-secret\nDo not export this.'})
        self.payload['revision']=next(c for c in skills.candidates(self.data)['candidates'] if c['id']==self.candidate['id'])['revision']
        with self.assertRaisesRegex(core.MnemosError,'credential'):skills.prepare(self.data,self.payload)

    def test_workflow_preserves_dependency_order_and_approval(self):
        candidate=next(c for c in skills.candidates(self.data,include_examples=True)['candidates'] if c['id']=='workflow:first-capture')
        payload={**self.payload,'candidate_id':candidate['id'],'revision':candidate['revision']}
        built=skills.prepare(self.data,payload)
        text=built['files']['SKILL.md']
        self.assertLess(text.index('`review-evidence`'),text.index('`capture-draft`'))
        self.assertLess(text.index('`capture-draft`'),text.index('`verify-document`'))
        self.assertIn('Requires an explicit approval checkpoint',text)
        self.assertEqual(built['provenance']['readiness'],'example')
        path=core.vault_path(self.data)/'Workflows/first-capture.json'
        workflow=json.loads(path.read_text());workflow['steps'][0]['depends_on']=['verify-document'];path.write_text(json.dumps(workflow))
        result=skills.candidates(self.data,include_examples=True)
        self.assertFalse(any(c['id']==candidate['id'] for c in result['candidates']))
        self.assertTrue(result['warnings'])

    def test_large_source_rejected_without_truncation(self):
        self.doc=core.save_document(self.data,{**self.doc,'body':'x'*210_000})
        candidate=next(c for c in skills.candidates(self.data)['candidates'] if c['id']==self.candidate['id'])
        self.assertFalse(candidate['buildable'])
        with self.assertRaises(core.MnemosError):skills.prepare(self.data,{**self.payload,'revision':candidate['revision']})

    def test_cli_discovery_preview_save_and_export(self):
        def cli(*args):
            stream=io.StringIO()
            with redirect_stdout(stream):self.assertEqual(main([*args,'--data',str(self.data)]),0)
            return json.loads(stream.getvalue())
        self.assertTrue(cli('skill-candidates','cache')['candidates'])
        settings=Path(self.temp.name)/'settings.json';settings.write_text(json.dumps(self.payload))
        preview=cli('skill-build','--file',str(settings))
        settings.write_text(json.dumps({**self.payload,'preview_revision':preview['preview_revision']}))
        built=cli('skill-build','--file',str(settings),'--save')
        output=Path(self.temp.name)/'skill.zip'
        cli('skill-export','--id',built['id'],'--output',str(output))
        self.assertTrue(zipfile.is_zipfile(output))

    def test_saved_build_directory_cannot_be_a_symlink(self):
        outside=Path(self.temp.name)/'outside';outside.mkdir()
        (self.data/'skill-builds').symlink_to(outside,target_is_directory=True)
        with self.assertRaises(core.MnemosError):self.saved()
        self.assertFalse(list(outside.iterdir()))
