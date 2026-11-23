/* The phone table (m/index.html only). It runs after the Modern Table's own script, reuses all of its rules and messages (so a phone can
   play a desktop), and changes only how the table is drawn and touched:
   - a tapped card opens larger with what you can do with it (its own menu, as buttons); LOOK reads a card instead (picture, text, right now)
   - your lands fold into one tile (a small picture per land, tapped ones turned); tapping it opens the lands box, which also opens while you pay
   - the hand is a fan of every card in the corner that opens into a tray; tapping a card there casts it, as a left click does on the desktop
   - menus open as a sheet with fingertip-sized rows; the hover enlargement is off */
'use strict';
const MVERSION = 'm0.3';
const M = {look:false, view:null, lands:null, autoLands:false, tap:null, swallow:0, lastTouch:0, stN:0};
const HT = document.documentElement;

/* ---------- no hover enlargement: LOOK replaces it ---------- */
showZoom = function(){};

/* ---------- menus: one sheet with big rows; a submenu replaces the rows, with a Back row ---------- */
let MCAP = null;
const deskMenu = menu;
menu = function(x, y, items){ if(MCAP){ MCAP.push(...items); return; } mMenu(items); };
function capture(fn){ MCAP = []; try{ fn(); } catch(e){ console.error(e); } const r = MCAP; MCAP = null; return r.filter(Boolean); }
function mMenu(items, title){ const el = $('#ctx'); const s = $('#ctx2'); if(s) s.hidden = true;
  mFill(el, items, [], fn=>{ closeMenu(); fn(); }, title); el.hidden = false; el.scrollTop = 0; hideZoom(); }
function mFill(el, items, trail, run, title){
  el.innerHTML = ''; el.classList.remove('swapped');
  if(title){ const t = document.createElement('div'); t.className = 'mtt'; t.textContent = title; el.appendChild(t); }
  if(trail.length){ const b = document.createElement('button'); b.className = 'back'; b.innerHTML = '<span>‹ Back</span>';
    b.onclick = e=>{ e.stopPropagation(); const p = trail[trail.length-1]; mFill(el, p.items, trail.slice(0,-1), run, p.title); }; el.appendChild(b);
    el.appendChild(document.createElement('hr')); }
  let lastHr = true;
  for(const it of items){ if(!it) continue;
    if(it === '-'){ if(!lastHr){ el.appendChild(document.createElement('hr')); lastHr = true; } continue; }
    lastHr = false;
    if(it.html){ const d = document.createElement('div'); d.className = it.cls || ''; d.innerHTML = it.html; if(it.wire) it.wire(d); el.appendChild(d); continue; }
    const b = document.createElement('button');
    if(Array.isArray(it[1])){ b.className = 'sub'; b.innerHTML = `<span>${esc(it[0])}</span><kbd>›</kbd>`;
      b.onclick = e=>{ e.stopPropagation(); mFill(el, it[1], [...trail, {items, title}], run, it[0]); el.scrollTop = 0; }; }
    else { b.innerHTML = `<span>${esc(it[0])}</span>`; if(it[3]) b.classList.add(it[3]); if(it.prim) b.classList.add('prim');
      b.onclick = e=>{ e.stopPropagation(); if(it[3]==='mnote') return; run(it[1]); }; }
    el.appendChild(b); }
  if(el.lastChild && el.lastChild.tagName === 'HR') el.lastChild.remove();
}
/* a backdrop under an open menu, so tapping beside it only closes it */
(function(){ const bd = document.createElement('div'); bd.id = 'mBackdrop'; bd.hidden = true; document.body.appendChild(bd);
  const ctx = $('#ctx'); new MutationObserver(()=>{ bd.hidden = ctx.hidden; }).observe(ctx, {attributes:true, attributeFilter:['hidden']});
  bd.addEventListener('click', ()=>{ closeMenu(); }); })();

