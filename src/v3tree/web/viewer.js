/* Content-tree viewer: a two-sided tidy tree in SVG. No external libraries.
   CTViewer.init({L, editable, onJudge}) once, then CTViewer.load(data, keepView) for each graph. */
window.CTViewer = (function(){
'use strict';
let L = {};
const t = (k, o) => { let s = (k in L) ? L[k] : k; if(o) for(const x in o) s = s.split('{'+x+'}').join(o[x]); return s; };
const NW = 214, NH = 44, GX = 150, GY = 22, COLW = NW + GX, ROWH = NH + GY;
// compact layout: wrap siblings once they stack taller than WRAP_MIN_H; gap between wrapped columns; target width/height
const WRAP_MIN_H = 6 * ROWH, WRAP_GAP = 40, ASPECT = 1.6;   // ASPECT is used when the window size is unknown
const COLORS = {je:'#d64545',button:'#ef8a2b',bar:'#c9a227',event:'#3b7dd8',decision:'#9b59b6',law:'#1aa38c',dp:'#b0446e',
  wargoal:'#b0446e',modifier:'#5f9a32',var:'#8a8f98',gvar:'#6f747d',onaction:'#21a9b6',seffect:'#5b6ee1',strigger:'#8e7cc3',
  svalue:'#8e7cc3',tag:'#a0522d',chartemplate:'#c4627a',customloc:'#7a8a99',history:'#555b66',culture:'#8d6e63',pop:'#8d6e63',
  movement:'#777',diplaction:'#777'};
const GROUPS = ['je','button','bar','event','decision','law','dp','modifier','var','onaction','seffect','strigger','tag','chartemplate','other'];
const TPRI = {je:0,event:1,button:2,bar:3,decision:4,dp:5,wargoal:5,onaction:6,seffect:7,strigger:8,svalue:9,modifier:10,law:11,var:12,gvar:12,tag:13,chartemplate:14};
const KPRI = {struct:0,call:1,cond:2,soft:3};
function grp(ty){ if(ty==='wargoal') return 'dp'; if(ty==='gvar') return 'var'; if(ty==='svalue') return 'strigger';
  return GROUPS.includes(ty) ? ty : 'other'; }
function groupLabel(g){ return L['ui.g.'+g] || L['type.'+g] || g; }
const NS = 'http://www.w3.org/2000/svg';
const $ = id => document.getElementById(id);
function el(tag,a,p){ const e=document.createElementNS(NS,tag); for(const k in a) e.setAttribute(k,a[k]); if(p) p.appendChild(e); return e; }
function cut(s,lim){ let w=0,o=''; for(const ch of String(s)){ w += /[⺀-￿]/.test(ch)?1:0.56; if(w>lim) return o+'…'; o+=ch; } return o; }
function esc(s){ return String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
function isDark(){ const a=document.documentElement.getAttribute('data-theme');
  return a==='dark' || (a!=='light' && matchMedia('(prefers-color-scheme: dark)').matches); }
function tint(hex,a){ const n=parseInt(hex.slice(1),16); const r=n>>16,g=(n>>8)&255,b=n&255; const base=isDark()?[33,34,39]:[255,255,255];
  return `rgb(${Math.round(base[0]+(r-base[0])*a)},${Math.round(base[1]+(g-base[1])*a)},${Math.round(base[2]+(b-base[2])*a)})`; }

let opts = {}, D = null, byKey, roots, outE, inE, parent, children, side, depth;
let POS = new Map(), curEdges = [], curVis = new Set(), box = {x0:0,y0:0,w:0,h:0};
const st = { types:new Set(GROUPS), labels:true, soft:true, boundary:true, disabled:false,
  collapsed:new Set(), sel:null, multi:new Set(), k:1, tx:40, ty:40, layout:'compact',
  focus:null };   // focus mode: {root, open:[...]}, or null for the whole map
try { const v=localStorage.getItem('v3tree.layout'); if(v==='tree'||v==='compact') st.layout=v; } catch(e){}
let svg, vp, gE, gN;

// ---------------- data
function expandable(n){ return n.v==='in' || (n.v==='unjudged' && !n.stopped); }
function buildTree(){
  byKey = new Map(D.nodes.map(n=>[n.k,n]));
  roots = D.meta.roots.filter(r=>byKey.has(r));
  outE = new Map(); inE = new Map();
  D.nodes.forEach(n=>{outE.set(n.k,[]);inE.set(n.k,[]);});
  D.edges.forEach((e,i)=>{ e.i=i; if(outE.has(e.s)) outE.get(e.s).push(e); if(inE.has(e.t)) inE.get(e.t).push(e); });
  parent = new Map(); children = new Map(); side = new Map(); depth = new Map();
  const q=[...roots]; const seen=new Set(roots); roots.forEach(r=>{side.set(r,0);depth.set(r,0);});
  while(q.length){ const c=q.shift();
    const cand=[...outE.get(c).map(e=>({o:e.t,d:'out',e})), ...inE.get(c).map(e=>({o:e.s,d:'in',e}))]
      .sort((a,b)=>(a.d===b.d?0:(a.d==='out'?-1:1)) || (KPRI[a.e.soft?'soft':a.e.k]-KPRI[b.e.soft?'soft':b.e.k]) ||
        ((TPRI[byKey.get(a.o).t]??20)-(TPRI[byKey.get(b.o).t]??20)) || String(byKey.get(a.o).name).localeCompare(String(byKey.get(b.o).name)));
    for(const {o,d} of cand){ if(seen.has(o)) continue; seen.add(o); parent.set(o,c);
      if(!children.has(c)) children.set(c,[]); children.get(c).push(o);
      side.set(o, side.get(c)===0 ? (d==='in'?-1:1) : side.get(c)); depth.set(o, depth.get(c)+1);
      if(expandable(byKey.get(o))) q.push(o); } }
  D.nodes.forEach(n=>{ if(!seen.has(n.k) && roots.length){ parent.set(n.k,roots[0]); side.set(n.k,1); depth.set(n.k,1);
    if(!children.has(roots[0])) children.set(roots[0],[]); children.get(roots[0]).push(n.k); } });
}
function hiddenByCollapse(){ const h=new Set(); for(const c of st.collapsed){ const stack=[...(children.get(c)||[])];
  while(stack.length){ const x=stack.pop(); if(h.has(x)) continue; h.add(x); (children.get(x)||[]).forEach(y=>stack.push(y)); } } return h; }
// ---------------- focus: a small tree of its own. It starts with one node and its neighbours; clicking a
// node opens its neighbours beside it, and what was opened before stays. st.focus = {root, open:[keys in the
// order they were opened]}; FT is the tree built from it, in the same shape the main map uses.
let FT = null;
function edgeShown(e){ return (st.soft||!e.soft) && (st.disabled || !e.flags.includes('disabled')); }
function nodeShown(n){ return st.types.has(grp(n.t)) && (!n.dis || st.disabled) && (n.v!=='boundary' || st.boundary); }
function nbrsOf(k){ const m=new Map();   // neighbour -> 'out' (k uses it), 'in' (it uses k) or 'both'
  for(const e of outE.get(k)||[]) if(edgeShown(e) && e.t!==k) m.set(e.t, m.get(e.t)==='in'?'both':(m.get(e.t)||'out'));
  for(const e of inE.get(k)||[]) if(edgeShown(e) && e.s!==k) m.set(e.s, m.get(e.s)==='out'?'both':(m.get(e.s)||'in'));
  return m; }
// a neighbour belongs to the opened node nearest the start; callers go left of the start, the rest right
function focusTree(){
  const f=st.focus, opened=new Set(f.open), seen=new Set([f.root]), q=[f.root];
  const T={roots:[f.root], children:new Map(), parent:new Map(), side:new Map([[f.root,0]]), opened, all:seen, more:new Set()};
  const ord=(a,b)=>((a.d==='in')-(b.d==='in')) || ((TPRI[byKey.get(a.o).t]??20)-(TPRI[byKey.get(b.o).t]??20)) ||
    String(byKey.get(a.o).name).localeCompare(String(byKey.get(b.o).name));
  while(q.length){ const c=q.shift(); if(!opened.has(c)) continue;
    const cand=[...nbrsOf(c)].map(([o,d])=>({o,d})).filter(x=>byKey.has(x.o)).sort(ord);
    for(const {o,d} of cand){ if(seen.has(o)) continue; seen.add(o); T.parent.set(o,c);
      if(!T.children.has(c)) T.children.set(c,[]); T.children.get(c).push(o);
      T.side.set(o, T.side.get(c)===0 ? (d==='in'?-1:1) : T.side.get(c)); q.push(o); } }
  // nodes that would add something if opened get a "+"
  for(const k of seen) if(!opened.has(k)) for(const o of nbrsOf(k).keys()) if(!seen.has(o)){ T.more.add(k); break; }
  return T; }
function treeSrc(){ return st.focus ? FT : {roots, children, parent, side}; }
function focusSubtree(k){ const out=[], stack=[k]; while(stack.length){ const x=stack.pop(); out.push(x); (FT.children.get(x)||[]).forEach(y=>stack.push(y)); } return out; }
function focusStart(k){ if(!byKey.has(k)) return; st.focus={root:k, open:[k]}; st.multi.clear(); draw(); syncFocusBar(); select(k); fitFocus(k); }
function focusOpen(k){ if(!st.focus || FT.opened.has(k) || !FT.all.has(k)) return; st.focus.open.push(k); draw(); syncFocusBar(); fitFocus(k); }
function focusClose(k){ if(!st.focus) return;
  if(k===st.focus.root){ focusExit(); return; }
  const drop=new Set(focusSubtree(k)); st.focus.open=st.focus.open.filter(x=>!drop.has(x));
  if(st.sel && drop.has(st.sel) && st.sel!==k){ st.sel=k; select(k); }
  draw(); syncFocusBar(); }
function focusBack(){ if(!st.focus) return; const o=st.focus.open;
  if(o.length<=1){ focusExit(); return; }
  const k=o.pop(); draw(); syncFocusBar(); if(st.sel && !FT.all.has(st.sel)) select(k); center(k); }
function focusExit(){ st.focus=null; FT=null; draw(); syncFocusBar(); if(st.sel && POS.has(st.sel)) center(st.sel); else fit(); }
// the bar shows the way from the start to the selected node; click a step to jump to it
function syncFocusBar(){ const fb=$('focusBar'); if(!fb) return;
  if(!st.focus){ fb.style.display='none'; return; }
  const cur = st.sel && FT && FT.all.has(st.sel) ? st.sel : st.focus.open[st.focus.open.length-1];
  const ch=[]; for(let x=cur; x; x=FT.parent.get(x)) ch.unshift(x);
  const arrow=(a,b)=>{ const o=(outE.get(a)||[]).some(e=>e.t===b), i=(inE.get(a)||[]).some(e=>e.s===b); return o&&i?'↔':(o?'→':'←'); };
  fb.innerHTML=`<b>${esc(t('ui.focus_title'))}</b> `+ch.map((k,i)=>(i?`<span class="ar">${arrow(ch[i-1],k)}</span>`:'')+
    `<a data-fk="${esc(k)}" class="${i===ch.length-1?'cur':''}">${esc(cut(byKey.get(k).name,18))}</a>`).join('')+
    ` <button data-fb="back" ${st.focus.open.length>1?'':'disabled'}>${esc(t('ui.focus_back'))}</button><button data-fb="exit">${esc(t('ui.focus_exit'))}</button>`+
    `<div class="muted">${esc(t('ui.focus_hint'))}</div>`;
  fb.style.display='block';
  fb.querySelectorAll('[data-fk]').forEach(a=>a.onclick=()=>{ select(a.dataset.fk); center(a.dataset.fk); syncFocusBar(); });
  fb.querySelector('[data-fb="back"]').onclick=focusBack; fb.querySelector('[data-fb="exit"]').onclick=focusExit; }
function bounds(){ let x0=Infinity,x1=-Infinity,y0=Infinity,y1=-Infinity;
  POS.forEach(p=>{ x0=Math.min(x0,p.x); x1=Math.max(x1,p.x+NW); y0=Math.min(y0,p.y); y1=Math.max(y1,p.y+NH); });
  if(!POS.size){ x0=y0=0; x1=y1=1; }
  return {x0,y0,w:x1-x0,h:y1-y0}; }

function visibleNodes(){
  if(st.focus){ FT=focusTree(); const vis=new Set([st.focus.root]);
    for(const k of FT.all){ const n=byKey.get(k); if(n && nodeShown(n)) vis.add(k); }
    return vis; }
  const hc=hiddenByCollapse(); const vis=new Set();
  for(const n of D.nodes){ if(hc.has(n.k)) continue; if(!st.types.has(grp(n.t))) continue;
    if(n.dis && !st.disabled) continue; if(n.v==='boundary' && !st.boundary) continue; vis.add(n.k); }
  roots.forEach(r=>vis.add(r)); return vis; }
function visibleEdges(vis){ return D.edges.filter(e=>vis.has(e.s)&&vis.has(e.t)&&(st.soft||!e.soft)&&(st.disabled || !e.flags.includes('disabled'))); }

// ---------------- layout: callers/readers of the root on the left, what it leads to on the right
function layout(vis){
  const {roots, children, parent, side} = treeSrc();   // the main map's tree, or the focus tree
  const vkids=new Map(); vis.forEach(k=>vkids.set(k,[]));
  const vpar=k=>{ let p=parent.get(k); while(p && !vis.has(p)) p=parent.get(p); return p; };
  const order=[], seenW=new Set();
  const walk=k=>{ if(seenW.has(k)) return; seenW.add(k); order.push(k); (children.get(k)||[]).forEach(walk); };
  roots.forEach(walk);
  for(const k of order){ if(!vis.has(k) || roots.includes(k)) continue; const p=vpar(k); if(p && vkids.has(p)) vkids.get(p).push(k); }
  POS=new Map();
  // Each node with its visible subtree is a block (w x h). A node sits at its block's top-left, its
  // children's blocks one column to the right. Tree layout stacks sibling blocks in one column.
  // Compact layout wraps them into several columns side by side once a column would grow taller
  // than H. One H serves the whole map; it is searched so the map comes out about window-shaped.
  const M=new Map(); let H=Infinity;
  const meas=k=>{ const ch=vkids.get(k);
    const m = ch.length ? (a=>({w:COLW+a.w, h:Math.max(ROWH,a.h), y:a.mid, kids:a.kids}))(pack(ch)) : {w:NW, h:ROWH, y:0, kids:[]};
    M.set(k,m); return m; };
  const pack=ch=>{ const bs=ch.map(c=>({k:c, m:meas(c)}));
    const kids=[]; let x=0, y=0, cw=0, col=0, ah=0;
    for(const b of bs){
      if(y>0 && y+b.m.h>H){ x+=cw+WRAP_GAP; y=0; cw=0; col++; }
      kids.push({k:b.k, dx:x, dy:y, col}); y+=b.m.h; cw=Math.max(cw,b.m.w); ah=Math.max(ah,y); }
    const cys=kids.map(q=>q.dy+M.get(q.k).y);
    return {w:x+cw, h:ah, mid:(Math.min(...cys)+Math.max(...cys))/2, kids}; };
  // sd=-1 mirrors the right-hand layout for the callers on the left
  const put=(k,X,Y,sd,g)=>{ const m=M.get(k); POS.set(k,{x:sd*X, y:Y+m.y, g});
    for(const q of m.kids) put(q.k, X+COLW+q.dx, Y+q.dy, sd, q.col); };
  const sideArea=sd=>{ const tops=roots.flatMap(r=>vkids.get(r).filter(c=>side.get(c)===sd)); return tops.length ? pack(tops) : null; };
  const build=h=>{ H=h; M.clear(); const R=sideArea(1), Lf=sideArea(-1);
    return {R, Lf, w:(R?COLW+R.w:NW)+(Lf?COLW+Lf.w:0), h:Math.max(R?R.h:0, Lf?Lf.h:0, roots.length*ROWH)}; };
  let B=build(Infinity);
  if(st.layout==='compact'){
    const r=svg.getBoundingClientRect(), want=(r.width>200 && r.height>200) ? r.width/r.height : ASPECT;
    if(B.w/B.h < want){   // taller than the window: find the tallest column height that is wide enough
      let lo=WRAP_MIN_H, hi=B.h;
      for(let i=0;i<18 && hi-lo>ROWH/2;i++){ const mid=(lo+hi)/2, b=build(mid); if(b.w/b.h > want) lo=mid; else hi=mid; }
      B=build(hi); } }
  const {R, Lf}=B;
  const rootY = R ? R.mid : (Lf ? Lf.mid : 0);
  if(R) R.kids.forEach(q=>put(q.k, COLW+q.dx, q.dy, 1, q.col));
  if(Lf){ const sh=rootY-Lf.mid; Lf.kids.forEach(q=>put(q.k, COLW+q.dx, q.dy+sh, -1, q.col)); }
  roots.forEach((r,i)=>POS.set(r,{x:0,y:rootY+i*ROWH,g:0}));
  return bounds();
}

// ---------------- draw
// draw() lays out the whole map and works out every edge's shape; render() then puts on the page only
// what lies near the view. A big map has tens of thousands of SVG elements, and the browser repaints
// all of them on every zoom step; with only the nearby part on the page, zooming and panning stay smooth.
let EG = [], RR = null, rendLod = -1, rendK = 1, lastRender = 0, renderTimer = 0, rafPending = false;
const LOD = () => st.k < 0.2 ? 0 : (st.k < 0.45 ? 1 : 2);   // 0: boxes only · 1: + names · 2: full detail
function edgeGeom(e){
  const a=POS.get(e.s), b=POS.get(e.t); if(!a||!b) return null;
  let x1,y1=a.y+NH/2,x2,y2=b.y+NH/2,d,reach=0;
  if(b.x>a.x){ x1=a.x+NW; x2=b.x; const m=Math.max(40,(x2-x1)*0.5); d=`M${x1},${y1} C${x1+m},${y1} ${x2-m},${y2} ${x2},${y2}`; }
  else if(b.x<a.x){ x1=a.x; x2=b.x+NW; const m=Math.max(40,(x1-x2)*0.5); d=`M${x1},${y1} C${x1-m},${y1} ${x2+m},${y2} ${x2},${y2}`; }
  else { x1=a.x+NW; x2=b.x+NW; reach=40+Math.min(300,Math.abs(y2-y1)*0.12); d=`M${x1},${y1} C${x1+reach},${y1} ${x2+reach},${y2} ${x2},${y2}`; }
  const P = treeSrc().parent, isTree = P.get(e.t)===e.s || P.get(e.s)===e.t;
  const inGrid = isTree && (a.g||b.g);   // runs under the grid's first columns: label only when selected
  const lx = b.x===a.x ? Math.max(x1,x2)+30 : (x1+x2)/2;
  return {e, d, lx, ly:(y1+y2)/2-3, x1, y1, x2, y2, reach, xt:!isTree,
    cls:['edge', e.soft?'soft':e.k, e.flags.includes('disabled')?'disabled':'', isTree?'':'xt', inGrid?'gl':''].join(' '),
    mk: e.soft?'arSoft':(e.k==='call'?'arCall':(e.k==='struct'?'arStruct':'arCond')),
    minx:Math.min(x1,x2), maxx:Math.max(x1,x2)+reach+(reach?60:0), miny:Math.min(y1,y2)-12, maxy:Math.max(y1,y2)+4}; }
// does an edge pass through rectangle R? The curve stays close to the line between its ends
// (it bends by at most about a third of the smaller side), so test that line, widened by that much.
function edgeNear(q,R){
  if(q.maxx<R.x0 || q.minx>R.x1 || q.maxy<R.y0 || q.miny>R.y1) return false;
  if(q.reach) return true;
  const pad=60+0.35*Math.min(Math.abs(q.x2-q.x1),Math.abs(q.y2-q.y1));
  const x0=R.x0-pad, x1=R.x1+pad, y0=R.y0-pad, y1=R.y1+pad, dx=q.x2-q.x1, dy=q.y2-q.y1;
  let t0=0, t1=1;   // Liang–Barsky clip of the segment against the widened rectangle
  for(const [pp,qq] of [[-dx,q.x1-x0],[dx,x1-q.x1],[-dy,q.y1-y0],[dy,y1-q.y1]]){
    if(pp===0){ if(qq<0) return false; continue; }
    const r=qq/pp; if(pp<0){ if(r>t1) return false; if(r>t0) t0=r; } else { if(r<t0) return false; if(r<t1) t1=r; } }
  return true; }
function draw(){
  curVis=visibleNodes(); curEdges=visibleEdges(curVis); box=layout(curVis);
  EG=[]; for(const e of curEdges){ const q=edgeGeom(e); if(q) EG.push(q); }
  const cnt=$('cnt'); if(cnt) cnt.textContent = t('ui.count',{a:curVis.size,b:D.nodes.length,e:curEdges.length});
  render(); applyTransform(true);
}
// the part of the map (in map coordinates) the window shows, widened by `margin` window-sizes on each side
function viewRect(margin){ const r=svg.getBoundingClientRect(), w=Math.max(r.width,200)/st.k, h=Math.max(r.height,200)/st.k;
  const x0=-st.tx/st.k, y0=-st.ty/st.k; return {x0:x0-w*margin, y0:y0-h*margin, x1:x0+w*(1+margin), y1:y0+h*(1+margin)}; }
function render(){
  const R=RR=viewRect(0.6), lod=rendLod=LOD(); rendK=st.k; lastRender=performance.now();
  gE.textContent=''; gN.textContent='';
  const fe=document.createDocumentFragment(), fn=document.createDocumentFragment();
  for(const q of EG){ if(!edgeNear(q,R)) continue;
    if(lod<1 && q.xt) continue;   // far out, the faint cross edges are only noise and cost the most
    const e=q.e, g=el('g',{class:q.cls,'data-i':e.i},fe);
    const inR=(x,y)=>x>=R.x0 && x<=R.x1 && y>=R.y0 && y<=R.y1;   // arrowheads and labels only where they can be seen
    el('path', inR(q.x2,q.y2) && (lod>=2 || (lod===1 && !q.xt)) ? {d:q.d,'marker-end':`url(#${q.mk})`} : {d:q.d}, g);
    if(lod<2) continue;
    el('title',{},g).textContent=`${byKey.get(e.s).name} → ${byKey.get(e.t).name}\n${e.ctx}${e.n>1?' ×'+e.n:''}\n${e.sites.map(s=>s.at).join('\n')}`;
    if(st.labels && inR(q.lx,q.ly)) el('text',{x:q.lx,y:q.ly,'text-anchor':'middle'},g).textContent =
      cut((e.soft?'⇢ ':'') + e.ctx + (e.n>1?' ×'+e.n:'') + (e.flags.includes('tooltip_only')?t('ui.tooltip_only'):''), 22); }
  for(const k of curVis){
    const n=byKey.get(k), p=POS.get(k); if(!p) continue;
    if(p.x+NW<R.x0 || p.x>R.x1 || p.y+NH+20<R.y0 || p.y-20>R.y1) continue;
    const col=COLORS[n.t]||'#777';
    const cls='node'+(n.v==='boundary'?' boundary':'')+(n.dis?' disabled':'')+(n.v==='unjudged'?' pending':'')+(n.fresh?' fresh':'')+(st.multi.has(k)?' multi':'')+
      (st.focus && (FT.opened.has(k) || k===st.focus.root)?' chain':'');
    const g=el('g',{class:cls,transform:`translate(${p.x},${p.y})`,'data-k':k},fn);
    el('rect',{class:'box',width:NW,height:NH,rx:7,fill:tint(col, n.v==='boundary'?0.08:(n.v==='unjudged'?0.1:0.18)),stroke:col},g);
    el('rect',{x:0,y:0,width:6,height:NH,rx:3,fill:col},g);
    g.addEventListener('click',ev=>{ ev.stopPropagation();
      if(opts.editable && (ev.ctrlKey||ev.metaKey)){ if(st.multi.has(k)) st.multi.delete(k); else st.multi.add(k); draw(); showMulti(); return; }
      st.multi.clear(); select(k);
      if(st.focus){ syncFocusBar(); if(FT.more.has(k)) focusOpen(k); } });   // in focus, a click also opens the node
    if(lod<1) continue;
    const nm=el('text',{class:'nm',x:12,y:18},g);
    nm.textContent = n.noloc ? cut(n.id,24) : cut(n.name,15);
    // the ± toggle: on the main map it folds a subtree; in focus it closes an opened node or opens one
    const ch=children.get(k);
    const tog = st.focus ? (FT.opened.has(k) && k!==st.focus.root ? '−' : (FT.more.has(k) ? '+' : ''))
                         : (ch && ch.length ? (st.collapsed.has(k)?'+':'−') : '');
    if(tog){ const tg=el('g',{class:'tg',transform:`translate(${NW-16},${NH/2})`},g);
      el('circle',{r:8,fill:tint(col,0.5),stroke:col},tg);
      el('text',{x:0,y:4,'text-anchor':'middle',style:'font-size:12px;fill:var(--ink);pointer-events:none'},tg).textContent = tog;
      tg.addEventListener('click',ev=>{ ev.stopPropagation();
        if(st.focus){ if(tog==='−') focusClose(k); else { select(k); focusOpen(k); } return; }
        if(st.collapsed.has(k)) st.collapsed.delete(k); else st.collapsed.add(k); draw(); }); }
    if(lod<2) continue;
    if(n.noloc) el('tspan',{class:'badge',dx:4},nm).textContent=t('ui.noloc');
    el('text',{class:'id',x:12,y:35},g).textContent = cut((n.noloc? n.tz : n.id),34);
    const top=[];
    if(n.v==='boundary') top.push(t('ui.boundary_badge')+(n.sys||''));
    if(n.v==='unjudged') top.push(n.stopped ? t('ui.stopped_badge') : t('ui.pending_badge'));
    if(n.fresh) top.push(t('ui.fresh_badge'));
    if(top.length) el('text',{class:'badge',x:NW-4,y:-4,'text-anchor':'end'},g).textContent=top.join(' · ');
    if(n.dis) el('text',{class:'badge',x:4,y:-4},g).textContent=t('ui.disabled_badge');
    el('title',{},g).textContent=`${n.name}\n${n.id}\n${n.tz}${n.v==='boundary'?'\n'+t('ui.boundary_badge')+n.sys:''}`;
  }
  gE.appendChild(fe); gN.appendChild(fn);
  applySel();
}
// render again when the view leaves the part on the page, the detail level changes, or we zoomed far in
function needRender(){ if(!RR || LOD()!==rendLod || st.k>rendK*2.5) return true;
  const v=viewRect(0); return v.x0<RR.x0 || v.y0<RR.y0 || v.x1>RR.x1 || v.y1>RR.y1; }
function checkRender(now){ clearTimeout(renderTimer); if(!EG.length && !curVis.size) return; if(!needRender()) return;
  if(now || performance.now()-lastRender>150) render(); else renderTimer=setTimeout(()=>{ if(needRender()) render(); }, 150); }
// now=true renders at once (fit, centre, jump to a node); wheel and drag go through scheduleTransform
function applyTransform(now){ vp.setAttribute('transform',`translate(${st.tx},${st.ty}) scale(${st.k})`); svg.classList.toggle('far', st.k<0.45); checkRender(now); }
function scheduleTransform(){ if(rafPending) return; rafPending=true; requestAnimationFrame(()=>{ rafPending=false; applyTransform(false); }); }
function sideW(){ return $('side').style.display==='block'?470:0; }
function fit(){ fitTo(box, 1.2); }
// keep clear of the focus bar at the top and of the open legend at the left (callers are drawn on the left)
function legendW(){ const lg=$('legend'), lb=$('lgBody'); if(!lg || !lb || lb.style.display==='none' || !lg.offsetWidth) return 0;
  return Math.max(0, lg.getBoundingClientRect().right - svg.getBoundingClientRect().left); }
function fitTo(b, maxK){ const r=svg.getBoundingClientRect();
  const fb=$('focusBar'), top=(fb && fb.style.display==='block') ? fb.offsetHeight+12 : 0, left=legendW();
  const k=Math.min((r.width-sideW()-left-40)/Math.max(b.w,1),(r.height-40-top)/Math.max(b.h,1),maxK); st.k=Math.max(k,0.03);
  st.tx=20+left-b.x0*st.k; st.ty=20+top-b.y0*st.k; applyTransform(true); }
// in focus mode, frame the node just opened and what it brought in, with a glimpse of where it hangs from
function fitFocus(k){ if(!st.focus || !POS.has(k)) return; let x0=Infinity,x1=-Infinity,y0=Infinity,y1=-Infinity;
  for(const x of [k, ...(FT.children.get(k)||[])]){ const p=POS.get(x); if(!p) continue;
    x0=Math.min(x0,p.x); x1=Math.max(x1,p.x+NW); y0=Math.min(y0,p.y); y1=Math.max(y1,p.y+NH); }
  const pp=POS.get(FT.parent.get(k)); if(pp){ if(pp.x<x0) x0-=COLW*0.6; else if(pp.x>x1-NW) x1+=COLW*0.6; }
  fitTo({x0,y0,w:x1-x0,h:y1-y0}, 1); }
function center(k){ const p=POS.get(k); if(!p) return; const r=svg.getBoundingClientRect(), left=legendW();
  st.k=Math.max(st.k,0.8); st.tx=left+(r.width-sideW()-left)/2-(p.x+NW/2)*st.k; st.ty=r.height/2-(p.y+NH/2)*st.k; applyTransform(true); }

// ---------------- selection and side panel
function applySel(){
  const k=st.sel; const hot=new Set();
  if(k) for(const e of curEdges) if(e.s===k||e.t===k){ hot.add(e.s); hot.add(e.t); }
  gE.querySelectorAll('.edge').forEach(g=>{ const e=D.edges[+g.dataset.i]; const on=k && (e.s===k||e.t===k);
    g.classList.toggle('hot',!!on); g.classList.toggle('dim',!!k && !on); });
  gN.querySelectorAll('.node').forEach(g=>{ const kk=g.dataset.k; g.classList.toggle('sel',kk===k); g.classList.toggle('dim',!!k && !hot.has(kk) && kk!==k); });
}
function vname(v){ return L['v.'+v] || v; }
function edgeRow(e,dir){ const o=dir==='out'?e.t:e.s; const on=byKey.get(o);
  const sites=e.sites.map(s=>`<div><code>${esc(s.at)}</code> <span class="muted">${esc(s.rel)}${s.acc?'·'+(s.acc==='write'?t('ui.write'):t('ui.read')):''}</span><br><code>${esc(s.code)}</code>${s.via?`<br><span class="muted">${esc(t('ui.via_param',{c:s.via.callee,s:s.via.call_site}))}</span>`:''}</div>`).join('');
  const kind = e.soft?t('ui.kind.soft'):t('ui.kind.'+e.k);
  return `<div class="el"><span class="pill">${esc(kind)}</span>${dir==='out'?'→':'←'} <a data-go="${esc(o)}">${esc(on?on.name:o)}</a> <span class="muted">${esc(on?on.tz:'')}</span><br><b>${esc(e.ctx)}</b>${e.n>1?' ×'+e.n:''}${e.flags.length?' <span class="muted">['+e.flags.join(',')+']</span>':''}${e.soft?'<br><span class="muted">'+t('ui.reason')+esc(e.why)+'</span>':''}${sites}</div>`; }
// roots are where the map starts; they cannot be judged, only replaced by a new search
const judgeable = keys => keys.filter(k=>!roots.includes(k));
function actButtons(keys, cur){
  if(!opts.editable) return '';
  const ks=judgeable(keys), note=ks.length<keys.length?`<div class="muted">${esc(t('ui.root_fixed'))}</div>`:'';
  if(!ks.length) return note;
  const b=(v,lab)=>`<button data-act="${v}" class="${cur===v?'on':''}">${esc(t(lab))}</button>`;
  return `<div class="acts">${b('in','ui.act_in')}${b('boundary','ui.act_boundary')}${b('out','ui.act_out')}</div>${note}<div class="muted">${esc(t('ui.act_hint'))}<br>${esc(t('ui.multi_hint'))}</div>`;
}
function bindActs(panel, keys){
  const ks=judgeable(keys);
  panel.querySelectorAll('[data-act]').forEach(btn=>btn.addEventListener('click',()=>{ if(opts.onJudge && ks.length) opts.onJudge(ks, btn.dataset.act); }));
}
function showMulti(){
  const panel=$('side'); if(!st.multi.size){ panel.style.display='none'; return; }
  panel.style.display='block';
  panel.innerHTML=`<button class="close" id="xClose">×</button><h2>${esc(t('ui.selected_n',{n:st.multi.size}))}</h2>${actButtons([...st.multi])}
   <div>${[...st.multi].map(k=>'<div class="el">'+esc(byKey.get(k).name)+' <code>'+esc(k)+'</code></div>').join('')}</div>`;
  bindActs(panel,[...st.multi]);
  $('xClose').onclick=()=>{ st.multi.clear(); panel.style.display='none'; draw(); };
}
function select(k){
  st.sel=k; applySel(); const n=byKey.get(k); const panel=$('side'); panel.style.display='block';
  const outs=outE.get(k)||[], ins=inE.get(k)||[]; const hid=(D.hidden||{})[k]||[];
  const lname = id => { const l=(D.meta.layers||[]).find(x=>x.id===id); return l ? l.name : id; };
  const sites=n.sites.map(s=>`<div><code>${esc(s.file)}:${s.line}</code> <span class="muted">${esc(lname(s.root))} · ${esc(s.how)}${s.replaced?' · replaced':''}${s.ignored?' · ignored (duplicate)':''}</span></div>`).join('') || `<span class="muted">${esc(t('ui.undefined_site'))}</span>`;
  const state = n.v==='unjudged' ? (n.stopped?t('ui.stopped_badge'):t('ui.pending_badge')) : vname(n.v);
  // where the definition in effect comes from: the game or a mod (several when INJECT adds to it)
  const layerName = id => { const l=(D.meta.layers||[]).find(x=>x.id===id); return !l ? id : (l.kind==='game' ? t('ui.src_game') : l.name); };
  const uniq = a => [...new Set(a)];
  const live = uniq(n.sites.filter(s=>!s.replaced && !s.ignored).map(s=>layerName(s.root)));
  const over = uniq(n.sites.filter(s=>s.replaced || s.ignored).map(s=>layerName(s.root))).filter(x=>!live.includes(x));
  const srcText = f => live.length ? live.map(f).join(' + ') + (over.length ? ' · '+t('ui.src_over',{x:over.map(f).join(' + ')}) : '') : t('ui.src_none');
  const srcFull = srcText(x=>x), srcShort = srcText(x=>cut(x,20));   // long mod names are shortened, the override note stays
  panel.innerHTML = `<button class="close" id="xClose">×</button><h2>${esc(n.name)}${n.noloc?' <span class="pill">'+esc(t('ui.noloc_pill'))+'</span>':''}</h2>
  <div class="sub">${esc(n.id)}</div>
  <div style="margin-top:6px"><span class="pill">${esc(n.tz)}</span><span class="pill" title="${esc(t('ui.src_label')+srcFull)}">${esc(t('ui.src_label')+srcShort)}</span><span class="pill">${esc(t('ui.verdict_label')+state)}${n.sys?' · '+esc(n.sys):''}</span>${n.dis?'<span class="pill">'+esc(t('ui.disabled_badge'))+': '+esc(n.dis)+'</span>':''}</div>
  <div class="acts"><button id="xFocus" title="${esc(t('ui.focus_hint'))}">${esc(t(st.focus?'ui.focus_exit':'ui.focus_start'))}</button></div>
  ${actButtons([k], n.v)}
  <div class="muted" style="margin-top:6px">${esc(t('ui.judgment'))}${esc(n.why)} <span class="pill">${esc(n.src)}</span>${n.from?'<br>'+t('ui.found_by',{x:'<a data-go="'+esc(n.from)+'">'+esc((byKey.get(n.from)||{}).name||n.from)+'</a>'}):''}</div>
  ${n.ls?'<div class="muted">'+esc(t('ui.loc'))+esc(n.nk)+' @ '+esc(n.ls)+'</div>':''}
  <h3>${esc(t('ui.def_sites'))}</h3>${sites}
  ${n.code?'<h3>'+esc(t('ui.code'))+'</h3><pre>'+esc(n.code)+'</pre>':''}
  <h3>${esc(t('ui.out_edges'))} (${outs.length})</h3>${outs.map(e=>edgeRow(e,'out')).join('')||'<span class="muted">'+esc(t('ui.none'))+'</span>'}
  <h3>${esc(t('ui.in_edges'))} (${ins.length})</h3>${ins.map(e=>edgeRow(e,'in')).join('')||'<span class="muted">'+esc(t('ui.none'))+'</span>'}
  <h3>${esc(t('ui.hidden_nb'))} (${hid.length})</h3>${hid.map(h=>`<div class="el">${h.d==='out'?'→':'←'} ${esc(h.name)} <code>${esc(h.o)}</code><br><b>${esc(h.ctx)}</b> <code>${esc(h.at)}</code><br><span class="muted">${esc(vname(h.v))}${h.why?': '+esc(h.why):''}</span></div>`).join('')||'<span class="muted">'+esc(t('ui.none'))+'</span>'}`;
  panel.querySelectorAll('[data-go]').forEach(a=>a.addEventListener('click',()=>goTo(a.dataset.go)));
  bindActs(panel,[k]);
  $('xFocus').onclick=()=>{ if(st.focus) focusExit(); else focusStart(k); };
  $('xClose').onclick=()=>{ panel.style.display='none'; st.sel=null; applySel(); };
}
function goTo(k){ if(!byKey.has(k)) return; const n=byKey.get(k);
  if(st.focus){ st.types.add(grp(n.t)); syncLegend();
    // a link in the panel points at a neighbour of the selected node: open that node so the target joins the tree
    if(!FT.all.has(k)){ if(st.sel && FT.all.has(st.sel) && nbrsOf(st.sel).has(k)) st.focus.open.push(st.sel); else { focusStart(k); return; } }
    draw(); syncFocusBar(); center(k); select(k); syncFocusBar(); return; }
  let p=parent.get(k); while(p){ st.collapsed.delete(p); p=parent.get(p); }
  st.types.add(grp(n.t)); syncLegend(); if(n.dis) st.disabled=true; if(n.v==='boundary') st.boundary=true; syncOpts();
  draw(); center(k); select(k);
  const g=gN.querySelector(`.node[data-k="${CSS.escape(k)}"]`); if(g){ g.classList.add('flash'); setTimeout(()=>g.classList.remove('flash'),1400);} }

// ---------------- legend, options, search
function syncLegend(){ document.querySelectorAll('#legend input[data-t]').forEach(i=>i.checked=st.types.has(i.dataset.t)); }
function buildLegend(){
  const legend=$('legend'); if(!legend) return;
  const cnt={}; D.nodes.forEach(n=>{ const g=grp(n.t); cnt[g]=(cnt[g]||0)+1; });
  const open = !legend.dataset.folded;
  let h=`<div id="lgHead" style="cursor:pointer"><b>${esc(t('ui.legend'))}</b> <span class="muted">${esc(t('ui.legend_hint'))}</span></div><div id="lgBody" style="${open?'':'display:none'}">`;
  for(const g of GROUPS){ if(!cnt[g]) continue; const c=COLORS[g]||'#777';
    h+=`<label class="row"><input type="checkbox" data-t="${g}" ${st.types.has(g)?'checked':''}><span class="sw" style="background:${tint(c,.18)};border-color:${c}"></span>${esc(groupLabel(g))} <span class="muted">${cnt[g]}</span></label>`; }
  h+=`<div class="lines" style="margin-top:6px"><b>${esc(t('ui.edges'))}</b>
  <div><svg width="34" height="10"><line x1="0" y1="5" x2="34" y2="5" stroke="var(--call)" stroke-width="2"/></svg>${esc(t('ui.e_call'))}</div>
  <div><svg width="34" height="10"><line x1="0" y1="5" x2="34" y2="5" stroke="var(--cond)" stroke-width="2"/></svg>${esc(t('ui.e_cond'))}</div>
  <div><svg width="34" height="10"><line x1="0" y1="5" x2="34" y2="5" stroke="var(--struct)" stroke-width="3"/></svg>${esc(t('ui.e_struct'))}</div>
  <div><svg width="34" height="10"><line x1="0" y1="5" x2="34" y2="5" stroke="var(--soft)" stroke-width="2" stroke-dasharray="6 4"/></svg>${esc(t('ui.e_soft'))}</div>
  <div><svg width="34" height="14"><rect x="1" y="1" width="32" height="12" rx="3" fill="none" stroke="var(--ink2)" stroke-dasharray="4 2"/></svg>${esc(t('ui.e_boundary'))}</div>
  <div class="muted" style="white-space:normal;max-width:230px">${esc(t('ui.legend_note'))}</div></div></div>`;
  legend.innerHTML=h;
  legend.querySelectorAll('input[data-t]').forEach(i=>i.addEventListener('change',()=>{ if(i.checked) st.types.add(i.dataset.t); else st.types.delete(i.dataset.t); draw(); }));
  $('lgHead').onclick=()=>{ const b=$('lgBody'); const fold=b.style.display!=='none'; b.style.display=fold?'none':''; legend.dataset.folded=fold?'1':''; };
}
function syncOpts(){ const m={optLabels:'labels',optSoft:'soft',optBoundary:'boundary',optDisabled:'disabled'};
  for(const id in m){ const e=$(id); if(e) e.checked=st[m[id]]; }
  const bl=$('btnLayout'); if(bl){ bl.textContent=t(st.layout==='compact'?'ui.layout_compact':'ui.layout_tree'); bl.title=t('ui.layout_tip'); } }
function placeChrome(){ const top=$('top'); const h=top?top.offsetHeight:0;
  ['stage','side'].forEach(id=>{ const e=$(id); if(e) e.style.top=h+'px'; }); const r=$('results'); if(r) r.style.top=(h+2)+'px';
  const fb=$('focusBar'); if(fb) fb.style.top=(h+8)+'px'; }
function foldTo(level){ st.collapsed.clear(); depth.forEach((d,k)=>{ if(d===level && (children.get(k)||[]).length) st.collapsed.add(k); }); }

function init(o){
  opts=o||{}; L=opts.L||{};
  svg=$('svg'); vp=$('vp'); gE=$('gE'); gN=$('gN');
  const setText=(id,k)=>{ const e=$(id); if(e) e.textContent=t(k); };
  const q=$('q'); if(q) q.placeholder=t('ui.search_ph');
  for(const [id,k] of [['tLabels','ui.labels'],['tAllLabels','ui.cross_labels'],['tSoft','ui.soft'],['tBoundary','ui.boundary'],['tDisabled','ui.disabled'],
    ['btnFit','ui.fit'],['btnExpand','ui.expand_all'],['btnFold','ui.fold3'],['btnTheme','ui.theme_toggle']]) setText(id,k);
  const al=$('lblAllLabels'); if(al) al.title=t('ui.cross_labels_tip');
  const bind=(id,f,ev)=>{ const e=$(id); if(e) e[ev||'onclick']=f; };
  bind('optLabels',ev=>{st.labels=ev.target.checked; draw();},'onchange');
  bind('optAllLabels',ev=>{ svg.classList.toggle('allLabels', ev.target.checked); },'onchange');
  bind('optSoft',ev=>{st.soft=ev.target.checked; draw();},'onchange');
  bind('optBoundary',ev=>{st.boundary=ev.target.checked; draw();},'onchange');
  bind('optDisabled',ev=>{st.disabled=ev.target.checked; draw();},'onchange');
  bind('btnFit',()=>fit());
  bind('btnExpand',()=>{ st.focus=null; syncFocusBar(); st.collapsed.clear(); draw(); });
  bind('btnFold',()=>{ st.focus=null; syncFocusBar(); foldTo(3); draw(); fit(); });
  if(!$('focusBar')){ const fb=document.createElement('div'); fb.id='focusBar'; document.body.appendChild(fb); }
  window.addEventListener('keydown',ev=>{ if(ev.key!=='Escape' || !st.focus) return;
    const a=document.activeElement; if(a && /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName)) return; focusBack(); });
  bind('btnLayout',()=>{ st.layout = st.layout==='compact'?'tree':'compact';
    try { localStorage.setItem('v3tree.layout', st.layout); } catch(e){}
    syncOpts(); draw(); if(st.sel && POS.has(st.sel)) center(st.sel); else fit(); });
  syncOpts();
  bind('btnTheme',()=>{ const r=document.documentElement; r.setAttribute('data-theme', isDark()?'light':'dark'); buildLegend(); draw(); });
  const res=$('results');
  if(q && res){
    q.addEventListener('input',()=>{ const s=q.value.trim().toLowerCase(); if(!s){ res.style.display='none'; return; }
      const hits=D.nodes.filter(n=>String(n.name).toLowerCase().includes(s)||n.id.toLowerCase().includes(s)).slice(0,60);
      res.innerHTML = hits.map(n=>`<div data-k="${esc(n.k)}"><b>${esc(n.name)}</b> <span class="muted">${esc(n.tz)}</span><br><code>${esc(n.id)}</code></div>`).join('') || `<div class="muted">${esc(t('ui.no_match'))}</div>`;
      res.style.display='block'; res.querySelectorAll('[data-k]').forEach(d=>d.onclick=()=>{ res.style.display='none'; goTo(d.dataset.k); }); });
    q.addEventListener('keydown',ev=>{ if(ev.key==='Enter'){ ev.preventDefault(); const s=q.value.trim().toLowerCase();
        const f=D.nodes.find(n=>n.id.toLowerCase()===s) || D.nodes.find(n=>String(n.name).toLowerCase().includes(s)||n.id.toLowerCase().includes(s));
        if(f){ res.style.display='none'; goTo(f.k);} } if(ev.key==='Escape') res.style.display='none'; });
  }
  let drag=null;
  svg.addEventListener('mousedown',ev=>{ drag={x:ev.clientX,y:ev.clientY,tx:st.tx,ty:st.ty,moved:false}; svg.classList.add('drag'); });
  window.addEventListener('mousemove',ev=>{ if(!drag) return; const dx=ev.clientX-drag.x, dy=ev.clientY-drag.y; if(Math.abs(dx)+Math.abs(dy)>3) drag.moved=true;
    st.tx=drag.tx+dx; st.ty=drag.ty+dy; scheduleTransform(); });
  window.addEventListener('mouseup',()=>{ svg.classList.remove('drag'); setTimeout(()=>{drag=null;},0); });
  svg.addEventListener('click',()=>{ if(drag && drag.moved) return; if(st.sel || st.multi.size){ st.sel=null; st.multi.clear(); applySel(); $('side').style.display='none'; draw(); } if(res) res.style.display='none'; });
  svg.addEventListener('wheel',ev=>{ ev.preventDefault(); const r=svg.getBoundingClientRect(); const mx=ev.clientX-r.left, my=ev.clientY-r.top;
    const f=Math.exp(-ev.deltaY*0.0015); const k=Math.min(4,Math.max(0.03,st.k*f)); st.tx=mx-(mx-st.tx)*k/st.k; st.ty=my-(my-st.ty)*k/st.k; st.k=k; scheduleTransform(); },{passive:false});
  let touch=null;
  svg.addEventListener('touchstart',ev=>{ if(ev.touches.length===1) touch={x:ev.touches[0].clientX,y:ev.touches[0].clientY,tx:st.tx,ty:st.ty}; },{passive:true});
  svg.addEventListener('touchmove',ev=>{ if(touch&&ev.touches.length===1){ st.tx=touch.tx+ev.touches[0].clientX-touch.x; st.ty=touch.ty+ev.touches[0].clientY-touch.y; scheduleTransform(); } },{passive:true});
  window.addEventListener('resize',()=>{ placeChrome(); checkRender(true); }); placeChrome();
}
function load(data, keepView){
  D=data; buildTree();
  if(!keepView){ st.collapsed.clear(); st.sel=null; st.multi.clear(); st.focus=null; foldTo(3); }
  else { [...st.collapsed].forEach(k=>{ if(!byKey.has(k)) st.collapsed.delete(k); }); [...st.multi].forEach(k=>{ if(!byKey.has(k)) st.multi.delete(k); });
    if(st.focus){ if(!byKey.has(st.focus.root)) st.focus=null; else st.focus.open=st.focus.open.filter(k=>byKey.has(k)); } }
  syncFocusBar();
  const ttl=$('ttl'); if(ttl) ttl.textContent=D.meta.title||'';
  const thm=$('thm'); if(thm) thm.textContent=D.meta.theme ? t('ui.theme_prefix')+D.meta.theme : '';
  buildLegend(); placeChrome(); draw();
  if(!keepView){ fit(); if(st.k<0.3 && roots.length){ st.k=0.6; center(roots[0]); } }
  if(keepView && st.sel && byKey.has(st.sel)) select(st.sel); else if(keepView && st.sel){ st.sel=null; $('side').style.display='none'; }
}
return {init, load, fit, goTo, focusStart, placeChrome, state: st};
})();
