'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const tour=require('../web/tutorial.js');

test('moving forward records review; returning does not inflate completion',()=>{
  const original=tour.blank();
  let p=tour.transition(original,'start');
  p=tour.transition(p,'next');
  assert.equal(p.current,'workspace');assert.deepEqual(p.completed,['welcome']);
  p=tour.transition(p,'back');p=tour.transition(p,'next');
  assert.deepEqual(p.completed,['welcome']);
  assert.deepEqual(original,tour.blank(),'transitions do not mutate stored state');
});
test('jumping to a chapter preserves the current place without marking skipped steps reviewed',()=>{
  let p=tour.transition(tour.blank(),'jump','brain');
  assert.equal(p.current,'brain');assert.equal(p.started,true);assert.deepEqual(p.completed,[]);
  p=tour.transition(p,'next');assert.deepEqual(p.completed,['brain']);assert.equal(p.current,'recall');
});
test('the last step returns to unreviewed content instead of falsely completing the tour',()=>{
  let p=tour.transition(tour.blank(),'jump',tour.lessons.at(-1).id);
  p=tour.transition(p,'next');
  assert.equal(p.current,'welcome');assert.equal(p.completed.length,1);
});
test('full progression completes once and replay starts cleanly',()=>{
  let p=tour.transition(tour.blank(),'start');
  for(const lesson of tour.lessons){assert.equal(p.current,lesson.id);p=tour.transition(p,'next');}
  assert.equal(new Set(p.completed).size,tour.lessons.length);
  assert.equal(tour.transition(p,'next').completed.length,tour.lessons.length);
  const reset=tour.transition(p,'restart');assert.deepEqual(reset.completed,[]);assert.equal(reset.current,'welcome');assert.equal(reset.started,true);
});
test('corrupt or obsolete progress cannot inject routes or completion IDs',()=>{
  for(const value of [null,42,'bad',{}, {version:0,current:'brain'}])assert.deepEqual(tour.normalize(value),tour.blank());
  const p=tour.normalize({version:1,current:'javascript:bad',completed:['brain','brain','unknown',null,{id:'ask'}],started:'yes'});
  assert.equal(p.current,'welcome');assert.deepEqual(p.completed,['brain']);assert.equal(p.started,false);
  assert.equal(tour.transition(p,'jump','/api/anything').current,'welcome');
});
test('progress is separated by workspace, access role, and portable reader mode',()=>{
  const keys=[tour.storageKey('one','owner',false),tour.storageKey('two','owner',false),tour.storageKey('one','reader',false),tour.storageKey('one','reader',true)];
  assert.equal(new Set(keys).size,keys.length);
  assert.notEqual(tour.storageKey('a:b','c',false),tour.storageKey('a','b:c',false));
});
test('tutorial feature links honor author, owner, and local-owner capabilities',()=>{
  const reader={write:false,owner:false,local:false},author={write:true,owner:false,local:false},remoteOwner={write:true,owner:true,local:false},localOwner={write:true,owner:true,local:true};
  for(const lesson of tour.lessons){
    assert.equal(!!tour.canOpen(lesson,reader),lesson.access==='all',lesson.id);
    assert.equal(!!tour.canOpen(lesson,author),['all','write'].includes(lesson.access),lesson.id);
    assert.equal(!!tour.canOpen(lesson,remoteOwner),lesson.access!=='local',lesson.id);
    assert.equal(!!tour.canOpen(lesson,localOwner),true,lesson.id);
  }
});
test('every tutorial destination is an existing in-app feature, never an operation or external upload',()=>{
  const destinations=new Set(['getting-started','/setup.html','library','capture','inbox','projects','graph','recall','ask','privacy','handoff','connections','skills','workflows','history','health','settings','recovery','search-settings']);
  assert.equal(new Set(tour.lessons.map(l=>l.id)).size,tour.lessons.length);
  for(const lesson of tour.lessons){assert.ok(destinations.has(lesson.route),lesson.route);assert.ok(tour.chapters.some(c=>c[0]===lesson.chapter),lesson.id);}
});