/* ---------- the right column: LOOK and the menu ---------- */
(function(){ const top = document.createElement('div'); top.id = 'mTop';
  top.innerHTML = `<button id="mLook" aria-pressed="false" title="LOOK: tap a card to read it"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5L21 21M10.5 7.5v6M7.5 10.5h6"/></svg>LOOK</button><button id="mMenu" aria-label="Menu">☰</button>`;
  $('#right').prepend(top);
  $('#mLook').onclick = ()=>setLook(!M.look);
  $('#mMenu').onclick = ()=>mainMenu();
  const h4 = $('#logwrap h4'); if(h4){ const x = document.createElement('button'); x.id = 'mLogX'; x.className = 'ghost'; x.textContent = 'Close'; x.onclick = ()=>HT.classList.remove('mlog'); h4.appendChild(x); }
})();
function setLook(on){ M.look = !!on; HT.classList.toggle('look', M.look); $('#mLook').setAttribute('aria-pressed', String(M.look)); if(!M.look) closeView(); }
function mainMenu(){
  const tm = capture(()=>tableMenu(0, 0)).filter(it=>!(Array.isArray(it) && /tour|explore/i.test(it[0])));
  mMenu([
    ['Undo', ()=>undo()],
    ['Your lands', ()=>openLands(true)],
    ['Hand actions…', ()=>handMenu(0, 0)],
    ['Token or any card…', ()=>tokenModal()],
    ['Roll a die or flip a coin…', ()=>$('#diceBtn').onclick({currentTarget:$('#mMenu')})],
    dummy() && ["Practice's side…", ()=>practiceMenu(0, 0)],
    ['Turn menu: stops and pauses…', ()=>turnMenu()],
    ['Game log and chat', ()=>HT.classList.add('mlog')],
    '-', ...tm ], 'Menu');
}

/* ---------- the hand: every card fanned in the bottom right corner (m0.3, the maintainer: m0.1's fan, but the whole hand and less overlap); tapping it opens the tray ---------- */
(function(){ const b = document.createElement('button'); b.id = 'mHandBtn'; b.setAttribute('aria-label', 'Your hand'); $('#board').appendChild(b);
  b.addEventListener('click', e=>{ if(Date.now()-M.swallow < 450) return; const f = e.target.closest('[data-hid]');
    if(M.look && f){ openLook(f.dataset.hid); return; } tray(!HT.classList.contains('mhand')); });
  const bk = document.createElement('div'); bk.id = 'mHandBack'; document.body.appendChild(bk); bk.onclick = ()=>tray(false);
  const hh = document.createElement('div'); hh.id = 'mHandHint'; document.body.appendChild(hh);
  hh.onclick = e=>{ const k = e.target.closest('[data-mh]'); if(!k) return; if(k.dataset.mh === 'x') tray(false); else { tray(false); handMenu(0, 0); } };
})();
function tray(on){ HT.classList.toggle('mhand', !!on); if(on) paintHint(); }
function paintHint(){ const n = G.me.hand.length;
  $('#mHandHint').innerHTML = `<span>Your hand · ${n} card${n===1?'':'s'} · ${M.look ? 'LOOK is on: tap a card to read it' : 'tap a card to cast or play it'}</span><span><button class="ghost" data-mh="menu">Hand actions…</button> <button class="ghost" data-mh="x">Close</button></span>`; }
const FAN_SHOW = .52;   /* the part of each card left uncovered by the next one (m0.1 showed 26%) */
function paintHandBtn(){ const b = $('#mHandBtn'); if(!b) return; const h = G.me.hand, n = h.length;
  b.innerHTML = h.map((c,i)=>{ const d = cdata(c), why = typeof handTimeWhy === 'function' ? handTimeWhy(c) : '';
    return `<span class="fc${why ? ' ntime' : ''}" data-hid="${esc(c.id)}" style="z-index:${i+1}">${d.img ? `<img src="${esc(d.img)}" alt="" draggable="false">` : `<span class="ft">${esc(d.n||'')}</span>`}</span>`; }).join('')
    + `<span class="hc" title="Cards in your hand">${n}</span>`;
  b.classList.toggle('none', !n); if(!n){ b.style.width = ''; return; }
  const fcs = [...b.querySelectorAll('.fc')], w = fcs[0].offsetWidth, room = Math.max(w, ($('#board').clientWidth || 600) * .48 - 12);
  const step = n > 1 ? Math.min(w * FAN_SHOW, (room - w) / (n - 1)) : 0, da = n > 1 ? Math.min(4, 16 / (n - 1)) : 0;   /* at most ±8° at the ends, so the fan stays inside the corner */
  b.style.width = Math.round(w + step * (n - 1) + 30) + 'px';
  fcs.forEach((el, i)=>{ el.style.left = Math.round(12 + i * step) + 'px'; el.style.transform = `rotate(${((i - (n - 1) / 2) * da).toFixed(2)}deg)`; }); }

