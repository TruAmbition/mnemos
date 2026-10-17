'use strict';

// Exercise the actual app's pure helpers with Node's built-in test runner.
// The minimal DOM stubs only allow registration; no simulated rendering is tested.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const appPath = path.join(__dirname, '..', 'web', 'app.js');
const source = fs.readFileSync(appPath, 'utf8');
const startup = /  load\(\);\n\}\)\(\);\s*$/;
assert.match(source, startup, 'Update this helper harness if application startup changes.');
const registrationTarget = {addEventListener() {}};
const context = {
  document: {querySelector() { return registrationTarget; }, addEventListener() {}},
  window: {KEYSTONE_STATIC: true, addEventListener() {}},
  Intl, Date, setTimeout, clearTimeout,
};
vm.createContext(context);
vm.runInContext(source.replace(startup,
  '  globalThis.helpers = {markdown, safeURL, calendarDate, scoreDocument, localRecall, parseImportedDocument, state};\n})();'), context);
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
