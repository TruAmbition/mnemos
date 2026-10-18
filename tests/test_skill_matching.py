import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from mnemos import core, skill_builder, skill_inventory, skill_matching


class MatchingTests(unittest.TestCase):
    def test_matching_distinguishes_provenance_exact_names_overlap_and_noise(self):
        candidate={'id':'document:cache', 'title':'Repair Nimbus cache', 'name':'repair-nimbus-cache',
                   'description':'Recover Nimbus cache entries'}
        inventory=[
            {'name':'repair-nimbus-cache','description':'Other environment','id':'exact'},
            {'name':'recover-nimbus-cache','description':'Cache diagnostics','id':'related'},
            {'name':'use-reusable-skills','description':'Follow documented workflow steps when asked','id':'noise'},
            {'name':'deploy-website','description':'Publish static HTML','id':'unrelated'},
            {'name':'old-name','description':'old wording','id':'old','candidate_id':candidate['id'],'freshness':'changed'},
            {'name':'current-name','description':'old wording','id':'current','candidate_id':candidate['id'],'freshness':'current'},
        ]
        result=skill_matching.rank(candidate, inventory)
        found={m['id']:m for m in result['matches']}
        self.assertEqual(set(found),{'exact','related','old','current'})
        self.assertEqual(found['old']['recommendation'],'extend')
        self.assertEqual(found['current']['recommendation'],'reuse')
        self.assertEqual(found['related']['recommendation'],'extend')
        self.assertEqual(found['exact']['recommendation'],'reuse')
        self.assertTrue(all(m['reason'] for m in found.values()))
        self.assertEqual(skill_matching.rank(candidate,inventory[2:4])['recommendation'],'create')

    def test_check_includes_saved_builds_and_rejects_stale_suggestions(self):
        with tempfile.TemporaryDirectory() as tmp:
            data=Path(tmp)/'data';core.initialize(data,'Engineer')
            doc=core.save_document(data,{'id':'repair-cache','title':'Repair Nimbus cache','type':'runbook','body':'Inspect cache entries.'})
            candidate=next(c for c in skill_builder.candidates(data)['candidates'] if c['id']=='document:repair-cache')
            payload={'candidate_id':candidate['id'],'revision':candidate['revision'],'name':'repair-nimbus-cache','target':'claude','description':'Recover Nimbus cache entries.'}
            preview=skill_builder.prepare(data,payload)
            built=skill_builder.save(data,{**payload,'preview_revision':preview['preview_revision']})
            with patch.object(skill_inventory,'inventory',return_value={'skills':[],'warnings':['Scan limit reached.'],'notice':'Local only.'}):
                result=skill_matching.check(data,payload)
                self.assertEqual(result['matches'][0]['id'],built['id'])
                self.assertEqual(result['recommendation'],'reuse')
                self.assertEqual(result['warnings'],['Scan limit reached.'])
                core.save_document(data,{**doc,'body':'Changed procedure.'})
                with self.assertRaises(core.MnemosError):skill_matching.check(data,payload)
                fresh=next(c for c in skill_builder.candidates(data)['candidates'] if c['id']==candidate['id'])
                result=skill_matching.check(data,{**payload,'revision':fresh['revision']})
                self.assertEqual(result['recommendation'],'extend')
                self.assertEqual(result['matches'][0]['freshness'],'changed')

    def test_bounded_matches_keep_total_and_do_not_mutate_inventory(self):
        candidate={'id':'document:cache','title':'Repair cache','name':'repair-cache','description':'Repair cache'}
        items=[{'name':'repair-cache','description':'Repair cache','id':str(n)} for n in range(20)]
        result=skill_matching.rank(candidate,items)
        self.assertEqual(result['total'],20);self.assertEqual(len(result['matches']),8)
        self.assertTrue(all('recommendation' not in item for item in items))