/* ---------- lands fold into a tile: a small picture per land (identical lands grouped with a count, tapped ones turned), m0.2 ---------- */
const foldable = c => isLand(c) && !isCreature(c);
function sideLands(mine){ const s = mine ? G.me : G.opp; if(!s) return []; return (s.bf||[]).filter(foldable).sort((a,b)=>(cdata(a).n||'').localeCompare(cdata(b).n||'') || (a.tap-b.tap)); }
function landGroups(lands){ const g = new Map();
  for(const c of lands){ const k = (c.fd ? '?' : cdata(c).n||'') + '|' + (c.tap ? 1 : 0); if(!g.has(k)) g.set(k, []); g.get(k).push(c); }
  return [...g.values()].sort((a,b)=>(a[0].tap?1:0)-(b[0].tap?1:0)); }
function landPic(c){ if(c.fd) return '<div class="back"></div>'; const d = cdata(c), img = (c.flip && d.back) ? d.back : d.img;
  return img ? `<img src="${esc(img)}" alt="" draggable="false" onerror="this.remove()">` : `<span class="ft">${esc(d.n||'')}</span>`; }
function foldLands(sel, mine){ const row = $(sel); if(!row) return; const lands = sideLands(mine); if(!lands.length) return;
  const ids = new Set(lands.map(c=>c.id)), side = mine ? G.me : G.opp, att = new Set((side.bf||[]).filter(c=>c.att && ids.has(c.att)).map(c=>c.id));
  row.querySelectorAll('.card[data-id]').forEach(el=>{ if(ids.has(el.dataset.id) || att.has(el.dataset.id)){ el.classList.add('mfold'); const p = el.parentElement; if(p && p.classList.contains('pilT') && [...p.children].every(k=>ids.has(k.dataset.id) || att.has(k.dataset.id))) p.classList.add('mfold'); } });
  const un = lands.filter(c=>!c.tap).length, gs = landGroups(lands);
  const t = document.createElement('div'); t.className = 'mlands'+(mine?'':' opp'); t.dataset.mlands = mine ? 'me' : 'opp';
  t.innerHTML = `<div class="mlh">LANDS<b>${lands.length}</b><span>${un} untapped</span></div><div class="mli">${gs.map(g=>`<span class="ml${g[0].tap?' t':''}" title="${esc((g[0].fd?'Face-down land':cdata(g[0]).n)+(g[0].tap?' (tapped)':''))}"><span class="pic">${landPic(g[0])}</span>${g.length>1?`<b class="mlc">${g.length}</b>`:''}${bfAtt(side, g)}</span>`).join('')}</div>`;
  t.onclick = ()=>openLands(mine);
  row.prepend(t);
  const box = t.querySelector('.mli'), kids = [...box.children], maxW = row.clientWidth*.55 - 16; let tot = kids.reduce((a,k)=>a+k.offsetWidth+3, 0);
  if(kids.length > 1 && tot > maxW){ const cut = (tot - maxW)/(kids.length - 1); kids.forEach((k,i)=>{ if(i) k.style.marginLeft = (3 - cut) + 'px'; }); } }
const bfAtt = (side, g) => (side.bf||[]).some(a=>g.some(c=>a.att===c.id)) ? '<i class="mla" title="Something is attached">◆</i>' : '';

/* ---------- the lands box ---------- */
(function(){ const el = document.createElement('div'); el.id = 'mLands'; el.hidden = true; document.body.appendChild(el);
  el.addEventListener('click', e=>{ const b = e.target.closest('[data-ml]'); if(!b) return; const k = b.dataset.ml;
    if(k === 'x'){ closeLands(); return; } if(k === 'more'){ openCard(b.dataset.id); } }); })();
function openLands(mine){ M.lands = {mine}; paintLands(); $('#mLands').hidden = false; tray(false); }
function closeLands(){ M.lands = null; M.autoLands = false; $('#mLands').hidden = true; }
/* the largest land size at which every land fits the box without scrolling (a tapped land turns sideways, so each takes a square) */
function landSize(n, paying){ const rc = parseFloat(getComputedStyle(HT).getPropertyValue('--rcol')) || 132, W = innerWidth - rc - (paying ? Math.min(340, innerWidth*.44) + 8 : 0) - 22, Hh = innerHeight - 84; let best = 44;
  for(let lw = 120; lw >= 44; lw -= 2){ const cell = lw*1.396 + 4 + 6, cols = Math.max(1, Math.floor((W+6)/cell)), rows = Math.max(1, Math.floor((Hh+6)/cell)); if(cols*rows >= n){ best = lw; break; } }
  return best; }
