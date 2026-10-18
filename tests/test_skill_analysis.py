import copy
import json
from pathlib import Path
import tempfile
import unittest
from mnemos import core,skill_analysis as analysis,skill_builder as builder,skill_inventory as inventory

class SkillAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.data=Path(self.temp.name).resolve()/'data';core.initialize(self.data,'Tester')
        self.docs=[core.save_document(self.data,{'id':i,'title':i,'type':'runbook','body':'## Steps\n1. Inspect '+i+'.\n2. Verify the result.'}) for i in ['prepare-service','verify-service']]
        self.request=analysis.request(self.data,{'goal':'Prepare and verify a service','source_ids':[d['id'] for d in self.docs]})
        self.proposal={'format':analysis.FORMAT,'request_id':self.request['id'],'title':'Release readiness','rationale':'The preparation and verification notes describe adjacent stages.',
            'skills':[{'id':i,'title':i,'description':'Use when asked to '+i,'source_ids':[i],'inputs':['Service identifier'],'outputs':['Observed status'],
                'steps':[{'instruction':'Inspect the service using the documented procedure.','source_ids':[i]}],
                'validation':['Confirm the documented result.'],'depends_on':[] if n==0 else ['prepare-service'],'requires_approval':n==1} for n,i in enumerate(['prepare-service','verify-service'])],'gaps':['Environment is unspecified.']}

    def accept(self):
        preview=analysis.validate(self.data,{'proposal':self.proposal})
        return analysis.accept(self.data,preview)

    def test_handoff_is_explicit_and_complete(self):
        for doc in self.docs:self.assertIn(doc['body'].replace('\n','\\n'),self.request['prompt'])
        self.assertEqual(len(self.request['sources']),2)
        self.assertEqual(builder.candidates(self.data)['method'],'document-types-and-procedural-structure')
        self.assertFalse((self.data/'skill-proposals').exists())
        for ids in [[],['prepare-service'],['prepare-service','prepare-service']]:
            with self.assertRaises(core.MnemosError):analysis.request(self.data,{'goal':'Task','source_ids':ids})

    def test_preview_accept_and_build_parent_and_children(self):
        count=len(core.list_documents(self.data));record=self.accept()
        suggestions=[c for c in builder.candidates(self.data)['candidates'] if c['id'].startswith('ai:')]
        self.assertEqual(len(suggestions),3);self.assertTrue(all(c['readiness']=='review-needed' for c in suggestions))
        parent=next(c for c in suggestions if c['id'].endswith(':workflow'))
        built=builder.prepare(self.data,{'candidate_id':parent['id'],'revision':parent['revision'],'target':'claude'})
        self.assertEqual(len(built['provenance']['sources']),2)
        text=built['files']['SKILL.md'];self.assertLess(text.index('### prepare-service'),text.index('### verify-service'))
        self.assertIn('Explicit approval required',text);self.assertIn('Environment is unspecified.',text)
        child=next(c for c in suggestions if c['id'].endswith(':verify-service'))
        single=builder.prepare(self.data,{'candidate_id':child['id'],'revision':child['revision'],'target':'chatgpt'})
        self.assertEqual(len(single['provenance']['sources']),1);self.assertIn('does not install its dependencies',single['files']['SKILL.md'])
        self.assertEqual(len(core.list_documents(self.data)),count)

    def test_reject_stale_review_and_changed_source(self):
        preview=analysis.validate(self.data,{'proposal':self.proposal})
        preview['proposal']['title']='A changed title'
        with self.assertRaises(core.MnemosError) as error:analysis.accept(self.data,preview)
        self.assertEqual(error.exception.status,409)
        self.accept()
        core.save_document(self.data,{**self.docs[0],'body':'Changed outside the analysis.'})
        with self.assertRaises(core.MnemosError) as error:analysis.validate(self.data,{'proposal':self.proposal})
        self.assertEqual(error.exception.status,409)
        result=builder.candidates(self.data);self.assertTrue(result['warnings']);self.assertFalse(any(c['id'].startswith('ai:') for c in result['candidates']))

    def test_reject_missing_sources_cycles_and_bad_shapes(self):
        mutations=[lambda p:p['skills'][0].update(source_ids=['invented']),
                   lambda p:p['skills'][0]['steps'][0].update(source_ids=['verify-service']),
                   lambda p:p['skills'][0].update(depends_on=['verify-service']),
                   lambda p:p['skills'][1].update(depends_on=['missing']),
                   lambda p:p['skills'][1].update(id='prepare-service'),
                   lambda p:p['skills'][0].update(requires_approval='true'),
                   lambda p:p.update(request_id='../config'),lambda p:p.update(skills=[])]
        for mutate in mutations:
            proposal=copy.deepcopy(self.proposal);mutate(proposal)
            with self.assertRaises(core.MnemosError):analysis.validate(self.data,{'proposal':proposal})
        self.assertFalse((self.data/'skill-proposals').exists())

    def test_handoff_refuses_large_sources_and_recognized_credentials(self):
        for body in ['x'*100001,'api_key: test-credential-not-real']:
            doc=core.get_document(self.data,'prepare-service');core.save_document(self.data,{**doc,'body':body})
            with self.assertRaises(core.MnemosError):analysis.request(self.data,{'goal':'Task','source_ids':['prepare-service','verify-service']})

    def test_proposal_storage_symlink_refused(self):
        outside=Path(self.temp.name).resolve()/'outside';outside.mkdir()
        (self.data/'skill-proposals').symlink_to(outside,target_is_directory=True)
        with self.assertRaises(core.MnemosError):self.accept()
        self.assertEqual(list(outside.iterdir()),[])

class SkillInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.data=self.root/'data';core.initialize(self.data,'Tester')
        self.skills=self.root/'external-skills';self.skills.mkdir()
        self.manifest=self.skills/'SKILL.md';self.manifest.write_text('---\nname: elsewhere\ndescription: >-\n  A skill made\n  somewhere else.\n---\nDo not execute this file.\n')

    def test_inventory_reads_metadata_and_preserves_files(self):
        before=self.manifest.read_bytes()
        result=inventory.inventory(self.data,[('Test',self.skills),('Duplicate',self.skills)])
        self.assertEqual(len(result['skills']),1)
        self.assertEqual(result['skills'][0]['description'],'A skill made somewhere else.')
        self.assertEqual(self.manifest.read_bytes(),before)
        self.assertIn('does not mean enabled',result['notice'])

    def test_missing_large_symlink_and_malformed_metadata(self):
        (self.skills/'alias').symlink_to(self.root,target_is_directory=True)
        nested=self.skills/'oversize';nested.mkdir();(nested/'SKILL.md').write_text('x'*100001)
        malformed=self.skills/'minimal';malformed.mkdir();(malformed/'SKILL.md').write_text('No metadata')
        result=inventory.inventory(self.data,[('Test',self.skills),('Missing',self.root/'missing')])
        self.assertEqual(len(result['skills']),2);self.assertTrue(result['warnings'])
        self.assertEqual(next(s for s in result['skills'] if s['name']=='minimal')['status'],'Metadata needs review')

    def test_explicit_folder_persists_without_affecting_other_settings(self):
        from unittest.mock import patch
        before=core.load_config(self.data)
        with patch.object(inventory,'inventory',return_value={}):
            inventory.add_folder(self.data,{'path':str(self.skills)})
            inventory.add_folder(self.data,{'path':str(self.skills)})
        after=core.load_config(self.data);self.assertEqual(after.pop('skill_folders'),[str(self.skills)])
        self.assertEqual(before,after)
        for path in ['relative',str(self.root/'missing'),str(Path.home())]:
            with self.assertRaises(core.MnemosError):inventory.add_folder(self.data,{'path':path})
