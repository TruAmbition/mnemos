/* Local, dependency-free knowledge graph. No invented edges or external requests. */
(function(root){
  'use strict';
  const kinds={project:['Project','#b39aff',22],repository:['Repository','#54d9f2',17],'skill-package':['Built skill','#f8c568',15],skill:['Skill note','#f8c568',13],workflow:['Workflow','#ed8bdb',15],runbook:['Runbook','#6fe0ad',10],knowledge:['Knowledge item','#8ebaff',9],troubleshooting:['Troubleshooting','#ff8994',11],decision:['Decision','#d0a4fb',10],'work-log':['Work log','#c6d1df',8],microtask:['Microtask','#91e4d1',8],context:['Context','#8dc6e8',10],flow:['Flow','#f2ab84',12]};
  const style=kind=>kinds[kind]||['Document','#b1c7e2',9];
  const radius=node=>Math.min(30,style(node.kind)[2]+Math.sqrt(node.connections||0)*1.7);
  const hash=text=>{let n=2166136261;for(const c of String(text)){n^=c.charCodeAt(0);n=Math.imul(n,16777619);}return n>>>0;};
  function filter(graph,{query='',kind='all',project='all',focus=null,limit=500}={}){
    const adjacent=new Set([focus]);
    if(focus)for(const e of graph.edges){if(e.source===focus)adjacent.add(e.target);if(e.target===focus)adjacent.add(e.source);}
    let nodes=graph.nodes.filter(n=>(kind==='all'||n.kind===kind)&&(project==='all'||(n.project_ids||[]).includes(project))&&(!focus||adjacent.has(n.id))&&(!query||`${n.label} ${n.summary||''}`.toLowerCase().includes(query.toLowerCase())));
    const total=nodes.length;
    nodes=nodes.slice().sort((a,b)=>(b.id===focus)-(a.id===focus)||(b.connections||0)-(a.connections||0)||a.id.localeCompare(b.id)).slice(0,limit);
    const ids=new Set(nodes.map(n=>n.id));
    const edges=graph.edges.filter(e=>ids.has(e.source)&&ids.has(e.target));
    return {nodes,edges,total,limited:total>nodes.length};
  }
  // Derive colors from the full catalog so filtering never reassigns a project's color.
  function colorScheme(graph,mode='type',catalog=graph){
    const palette=['#b39aff','#54d9f2','#f8c568','#6fe0ad','#ff8994','#8ebaff','#ed8bdb','#f2ab84','#91e4d1','#d0a4fb','#d3df8a','#9db1e3'];
    const projects=catalog.nodes.filter(n=>n.kind==='project').slice().sort((a,b)=>a.id.localeCompare(b.id));
    const entries=new Map(projects.map((n,i)=>[n.project_id||(n.project_ids||[])[0]||n.id,{key:n.project_id||(n.project_ids||[])[0]||n.id,label:n.label,color:palette[i]||`hsl(${Math.round(i*137.508)%360} 65% 72%)`} ]));
    const shared={key:'shared',label:'Shared across projects',color:'#cbd5e1'},unassigned={key:'unassigned',label:'No project assigned',color:'#8494aa'};
    function entry(node){
      if(mode!=='project'){const [label,color]=style(node.kind);return {key:node.kind,label,color};}
      const ids=[...new Set(node.kind==='project'?[node.project_id||(node.project_ids||[])[0]||node.id]:(node.project_ids||[]))];
      if(ids.length>1)return shared;
      return entries.get(ids[0])||unassigned;
    }
    const legend=[...new Map(graph.nodes.map(n=>{const e=entry(n);return [e.key,e];})).values()].sort((a,b)=>a.label.localeCompare(b.label));
    return {entry,legend};
  }
  function constrain(point,brain){
    if(!brain){point.x=Math.max(50,Math.min(950,point.x));point.y=Math.max(45,Math.min(655,point.y));return;}
    const cx=point.side?645:355,dx=(point.x-cx)/215,dy=(point.y-345)/260,n=Math.hypot(dx,dy);
    if(n>1){point.x=cx+dx/n*215;point.y=345+dy/n*260;}
    point.x=point.side?Math.max(515,point.x):Math.min(485,point.x);
  }
  function layout(graph,mode='brain',size=1){
    const brain=mode==='brain', counts=[0,0], index=new Map();
    const points=graph.nodes.slice().sort((a,b)=>a.id.localeCompare(b.id)).map(n=>{
      const side=hash(n.id)%2,i=counts[side]++,angle=i*2.399963+hash(n.id)%19,scale=Math.sqrt((hash(n.id)%900+80)/1000);
      const point={...n,side,x:(side?645:355)+Math.cos(angle)*195*scale,y:345+Math.sin(angle)*245*scale,r:radius(n)*size};
      point.homeX=point.x;point.homeY=point.y;index.set(n.id,point);return point;
    });
    for(let pass=0;pass<45;pass++){
      for(const e of graph.edges){const a=index.get(e.source),b=index.get(e.target);if(!a||!b)continue;const dx=b.x-a.x,dy=b.y-a.y,dist=Math.hypot(dx,dy)||1,pull=Math.max(0,dist-160)*.003/Math.sqrt(Math.max(1,a.connections,b.connections));a.x+=dx/dist*pull;a.y+=dy/dist*pull;b.x-=dx/dist*pull;b.y-=dy/dist*pull;}
      for(let i=0;i<points.length;i++)for(let j=i+1;j<points.length;j++){
        const a=points[i],b=points[j];let dx=b.x-a.x,dy=b.y-a.y,d=Math.hypot(dx,dy),desired=a.r+b.r+17;
        if(d<desired){if(d<.01){dx=1;dy=.4;d=Math.hypot(dx,dy);}const push=(desired-d)*.34;a.x-=dx/d*push;a.y-=dy/d*push;b.x+=dx/d*push;b.y+=dy/d*push;}
      }
      for(const p of points){p.x+=(p.homeX-p.x)*.12;p.y+=(p.homeY-p.y)*.12;constrain(p,brain);}
    }
    return points;
  }
  const ns='http://www.w3.org/2000/svg';
  function el(name,attrs={},text){const node=document.createElementNS(ns,name);for(const [k,v]of Object.entries(attrs))node.setAttribute(k,String(v));if(text!==undefined)node.textContent=text;return node;}
  function mount(container,graph,options={}){
    const svg=el('svg',{viewBox:'0 0 1000 700',role:'group','aria-label':'Knowledge brain. Select a node to inspect its recorded connections.',tabindex:0});
    const defs=el('defs');svg.append(defs);
    const gradients=new Map();
    function fill(color){
      if(!gradients.has(color)){
        const id='brain-orb-'+gradients.size,gradient=el('radialGradient',{id,cx:'32%',cy:'28%',r:'75%'});
        for(const [offset,value]of [['0%','#ffffff'],['20%',color],['100%','#182742']])gradient.append(el('stop',{offset,'stop-color':value}));
        defs.append(gradient);gradients.set(color,id);
      }
      return `url(#${gradients.get(color)})`;
    }
    const viewport=el('g');svg.append(viewport);
    const outlines=el('g',{'aria-hidden':'true',class:'brain-contours'});viewport.append(outlines);
    if(options.mode!=='network'){
      const outer='M486 118 C465 68 420 66 389 87 C340 57 297 86 284 113 C231 96 187 136 190 177 C141 193 121 234 142 275 C105 313 120 366 149 388 C122 436 156 482 191 491 C188 546 237 577 276 562 C301 614 352 615 381 590 C427 614 472 582 486 542 Z';
      outlines.append(el('path',{d:outer}),el('path',{d:outer,transform:'translate(1000 0) scale(-1 1)'}));
      const folds=['M389 87 C365 140 420 153 454 174 C482 202 437 240 407 219','M284 113 C325 148 268 187 235 199 C212 232 238 264 277 255','M142 275 C195 286 188 342 230 346 C276 351 291 310 324 319','M191 491 C243 469 220 421 261 405 C297 397 321 430 352 419','M276 562 C307 524 357 542 382 507 C403 473 376 441 394 409','M486 284 C431 265 410 298 418 334 C430 372 465 374 486 363','M337 189 C371 217 341 249 342 274','M149 388 C178 377 199 401 193 430','M486 542 C452 523 431 553 433 579'];
      for(const d of folds)outlines.append(el('path',{d,class:'brain-fold'}),el('path',{d,class:'brain-fold',transform:'translate(1000 0) scale(-1 1)'}));
    }
    const points=layout(graph,options.mode,options.size||1),indexed=new Map(points.map(p=>[p.id,p]));
    const lines=el('g',{'aria-hidden':'true',class:'brain-edges'});viewport.append(lines);
    for(const e of graph.edges){const a=indexed.get(e.source),b=indexed.get(e.target);if(!a||!b)continue;const path=el('path',{d:`M${a.x} ${a.y} Q${(a.x+b.x)/2} ${(a.y+b.y)/2-18} ${b.x} ${b.y}`,class:'brain-edge',stroke:style(a.kind)[1]});path.dataset.source=e.source;path.dataset.target=e.target;lines.append(path);}
    const orbs=el('g');viewport.append(orbs);
    const choose=id=>{options.onSelect?.(id);highlight(id);};
    for(const p of points){
      const g=el('g',{transform:`translate(${p.x} ${p.y})`,class:'brain-node',role:'button',tabindex:0,'aria-label':`${p.label}, ${style(p.kind)[0]}, ${p.connections||0} connections`});g.dataset.id=p.id;
      g.append(el('title',{},`${p.label} · ${style(p.kind)[0]}`),el('circle',{r:p.r+7,fill:style(p.kind)[1],opacity:.12,class:'brain-halo'}),el('circle',{r:p.r,fill:fill(style(p.kind)[1]),stroke:style(p.kind)[1],'stroke-width':1.2}));
      const label=el('text',{y:p.r+20,'text-anchor':'middle',class:'brain-node-label'},p.label.length>32?p.label.slice(0,30)+'…':p.label);
      if(!options.labels && !['project','repository'].includes(p.kind))label.classList.add('brain-label-quiet');g.append(label);
      g.addEventListener('click',()=>choose(p.id));g.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();choose(p.id);}});
      g.addEventListener('mouseenter',()=>highlight(p.id));g.addEventListener('mouseleave',()=>highlight(selected));
      g.addEventListener('focus',()=>highlight(p.id));g.addEventListener('blur',()=>highlight(selected));orbs.append(g);
    }
    let selected=options.selected||null,zoom=1,panX=0,panY=0,drag=null;
    function transform(){viewport.setAttribute('transform',`translate(${panX} ${panY}) translate(500 350) scale(${zoom}) translate(-500 -350)`);}
    function highlight(id){const adjacent=new Set([id]);for(const e of graph.edges){if(e.source===id)adjacent.add(e.target);if(e.target===id)adjacent.add(e.source);}
      for(const n of orbs.children){n.classList.toggle('brain-dim',!!id&&!adjacent.has(n.dataset.id));n.classList.toggle('brain-selected',n.dataset.id===id);}
      for(const line of lines.children){line.classList.toggle('brain-edge-active',line.dataset.source===id||line.dataset.target===id);line.classList.toggle('brain-dim',!!id&&line.dataset.source!==id&&line.dataset.target!==id);}
    }
    function changeZoom(factor){zoom=Math.max(.45,Math.min(3.2,zoom*factor));transform();}
    svg.addEventListener('wheel',e=>{e.preventDefault();changeZoom(e.deltaY<0?1.08:1/1.08);},{passive:false});
    svg.addEventListener('pointerdown',e=>{if(e.target.closest('.brain-node'))return;drag={x:e.clientX,y:e.clientY,panX,panY};svg.setPointerCapture(e.pointerId);});
    svg.addEventListener('pointermove',e=>{if(!drag)return;const box=svg.getBoundingClientRect(),scale=Math.min(box.width/1000,box.height/700);panX=drag.panX+(e.clientX-drag.x)/scale;panY=drag.panY+(e.clientY-drag.y)/scale;transform();});
    svg.addEventListener('pointerup',()=>drag=null);svg.addEventListener('pointercancel',()=>drag=null);
    svg.addEventListener('keydown',e=>{if(e.target!==svg)return;if(e.key==='+'||e.key==='='){changeZoom(1.15);e.preventDefault();}else if(e.key==='-'){changeZoom(1/1.15);e.preventDefault();}else if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key)){e.preventDefault();panX+=e.key==='ArrowLeft'?30:e.key==='ArrowRight'?-30:0;panY+=e.key==='ArrowUp'?30:e.key==='ArrowDown'?-30:0;transform();}});
    function setColors(scheme){
      for(const n of orbs.children){const point=indexed.get(n.dataset.id),entry=scheme.entry(point),circles=n.querySelectorAll('circle');
        circles[0].setAttribute('fill',entry.color);circles[1].setAttribute('fill',fill(entry.color));circles[1].setAttribute('stroke',entry.color);
        n.querySelector('title').textContent=`${point.label} · ${style(point.kind)[0]} · ${entry.label}`;
        n.setAttribute('aria-label',`${point.label}, ${style(point.kind)[0]}, ${point.connections||0} connections, color: ${entry.label}`);
      }
      for(const line of lines.children)line.setAttribute('stroke',scheme.entry(indexed.get(line.dataset.source)).color);
    }
    container.replaceChildren(svg);setColors(options.colors||colorScheme(graph));highlight(selected);
    return {setColors,select(id){selected=id;highlight(id);},zoomIn(){changeZoom(1.2);},zoomOut(){changeZoom(1/1.2);},reset(){zoom=1;panX=panY=0;transform();},destroy(){container.replaceChildren();}};
  }
  const api={kinds,style,radius,filter,layout,colorScheme,mount};
  if(typeof module==='object'&&module.exports)module.exports=api;else root.MnemosBrain=api;
})(typeof window==='undefined'?globalThis:window);