/* a land with something to do besides tapping for mana (Mutavault, Fiery Islet's draw, Urza's Saga's construct): its button reads Abilities */
function landExtra(c){ return capture(()=>cardMenu(c.id, 0, 0)).some(it=>it && it.own && Array.isArray(it) && !Array.isArray(it[1]) && !/^(Tap|Untap)\b/.test(it[0])); }
function paintLands(){ const el = $('#mLands'); if(!M.lands) return; const mine = M.lands.mine, side = mine ? G.me : G.opp; if(!side){ closeLands(); return; }
  const lands = sideLands(mine), bf = side.bf || [];
  const pool = mine ? MANA.filter(k=>(G.me.mana||{})[k]).map(k=>`<span style="display:inline-flex;align-items:center">${(G.me.mana[k]>1?`<b style="font-size:11px">${G.me.mana[k]}</b>`:'')}<i class="ms ms-${k}">${k}<img src="https://svgs.scryfall.io/card-symbols/${k}.svg" alt="" onerror="this.remove()"></i></span>`).join('') : '';
  const paying = mine && !$('#payPanel').hidden;
  el.innerHTML = `<header><h3>${mine ? 'Your lands' : esc((G.opp&&G.opp.name)||'Opponent')+"'s lands"}</h3>${mine ? `<span class="mhint">${pool ? 'Pool' : 'Pool empty'}</span><span class="pool">${pool}</span>` : ''}<button class="${paying?'ghost':'go'}" data-ml="x">${paying ? 'Hide' : 'Done'}</button></header>
    <div class="mhint">${G.mode ? 'Tap a land to choose it.' : M.look ? 'LOOK is on: tap a land to read it.' : mine ? (paying ? 'Tap lands to pay; each symbol in the payment box lights up as your pool covers it.' : 'Tap a land to tap it for mana (a land with choices asks which); tap a tapped land to untap it. Abilities opens the rest.') : 'Tap a land to read it.'}</div>
    <div class="mlg" style="--lw:${landSize(lands.length, paying)}px">${lands.length ? lands.map(c=>`<div class="mlc">${bf.filter(a=>a.att===c.id).map(a=>cardHTML(a,'bf',mine,'under')).join('')}${cardHTML(c,'bf',mine)}${mine ? (landExtra(c) ? `<button class="mlm ab" data-ml="more" data-id="${c.id}">Abilities</button>` : `<button class="mlm" data-ml="more" data-id="${c.id}" aria-label="More">⋯</button>`) : ''}</div>`).join('') : '<span class="mhint">No lands.</span>'}</div>`; }
new MutationObserver(()=>{ const pp = $('#payPanel'), v = !pp.hidden; HT.classList.toggle('mpay', v);
  if(v){ tray(false); closeView(); if(!M.lands && sideLands(true).length){ openLands(true); M.autoLands = true; } else if(M.lands) paintLands(); }
  else if(M.autoLands) closeLands(); else if(M.lands) paintLands(); }).observe($('#payPanel'), {attributes:true, attributeFilter:['hidden']});

/* ---------- the card sheet and the LOOK view ---------- */
(function(){ const v = document.createElement('div'); v.id = 'mView'; v.hidden = true; document.body.appendChild(v);
  v.addEventListener('click', e=>{
    if(e.target === v){ closeView(); return; }
    if(e.target.closest('.mpic')){ closeView(); return; }
    const b = e.target.closest('[data-mv]'); if(b){ const k = b.dataset.mv; if(k === 'x') closeView(); else if(k === 'look' && M.view) openLook(M.view.id); return; }
    const ab = e.target.closest('[data-abx]'); if(ab){ const a = $('#about'); closeView(); if(a && a.onclick) a.onclick({target:ab}); } }); })();
function closeView(){ M.view = null; const v = $('#mView'); if(v){ v.hidden = true; v.innerHTML = ''; } }
function picHTML(c, mine){ if(c.fd && !mine) return `<div class="mpic"><div class="back" style="position:absolute;inset:0"></div></div>`;
  const d = cdata(c), img = (c.flip && d.back) ? d.back : d.img;
  return `<div class="mpic">${img ? `<img src="${esc(img)}" alt="${esc(d.n||'')}" draggable="false" onerror="this.remove()">` : ''}${img ? '' : `<div class="txt"><b>${esc(d.n||'')}</b><span>${esc(d.mc||'')}</span><i>${esc(d.t||'')}</i><span>${esc(d.o||'')}</span></div>`}</div>`; }
