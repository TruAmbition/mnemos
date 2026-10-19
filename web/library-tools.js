/* Private local-owner history, grounded answers, and documentation review. */
window.MnemosLibraryTools = function(host) {
  const {root, api, escape:esc, notice, toast, download} = host;
  const $ = selector => root.querySelector(selector);
  const post = (path, body={}) => api(path, {method:'POST', body:JSON.stringify(body)});
  const intro = (title,text) => `<div class="page-heading"><div><span class="eyebrow">YOUR ENGINEERING MEMORY</span><h1>${title}</h1><p>${text}</p></div></div>`;
  const date = value => value ? new Date(value).toLocaleString() : 'Not recorded';
  function run(button, action) {
    button.disabled=true;
    if($('#tool-status'))$('#tool-status').innerHTML='';
    return Promise.resolve().then(action).catch(error=>{if(root.isConnected){if($('#tool-status'))$('#tool-status').innerHTML=notice(error.message,'error');else toast(error.message,true);}}).finally(()=>{button.disabled=false;});
  }
  const projectOptions = selected => '<option value="">All projects</option>'+host.projects().map(p=>`<option value="${esc(p.id)}"${p.id===selected?' selected':''}>${esc(p.name)}</option>`).join('');
  const docLink = (id,title) => `<button class="button text small" data-document="${esc(id)}">${esc(title)}</button>`;

  async function history() {
    root.innerHTML=intro('Note history','Compare earlier versions and restore a note without losing the current one.')+'<section class="panel" id="history-panel">Loading history…</section><div id="tool-status" aria-live="polite"></div>';
    const result=await api('/api/note-history');if(!$('#history-panel'))return;
    const grouped=new Map();for(const v of result.versions){if(!grouped.has(v.id))grouped.set(v.id,v);}
    const requested=decodeURIComponent(window.location.hash.split('/')[1]||'');
    $('#history-panel').innerHTML=`<p class="connection-help">${esc(result.notice)}</p><div class="field"><label for="history-note">Note</label><select id="history-note">${[...grouped.values()].map(v=>`<option value="${esc(v.id)}"${v.id===requested?' selected':''}>${esc(v.title)}${v.missing?' · missing from vault':''}</option>`).join('')}</select></div><div class="history-layout"><div id="history-versions" aria-label="Saved versions"></div><section id="history-preview" aria-live="polite"><p>Select a version to compare it with the current note.</p></section></div>`;
    if(!grouped.size){$('#history-panel').innerHTML=notice('No history yet. Open or save notes in Mnemos to begin capturing versions.');return;}
    function versions(){
      const id=$('#history-note').value;$('#history-preview').innerHTML='<p>Select a version to compare it with the current note.</p>';
      $('#history-versions').innerHTML=result.versions.filter(v=>v.id===id).map(v=>`<button class="session-list-item" data-history-revision="${esc(v.revision)}"><strong>${v.current?'Current version':'Saved version'}</strong><small>${esc(date(v.captured))} · ${esc(v.status)}<br>${esc(v.revision.slice(0,12))} · ${v.origin==='app-save'?'Mnemos save':'Observed on this computer'}</small></button>`).join('');
      root.querySelectorAll('[data-history-revision]').forEach(b=>b.addEventListener('click',()=>run(b,async()=>{
        const selected={id,revision:b.dataset.historyRevision};const checked=await post('/api/note-history/preview',selected);if(!$('#history-preview'))return;
        $('#history-preview').innerHTML=`<h2>${esc(checked.title)}</h2><p>${esc(checked.notice)}</p><details open><summary>Changes from the current version</summary><pre class="history-diff">${esc(checked.diff||'This is the current version. Restoring it still creates a draft.')}</pre></details><details><summary>Read the selected version</summary><pre class="history-diff">${esc(checked.draft.body)}</pre></details><button class="button primary" id="history-restore">Restore as a new draft</button>`;
        $('#history-restore').addEventListener('click',event=>run(event.target,async()=>{
          const saved=await post('/api/note-history/restore',{...selected,review_revision:checked.review_revision});
          await host.refreshDocuments();toast(saved.notice);await history();
        }));
      })));
    }
    $('#history-note').addEventListener('change',versions);versions();
  }

  async function ask() {
    root.innerHTML=intro('Ask my library','Get a sourced answer from your documentation, with gaps and uncertainty kept visible.')+`<button class="button" id="ask-new" hidden>Ask another question</button><div class="answer-layout"><div><form class="panel" id="ask-form"><div class="field"><label for="ask-question">What do you want to understand?</label><textarea id="ask-question" rows="2" maxlength="1000" required placeholder="How does our deployment recover from a failed release?"></textarea></div><div class="form-row"><div class="field"><label for="ask-project">Project</label><select id="ask-project">${projectOptions('')}</select></div><div class="field"><label for="ask-method">Find evidence using</label><select id="ask-method"><option value="keyword">Keywords</option><option value="semantic">Meaning + keywords</option></select></div></div><details><summary>Choose specific notes instead</summary><p class="connection-help">Optional: choose up to six notes. Otherwise Mnemos finds relevant excerpts.</p><div id="ask-source-options" class="session-sources"></div></details><button class="button primary" type="submit">Find sources</button><p class="connection-help">Search stays local. Review the evidence before choosing a local model or an assistant handoff.</p></form><div id="ask-work"></div></div><aside class="panel"><h2>Saved questions</h2><p class="connection-help">Private to this workspace. Answers are saved separately from library notes.</p><div id="ask-saved"></div></aside></div><div id="tool-status" aria-live="polite"></div>`;
    function choices(){const project=$('#ask-project').value;$('#ask-source-options').innerHTML=host.docs().filter(d=>!d.example&&d.status!=='archived'&&(!project||(d.project_ids||[]).includes(project))).map(d=>`<label><input name="ask-source" type="checkbox" value="${esc(d.id)}"> ${esc(d.title)}</label>`).join('')||'<p>No notes in this scope.</p>';}
    $('#ask-new').addEventListener('click',()=>{if(host.isDirty()&&!confirm('Discard the unsaved assistant response?'))return;host.dirty(false);$('#ask-form').hidden=false;$('#ask-new').hidden=true;$('#ask-work').innerHTML='';$('#ask-question').value='';root.querySelectorAll('[name="ask-source"]').forEach(i=>i.checked=false);$('#ask-question').focus();});
    choices();$('#ask-project').addEventListener('change',choices);
    $('#ask-form').addEventListener('input',()=>host.dirty(true));
    $('#ask-form').addEventListener('submit',event=>{event.preventDefault();run(event.submitter,async()=>{
      const ids=[...root.querySelectorAll('[name="ask-source"]:checked')].map(i=>i.value);
      const record=await post('/api/library-answers',{question:$('#ask-question').value,project_id:$('#ask-project').value,method:$('#ask-method').value,...(ids.length?{source_ids:ids}:{})});
      host.dirty(false);await openAnswer(record.id);await savedQuestions();
    });});
    await savedQuestions();
  }
  async function savedQuestions(){
    const result=await api('/api/library-answers');if(!$('#ask-saved'))return;
    $('#ask-saved').innerHTML=result.questions.map(r=>`<button class="session-list-item" data-answer-id="${esc(r.id)}"><strong>${esc(r.question)}</strong><small>${esc(r.provider||'Evidence collected')} · ${esc(date(r.created))}</small></button>`).join('')||'<p class="connection-help">Questions will appear here after you find sources.</p>';
    root.querySelectorAll('[data-answer-id]').forEach(b=>b.addEventListener('click',()=>run(b,async()=>{if(host.isDirty()&&!confirm('Discard unsaved text and open this question?'))return;host.dirty(false);await openAnswer(b.dataset.answerId);})));
  }
  async function openAnswer(id){
    const record=await api('/api/library-answers/'+encodeURIComponent(id));if(!$('#ask-work'))return;
    const stale=record.changed_sources.length>0;
    $('#ask-form').hidden=true;$('#ask-new').hidden=false;
    $('#ask-work').innerHTML=`<section class="panel"><span class="eyebrow">SELECTED EVIDENCE</span><h2>${esc(record.question)}</h2>${stale?notice('Sources or their permissions changed. This saved answer is historical. Find sources again to generate or save a current answer.','error'):''}<details id="answer-evidence-controls"${record.answer?'':' open'}><summary>Review sources & answer options</summary>${record.sources.length?`<p>${record.sources.length} source excerpts. Drafts and changed evidence need review.</p>${record.sources.map((s,index)=>`<details class="answer-source"><summary>[${index+1}] ${esc(s.title)} <span class="tag">${esc(s.status)}</span>${s.evidence_changed.length?' · evidence changed':''}</summary><p>${docLink(s.id,'Open current note')} · revision ${esc(s.revision.slice(0,12))}</p><p>${esc(s.summary)}</p><pre>${esc(s.excerpt)}</pre></details>`).join('')}`:notice('No related evidence found. Try an exact project, error, or feature name, or select notes above. No answer was invented.')}
      ${record.sources.length&&!stale?`<section class="session-step"><h3>Choose how to answer</h3><p>Use your existing ChatGPT or Claude account through a file, or generate on this computer with Ollama.</p><div class="project-actions"><button class="button primary" id="answer-handoff">Prepare assistant handoff</button><button class="button" id="answer-models">Use a local model</button></div><div id="answer-provider"></div><p class="connection-help">A cloud handoff requires current note approval in <a href="#privacy">Privacy & sharing</a>. A local model uses the displayed question and excerpts on this computer. No tunnel, API key, or automatic model download.</p><details id="answer-import"><summary>Import your assistant’s answer</summary><label for="answer-json">Paste the JSON response</label><textarea id="answer-json" rows="6" class="code-editor" maxlength="100000"></textarea><label for="answer-file">Or choose its JSON file</label><input id="answer-file" type="file" accept=".json"><button class="button" id="answer-accept">Check citations & show answer</button></details></section>`:''}
      </details><div id="answer-result" aria-live="polite"></div><details class="session-step"><summary>Manage this saved question</summary><p>Removes the question, source excerpts, and answer. Any draft already saved in the library remains.</p><button class="button small" id="answer-remove">Remove saved question</button></details></section>`;
    showAnswer(record);
    $('#answer-handoff')?.addEventListener('click',event=>run(event.target,async()=>{
      const pack=await post('/api/library-answers/handoff',{id});if(!$('#answer-provider'))return;
      $('#answer-provider').innerHTML=`<label for="answer-prompt">Review before sharing</label><textarea id="answer-prompt" rows="7" class="code-editor" readonly>${esc(pack.prompt)}</textarea><button class="button" id="answer-download">Download question & evidence</button><p>Attach this file to your assistant and ask it to answer. Import its JSON response below.</p>`;
      $('#answer-download').addEventListener('click',event=>run(event.target,async()=>{const current=await post('/api/library-answers/handoff',{id});download('mnemos-library-question.md',current.prompt);}));
    }));
    $('#answer-models')?.addEventListener('click',event=>run(event.target,async()=>{
      const result=await api('/api/library-answers/models');if(!$('#answer-provider'))return;
      $('#answer-provider').innerHTML=`<div class="field"><label for="answer-model">Installed local model</label><select id="answer-model">${result.models.map(m=>`<option>${esc(m)}</option>`).join('')}</select></div><p>${esc(result.notice)}</p><button class="button primary" id="answer-generate"${result.models.length?'':' disabled'}>Generate local answer</button><p id="answer-progress" role="status"></p>`;
      $('#answer-generate').addEventListener('click',event=>run(event.target,async()=>{
        $('#answer-progress').textContent='Reading the selected evidence… Local generation may take up to a minute.';
        try{const result=await post('/api/library-answers/generate',{id,model:$('#answer-model').value});if(!$('#answer-result'))return;showAnswer(result);await savedQuestions();}
        finally{if($('#answer-progress'))$('#answer-progress').textContent='';}
      }));
    }));
    $('#answer-json')?.addEventListener('input',()=>host.dirty(true));
    $('#answer-file')?.addEventListener('change',event=>run(event.target,async()=>{
      const file=event.target.files[0];if(!file)return;if(file.size>100000)throw Error('Use a response under 100 KB.');
      const text=await file.text();if($('#answer-json')){$('#answer-json').value=text;host.dirty(true);}
    }));
    $('#answer-accept')?.addEventListener('click',event=>run(event.target,async()=>{
      const result=await post('/api/library-answers/accept',{id,answer:JSON.parse($('#answer-json').value)});host.dirty(false);if(!$('#answer-result'))return;showAnswer(result);await savedQuestions();
    }));
    $('#answer-remove').addEventListener('click',event=>run(event.target,async()=>{if(!confirm('Remove this saved question and its answer?'))return;await post('/api/library-answers/remove',{id});host.dirty(false);$('#ask-work').innerHTML='';await savedQuestions();}));
  }
  function showAnswer(record){
    if(!record.answer){$('#answer-result').innerHTML='';return;}
    if($('#answer-evidence-controls'))$('#answer-evidence-controls').open=false;
    const source=id=>record.sources.find(s=>s.id===id);
    const stale=record.changed_sources?.length>0;
    $('#answer-result').innerHTML=`<section class="answer-output"><span class="eyebrow">${esc(record.provider||'ASSISTANT ANSWER')}</span><h2>${record.answer.claims.length?'Answer with evidence':'Not enough evidence'}</h2><p class="connection-help">Citations match the selected excerpts; this does not prove the reasoning is correct. Review before acting.</p>${record.answer.claims.map(c=>`<article class="answer-claim">${c.kind==='inference'?'<span class="tag">Inference</span>':''}<p>${esc(c.text)}</p><details><summary>Supporting evidence · ${c.citations.length} citation${c.citations.length===1?'':'s'}</summary>${c.citations.map(ref=>`<blockquote>${esc(ref.quote)}</blockquote><p>${docLink(ref.source_id,source(ref.source_id)?.title||ref.source_id)} · ${esc(source(ref.source_id)?.status||'')} · ${esc(source(ref.source_id)?.revision.slice(0,12)||'')}</p>`).join('')}</details></article>`).join('')}<section class="answer-gaps"><h3>Gaps & uncertainties</h3>${record.answer.unknowns.length?`<ul>${record.answer.unknowns.map(u=>`<li>${esc(u)}</li>`).join('')}</ul>`:'<p>The assistant reported no gaps. This is not a guarantee of completeness.</p>'}</section><button class="button" id="answer-save"${stale?' disabled':''}>Save answer as a draft note</button><div id="answer-save-result"></div></section>`;
    $('#answer-save').addEventListener('click',event=>run(event.target,async()=>{
      const saved=await post('/api/library-answers/save',{id:record.id,answer_revision:record.answer_revision});await host.refreshDocuments();if($('#answer-save-result'))$('#answer-save-result').innerHTML=`<p>${saved.already_saved?'This question already has a library note.':'Saved as a draft with linked source revisions.'} ${docLink(saved.document.id,'Open draft')}</p>`;
    }));
  }

  async function health(){
    root.innerHTML=intro('Documentation health','Review what changed, close knowledge gaps, and keep reusable procedures trustworthy.')+`<section class="panel"><div class="form-row"><div class="field"><label for="health-project">Project</label><select id="health-project">${projectOptions('')}</select></div><div class="field"><label for="health-category">Finding</label><select id="health-category"><option value="">All findings</option></select></div><div class="field"><label for="health-state">Show</label><select id="health-state"><option value="active">Needs review</option><option value="snoozed">Snoozed</option></select></div></div><div id="health-counts" class="health-counts"></div><div id="health-list" aria-live="polite">Checking documentation…</div><details class="session-step"><summary>Review settings & how checks work</summary><form id="health-settings"><div class="field"><label for="health-days">Remind me to review verification after this many days</label><input id="health-days" type="number" min="1" max="730" required value="90"></div><p class="connection-help">Uses each verified note’s recorded verification date. Defaults to 90 days. This reminder does not change a note’s status.</p><button class="button small" type="submit">Save review interval</button></form><p id="health-notice"></p><p>Open questions use explicit TODO / FIXME / TBD markers, unchecked tasks, and populated “Open questions,” “Unknowns,” “Unresolved issues,” or “Gaps and uncertainties” sections. Examples, archived notes, and superseded repository snapshots are excluded. Snoozed findings reappear when their evidence changes.</p></details></section><div id="tool-status" aria-live="polite"></div>`;
    let result;
    async function refresh(){await host.refreshDocuments();if(!$('#health-project'))return;result=await api('/api/documentation-health?project_id='+encodeURIComponent($('#health-project').value));if(!$('#health-list'))return;
      const category=$('#health-category').value;$('#health-category').innerHTML='<option value="">All findings</option>'+Object.entries(result.categories).map(([id,label])=>`<option value="${esc(id)}"${id===category?' selected':''}>${esc(label)}</option>`).join('');$('#health-days').value=result.review_days;$('#health-notice').textContent=result.notice;draw();}
    function draw(){
      const category=$('#health-category').value,snoozed=$('#health-state').value==='snoozed';
      const visible=result.items.filter(i=>i.snoozed===snoozed&&(!category||i.category===category));
      $('#health-counts').innerHTML=`<strong>${result.items.filter(i=>!i.snoozed).length} findings need review</strong><span>${result.items.filter(i=>i.snoozed).length} snoozed · Multiple findings can refer to the same note.</span>`;
      $('#health-list').innerHTML=visible.map(i=>`<article class="health-item"><div><span class="tag ${i.priority===1?'health-urgent':''}">${esc(i.label)}</span><h2>${esc(i.title)}</h2><p>${esc(i.reason)}</p>${i.snoozed?`<small>Snoozed until ${esc(date(i.until))}</small>`:''}</div><div class="health-actions">${i.target.kind==='document'?docLink(i.target.id,'Review note'):`<a class="button small" href="#skills">Review / rebuild skill</a>${(i.target.source_ids||[]).map(id=>docLink(id,host.docs().find(d=>d.id===id)?.title||id)).join('')}`}<button class="button small" data-snooze="${esc(i.id)}" data-days="${i.snoozed?0:7}">${i.snoozed?'Review now':'Snooze 7 days'}</button></div></article>`).join('')||notice(snoozed?'No snoozed findings in this view.':'No findings in this view. Automated checks cannot establish that every note is correct.');
      root.querySelectorAll('[data-snooze]').forEach(b=>b.addEventListener('click',()=>run(b,async()=>{const item=result.items.find(i=>i.id===b.dataset.snooze);await post('/api/documentation-health/snooze',{id:item.id,fingerprint:item.fingerprint,days:Number(b.dataset.days)});await refresh();})));
    }
    $('#health-project').addEventListener('change',event=>run(event.target,refresh));$('#health-category').addEventListener('change',()=>result&&draw());$('#health-state').addEventListener('change',()=>result&&draw());
    $('#health-settings').addEventListener('submit',event=>{event.preventDefault();run(event.submitter,async()=>{await post('/api/documentation-health/configure',{review_days:Number($('#health-days').value)});await refresh();toast('Review interval saved.');});});
    await refresh();
  }
  return {history,ask,health};
};
