const test=require('node:test'),assert=require('node:assert/strict'),brain=require('../web/brain.js');
const graph={nodes:[{id:'p',label:'Project',kind:'project',project_ids:['p'],connections:2},{id:'a',label:'Deploy',kind:'runbook',project_ids:['p'],connections:1},{id:'b',label:'Repair',kind:'troubleshooting',project_ids:[],connections:1}],edges:[{source:'p',target:'a',relation:'contains'},{source:'a',target:'b',relation:'links'}]};
test('filters never leave edges to hidden nodes',()=>{const result=brain.filter(graph,{project:'p'});assert.deepEqual(result.nodes.map(n=>n.id).sort(),['a','p']);assert.equal(result.edges.length,1);});
test('search, type, neighborhood and node cap are explicit',()=>{assert.equal(brain.filter(graph,{query:'repair'}).nodes.length,1);assert.equal(brain.filter(graph,{kind:'repository'}).nodes.length,0);assert.equal(brain.filter(graph,{focus:'p'}).nodes.length,2);const limited=brain.filter(graph,{limit:1});assert.equal(limited.total,3);assert.equal(limited.limited,true);assert.equal(limited.edges.length,0);});
test('deterministic layout stays bounded and does not invent nodes',()=>{const one=brain.layout(graph),two=brain.layout(graph);assert.deepEqual(one,two);assert.equal(one.length,3);for(const p of one){assert.ok(Number.isFinite(p.x)&&Number.isFinite(p.y));assert.ok(p.x>=130&&p.x<=870&&p.y>=80&&p.y<=610);assert.ok(p.side?p.x>=515:p.x<=485);}});
test('orb colors distinguish categories and sizes encode hubs and connectivity',()=>{assert.notEqual(brain.style('project')[1],brain.style('repository')[1]);assert.ok(brain.radius({kind:'project'})>brain.radius({kind:'context'}));assert.ok(brain.radius({kind:'runbook',connections:16})>brain.radius({kind:'runbook',connections:0}));assert.ok(brain.radius({kind:'project',connections:10000})<=30);});
test('empty and dense graphs remain finite',()=>{assert.deepEqual(brain.layout({nodes:[],edges:[]}),[]);const dense={nodes:Array.from({length:160},(_,i)=>({id:'n'+i,label:'N'+i,kind:'knowledge'})),edges:[]};assert.ok(brain.layout(dense).every(p=>Number.isFinite(p.x)&&Number.isFinite(p.y)));});
test('type is default; project colors stay consistent across node kinds and filtering',()=>{
  const catalog={nodes:[{id:'project:a',project_id:'a',label:'Atlas',kind:'project',project_ids:['a']},{id:'project:b',project_id:'b',label:'Commerce',kind:'project',project_ids:['b']},{id:'repo:a',label:'API',kind:'repository',project_ids:['a']},{id:'note:b',label:'Deploy',kind:'runbook',project_ids:['b']}],edges:[]};
  const original=JSON.stringify(catalog),types=brain.colorScheme(catalog),projects=brain.colorScheme(catalog,'project');
  assert.equal(types.entry(catalog.nodes[2]).color,brain.style('repository')[1]);
  assert.equal(projects.entry(catalog.nodes[0]).color,projects.entry(catalog.nodes[2]).color);
  assert.notEqual(projects.entry(catalog.nodes[0]).color,projects.entry(catalog.nodes[1]).color);
  const filtered=brain.filter(catalog,{kind:'runbook'}),subset=brain.colorScheme(filtered,'project',catalog);
  assert.equal(subset.entry(filtered.nodes[0]).color,projects.entry(catalog.nodes[1]).color);
  assert.deepEqual(subset.legend.map(e=>e.label),['Commerce']);assert.equal(JSON.stringify(catalog),original);
});
test('shared and unassigned knowledge have explicit neutral project colors',()=>{
  const catalog={nodes:[{id:'project:a',label:'Atlas',kind:'project',project_ids:['a']},{id:'x',label:'Shared skill',kind:'skill',project_ids:['a','b']},{id:'y',label:'Personal note',kind:'knowledge',project_ids:[]}],edges:[]};
  const colors=brain.colorScheme(catalog,'project');
  assert.equal(colors.entry(catalog.nodes[1]).label,'Shared across projects');
  assert.equal(colors.entry(catalog.nodes[2]).label,'No project assigned');
  assert.notEqual(colors.entry(catalog.nodes[1]).color,colors.entry(catalog.nodes[0]).color);
  assert.equal(colors.entry({...catalog.nodes[0],project_ids:['a','a'],kind:'repository'}).color,colors.entry(catalog.nodes[0]).color);
  assert.deepEqual(brain.colorScheme({nodes:[],edges:[]},'project').legend,[]);
});