function nowHTML(a){ const c = a.c; if(a.z !== 'bf') return '';
  if(isCreature(c) && !(c.fd && !a.mine)){ deskAbout(c.id, 0, 0); const el = $('#about'); const h = el ? el.innerHTML : ''; if(el) el.hidden = true; return h ? `<div class="mnow"><h5>RIGHT NOW</h5>${h}</div>` : ''; }
  const bits = []; try{ const l = ctrLine(c); if(l) bits.push(esc(l)); }catch(e){}
  if(c.tap) bits.push('Tapped'); if(c.note) bits.push('Note: '+esc(c.note)); if(c.cp && c.cp.orig) bits.push(esc(`${c.cp.orig}, copying ${cdata(c).n}`));
  return bits.length ? `<div class="mnow"><h5>RIGHT NOW</h5>${bits.join('<br>')}</div>` : ''; }
const zoneName = z => ({bf:'on the battlefield', hand:'in hand', st:'on the stack', gy:'in the graveyard', ex:'in exile', lib:'in the library', side:'in the sideboard'})[z] || '';
function openLook(id){ const a = findAny(id) || (PEEK.get(id) ? {c:PEEK.get(id), mine:false, z:''} : null); if(!a) return; closeMenu();
  const c = a.c, hid = c.fd && !a.mine, d = hid ? {} : cdata(c), v = $('#mView');
  M.view = {id, look:true};
  v.innerHTML = picHTML(c, a.mine) + `<div class="mside"><button class="ghost mx" data-mv="x">Close</button>
    <h3>${hid ? 'A face-down card' : esc(d.n||'')}</h3><div class="mty">${hid ? '' : esc([d.mc, d.t, d.pt, d.loy ? 'loyalty '+d.loy : ''].filter(Boolean).join(' · '))}${a.z ? ` · ${a.mine ? 'yours' : esc((G.opp&&G.opp.name)||'opponent')+"'s"}, ${zoneName(a.z)}` : ''}</div>
    ${nowHTML(a)}${hid ? '' : `<div class="mox">${esc(d.o||'')}</div>`}<div class="mhint">Tap the picture to close${M.look ? '; LOOK stays on' : ''}.</div></div>`;
  v.hidden = false; }
function primaryFor(c, id){ const lbl = c.tap ? 'Untap' : isPW(c) && !isCreature(c) ? 'Loyalty abilities…' : isLand(c) ? 'Tap for mana' : 'Tap';
  const it = [lbl, ()=>toggleTap(id, innerWidth/2, innerHeight-40)]; it.prim = 1; return it; }
function openCard(id){ const a = findAny(id); if(!a) return; if(!a.mine || a.z !== 'bf'){ openLook(id); return; } closeMenu();
  const c = a.c, d = cdata(c), items = capture(()=>cardMenu(id, 0, 0)).filter(it=>!(Array.isArray(it) && /^Right now:/.test(it[0]))), v = $('#mView');
  M.view = {id, look:false};
  let now = ''; if(isCreature(c) && !c.fd){ try{ now = `<div class="mty" style="color:#5fd3c0">Right now: ${esc(aboutSum(c, true))}${c.tap ? ' · tapped' : ''}</div>`; }catch(e){} }
  v.innerHTML = picHTML(c, true) + `<div class="mside"><button class="ghost mx" data-mv="x">Close</button><h3>${esc(c.fd ? 'Face-down card' : d.n||'')}</h3>${now}<div class="mact"></div><button class="ghost" data-mv="look">Read the card (LOOK)</button></div>`;
  mFill(v.querySelector('.mact'), [primaryFor(c, id), '-', ...items], [], fn=>{ closeView(); fn(); });
  v.hidden = false; }
const deskAbout = aboutCard;
aboutCard = function(id){ openLook(id); };

