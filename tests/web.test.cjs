'use strict';

// Exercise the actual app's pure helpers with Node's built-in test runner.
// The minimal DOM stubs only allow registration; no simulated rendering is tested.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const appPath = path.join(__dirname, '..', 'web', 'app.js');
const source = fs.readFileSync(appPath, 'utf8').replace(/\r\n/g, '\n');
const startup = /  load\(\);\n\}\)\(\);\s*$/;
assert.match(source, startup, 'Update this helper harness if application startup changes.');
const registrationTarget = {addEventListener() {}};
const context = {
  document: {querySelector() { return registrationTarget; }, addEventListener() {}},
  window: {MNEMOS_STATIC: true, addEventListener() {}},
  Intl, Date, setTimeout, clearTimeout,
};
vm.createContext(context);
vm.runInContext(source.replace(startup,
  '  globalThis.helpers = {markdown, safeURL, calendarDate, scoreDocument, localRecall, parseImportedDocument, selectedHandoffPack, handoffMarkdown, workspaceHeaders, workspaceDownloadURL, recoveryFromValues, connectionCard, projectCard, skillCandidateCard, skillPackageView, analysisReview, localSkillCards, skillMatchesView, skillMatchPrompt, firstVisitView, rememberGettingStarted, navigationGroups, readingBody, state};\n})();'), context);
const h = context.helpers;
const plain = value => JSON.parse(JSON.stringify(value));

test('Markdown escapes raw HTML in headings, paragraphs, and code fences', () => {
  const rendered = h.markdown('# <script>alert(1)</script>\n\n<img src=x onerror=alert(1)>\n\n```html\n<svg onload=alert(1)>\n```');
  assert.ok(!/<(?:script|img|svg)\b/i.test(rendered));
  assert.match(rendered, /&lt;script&gt;/);
  assert.match(rendered, /<pre><code>&lt;svg/);
});

test('Markdown rejects script/data links and safely renders HTTPS references', () => {
  for (const url of ['javascript:alert', 'JaVaScRiPt:alert', 'data:text/html,test', 'vbscript:test']) {
    assert.equal(h.safeURL(url), null);
    assert.ok(!h.markdown(`[source](${url})`).includes('<a '));
  }
  const rendered = h.markdown('[source](https://example.com/?x="test")');
  assert.match(rendered, /href="https:\/\/example.com\/\?x=&quot;test&quot;"/);
  assert.match(rendered, /rel="noopener noreferrer"/);
});

test('Markdown renders headings, numbered procedures, and tables', () => {
  const rendered = h.markdown('## Procedure\n\n1. First\n2. Second\n\n| Input | Output |\n| --- | --- |\n| request | result |');
  assert.match(rendered, /<h2>Procedure<\/h2>/);
  assert.match(rendered, /<ol><li>First<\/li><li>Second<\/li><\/ol>/);
  assert.match(rendered, /<th>Input<\/th>/);
  assert.match(rendered, /<td>result<\/td>/);
});

test('Date-only metadata retains its local calendar date', () => {
  const previous = process.env.TZ;
  try {
    process.env.TZ = 'America/Phoenix';
    const date = h.calendarDate('2026-10-17');
    assert.equal(date.getFullYear(), 2026);
    assert.equal(date.getMonth(), 9);
    assert.equal(date.getDate(), 17);
  } finally {
    if (previous === undefined) delete process.env.TZ;
    else process.env.TZ = previous;
  }
});

test('Plain JSON import preserves references and cannot import verification or identity', () => {
  const result = plain(h.parseImportedDocument(JSON.stringify({
    id:'existing-id', revision:'old-revision', author:'claimed-owner', status:'verified',
    title:'A recovery procedure', type:'runbook', body:'## Steps\n\n1. Check health',
    sources:['https://example.com/evidence'], related_ids:['health-check'], tags:['recovery'],
  }), 'capture.json'));
  assert.equal(result.status, 'draft');
  assert.equal(result.body, '## Steps\n\n1. Check health');
  assert.deepEqual(result.sources, ['https://example.com/evidence']);
  assert.deepEqual(result.related_ids, ['health-check']);
  for (const key of ['id','revision','author']) assert.ok(!(key in result));
});

test('Document-envelope JSON imports preserve sources and normalize type aliases', () => {
  const result = plain(h.parseImportedDocument(JSON.stringify({document:{
    title:'A bounded task', type:'micro-task', body:'One step.', status:'verified',
    sources:['https://example.com/task'], related_ids:['prerequisite'],
  }}), 'capture.json'));
  assert.equal(result.type, 'microtask');
  assert.equal(result.status, 'draft');
  assert.deepEqual(result.sources, ['https://example.com/task']);
  assert.deepEqual(result.related_ids, ['prerequisite']);
});

