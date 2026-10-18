/* Mnemos setup runs only against the loopback setup API. No third-party requests. */
(() => {
  'use strict';
  const $ = selector => document.querySelector(selector);
  const escape = value => String(value ?? '').replace(/[&<>"']/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]));
  const labels = ['Your vault','Your backups','Your assistant','Review & create'];
  const modes = {
    local: {title:'Local assistant',description:'Use an assistant on this computer with permitted file access and tools.',detail:'Portable skills guide capture, recall, and documented workflows. Skills do not grant file access by themselves.'},
    handoff: {title:'Cloud file handoff',description:'Work in ChatGPT, Claude, or another cloud chat by exchanging files.',detail:'Choose source documents, download a context pack, attach it to your chat, and import the returned draft. No tunnel or account connection is needed.'},
    connected: {title:'Connected assistant · optional',description:'Use an optional OpenAI tunnel for direct ChatGPT access to this vault.',detail:'ChatGPT can recall current notes and save drafts without file transfers. Read the benefits and tradeoffs below. Setup only records your preference; it does not start or stop a connection.'},
  };
  const state = {step:0,info:null,result:null,values:null,busy:false,commandTab:'codex',commandPanelOpen:false};
  let toastTimer;
  const note = (text,kind='') => `<div class="notice ${kind}"><span>${escape(text)}</span></div>`;
  async function request(method='GET',payload) {
    const response=await fetch('/api/setup',{method,credentials:'same-origin',headers:payload?{'Content-Type':'application/json'}:{},...(payload?{body:JSON.stringify(payload)}:{})});
    let result;try{result=await response.json();}catch{throw new Error('The local setup service returned an unreadable response.');}
    if(!response.ok)throw new Error(result.error||`Setup request failed (${response.status}).`);
    return result;
  }
  function defaults(info) {
    return {data_path:info.data_path||'',author:info.author||'Local engineer',backup:{provider:info.backup?.provider==='rclone'?'rclone':'local',destination:info.backup?.destination||'',remote:info.backup?.remote||''},assistant_mode:['local','handoff','connected'].includes(info.assistant_mode)?info.assistant_mode:'local',install_obsidian:!info.obsidian?.installed};
  }
  function payloadFor(values) {
    return {data_path:String(values.data_path||'').trim(),author:String(values.author||'').trim(),backup:{provider:values.backup.provider==='rclone'?'rclone':'local',destination:String(values.backup.destination||'').trim(),remote:String(values.backup.remote||'').trim()},assistant_mode:['local','handoff','connected'].includes(values.assistant_mode)?values.assistant_mode:'local',install_obsidian:values.install_obsidian===true};
  }
  function relocateDefaultBackup(previous, next, destination) {
    const normalized=value=>String(value||'').replace(/\\/g,'/').replace(/\/+$/,'');
    if(normalized(destination)!==normalized(previous)+'/backups')return destination;
    const separator=String(next).includes('\\')&&!String(next).includes('/')?'\\':'/';
    return String(next).replace(/[\\/]+$/,'')+separator+'backups';
  }
  function toast(message) {
    clearTimeout(toastTimer);$('#setup-toast').textContent=message;$('#setup-toast').hidden=false;toastTimer=setTimeout(()=>{$('#setup-toast').hidden=true;},5000);
  }
  async function copy(text) {
    try{await navigator.clipboard.writeText(text);toast('Copied. Use this in the indicated assistant or terminal.');}
    catch{const input=document.createElement('textarea');input.value=text;input.style.cssText='position:fixed;left:-9999px';document.body.append(input);input.select();const success=document.execCommand('copy');input.remove();toast(success?'Copied.':'Select the displayed text and copy it manually.');}
  }
  function progress() {
    $('#setup-progress').innerHTML=labels.map((label,index)=>`<li class="${state.result||index<state.step?'complete':index===state.step?'current':''}"${index===state.step&&!state.result?' aria-current="step"':''}><span>${state.result||index<state.step?'✓':String(index+1).padStart(2,'0')}</span><div>${label}${index===0?'<small>A separate space for your knowledge</small>':index===1?'<small>A copy, where you choose</small>':index===2?'<small>Local tools or a file handoff</small>':'<small>Your choices, before anything changes</small>'}</div></li>`).join('');
  }
  function heading(title,description) {
    return `<div class="setup-heading"><span class="eyebrow">STEP ${state.step+1} OF 4</span><h2>${title}</h2><p>${description}</p></div>`;
  }
  function buttons() {
    return `<div class="setup-actions">${state.step?'<button class="button secondary" type="button" data-action="back">← Back</button>':'<span>Nothing is saved until you apply.</span>'}<button class="button primary" type="submit">${state.step===3?'Apply this setup':'Continue'} <span aria-hidden="true">→</span></button></div>`;
  }
  function tunnelComparison() {
    return `<section class="setup-tunnel-choice" aria-labelledby="tunnel-choice-title"><h3 id="tunnel-choice-title">Is a ChatGPT tunnel worth it?</h3><p>Start without one for local tools or occasional cloud file handoffs. Choose a tunnel for frequent direct ChatGPT use when your organization permits it.</p><div class="setup-tunnel-columns"><div><h4>What you gain</h4><ul><li>Recall current vault notes and save drafts directly from ChatGPT.</li><li>Skip repeated exports and imports. Your local server needs no public address or inbound internet port.</li></ul></div><div><h4>What you take on</h4><ul><li>The computer must stay awake, online, and running the tunnel client.</li><li>Runtime key maintenance, connection troubleshooting, and any workplace approvals.</li><li>Requested note content travels to OpenAI for cloud processing.</li></ul></div></div><p class="setup-tunnel-scope"><strong>Access in this version:</strong> the connector can read every note in its dedicated vault, including drafts. It can create notes and update existing notes with a matching revision; saves remain drafts. Website reader restrictions do not limit this connector.</p><p><strong>Without a tunnel:</strong> local assistants still connect directly; cloud chats use files you explicitly share. Local assistants may also use cloud models. A tunnel adds neither backups nor automatic task execution, and does not guarantee token savings.</p><p class="setup-tunnel-source">This OpenAI connection does not connect Claude. Stopping the client stops future local calls; content already shared in chats remains there. <a href="https://developers.openai.com/api/docs/guides/secure-mcp-tunnels" target="_blank" rel="noopener noreferrer">Official tunnel guide ↗</a></p></section>`;
  }
  function render() {
    progress();if(state.result){renderSuccess();return;}
    const v=state.values;
    let content='';
    if(state.step===0){
      content=heading('A space of your own.','Choose where your engineering knowledge belongs. Mnemos keeps this vault separate from your other Obsidian workspaces.')+
        `${state.info.initialized?note('An existing Mnemos setup was found. Your documents and access tokens are preserved when updating its settings.'):''}<div class="field"><label for="setup-author">Your name or author identity</label><input id="setup-author" name="author" required maxlength="120" autocomplete="name" value="${escape(v.author)}" placeholder="e.g. Alex Morgan"><small>This identity is attached to work you document locally.</small></div><div class="field"><label for="setup-folder">Dedicated data folder</label><input id="setup-folder" name="data_path" required value="${escape(v.data_path)}" placeholder="/absolute/path/to/Mnemos"><small>Use a separate folder for Mnemos. Your notes, configuration, and vault will live here.</small></div><div class="setup-detection"><span class="setup-app-mark" aria-hidden="true">◇</span><div><strong>Obsidian</strong><p>${state.info.obsidian?.installed?'Detected on this computer. Mnemos will use its own dedicated vault.':'Obsidian was not detected. You can install it as part of this setup.'}</p></div><span class="status ${state.info.obsidian?.installed?'verified':'draft'}">${state.info.obsidian?.installed?'Detected':'Not detected'}</span></div>${!state.info.obsidian?.installed?`<label class="setup-check"><input name="install_obsidian" type="checkbox"${v.install_obsidian?' checked':''}><span><strong>Install Obsidian during setup</strong><small>The installer may take a few minutes or require an operating-system prompt. Your vault can still be created if installation needs a follow-up.</small></span></label>`:''}`;
    }else if(state.step===1){
      content=heading('A second copy. Peace of mind.','Choose a backup destination for your vault. You can change it later in Settings.')+
        `<div class="backup-choice"><label><input type="radio" name="provider" value="local"${v.backup.provider==='local'?' checked':''}><span><strong>Local folder</strong><small>A backup drive, mounted volume, or folder.</small></span></label><label><input type="radio" name="provider" value="rclone"${v.backup.provider==='rclone'?' checked':''}><span><strong>Cloud via rclone</strong><small>A remote you have already configured.</small></span></label></div><div class="field" id="setup-local-field"${v.backup.provider==='rclone'?' hidden':''}><label for="setup-backup-folder">Backup folder</label><input id="setup-backup-folder" name="destination" value="${escape(v.backup.destination)}" placeholder="/absolute/path/to/Mnemos-backups"><small>Choose a folder outside the vault. A separate device protects against failure of this computer.</small></div><div class="field" id="setup-cloud-field"${v.backup.provider!=='rclone'?' hidden':''}><label for="setup-remote">Configured rclone remote</label><input id="setup-remote" name="remote" value="${escape(v.backup.remote)}" placeholder="myremote:mnemos-backups"><small>Configure authentication in rclone first. Mnemos uses that existing connection; no cloud password belongs in this field.</small></div>${note('This sets the backup destination. Create a backup from Settings after setup. Backups do not run automatically unless you separately configure a schedule.')}`;
    }else if(state.step===2){
      content=heading('Work with the assistant you use.','Start with a local assistant or a simple cloud file handoff. Your knowledge stays portable either way.')+
        `<div class="setup-mode-options">${Object.entries(modes).map(([id,mode])=>`<label class="setup-mode"><input type="radio" name="assistant_mode" value="${id}"${v.assistant_mode===id?' checked':''}><span><strong>${mode.title}${id==='handoff'?'<span class="example-tag">No tunnel</span>':''}</strong><span class="mode-description">${mode.description}</span><small>${mode.detail}</small></span></label>`).join('')}</div>${tunnelComparison()}<div class="setup-link-note"><span aria-hidden="true">↗</span><p>Obsidian links remain ordinary <code>[[wikilinks]]</code> in your notes. Keep connecting ideas and use Obsidian’s graph as your library grows.</p></div>`;
    }else{
      content=heading('Make sure it feels right.','Review the actual choices below. Apply creates or updates this dedicated Mnemos setup.')+
        `<dl class="setup-review"><div><dt>Author</dt><dd>${escape(v.author)}</dd></div><div><dt>Data folder</dt><dd class="mono">${escape(v.data_path)}</dd></div><div><dt>Backup type</dt><dd>${v.backup.provider==='rclone'?'Cloud via rclone':'Local folder'}</dd></div><div><dt>Backup destination</dt><dd class="mono">${escape(v.backup.provider==='rclone'?v.backup.remote:v.backup.destination)}</dd></div><div><dt>Obsidian</dt><dd>${state.info.obsidian?.installed?'Use the existing installation':v.install_obsidian?'Install during setup':'Set up the vault; install Obsidian later'}</dd></div><div><dt>Assistant workflow</dt><dd>${modes[v.assistant_mode].title}</dd></div></dl>${note(v.assistant_mode==='handoff'?'Cloud handoff exchanges only files you choose. Setup does not upload your documents or connect a cloud account.':v.assistant_mode==='connected'?'Connected mode is a preference only; it does not start or stop an existing tunnel. Once configured and running, ChatGPT can read all notes in this dedicated vault, including drafts, and create or update draft notes. Returned content is processed in the cloud. Keep the computer and client running, maintain the runtime key, and follow workplace policy.':'Local skills require an assistant with permitted access to the vault and the tools needed for the requested work.')}<div class="setup-review-foot"><span aria-hidden="true">◇</span><span>Your existing Obsidian vaults remain separate. New captures start as drafts for review. Changing this preference does not enable or disable an existing tunnel.</span></div>`;
    }
    $('#setup-content').innerHTML=`<form id="setup-form">${content}<div id="setup-error" aria-live="polite"></div>${buttons()}</form>`;
    $('#setup-form').addEventListener('submit',next);
    $('#setup-form').addEventListener('change',event=>{if(event.target.name==='provider'){$('#setup-local-field').hidden=event.target.value==='rclone';$('#setup-cloud-field').hidden=event.target.value!=='rclone';}});
  }
  function collect() {
    const form=$('#setup-form');const data=new FormData(form);
    if(state.step===0){
      const previous=state.values.data_path;state.values.author=String(data.get('author')||'').trim();state.values.data_path=String(data.get('data_path')||'').trim();state.values.install_obsidian=!state.info.obsidian?.installed&&data.get('install_obsidian')==='on';
      if(state.values.data_path!==previous)state.values.backup.destination=relocateDefaultBackup(previous,state.values.data_path,state.values.backup.destination);
    }else if(state.step===1){state.values.backup={provider:data.get('provider'),destination:String(data.get('destination')||'').trim(),remote:String(data.get('remote')||'').trim()};}
    else if(state.step===2)state.values.assistant_mode=data.get('assistant_mode');
  }
  function validateStep() {
    if(!$('#setup-form').reportValidity())return false;
    if(state.step===0&&(!state.values.author||!state.values.data_path)){showError('Enter an author and dedicated data folder.');return false;}
    if(state.step===1){
      if(state.values.backup.provider==='local'&&!state.values.backup.destination){showError('Choose a local backup folder.');return false;}
      if(state.values.backup.provider==='rclone'&&!/^[A-Za-z0-9_-]+:[^\x00-\x1f]+$/.test(state.values.backup.remote)){showError('Enter a configured remote and folder, such as myremote:mnemos-backups.');return false;}
    }
    return true;
  }
  function showError(message) {$('#setup-error').innerHTML=note(message,'error');}
  async function next(event) {
    event.preventDefault();if(state.busy)return;collect();if(!validateStep())return;
    if(state.step<3){state.step++;render();$('#setup-main').focus();window.scrollTo({top:0,behavior:'smooth'});return;}
    state.busy=true;const form=$('#setup-form');for(const button of form.querySelectorAll('button'))button.disabled=true;
    $('#setup-error').innerHTML=`<div class="setup-pending" role="status"><span class="loader"></span><div><strong>Preparing your knowledge workspace…</strong><p>${state.values.install_obsidian?'Installing Obsidian can take a few minutes. Keep this page open until setup finishes.':'Creating the dedicated vault and saving your choices.'}</p></div></div>`;
    try{state.result=await request('POST',payloadFor(state.values));state.info=state.result;render();$('#setup-main').focus();}
    catch(error){showError(error.message);for(const button of form.querySelectorAll('button'))button.disabled=false;}
    finally{state.busy=false;}
  }
  function renderSuccess() {
    const result=state.result;
    const warnings=Array.isArray(result.warnings)?result.warnings:[];
    const installFailed=result.obsidian?.status==='failed';
    const commandShell=result.command_shell==='powershell'?'PowerShell':'Terminal';
    const projectExample=result.command_shell==='powershell'?"--project 'C:\\path\\to\\your-project'":"--project '/absolute/path/to/your-project'";
    const commandLabels={codex:'Codex',claude_code:'Claude Code',claude_desktop:'Claude Desktop',chatgpt:'Optional tunnel'};
    const commands=Object.entries(result.commands||{}).filter(([key,value])=>typeof value==='string'&&value.trim()&&(key!=='chatgpt'||result.assistant_mode==='connected'));
    if(!commands.some(([key])=>key===state.commandTab))state.commandTab=commands[0]?.[0]||'';
    const libraryURL=result.library_url==='/'?'/':result.library_url?.startsWith('/')&&!result.library_url.startsWith('//')?result.library_url:'/';
    $('#setup-content').innerHTML=`<div class="setup-success"><span class="setup-success-mark">✓</span><span class="eyebrow">YOUR WORKSPACE IS READY</span><h2>A place for your next good idea.</h2><p>Your Mnemos vault is ready. Capture a completed task, bring context into a cloud chat, or connect a local assistant.</p></div>${installFailed?note(result.obsidian.error||'The vault is ready, but Obsidian installation did not complete. Follow up with the installer before opening the vault in Obsidian.','error'):''}${warnings.filter(warning=>warning!==result.obsidian?.error).map(warning=>note(String(warning))).join('')}<div class="setup-result-path"><span class="field-label">Your dedicated data folder</span><code>${escape(result.data_path||state.values.data_path)}</code><div><span>Obsidian</span><strong>${result.obsidian?.installed?'Installed':installFailed?'Installation needs attention':'Not installed'}</strong></div></div>${result.assistant_mode==='connected'?tunnelComparison():''}${result.assistant_mode==='handoff'?note('Cloud file handoff is your selected workflow: choose approved context, download a pack, and attach it to your cloud chat yourself. No tunnel is needed.'):''}<div class="setup-success-actions"><a class="button primary" href="${escape(libraryURL)}">Open your library →</a><a class="button" href="${escape(libraryURL)}#handoff">Cloud file handoff ↗</a><a class="button" href="/api/skills/export" download="mnemos-skills.zip">Download skills ZIP ↓</a></div>${commands.length?`<${result.assistant_mode==='handoff'?'details':'section'} class="setup-command-panel"${result.assistant_mode==='handoff'&&state.commandPanelOpen?' open':''}>${result.assistant_mode==='handoff'?'<summary>Optional local assistant setup</summary>':'<h3>Set up your assistant</h3>'}<p>Use the exact instructions returned by your local setup service. A local skill needs an assistant with permitted filesystem access and tools.</p><p class="setup-project-guidance">Codex and Claude Code commands install into the Mnemos toolkit project by default. To choose another repository, append <code>${escape(projectExample)}</code> before running the command.</p><div class="editor-tabs">${commands.map(([key])=>`<button class="${state.commandTab===key?'active':''}" type="button" data-command-tab="${escape(key)}">${escape(commandLabels[key]||key)}</button>`).join('')}</div><span class="setup-shell-label">${commandShell}</span><div class="setup-command"><pre id="setup-command-text">${escape(result.commands[state.commandTab])}</pre><button class="button small" type="button" data-action="copy-command">Copy</button></div></${result.assistant_mode==='handoff'?'details':'section'}>`:''}<div class="setup-link-note"><span aria-hidden="true">◇</span><p>${escape(result.assistant_mode==='connected'?'Your connected-assistant preference is saved. Complete the separately documented authentication and hosting steps before using remote access.':result.assistant_mode==='handoff'?'Cloud handoff is ready: choose approved context, attach the downloaded pack to your cloud chat, then review the returned draft before saving.':'Start with a small completed task. Capture the goal, changes, evidence, and the next repeatable step.')}</p></div>`;
  }
  document.addEventListener('click',event=>{
    const button=event.target.closest('button');if(!button)return;
    if(button.dataset.action==='back'&&!state.busy){collect();state.step=Math.max(0,state.step-1);render();$('#setup-main').focus();}
    if(button.dataset.action==='retry')load();
    if(button.dataset.commandTab){state.commandTab=button.dataset.commandTab;state.commandPanelOpen=true;renderSuccess();}
    if(button.dataset.action==='copy-command')copy(state.result?.commands?.[state.commandTab]||'');
  });
  window.addEventListener('beforeunload',event=>{if(state.busy){event.preventDefault();event.returnValue='';}});
  async function load() {
    try{state.info=await request();state.values=defaults(state.info);render();}
    catch(error){$('#setup-content').innerHTML=`<div class="setup-heading"><span class="eyebrow">LOCAL SETUP</span><h2>Open setup on this computer.</h2><p>This wizard is available through the local Mnemos setup service. Shared and authenticated servers keep setup controls disabled.</p></div>${note(error.message,'error')}<button class="button" data-action="retry">Try again</button>`;}
  }
  load();
})();