/* ---------- taps on cards ---------- */
const ROWS = '#myFront,#myBack,#oppFront,#oppBack';
function tapKind(el){
  if(el.closest('#mLands')) return 'lands';
  if(M.look && el.closest('#modal') && !el.closest('.pile')) return 'look';
  if(el.closest('#modal,#payPanel,#pactPanel,#coPanel,#shown,#ctx,#ctx2,#mView,.pile')) return null;
  if(el.closest('#myHand')) return G.mode && !M.look ? null : 'hand';
  if(M.look) return 'look';
  if(G.mode) return null;
  if(el.closest(ROWS) && el.dataset.z === 'bf'){
    if(el.dataset.o !== 'me') return iControl() ? null : 'opp';
    if(G.atkSel && atkStep()) return null;
    const f = find(el.dataset.id); if(blockStep() && f && isCreature(f.c) && !f.c.tap) return null;
    return 'mine'; }
  return null; }
function handPlay(id, x, y){ const f = find(id); if(!f) return; if(G.me.ctl){ playFromHand(id); return; }
  if(mdfcLand(f.c)){ mdfcMenu(id, x, y); return; } if(isLand(f.c) && cyclingOf(f.c).length) cycLandClick(id); else playFromHand(id); }
function mAct(kind, el, x, y){ const id = el.dataset.id;
  if(kind === 'hand'){ if(M.look){ openLook(id); return; } tray(false); handPlay(id, x, y); return; }
  if(kind === 'look' || kind === 'opp'){ openLook(id); return; }
  if(kind === 'mine'){ openCard(id); return; }
  if(kind === 'lands'){ if(M.look){ openLook(id); return; } if(G.mode){ finishMode(id); return; } if(el.dataset.o === 'me') toggleTap(id, x, y); else openLook(id); } }
addEventListener('pointerdown', e=>{ if(e.pointerType === 'touch') M.lastTouch = Date.now();
  if(e.pointerType === 'mouse' && e.button !== 0) return;
  const el = e.target.closest && e.target.closest('.card[data-id]'); if(!el) return; const kind = tapKind(el); if(!kind) return;
  e.stopPropagation(); closeMenu(); try{ sndUnlock(); }catch(_){}
  M.tap = {el, kind, x:e.clientX, y:e.clientY, moved:false}; }, true);
addEventListener('pointermove', e=>{ const t = M.tap; if(t && Math.hypot(e.clientX-t.x, e.clientY-t.y) > 10) t.moved = true; }, true);
addEventListener('pointercancel', ()=>{ M.tap = null; }, true);
addEventListener('pointerup', e=>{ const t = M.tap; if(!t) return; M.tap = null; e.stopPropagation(); if(t.moved) return; M.swallow = Date.now(); M.swXY = [e.clientX, e.clientY]; mAct(t.kind, t.el, e.clientX, e.clientY); }, true);
/* the click that follows a handled tap lands on whatever the tap just opened (the card sheet, the LOOK view): swallow it */
addEventListener('click', e=>{ if(Date.now()-M.swallow < 450 && M.swXY && Math.hypot(e.clientX-M.swXY[0], e.clientY-M.swXY[1]) < 24){ M.swallow = 0; e.stopPropagation(); e.preventDefault(); } }, true);
addEventListener('contextmenu', e=>{ if(e.pointerType === 'touch' || Date.now()-M.lastTouch < 1500){ e.preventDefault(); e.stopPropagation(); } }, true);

/* ---------- after every redraw ---------- */
const deskRender = render;
render = function(){ const r = deskRender.apply(this, arguments); try{ mAfter(); }catch(e){ console.error('phone layer', e); } return r; };
function mAfter(){ if($('#table').hidden) return;
  foldLands('#myBack', true); if(G.opp) foldLands('#oppBack', false);
  paintHandBtn(); if(HT.classList.contains('mhand')){ if(!G.me.hand.length) tray(false); else paintHint(); }
  if(M.lands) paintLands();
  if(M.view){ const a = findAny(M.view.id) || PEEK.get(M.view.id); if(!a) closeView(); else if(!M.view.look && (a.z !== 'bf' || !a.mine)) closeView(); }
  const se = $('#stack'), n = se.children.length; if(n !== M.stN){ se.scrollTop = se.scrollHeight; M.stN = n; } }
addEventListener('resize', ()=>{ try{ render(); }catch(e){} });

/* ---------- the front page ---------- */
(function(){ const lm = $('.lmain'); if(!lm) return; const n = document.createElement('p'); n.id = 'mNote';
  n.innerHTML = `<b>The phone table, an early test</b> (${MVERSION}). Hold your phone sideways. Practice alone is ready to try; playing a friend from a phone hasn't been tried yet. <a href="../">The desktop table</a>`;
  lm.prepend(n); })();
