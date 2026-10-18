import json
from pathlib import Path
import shutil
import tempfile
import unittest
from mnemos import core, graph, knowledge_projects as kp, privacy


class KnowledgeGraphTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.data=Path(self.temp.name)/'data';core.initialize(self.data)
        shutil.rmtree(core.vault_path(self.data));core.vault_path(self.data).mkdir()

    def note(self, identifier, **fields):
        return core.save_document(self.data, {'id':identifier,'title':identifier.title(),'body':'Recorded work.',**fields})

    def test_explicit_relationships_only_with_types_and_degree(self):
        config=core.load_config(self.data);config['projects']=[{'id':'project-api','name':'API'}];core.save_config(self.data,config)
        p=kp.save(self.data, {'name':'Product','repository_ids':['project-api']})['knowledge_project']
        a=self.note('deploy',type='runbook',project_id=p['id'],repository_ids=['project-api'])
        # The actual generated filename is resolved using the note ID, not an invented target.
        b=self.note('fix',type='troubleshooting',body=f"[[{a['path']}#Steps|Deploy]]",related_ids=[a['id']])
        g=graph.build(self.data,local=True);nodes={n['id']:n for n in g['nodes']}
        self.assertEqual(nodes['note:deploy']['kind'],'runbook')
        self.assertEqual(nodes['note:fix']['kind'],'troubleshooting')
        self.assertEqual(nodes['repo:project-api']['kind'],'repository')
        self.assertTrue(any(e['relation']=='links to' for e in g['edges']))
        self.assertEqual(nodes['note:deploy']['connections'],3)
        self.assertNotIn(str(self.data),json.dumps(g))
        for e in g['edges']: self.assertIn(e['source'],nodes);self.assertIn(e['target'],nodes)

    def test_no_phantom_ambiguous_or_external_nodes(self):
        docs=[{'id':'a','title':'Same','path':'one/a.md','body':'[[Same]] [[missing]] [web](https://example.com/a)\n```md\n[[b]]\n```\n`[[b]]` <!-- [[b]] -->','type':'context'},
              {'id':'b','title':'Same','path':'two/b.md','body':'','type':'context'}]
        g=graph.assemble(docs);self.assertEqual(len(g['nodes']),2);self.assertFalse(g['edges'])

    def test_relative_markdown_aliases_sources_and_self_links(self):
        docs=[{'id':'a','title':'A','path':'Notes/a.md','body':'[B](../Elsewhere/b.md#heading) [[a]]','sources':['mnemos:b@123']},
              {'id':'b','title':'B','path':'Elsewhere/b.md','body':''}]
        g=graph.assemble(docs)
        self.assertEqual({e['relation'] for e in g['edges']},{'links to','uses source'})
        self.assertTrue(all(e['source']!=e['target'] for e in g['edges']))

    def test_private_notes_and_local_metadata_are_not_exposed_to_shared_sessions(self):
        secret=self.note('secret')
        shared=self.note('public',status='verified',body='Reviewed work.')
        privacy.update(self.data, {'id':shared['id'],'operation':'policy','mode':'team','fingerprint':core.get_document(self.data,shared['id'])['privacy']['fingerprint']})
        config=core.load_config(self.data);config['projects']=[{'id':'project-private','name':'Confidential repository'}];core.save_config(self.data,config)
        with privacy.audience('team'):
            g=graph.build(self.data,'reader',local=True)
        self.assertEqual([n['id'] for n in g['nodes']],['note:public'])
        self.assertFalse(g['edges']);self.assertNotIn('secret',json.dumps(g));self.assertNotIn('Confidential',json.dumps(g))
        with privacy.audience('ai'):
            self.assertFalse(graph.build(self.data,'owner',local=True)['nodes'])

    def test_workflows_and_built_skills_link_only_visible_sources(self):
        d=self.note('run',type='microtask')
        g=graph.assemble([d],workflows=[{'id':'release','title':'Release flow','steps':[{'document_id':'run'}]}],skills=[{'id':'skill-one','name':'Release skill','source_ids':['run','missing'],'target':'claude'}])
        nodes={n['id']:n for n in g['nodes']}
        self.assertEqual(nodes['package:skill-one']['kind'],'skill-package')
        self.assertEqual(nodes['note:run']['connections'],2)
        self.assertEqual(len(g['edges']),2)