test('Metadata-envelope JSON imports use the same draft contract', () => {
  const result = plain(h.parseImportedDocument(JSON.stringify({metadata:{
    title:'Context', type:'context', sources:['https://example.com/session'], status:'verified',
  },body:'## Current state\nDone.'}), 'context.json'));
  assert.equal(result.title, 'Context');
  assert.equal(result.type, 'context');
  assert.equal(result.status, 'draft');
  assert.deepEqual(result.sources, ['https://example.com/session']);
});

test('Malformed JSON and non-document imports fail explicitly', () => {
  for (const content of ['{broken', '[]', 'null', '{"document":[]}', '{"title":"Missing body"}', '{"body":42}']) {
    assert.throws(() => h.parseImportedDocument(content, 'bad.json'));
  }
});

test('Markdown import reads simple metadata and preserves the body as a draft', () => {
  const result = plain(h.parseImportedDocument('---\ntitle: "Recovery"\ntype: "runbook"\nstatus: "verified"\nsources: ["https://example.com/reference"]\nrelated_ids: ["backup"]\n---\n## Procedure\n\n1. Restore\n', 'recovery.md'));
  assert.equal(result.title, 'Recovery');
  assert.equal(result.body, '## Procedure\n\n1. Restore\n');
  assert.equal(result.status, 'draft');
  assert.deepEqual(result.sources, ['https://example.com/reference']);
  assert.deepEqual(result.related_ids, ['backup']);
});

test('Markdown without metadata gets its title from a heading or filename', () => {
  assert.equal(h.parseImportedDocument('# Session context\n\nNotes.', 'export.md').title, 'Session context');
  assert.equal(h.parseImportedDocument('Notes only.', 'session-context.md').title, 'session context');
});

test('Recall matches useful terms in a natural-language task request', () => {
  const doc = {title:'Rotate credentials', summary:'Recover deployment credentials', body:'Check health', tags:['auth']};
  assert.ok(h.scoreDocument(doc, 'how do I recover deployment credentials') > 0);
  assert.equal(h.scoreDocument(doc, 'unrelated nonexistent'), 0);
});

test('Static recall stays within each supported character budget and cites its source', () => {
  h.state.data = {documents:[{id:'credentials', title:'Rotate credentials', status:'draft', type:'runbook',
    summary:'Recover deployment credentials', body:'Check deployment health. '.repeat(1000),
    tags:['auth'], revision:'revision-1', example:true}]};
  for (const budget of [3000,6000,12000]) {
    const result = h.localRecall('deployment', budget);
    assert.ok(result.characters <= budget);
    assert.equal(result.characters, result.context.length);
    assert.equal(result.items.length, 1);
    assert.equal(result.items[0].id, 'credentials');
    assert.match(result.context, /Revision: revision-1/);
    assert.match(result.context, /Example content: yes/);
  }
});


test('Cloud handoff exports only explicitly selected source documents and excerpts', () => {
  const pack = {format:'mnemos-context-pack-v1', query:'Recovery', generated_at:'2026-10-17',
    documents:[{id:'chosen',title:'Chosen',revision:'rev-1',body:'Approved body'}, {id:'private',title:'Private',body:'Do not share this'}],
    recall:{context:'Original context contains private content',items:[{id:'chosen',title:'Chosen',revision:'rev-1',excerpt:'Approved excerpt'}, {id:'private',title:'Private',excerpt:'Excluded excerpt'}]},
    instructions:'Read the approved references.'};
  const result = plain(h.selectedHandoffPack(pack, ['chosen']));
  assert.deepEqual(result.documents.map(doc=>doc.id), ['chosen']);
  assert.deepEqual(result.recall.items.map(item=>item.id), ['chosen']);
  assert.match(result.recall.context, /Approved excerpt/);
  assert.ok(!JSON.stringify(result).includes('Do not share'));
  assert.ok(!JSON.stringify(result).includes('Excluded excerpt'));
  assert.ok(!result.recall.context.includes('Original context'));
});

test('An empty cloud handoff selection contains no source content', () => {
  const result = plain(h.selectedHandoffPack({query:'Task',documents:[{id:'a',body:'Sensitive'}],recall:{items:[{id:'a',excerpt:'Sensitive'}],context:'Sensitive'}}, []));
  assert.deepEqual(result.documents, []);
  assert.deepEqual(result.recall.items, []);
  assert.ok(!JSON.stringify(result).includes('Sensitive'));
});

test('Markdown handoff preserves source revisions, status, body, and citations', () => {
  const markdown = h.handoffMarkdown({query:'Deploy',generated_at:'2026-10-17',instructions:'Review first.',documents:[{id:'deploy',title:'Deployment',revision:'abc123',status:'draft',example:true,body:'## Check\nCheck health.',sources:['https://example.com/evidence']}]});
  assert.match(markdown, /Revision: abc123/);
  assert.match(markdown, /Status: draft/);
  assert.match(markdown, /Example content: yes/);
  assert.match(markdown, /## Check\nCheck health\./);
  assert.match(markdown, /https:\/\/example.com\/evidence/);
});

const setupSource = fs.readFileSync(path.join(__dirname,'..','web','setup.js'),'utf8').replace(/\r\n/g, '\n');
assert.match(setupSource, startup, 'Update the helper harness if setup startup changes.');
const setupContext = {document:{addEventListener(){}},window:{addEventListener(){}},setTimeout,clearTimeout};
vm.createContext(setupContext);
vm.runInContext(setupSource.replace(startup, '  globalThis.helpers={defaults,payloadFor,relocateDefaultBackup,planSetupFlow,setupSubmission,allowedFlows};\n})();'), setupContext);
const setup = setupContext.helpers;

test('First-run setup defaults to local assistant and a dedicated backup destination', () => {
  const result = plain(setup.defaults({data_path:'/vault-data',backup:{provider:'local',destination:'/vault-data/backups'},obsidian:{installed:false}}));
  assert.equal(result.assistant_mode, 'local');
  assert.equal(result.data_path, '/vault-data');
  assert.equal(result.backup.destination, '/vault-data/backups');
  assert.equal(result.install_obsidian, true);
});

test('Existing Obsidian is reused and handoff mode requires no invented connection settings', () => {
  const result = plain(setup.defaults({data_path:'/vault-data',author:'Alex',assistant_mode:'handoff',obsidian:{installed:true},backup:{provider:'rclone',remote:'remote:mnemos'}}));
  assert.equal(result.install_obsidian, false);
  assert.equal(result.assistant_mode, 'handoff');
  assert.equal(result.backup.remote, 'remote:mnemos');
  assert.ok(!('tunnel' in result));
  assert.ok(!('token' in result));
});

test('Setup apply payload preserves explicit choices and includes no unrelated fields', () => {
  const result = plain(setup.payloadFor({data_path:' /private/mnemos ',author:' Alex ',backup:{provider:'rclone',destination:' /local/cache ',remote:' remote:mnemos '},assistant_mode:'connected',install_obsidian:false,unexpected:'discard'}));
  assert.deepEqual(result,{data_path:'/private/mnemos',author:'Alex',backup:{provider:'rclone',destination:'/local/cache',remote:'remote:mnemos'},assistant_mode:'connected',install_obsidian:false});
});


test('Import handler replaces an existing editor with a new draft before populating fields', async () => {
  const fields = new Map();
  const element = selector => {
    if (!fields.has(selector)) fields.set(selector, {value:'',innerHTML:'',textContent:'',hidden:false,className:'',dispatchEvent(){},addEventListener(){}});
    return fields.get(selector);
  };
  const fakeDocument = {querySelector:element,addEventListener(){}};
  const importContext = {document:fakeDocument,window:{MNEMOS_STATIC:true,addEventListener(){},confirm(){return true;}},Event:class Event{},Intl,Date,setTimeout(){return 1;},clearTimeout(){}};
  vm.createContext(importContext);
  const exposed = source.replace(startup, '  globalThis.importHarness={state,importDocument,replaceRenderer(callback){renderCapture=callback;}};\n})();');
  vm.runInContext(exposed,importContext);
  const handler=importContext.importHarness;
  handler.state.editing='existing-note';
  element('#capture-form [name="id"]').value='existing-note';
  let freshFormCreated=false;
  // This boundary represents rebuilding the form; rendering itself is browser-tested.
  handler.replaceRenderer(()=>{
    assert.equal(handler.state.editing,null);
    freshFormCreated=true;
    element('#capture-form [name="id"]').value='';
    handler.state.editorMode='write';
  });
  const file={size:100,name:'roundtrip.json',text:async()=>JSON.stringify({id:'existing-note',revision:'old',status:'verified',title:'Imported result',type:'context',body:'A new result',sources:['source-id revision abc'],related_ids:['source-id']})};
  const input={files:[file],value:'roundtrip.json'};
  await handler.importDocument({target:input});
  assert.equal(freshFormCreated,true);
  assert.equal(handler.state.editing,null);
  assert.equal(element('#capture-form [name="id"]').value,'');
  assert.equal(element('#doc-status').value,'draft');
  assert.equal(element('#doc-title').value,'Imported result');
  assert.equal(element('#doc-sources').value,'source-id revision abc');
  assert.equal(element('#doc-related').value,'source-id');
  assert.equal(input.value,'');
});


test('Copied handoff context keeps status and example labels within every selected budget', () => {
  const documents=[{id:'verified-source',title:'Verified source',revision:'abc123',status:'verified',example:true}, {id:'draft-source',title:'Draft source',revision:'def456',status:'draft',example:false}];
  for(const budget of [3000,6000,12000]){
    const instructions='KEEP COMPLETE INSTRUCTIONS. '.repeat(1000);
    const pack={query:'Continue recovery',instructions,documents,recall:{budget,items:documents.map(doc=>({id:doc.id,title:doc.title,revision:doc.revision,summary:'A source summary',excerpt:'Detailed source evidence. '.repeat(1000)}))}};
    const result=plain(h.selectedHandoffPack(pack,documents.map(doc=>doc.id)));
    assert.ok(result.recall.context.length<=budget);
    assert.equal(result.recall.characters,result.recall.context.length);
    assert.match(result.recall.context,/Status: verified · EXAMPLE CONTENT/);
    assert.match(result.recall.context,/Status: draft/);
    assert.equal(result.instructions,instructions);
    assert.ok(!result.recall.context.includes('KEEP COMPLETE INSTRUCTIONS'));
  }
});

test('Wikilinks resolve an extensionless full vault path when the document ID differs', () => {
  h.state.data={documents:[{id:'capture-procedure-007',title:'Capture procedure',path:'Runbooks/first-capture.md'}]};
  const rendered=h.markdown('<!-- mnemos:related:start -->\nSee [[Runbooks/first-capture|First capture]].\n<!-- mnemos:related:end -->\n\n<!-- other comment -->');
  assert.match(rendered,/data-document="capture-procedure-007"/);
  assert.match(rendered,/>First capture<\/a>/);
  assert.ok(!rendered.includes('mnemos:related:'));
  assert.match(rendered,/&lt;!-- other comment --&gt;/);
});

test('Windows backup defaults follow the chosen data folder across slash conventions', () => {
  assert.equal(setup.relocateDefaultBackup('C:\\old\\data','D:\\new\\data','C:/old/data/backups'),'D:\\new\\data\\backups');
  assert.equal(setup.relocateDefaultBackup('C:/old/data/','D:/new/data','C:\\old\\data\\backups'),'D:/new/data/backups');
  assert.equal(setup.relocateDefaultBackup('C:\\old\\data','D:\\new\\data','E:\\separate-backups'),'E:\\separate-backups');
});

function pasteHarness() {
  const fields=new Map();
  const element=selector=>{
    if(!fields.has(selector))fields.set(selector,{value:'',innerHTML:'',textContent:'',hidden:false,className:'',dispatchEvent(){},addEventListener(){}});
    return fields.get(selector);
  };
  let saves=0,renders=0;
  const environment={document:{querySelector:element,addEventListener(){}},window:{MNEMOS_STATIC:true,addEventListener(){},confirm(){return true;}},Event:class Event{},Intl,Date,setTimeout(){return 1;},clearTimeout(){},fetch(){saves++;throw new Error('Preview must not save');}};
  vm.createContext(environment);
  vm.runInContext(source.replace(startup,'  globalThis.pasteHarness={state,previewPastedDraft,replaceRenderer(callback){renderCapture=callback;}};\n})();'),environment);
  const handler=environment.pasteHarness;
  handler.state.editing='existing-page';
  element('#capture-form [name="id"]').value='existing-page';
  handler.replaceRenderer(()=>{renders++;assert.equal(handler.state.editing,null);element('#capture-form [name="id"]').value='';});
  return {handler,element,saves:()=>saves,renders:()=>renders};
}

test('Pasted JSON preview creates a new draft, preserves source references, and never saves', () => {
  const app=pasteHarness();
  app.element('#pasted-draft').value=JSON.stringify({id:'existing-page',revision:'old',status:'verified',type:'context',title:'Roundtrip result',body:'## Evidence\nObserved success.',sources:['source-1 revision abc'],related_ids:['source-1']});
  app.handler.previewPastedDraft();
  assert.equal(app.handler.state.editing,null);
  assert.equal(app.element('#capture-form [name="id"]').value,'');
  assert.equal(app.element('#doc-title').value,'Roundtrip result');
  assert.equal(app.element('#doc-status').value,'draft');
  assert.equal(app.element('#doc-sources').value,'source-1 revision abc');
  assert.equal(app.element('#doc-related').value,'source-1');
  assert.equal(app.handler.state.editorMode,'preview');
  assert.equal(app.element('#editor-field').hidden,true);
  assert.equal(app.element('#editor-preview').hidden,false);
  assert.match(app.element('#editor-preview').innerHTML,/<h2>Evidence<\/h2>/);
  assert.equal(app.saves(),0);
});

test('Pasted malformed JSON leaves the current editor intact and reports the error', () => {
  const app=pasteHarness();
  app.element('#pasted-draft').value='{broken';
  app.handler.previewPastedDraft();
  assert.equal(app.handler.state.editing,'existing-page');
  assert.equal(app.element('#capture-form [name="id"]').value,'existing-page');
  assert.equal(app.renders(),0);
  assert.equal(app.saves(),0);
  assert.match(app.element('#paste-error').innerHTML,/notice error/);
});

const activeSetup = () => ({initialized:true,data_path:'/workspaces/old',author:'Previous author',backup:{provider:'rclone',destination:'/old-cache',remote:'cloud:old'},assistant_mode:'connected',obsidian:{installed:true},active_workspace:{data_path:'/workspaces/old',revision:'pointer-1'},workspace_id:'workspace-1',settings_revision:'settings-1',setup_modes:['update','create','select'],selection_scope:'default'});

test('Creating a new default starts fresh without mutating the active setup', () => {
  const original=activeSetup();const before=plain(original);
  const flow=plain(setup.planSetupFlow(original,'create'));
  assert.equal(flow.screen,'wizard');assert.equal(flow.step,0);
  assert.deepEqual(flow.values,{data_path:'',author:'Local engineer',backup:{provider:'local',destination:'',remote:''},assistant_mode:'local',install_obsidian:false});
  flow.values.data_path='/workspaces/new';flow.values.backup.destination='/workspaces/new/backups';
  assert.deepEqual(original,before);
});

test('Updating a setup copies its choices while retaining its dedicated folder', () => {
  const original=activeSetup();const flow=setup.planSetupFlow(original,'update');
  assert.equal(flow.values.data_path,original.data_path);
  assert.deepEqual(plain(flow.values.backup),original.backup);
  flow.values.backup.remote='cloud:changed';
  assert.equal(original.backup.remote,'cloud:old');
  const payload=plain(setup.setupSubmission(original,'update',flow.values));
  assert.deepEqual(payload.expected_workspace,original.active_workspace);
  assert.equal(payload.expected_settings_revision,'settings-1');
  assert.equal(payload.data_path,'/workspaces/old');
});

test('Selecting an existing workspace sends only identity and revision guards', () => {
  const active=activeSetup();
  const target={data_path:'/workspaces/existing',author:'Target author',backup:{provider:'local',destination:'/target-backups'},assistant_mode:'handoff',settings_revision:'target-settings-7'};
  const result=plain(setup.setupSubmission(active,'select',target,target));
  assert.deepEqual(result,{mode:'select',data_path:'/workspaces/existing',expected_workspace:{data_path:'/workspaces/old',revision:'pointer-1'},expected_settings_revision:'settings-1',expected_target_settings_revision:'target-settings-7'});
});

test('Pinned servers permit only their advertised modes and keep the fresh fixed folder', () => {
  assert.deepEqual(plain(setup.allowedFlows({...activeSetup(),setup_modes:['update'],selection_scope:'pinned'})),['update']);
  const fresh={initialized:false,selection_scope:'pinned',setup_modes:['create'],data_path:'/fixed-folder',backup:{provider:'local',destination:'/fixed-folder/backups'}};
  assert.deepEqual(plain(setup.allowedFlows(fresh)),['create']);
  assert.equal(setup.planSetupFlow(fresh,'create').values.data_path,'/fixed-folder');
});

function workspaceSetupHarness(info, replies=[]) {
  const elements=new Map();const calls=[];let renders=0;
  const element=selector=>{if(!elements.has(selector))elements.set(selector,{value:'',innerHTML:'',hidden:false,disabled:false,focus(){},querySelectorAll(){return [];}});return elements.get(selector);};
  const environment={document:{querySelector:element,addEventListener(){}},window:{addEventListener(){}},setTimeout(){return 1;},clearTimeout(){},FormData:class FormData{constructor(form){this.fields=form.fields||{};}get(name){return this.fields[name]??null;}},fetch:async(path,options)=>{calls.push({path,options,payload:options.body?JSON.parse(options.body):null});const reply=replies.shift();assert.ok(reply,'Unexpected network call');return {ok:reply.ok!==false,status:reply.status||200,json:async()=>reply.body};}};
  vm.createContext(environment);
  vm.runInContext(setupSource.replace(startup,'  globalThis.flowHarness={state,beginFlow,overview,collect,inspectExisting,applySetup,request,replaceRender(fn){render=fn;}};\n})();'),environment);
  const handler=environment.flowHarness;handler.state.info=info;handler.replaceRender(()=>{renders++;});
  return {handler,element,calls,renders:()=>renders};
}

test('Starting and cancelling a new setup leaves the active configuration untouched and sends no request', () => {
  const info=activeSetup();const snapshot=plain(info);const app=workspaceSetupHarness(info);
  app.handler.beginFlow('create');assert.equal(app.handler.state.screen,'wizard');
  app.element('#setup-form').fields={author:'Next author',data_path:'D:\\mnemos-next'};
  app.handler.collect();
  assert.equal(app.handler.state.values.backup.destination,'D:\\mnemos-next\\backups');
  app.handler.overview();assert.equal(app.handler.state.screen,'overview');
  assert.equal(app.handler.state.values,null);assert.equal(app.calls.length,0);assert.deepEqual(info,snapshot);
});

test('Cancelling existing-workspace selection during first run returns to a valid fresh form', () => {
  const info={initialized:false,data_path:'/fresh',setup_modes:['create','select'],backup:{provider:'local',destination:'/fresh/backups'}};
  const app=workspaceSetupHarness(info);app.handler.beginFlow('select');
  assert.equal(app.handler.state.values,null);app.handler.overview();
  assert.equal(app.handler.state.screen,'wizard');assert.equal(app.handler.state.flowMode,'create');
  assert.equal(app.handler.state.values.data_path,'/fresh');assert.equal(app.calls.length,0);
});

test('Inspect reads the target settings; Apply sends both target and active guards without copying settings', async () => {
  const info=activeSetup();const target={data_path:'/existing',author:'Existing author',backup:{provider:'local',destination:'/existing-backups'},assistant_mode:'handoff',settings_revision:'target-9'};
  const applied={...target,initialized:true,workspace_id:'workspace-2',active_workspace:{data_path:'/existing',revision:'pointer-2'}};
  const app=workspaceSetupHarness(info,[{body:{workspace:target}},{body:applied}]);
  app.handler.beginFlow('select');app.element('#existing-folder').value='/existing';
  await app.handler.inspectExisting({preventDefault(){},currentTarget:{reportValidity(){return true;},querySelector(){return {disabled:false};}}});
  assert.equal(app.calls[0].path,'/api/setup/inspect');assert.equal(app.calls[0].options.headers['X-Mnemos-Workspace'],'workspace-1');
  assert.deepEqual(app.calls[0].payload,{data_path:'/existing',expected_workspace:{data_path:'/workspaces/old',revision:'pointer-1'},expected_settings_revision:'settings-1'});
  assert.equal(app.handler.state.info,info);assert.equal(app.handler.state.inspected.author,'Existing author');
  await app.handler.applySetup();
  assert.deepEqual(app.calls[1].payload,{mode:'select',data_path:'/existing',expected_workspace:{data_path:'/workspaces/old',revision:'pointer-1'},expected_settings_revision:'settings-1',expected_target_settings_revision:'target-9'});
  assert.equal(app.handler.state.info.workspace_id,'workspace-2');
  assert.equal(app.handler.state.previousPath,'/workspaces/old');assert.equal(app.handler.state.screen,'success');
});

test('Setup refresh intentionally omits the stale workspace header while mutations retain it', async () => {
  const app=workspaceSetupHarness(activeSetup(),[{body:{initialized:true}},{body:{status:'ready'}}]);
  await app.handler.request();await app.handler.request('POST',{mode:'update'});
  assert.equal(app.calls[0].options.headers['X-Mnemos-Workspace'],undefined);
  assert.equal(app.calls[1].options.headers['X-Mnemos-Workspace'],'workspace-1');
});

test('Vault download URLs keep the originating workspace and encode its identifier', () => {
  assert.equal(h.workspaceDownloadURL('/api/export','old workspace&1'),'/api/export?workspace=old%20workspace%261');
  assert.equal(h.workspaceDownloadURL('/api/export?format=zip','old'),'/api/export?format=zip&workspace=old');
  assert.equal(h.workspaceDownloadURL('/api/export',''),'/api/export');
});

function workspaceAppHarness(reply) {
  const calls=[];const storage=new Map();let notices=0;
  const form={fields:{id:'existing-doc',revision:'old-revision',title:'Unsaved result',type:'context',body:'Preserve this evidence.',status:'verified',tags:'one, two',sources:'source-1 revision abc\nhttps://example.com',related_ids:'source-1'}};
  const element=selector=>selector==='#capture-form'?form:selector==='#workspace-notice'?null:selector==='#main'?{insertAdjacentHTML(){notices++;}}:registrationTarget;
  const environment={document:{querySelector:element,addEventListener(){}},window:{MNEMOS_STATIC:true,addEventListener(){}},Intl,Date,setTimeout,clearTimeout,sessionStorage:{getItem:key=>storage.get(key)||null,setItem:(key,value)=>storage.set(key,value)},FormData:class FormData{constructor(value){this.form=value;}entries(){return Object.entries(this.form.fields);}},fetch:async(path,options)=>{calls.push({path,options});return {ok:reply.ok,status:reply.status||200,json:async()=>reply.body};}};
  vm.createContext(environment);
  vm.runInContext(source.replace(startup,'  globalThis.workspaceHarness={state,api,readRecovery,reloadActiveWorkspace,setDirty(value){dirty=value;}};\n})();'),environment);
  const handler=environment.workspaceHarness;handler.state.data={workspace_id:'workspace-old',active_workspace:{data_path:'/old-vault'}};
  return {handler,calls,storage,form,notices:()=>notices};
}

test('API requests guard writes and background reads; only bootstrap deliberately refreshes', async () => {
  const app=workspaceAppHarness({ok:true,body:{ok:true}});
  for(const route of ['/api/documents','/api/settings','/api/login','/api/logout'])await app.handler.api(route,{method:'POST',body:'{}'});
  await app.handler.api('/api/backups');await app.handler.api('/api/recall?query=task');await app.handler.api('/api/bootstrap');
  for(const call of app.calls.slice(0,-1))assert.equal(call.options.headers['X-Mnemos-Workspace'],'workspace-old');
  assert.equal(app.calls.at(-1).options.headers['X-Mnemos-Workspace'],undefined);
});

test('A stale save retains the old workspace and preserves a separate recoverable draft', async () => {
  const app=workspaceAppHarness({ok:false,status:409,body:{code:'workspace_changed',error:'The active workspace changed.',reload_required:true}});
  app.handler.setDirty(true);
  await assert.rejects(app.handler.api('/api/documents',{method:'POST',body:'{}'}),error=>error.code==='workspace_changed');
  assert.equal(app.handler.state.workspaceStale,true);assert.equal(app.handler.state.data.workspace_id,'workspace-old');
  const recovered=plain(app.handler.readRecovery());
  assert.equal(recovered.workspace_path,'/old-vault');assert.equal(recovered.original_document_id,'existing-doc');
  assert.equal(recovered.document.body,'Preserve this evidence.');assert.equal(recovered.document.status,'draft');
  assert.deepEqual(recovered.document.tags,['one','two']);assert.deepEqual(recovered.document.related_ids,['source-1']);
  assert.ok(!('id' in recovered.document));assert.ok(!('revision' in recovered.document));
  assert.equal(app.form.fields.id,'existing-doc');assert.equal(app.calls.length,1);assert.equal(app.notices(),1);
});

test('Cross-process workspace changes retain the draft and do not enter a reload loop', async () => {
  const app=workspaceAppHarness({ok:false,status:409,body:{code:'workspace_changed',error:'Restart the server.',reload_required:true,restart_required:true}});
  app.handler.setDirty(true);
  await assert.rejects(app.handler.api('/api/backups'),error=>error.restartRequired===true);
  assert.equal(app.handler.state.workspaceRestart,true);await app.handler.reloadActiveWorkspace();
  assert.equal(app.calls.length,1);assert.equal(app.handler.readRecovery().document.body,'Preserve this evidence.');
});


test('Connection cards escape local configuration text and distinguish pinned targets', () => {
  const html = h.connectionCard({id:'claude-code',name:'<img src=x>',status:'tested',detail:'Local tools only',workspace:'/old/<script>',binding:'Pinned workspace',matches_active:false,testable:true,last_tested:null});
  assert.match(html,/Tested locally/);
  assert.match(html,/Uses a different workspace/);
  assert.match(html,/&lt;script&gt;/);
  assert.ok(!html.includes('<img'));
  assert.match(html,/data-client="claude-code"/);
});


test('Project cards escape repository text and show snapshot scope without claiming live sync', () => {
  const rendered = h.projectCard({id:'project-safe', name:'<img src=x onerror=alert(1)>', path:'/local/<script>repo</script>', include:['<b>README.md</b>'], exclude:[], needs_refresh:true, last_refresh:{at:'2026-10-17T20:00:00Z', branch:'<svg onload=alert(1)>', commit:'abcdef1234567890', source_count:2, changed_count:3, document_id:'context-safe', warnings:['<script>unsafe</script>']}});
  assert.ok(!rendered.includes('<img'));
  assert.ok(!rendered.includes('<script>'));
  assert.ok(!rendered.includes('<svg onload'));
  assert.match(rendered, /Selection changed/);
  assert.match(rendered, /Refresh project context/);
  assert.match(rendered, /Captured/);
  assert.match(rendered, /data-context-id="context-safe"/);
});


test('Automatic project controls expose persisted on/off and escape check failures', () => {
  const project={id:'project-1',name:'Nimbus',path:'/repo',include:['README.md'],exclude:[]};
  assert.match(h.projectCard(project),/role="switch" aria-checked="false"/);
  const enabled=h.projectCard({...project,auto_refresh:true,automatic_status:{state:'error',detail:'<img src=x onerror=alert(1)>',checked_at:'2026-10-17T20:00:00Z'}});
  assert.match(enabled,/role="switch" aria-checked="true"/);
  assert.match(enabled,/Automatic refresh: On/);
  assert.match(enabled,/Last checked/);
  assert.ok(!enabled.includes('<img'));
});


test('Suggested skill cards escape source text and keep review/example labels', () => {
  const card=h.skillCandidateCard({id:'document:test',title:'<img src=x>',readiness:'example',source_count:1,project:'<script>',reason:'<svg>',why:{summary:'<img src=x>',evidence:'<script>evidence</script>',basis:'<svg>'},sources:[{id:'test',title:'<img>',revision:'abc',status:'draft',example:true}],buildable:false});
  assert.ok(!card.includes('<img'));assert.ok(!card.includes('<script>'));assert.ok(!card.includes('<svg>'));
  assert.match(card,/Example only/);assert.match(card,/disabled/);assert.match(card,/data-source-id="test"/);
});

test('Skill preview renders text safely and offers workspace-bound downloads only for saved builds', () => {
  const built={id:'skill-1234567890abcdef',guidance:'<img>',files:{'SKILL.md':'</textarea><script>alert(1)</script>'}};
  const preview=h.skillPackageView(built,false);assert.ok(!preview.includes('<script>'));assert.match(preview,/Save skill/);assert.ok(!preview.includes('Download skill ZIP'));
  h.state.data={workspace_id:'current-workspace'};
  const saved=h.skillPackageView(built,true);assert.match(saved,/workspace=current-workspace/);assert.match(saved,/Download skill ZIP/);assert.match(saved,/Download cloud handoff/);
});


test('AI proposal review escapes steps and shows dependency and evidence gaps', () => {
  const html=h.analysisReview({notice:'Review evidence',sources:[{id:'<source>',title:'Source'}],proposal:{title:'<img src=x>',rationale:'Why',gaps:['<script>gap</script>'],skills:[{title:'Skill',description:'Description',inputs:['Input'],outputs:['Output'],depends_on:['prior-step'],requires_approval:true,steps:[{instruction:'<script>bad</script>',source_ids:['<source>']}],validation:['Verify']}]}});
  assert.ok(!/<(?:script|img)\b/.test(html));assert.match(html,/prior-step/);assert.match(html,/Required/);assert.match(html,/&lt;source&gt;/);assert.match(html,/Evidence gaps/);
});
test('Existing skill cards filter metadata and escape untrusted paths', () => {
  const result={notice:'Read only',warnings:[],skills:[{name:'deploy',description:'Deploy safely',location:'Personal',status:'Manifest found',path:'/tmp/<script>.md'},{name:'review',description:'Review docs',location:'Project',status:'Manifest found',path:'/tmp/review'}]};
  const html=h.localSkillCards(result,'deploy');assert.match(html,/1 local skill manifests/);assert.ok(!html.includes('<script>'));assert.ok(!html.includes('/tmp/review'));assert.match(html,/&lt;script&gt;/);
});


test('Skill matching safely renders local metadata and scoped review handoffs', () => {
  const evil='<img src=x onerror=alert(1)>';
  const match={name:evil,description:evil,path:evil,location:evil,status:evil,reason:evil,kind:'local',recommendation:'extend'};
  const rendered=h.skillMatchesView({recommendation:'extend',scanned:1,total:1,matches:[match],warnings:[evil],notice:evil});
  assert.ok(!/<img\b/i.test(rendered));
  assert.match(rendered,/&lt;img/);
  const candidate={title:'Repair cache',description:'Recover entries',sources:[{id:'cache-note',revision:'revision-one'}]};
  const prompt=h.skillMatchPrompt(candidate,{name:'repair-cache',path:'/local/SKILL.md'},'extend');
  assert.match(prompt,/cache-note @ revision-one/);
  assert.match(prompt,/do not overwrite or install/);
  assert.match(prompt,/If files or tools are unavailable/);
});


test('First visit opens the guide, remembers it, and preserves direct destinations', () => {
  const values=new Map();
  context.window.localStorage={getItem:key=>values.get(key)??null,setItem:(key,value)=>values.set(key,value)};
  assert.equal(h.firstVisitView(''),'getting-started');
  assert.equal(h.firstVisitView('library'),'getting-started');
  for(const destination of ['capture','recall','skills','document','getting-started'])assert.equal(h.firstVisitView(destination),destination);
  assert.equal(values.size,0,'Checking a destination should not mark the guide as viewed');
  h.rememberGettingStarted();
  assert.equal(h.firstVisitView(''),'library');
  assert.equal(h.firstVisitView('library'),'library');
  assert.equal(h.firstVisitView('getting-started'),'getting-started');
  values.clear();
  assert.equal(h.firstVisitView(''),'getting-started');
  delete context.window.localStorage;
});

test('Blocked browser storage does not break onboarding or explicit links', () => {
  Object.defineProperty(context.window,'localStorage',{configurable:true,get(){throw new Error('Storage blocked');}});
  assert.equal(h.firstVisitView(''),'getting-started');
  assert.doesNotThrow(()=>h.rememberGettingStarted());
  assert.equal(h.firstVisitView('document'),'document');
  delete context.window.localStorage;
});


test('Grouped navigation preserves role boundaries and setup availability', () => {
  const ids = groups => Object.values(groups).flat().map(item=>item.id);
  assert.deepEqual(plain(h.navigationGroups(false,false,false,false).primary.map(item=>item.id)), ['library','recall']);
  assert.deepEqual(plain(h.navigationGroups(false,false,true,false).manage.map(item=>item.id)), ['settings']);
  assert.ok(!ids(h.navigationGroups(true,false,false,false)).includes('setup'));
  assert.deepEqual(plain(h.navigationGroups(true,true,false,true).manage.map(item=>item.id)), ['projects','connections','settings','setup']);
  assert.deepEqual(plain(h.navigationGroups(true,true,false,false).manage.map(item=>item.id)), ['settings']);
});

test('Focused reading hides only an identical leading title without mutating notes', () => {
  const doc={title:'Deploy the service',body:'# Deploy the service\n\n## Steps\n1. Verify'};
  assert.equal(h.readingBody(doc),'\n## Steps\n1. Verify');
  assert.equal(doc.body,'# Deploy the service\n\n## Steps\n1. Verify');
  for(const body of ['# Different title\nKeep this','## Deploy the service\nKeep this','Intro\n# Deploy the service','```\n# Deploy the service\n```']) {
    assert.equal(h.readingBody({title:doc.title,body}),body);
  }
});
