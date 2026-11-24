/* The phone table (m/index.html only). It runs after the Modern Table's own script, reuses all of its rules and messages (so a phone can
   play a desktop), and changes only how the table is drawn and touched:
   - a tapped card opens larger with what you can do with it (its own menu, as buttons); LOOK reads a card instead (picture, text, right now)
   - your lands fold into one tile (a small picture per land, tapped ones turned); tapping it opens the lands box, which also opens while you pay
   - the hand is a fan of every card in the corner that opens into a tray; tapping a card there casts it, as a left click does on the desktop
   - menus open as a sheet with fingertip-sized rows; the hover enlargement is off
   - choosing targets has a strip that says what to tap, legal targets outlined in orange, and a Done button (m0.5)
   - blocking is guided: tap a blocker, then the attacker it blocks; blockers group under their attackers (m0.6) */
'use strict';
const MVERSION = 'm0.11';
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
  const tm = capture(()=>tableMenu(0, 0)).filter(it=>!(Array.isArray(it) && /tour|explore|^Leave the table/i.test(it[0])));   /* m0.9: Leave the table is Home, at the top */
  mMenu([
    ['⌂ Home (the front page)', ()=>mHome()],
    ['↻ Reload (back to this table)', ()=>mReload()],
    '-',
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

/* ---------- the hand: every card fanned at the bottom centre of the board (m0.3, m0.4 centred so tokens and markers in the corner stay in view; the maintainer: m0.1's fan, but the whole hand and less overlap); tapping it opens the tray ---------- */
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

/* ---------- screen edges (m0.4, the maintainer): keep the table clear of the iPhone's camera notch, with a manual margin per edge in Settings → Phone ----------
   The page fills the whole screen (viewport-fit=cover), so the phone reports how much of each edge its hardware covers (safe-area insets). In landscape
   an iPhone reports the same inset on both sides, so the camera side comes from how the phone is turned (angle 90: camera on the left, 270: right);
   only that side is kept clear, unless the phone doesn't say how it's turned. The margins below add to that, and follow the camera when the phone turns. */
const EDGE_PX = {'0':'None', '4':'+4', '8':'+8', '12':'+12', '20':'+20', '32':'+32'};
function envInsets(){ let pr = $('#mEnv'); if(!pr){ pr = document.createElement('div'); pr.id = 'mEnv';
    pr.style.cssText = 'position:fixed;left:0;top:0;width:0;height:0;visibility:hidden;pointer-events:none;padding:env(safe-area-inset-top,0px) env(safe-area-inset-right,0px) env(safe-area-inset-bottom,0px) env(safe-area-inset-left,0px)'; document.body.appendChild(pr); }
  const cs = getComputedStyle(pr); return {l:parseFloat(cs.paddingLeft)||0, r:parseFloat(cs.paddingRight)||0, b:parseFloat(cs.paddingBottom)||0}; }
function camSide(){ const o = screen.orientation, a = o && typeof o.angle === 'number' ? o.angle : (typeof window.orientation === 'number' ? (window.orientation + 360) % 360 : null);
  return a === 90 ? 'l' : a === 270 ? 'r' : null; }
function applyEdges(){ const e = envInsets(), auto = (S.mNotch || 'auto') === 'auto', side = camSide(), cam = +(S.mCam || 0), oth = +(S.mOth || 0), bot = +(S.mBot || 0), env = Math.max(e.l, e.r);
  let l = 0, r = 0; if(auto){ if(side === 'l') l = env; else if(side === 'r') r = env; else { l = e.l; r = e.r; } }
  if((side || 'l') === 'l'){ l += cam; r += oth; } else { r += cam; l += oth; }
  const was = M.edge; M.edge = {l, r, b:bot, side, env};
  HT.style.setProperty('--sl', l + 'px'); HT.style.setProperty('--sr', r + 'px'); HT.style.setProperty('--sb', bot + 'px');
  if(was && (was.l !== l || was.r !== r || was.b !== bot)) setTimeout(()=>{ try { render(); drawArrows(); } catch(err){} }, 60); }
function edgeHint(){ const e = M.edge || {}; if(!e.env) return 'Your phone reports no notch here, so the whole screen is used. The margins below still apply.';
  const where = e.side === 'l' ? 'on the left' : e.side === 'r' ? 'on the right' : 'on one side'; return `Your phone's camera is ${where} right now; ${Math.round(e.env)} px are kept clear there. It follows the camera when you turn the phone.`; }
SETROWS.unshift(
  {g:'Phone', k:'mnotch', l:'Camera notch', h:()=>edgeHint(), o:{auto:'Keep clear', off:'Use the whole screen'}, get:()=>S.mNotch || 'auto', set:v=>{ S.mNotch = v; applyEdges(); }},
  {g:'Phone', k:'mcam', l:'Extra margin, camera side', h:'Moves the table further in from the side your camera is on, in pixels.', o:EDGE_PX, get:()=>String(S.mCam || 0), set:v=>{ S.mCam = +v; applyEdges(); }},
  {g:'Phone', k:'moth', l:'Extra margin, other side', h:'For a rounded corner or a phone case on the other side.', o:EDGE_PX, get:()=>String(S.mOth || 0), set:v=>{ S.mOth = +v; applyEdges(); }},
  {g:'Phone', k:'mbot', l:'Extra margin, bottom', h:'Lifts the table above the home bar at the bottom of the screen.', o:EDGE_PX, get:()=>String(S.mBot || 0), set:v=>{ S.mBot = +v; applyEdges(); }});
applyEdges(); addEventListener('resize', applyEdges); addEventListener('orientationchange', ()=>setTimeout(applyEdges, 120));
if(screen.orientation && screen.orientation.addEventListener) screen.orientation.addEventListener('change', ()=>setTimeout(applyEdges, 120));

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
function landSize(n, paying, o){ o = o || 0;   /* n lands, then o other mana sources on rows of their own under a separator */ const rc = parseFloat(getComputedStyle(HT).getPropertyValue('--rcol')) || 132, ed = M.edge || {l:0, r:0, b:0}, W = innerWidth - rc - ed.l - ed.r - (paying ? Math.min(340, innerWidth*.44) + 8 : 0) - 22, Hh = innerHeight - ed.b - 84 - (o ? 26 : 0); let best = 44;
  for(let lw = 120; lw >= 44; lw -= 2){ const cell = lw*1.396 + 4 + 6, cols = Math.max(1, Math.floor((W+6)/cell)), rows = Math.max(1, Math.floor((Hh+6)/cell)); if(Math.ceil(n/cols) + Math.ceil(o/cols) <= rows){ best = lw; break; } }
  return best; }
/* a land with something to do besides tapping for mana (Mutavault, Fiery Islet's draw, Urza's Saga's construct): its button reads Abilities */
function landExtra(c){ return capture(()=>cardMenu(c.id, 0, 0)).some(it=>it && it.own && Array.isArray(it) && !Array.isArray(it[1]) && !/^(Tap|Untap)\b/.test(it[0])); }
/* m0.4 (the maintainer): mana you have besides lands (Treasures, mana rocks, mana creatures) sits in the same box, so it is in view while you pay.
   Identical ones are grouped (one card with a count); a tap is the desktop's left click on the top one. */
function manaOthers(){ return (G.me.bf||[]).filter(c=>{ if(foldable(c) || c.att) return false; try { return manaAbilities(c).length > 0; } catch(e){ return false; } }); }
function paintLands(){ const el = $('#mLands'); if(!M.lands) return; const mine = M.lands.mine, side = mine ? G.me : G.opp; if(!side){ closeLands(); return; }
  const lands = sideLands(mine), bf = side.bf || [], others = mine ? landGroups(manaOthers()) : [];
  const pool = mine ? MANA.filter(k=>(G.me.mana||{})[k]).map(k=>`<span style="display:inline-flex;align-items:center">${(G.me.mana[k]>1?`<b style="font-size:11px">${G.me.mana[k]}</b>`:'')}<i class="ms ms-${k}">${k}<img src="https://svgs.scryfall.io/card-symbols/${k}.svg" alt="" onerror="this.remove()"></i></span>`).join('') : '';
  const paying = mine && !$('#payPanel').hidden;
  el.innerHTML = `<header><h3>${mine ? (others.length ? 'Your lands and mana' : 'Your lands') : esc((G.opp&&G.opp.name)||'Opponent')+"'s lands"}</h3>${mine ? `<span class="mhint">${pool ? 'Pool' : 'Pool empty'}</span><span class="pool">${pool}</span>` : ''}<button class="${paying?'ghost':'go'}" data-ml="x">${paying ? 'Hide' : 'Done'}</button></header>
    <div class="mhint">${G.mode ? 'Tap a land to choose it.' : M.look ? 'LOOK is on: tap a land to read it.' : mine ? (paying ? (others.length ? 'Tap lands, or a Treasure or other mana below, to pay; each symbol in the payment box lights up as your pool covers it.' : 'Tap lands to pay; each symbol in the payment box lights up as your pool covers it.') : 'Tap a land to tap it for mana (a land with choices asks which); tap a tapped land to untap it. Abilities opens the rest.') : 'Tap a land to read it.'}</div>
    <div class="mlg" style="--lw:${landSize(lands.length, paying, others.length)}px">${lands.length ? lands.map(c=>`<div class="mlc">${bf.filter(a=>a.att===c.id).map(a=>cardHTML(a,'bf',mine,'under')).join('')}${cardHTML(c,'bf',mine)}${mine ? (landExtra(c) ? `<button class="mlm ab" data-ml="more" data-id="${c.id}">Abilities</button>` : `<button class="mlm" data-ml="more" data-id="${c.id}" aria-label="More">⋯</button>`) : ''}</div>`).join('') : '<span class="mhint">No lands.</span>'}${others.length ? `<div class="mlsep">Other mana</div>` + others.map(g=>{ const c = g[0]; return `<div class="mlc mlo">${cardHTML(c,'bf',true)}${g.length > 1 ? `<b class="mlcnt">×${g.length}</b>` : ''}${landExtra(c) ? `<button class="mlm ab" data-ml="more" data-id="${c.id}">Abilities</button>` : `<button class="mlm" data-ml="more" data-id="${c.id}" aria-label="More">⋯</button>`}</div>`; }).join('') : ''}</div>`; }
new MutationObserver(()=>{ const pp = $('#payPanel'), v = !pp.hidden; HT.classList.toggle('mpay', v);
  if(v){ tray(false); closeView(); if(!M.lands && (sideLands(true).length || manaOthers().length)){ openLands(true); M.autoLands = true; } else if(M.lands) paintLands(); }
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
  if(M.pre){ const z = el.dataset.z; return (el.closest(ROWS) || el.closest('#stack')) && (z === 'bf' || z === 'st') ? 'pre' : null; }
  if(G.mode) return null;
  if(el.closest('#offerwrap')) return 'look';   // m0.11 (the maintainer): a card in the Exiled by cards box isn't in my hand, so a tap reads it
  if(el.closest(ROWS) && el.dataset.z === 'bf' && blkCtx()){ const B = blkCtx(), a = findAny(el.dataset.id);
    if(a && (isBlockerOf(B, a.c) || (a.c.atk && (B.as.bf||[]).some(x=>x.id === a.c.id)))) return 'blk'; }
  if(el.closest(ROWS) && el.dataset.z === 'bf'){
    if(el.dataset.o !== 'me') return iControl() ? null : 'opp';
    if(G.atkSel && atkStep()) return null;
    const f = find(el.dataset.id); if(blockStep() && f && isCreature(f.c) && !f.c.tap) return null;
    return 'mine'; }
  return null; }
function handPlay(id, x, y){ const f = find(id); if(!f) return; if(G.me.ctl){ playFromHand(id); return; }
  if(preEligible(id)){ if(waitMull()) return; preStart(id); return; }
  if(mdfcLand(f.c)){ mdfcMenu(id, x, y); return; } if(isLand(f.c) && cyclingOf(f.c).length) cycLandClick(id); else playFromHand(id); }
function mAct(kind, el, x, y){ const id = el.dataset.id;
  if(kind === 'hand'){ if(M.look){ openLook(id); return; } if(M.pre){ if(id !== M.pre.id) toast(`Cast ${unlink(cname(find(M.pre.id).c))} or cancel it first.`); tray(false); return; } tray(false); handPlay(id, x, y); return; }
  if(kind === 'pre'){ preTap(id); return; }
  if(kind === 'look' || kind === 'opp'){ openLook(id); return; }
  if(kind === 'mine'){ openCard(id); return; }
  if(kind === 'blk'){ blkTap(el); return; }
  if(kind === 'lands'){ if(M.look){ openLook(id); return; } if(M.pre){ const f = find(M.pre.id), sp = f && tgtSpec(f.c, preMax().k); let ok = false; try { ok = !!sp && tgtCheck(sp, id).ok; } catch(e){} if(ok || M.pre.arr.some(a=>a.b === id)){ preTap(id); return; } } if(G.mode){ finishMode(id); return; } if(el.dataset.o === 'me') toggleTap(id, x, y); else openLook(id); } }
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

/* ---------- targeting (m0.5, the maintainer's design, step 2) ----------
   While a spell, ability or trigger of mine on the stack is choosing its targets (the desktop's arrow mode), a strip at the top says what it can target,
   legal targets get a dashed orange outline (the desktop already dims the rest), chosen ones an orange ring with a TARGET tag, and the big button reads
   Done / No target / Next target. The maintainer's rules: targets can be chosen up to the most allowed and Done pressed at any time before; at the most,
   the table waits for Done (it doesn't move on by itself), so a target can still be swapped: tapping a chosen target takes it back, and with room for
   only one, tapping another moves it. Too few on Done asks first (warn, don't refuse). Done is the desktop's Esc, so the rest (the next target phrase,
   a trigger marked as having no target) is the desktop's own. Cards with their own two-step flows (Searing Blaze, earthbend, bestow, blink, Auras) keep
   the desktop's behaviour under the strip. */
function mTgSrc(){ const md = G.mode; if(!md || md.type !== 'arrow' || !md.from || md.second) return null; const f = find(md.from); return f && f.z === 'st' ? f : null; }
function tgPlain(f){ const c = f.c; if(c.fd || c.bw || (c.ab && (c.ab.eb || c.ab.auto))) return false;
  try { if(twoTgt(c)) return false; if(!c.ab && !c.ch && isAura(c) && enchantOf(c)) return false; if(blinkOf(stackText(c) || '')) return false; return !!tgtSpec(c, 0); } catch(e){ return false; } }
const tgOwn = from => a => a.a === from && !a.blk;
function tgMax(md){ const f = find(md.from); if(!f) return null; const sl = tgtSlotsOf(md.from), k = md.slot || 0;
  if(sl) return {sl, k, max:sl[k].n, upto:!!sl[k].upto, last:k >= sl.length - 1};
  let ph = []; try { ph = tgtPhrases(tgtText(f.c)); } catch(e){}
  return {sl:null, k:0, max:ph[0] ? (ph[0].n === 'X' ? 1 : ph[0].n) : 1, upto:!!(ph[0] && ph[0].upto), last:true}; }
const tgName = t => t === G.myId ? G.me.name : t === oppId() ? ((G.opp && G.opp.name) || 'your opponent') : (findAny(t) ? cname(findAny(t).c) : 'that');
/* keep the session's arrow mode on until Done (runs before the desktop's autoArm, so another trigger doesn't take over before Done) */
function tgRearm(){ const t = M.tg; if(!t || t.done || !t.plain || G.mode) return false; const s = find(t.from);
  if(!s || s.z !== 'st'){ M.tg = null; return false; }
  if(G.trigHold || G.ordHold || PAY || G.atkSel || !$('#modal').hidden || isHeldTrig(s.c)) return false;
  G.mode = {type:'arrow', from:t.from, slot:t.slot || 0}; if(t.tq) G.mode.tq = 1; return true; }
const deskAutoArm = autoArm;
autoArm = function(){ if(tgRearm()) return; return deskAutoArm.apply(this, arguments); };
const deskFinish = finishMode;
finishMode = function(target){ const md = G.mode, t = M.tg;
  if(md && md.type === 'arrow' && t && t.plain && md.from === t.from){ const f = find(md.from), own = tgOwn(md.from);
    if(target === md.from){ toast(`Tap what ${unlink(srcName(f.c))} targets, then Done.`); return; }
    const hit = G.me.arrows.find(a=>own(a) && a.b === target);
    if(hit){ G.me.arrows = G.me.arrows.filter(a=>a !== hit); log(`${unlink(srcName(f.c))} no longer targets ${unlink(tgName(target))}.`);
      G.mode = {type:'arrow', from:md.from, slot:typeof hit.s === 'number' ? hit.s : (md.slot || 0)}; if(md.tq || t.tq) G.mode.tq = 1; changed(); return; }
    const mx = tgMax(md), mine = a=>own(a) && (!mx.sl || a.s === mx.k), have = G.me.arrows.filter(mine).length;
    if(mx.max < 99 && have >= mx.max){
      if(mx.max === 1){ if(!md.tgtOK){ const sp = tgtSpec(f.c, mx.k), r = sp && tgtCheck(sp, target); if(r && (!r.ok || r.cok === false)) return deskFinish.apply(this, arguments); }   // an illegal pick asks first; the old target stays until it's confirmed
        G.me.arrows = G.me.arrows.filter(a=>!mine(a)); }
      else { toast(`${mx.max} of ${mx.max} chosen: tap one to take it back, or Done.`); render(); return; } } }
  return deskFinish.apply(this, arguments); };
function mEsc(){ document.dispatchEvent(new KeyboardEvent('keydown', {key:'Escape', bubbles:true})); }
function tgDone(force){ const md = G.mode, f = mTgSrc(); if(!md || !f) return; const t = M.tg || {}, mx = tgMax(md) || {k:0, max:1, last:true}, own = tgOwn(md.from);
  const have = G.me.arrows.filter(a=>own(a) && (!mx.sl || a.s === mx.k)).length, nm = unlink(srcName(f.c)), sp = md.auto ? null : tgtSpec(f.c, mx.k);
  if(!force && !md.auto && t.plain && !mx.upto){
    if(!have){ const none = !G.me.arrows.some(own);
      modal(`${nm}: no target?`, `<span class="hint">${esc(nm)} asks for ${esc(sp ? sp.phrase : 'a target')}. ${none ? `Without one it won't do what it says to its target.` : 'Without one, that part does nothing.'}<br><br>Go on without a target only if you've both agreed it's allowed.</span>`,
        [['Choose a target', ()=>{ closeModal(); render(); }, 'ghost'], ['No target', ()=>{ closeModal(); tgDone(true); }, 'go']]); return; }
    if(mx.max > 1 && mx.max < 99 && have < mx.max){
      modal(`${nm}: only ${have} of ${mx.max}?`, `<span class="hint">${esc(nm)} asks for ${mx.max} targets and ${have === 1 ? 'one is' : have + ' are'} chosen.</span>`,
        [['Choose another', ()=>{ closeModal(); render(); }, 'ghost'], [`Go on with ${have}`, ()=>{ closeModal(); tgDone(true); }, 'go']]); return; } }
  if(mx.last && M.tg) M.tg.done = true;
  mEsc(); }
/* outlines legal targets, rings and tags chosen ones (arr: [{b, s}]), marks the source: shared by the stack's targeting (m0.5) and targets before paying (m0.8) */
function tgMark(from, arr, sp, tagOf){
  for(const el of document.querySelectorAll([...ROWS.split(','), '#stack', '#mLands'].map(r=>r + ' .card[data-id]').join(','))){ const id = el.dataset.id, z = el.dataset.z;
    if(id === from){ el.classList.add('mtsrc'); continue; } if(z !== 'bf' && z !== 'st') continue;
    const a = arr.find(x=>x.b === id); if(a){ el.classList.add('mtc'); const tg = document.createElement('span'); tg.className = 'mttag'; tg.textContent = tagOf(a); el.appendChild(tg); continue; }
    if(sp && !el.classList.contains('mfold')){ try { if(tgtCheck(sp, id).ok) el.classList.add('mtl'); } catch(e){} } }
  for(const av of [$('#oppAv'), $('#myAv')]){ if(!av) continue; const pl = av.dataset.pl; if(arr.some(x=>x.b === pl)) av.classList.add('mtc'); else if(sp){ try { if(tgtCheck(sp, pl).ok) av.classList.add('mtl'); } catch(e){} } }
  for(const tile of document.querySelectorAll('.mlands')){ const ls = sideLands(tile.dataset.mlands === 'me');
    if(ls.some(l=>arr.some(x=>x.b === l.id))) tile.classList.add('mtc'); else if(sp && ls.some(l=>{ try { return tgtCheck(sp, l.id).ok; } catch(e){ return false; } })) tile.classList.add('mtl'); } }
function tgPaint(){ const f = mTgSrc(), on = !!f && $('#table').hidden === false; HT.classList.toggle('mtgt', on);
  const strip = $('#mTgt'), go = $('#mTgtGo');
  document.querySelectorAll('.mtl,.mtc,.mtsrc').forEach(el=>el.classList.remove('mtl','mtc','mtsrc')); document.querySelectorAll('.mttag').forEach(el=>el.remove());
  if(!on){ strip.hidden = true; go.hidden = true; return; }
  const md = G.mode, c = f.c, mx = tgMax(md), own = tgOwn(md.from), arr = G.me.arrows.filter(own), have = arr.filter(a=>!mx.sl || a.s === mx.k).length;
  const sp = md.auto ? null : (TGS || tgtSpec(c, mx.k)), nm = unlink(srcName(c));
  tgMark(md.from, arr, sp, a=>mx.sl && mx.sl.length > 1 ? `TARGET ${(a.s || 0) + 1}` : 'TARGET');
  /* the strip */
  const what = md.auto ? ((c.ab && c.ab.what) || 'its target') : sp ? sp.phrase : 'its target', cnt = mx.max >= 99 ? `${have} chosen` : mx.max > 1 ? `${have} of ${mx.max} chosen` : '';
  strip.innerHTML = `<div class="in"><b>${esc(nm)}</b>${mx.sl && mx.sl.length > 1 ? `<span class="n">Target ${mx.k + 1} of ${mx.sl.length}</span>` : ''}${cnt ? `<span class="n">${cnt}</span>` : ''}<span class="c">tap ${esc(what)}${sp && sp.cond ? ` · ${esc(sp.cond.note)}` : ''}${mx.upto ? ' (or none)' : ''}${arr.length && M.tg && M.tg.plain ? ' · tap one again to take it back' : ''}</span></div>`;
  strip.hidden = false; { const mr = $('#mid').getBoundingClientRect(); if(mr.height) Object.assign(strip.style, {top:(mr.top + mr.height / 2) + 'px', left:(mr.left + 6) + 'px', right:Math.max(0, innerWidth - mr.right + 6) + 'px'}); }
  /* the big button, over the desktop's */
  const lbl = mx.sl && !mx.last ? (have || !mx.upto ? 'Next target' : `Skip target ${mx.k + 1}`) : (have || arr.length ? 'Done' : 'No target');
  const sub = mx.sl && !mx.last ? `then target ${mx.k + 2} of ${mx.sl.length}` : cnt || (have ? `targets: ${arr.map(a=>unlink(tgName(a.b))).join(', ')}` : '');
  go.innerHTML = `<b>${esc(lbl)}</b>${sub ? `<small>${esc(sub)}</small>` : ''}`; go.classList.toggle('none', lbl === 'No target');
  const r = $('#next').getBoundingClientRect(); if(r.width){ Object.assign(go.style, {left:r.left + 'px', top:r.top + 'px', width:r.width + 'px', height:Math.max(48, r.height) + 'px'}); }
  go.hidden = false; }
(function(){ const s = document.createElement('div'); s.id = 'mTgt'; s.hidden = true; document.body.appendChild(s);
  const g = document.createElement('button'); g.id = 'mTgtGo'; g.hidden = true; document.body.appendChild(g); g.onclick = ()=>tgDone();
  /* the desktop's other "click something" modes (attach, block, exile with…) get tap wording and a button in place of Esc */
  $('#modebar').addEventListener('click', e=>{ if(e.target.closest('[data-mesc]')){ e.stopPropagation(); mEsc(); } }); })();
function modebarPhone(){ const mb = $('#modebar'); if(!mb || mb.hidden || HT.classList.contains('mtgt') || !G.mode || mb.querySelector('[data-mesc],[data-notgt]')) return;
  const lbl = G.mode.type === 'atktgt' ? `Attack ${(G.opp && G.opp.name) || 'the player'}` : 'Cancel';
  mb.innerHTML = esc(mb.textContent.replace(/ · Esc cancels$/, '').replace(/\b([Cc])lick(ed|ing|s)?\b/g, (z, c0, e)=>(c0 === 'C' ? 'T' : 't') + 'ap' + (e === 'ed' ? 'ped' : e === 'ing' ? 'ping' : e || ''))) + ` <button data-mesc>${esc(lbl)}</button>`; }
/* toasts: the strip already says what to tap; the rest say tap, not click, and lose their Esc hints */
const deskToast = toast;
toast = function(t){ t = String(t == null ? '' : t);
  if(mTgSrc() && /\bclick\b/i.test(t) && /target|Esc|enchant/i.test(t)) return;
  t = t.replace(/\s*\((?:[^()]*?;\s*)?Esc\b[^()]*\)/g, '').replace(/,? or NO TARGET/, '').replace(/\b([Cc])lick(ed|ing|s)?\b/g, (z, c0, e)=>(c0 === 'C' ? 'T' : 't') + 'ap' + (e === 'ed' ? 'ped' : e === 'ing' ? 'ping' : e || ''));
  return deskToast.call(this, t); };

/* ---------- targets before paying (m0.8, the maintainer's prototype: target first, then "Cast it: pay {R}") ----------
   Tapping an instant or sorcery in the hand that targets (Lightning Bolt, Fatal Push, Counterspell) doesn't pay at once: the card sits in the
   stack column as CASTING, the strip says what to tap, legal targets are outlined and chosen ones ringed (the same marks as m0.5), an orange line
   joins the card to each target, and the big button reads "Cast it" with the cost under it (Next target for a spell with several target phrases).
   Cancel in the strip puts it back. Cast it runs the desktop's own cast (timing, payment window, everything); once the spell reaches the stack
   its targets are put on it, so the m0.5 screen doesn't open again. A spell whose cast has its own choices (X, modes, kicker and other ways to
   cast, split, adventure and double-faced cards, Auras, divided damage, graveyard targets, Searing Blaze-style two-step targets) keeps the
   desktop's order: pay, then target. The same rules as m0.5: up to the most allowed, tap a chosen target to take it back, with room for one
   tapping another moves it, too few asks first, an illegal one asks Pick another / Target anyway (logged once it's cast). */
function preEligible(id){ const f = find(id); if(M.preOff || !f || f.z !== 'hand' || G.me.ctl || G.mode || PAY) return false;   /* M.preOff: tests of the m0.5 screen with spells */ const c = f.c; if(c.fd || !(c.k || c.cu)) return false;
  try { const d = cdata(c), o = d.o || '', txt = stackText(c) || o;
    if(!/\b(?:Instant|Sorcery)\b/.test(d.t || '') || isLand(c) || isSplit(c) || d.back || /adventure|split|modal|transform|flip/i.test(d.lay || '')) return false;
    if(/\{X\}/.test(d.mc || '') || /\bchoose (?:one|two|three|four|any number|one or more|one or both)\b|\b(?:Spree|Escalate|Entwine|Kicker|Multikicker|Overload|Replicate|Splice|Buyback|Cleave|Strive)\b|\bdivided\b|\btarget[^.]*graveyard/i.test(o)) return false;
    if(!needsTarget(txt) || !tgtSpec(c, 0) || twoTgt(c) || blinkOf(txt) || (isAura(c) && enchantOf(c))) return false;
    if(castWays(c, id).length || castTimeWhy(c)) return false;
    return true; } catch(e){ return false; } }
function preMax(){ const p = M.pre, f = p && find(p.id); if(!f) return null; const k = p.slot || 0; let sl = null; try { sl = tgtSlots(f.c); } catch(e){}
  if(sl && sl.length) return {sl, k, max:sl[k].n === 'X' ? 1 : sl[k].n, upto:!!sl[k].upto, last:k >= sl.length - 1};
  let ph = []; try { ph = tgtPhrases(tgtText(f.c)); } catch(e){}
  return {sl:null, k:0, max:ph[0] ? (ph[0].n === 'X' ? 1 : ph[0].n) : 1, upto:!!(ph[0] && ph[0].upto), last:true}; }
function preStart(id){ M.pre = {id, slot:0, arr:[]}; closeMenu(); render(); }
function preEnd(note){ if(!M.pre) return; M.pre = null; if(note) toast(note); render(); }
function preTap(t){ const p = M.pre, f = p && find(p.id); if(!f) return; const c = f.c, nm = unlink(cname(c)), mx = preMax();
  if(t === p.id) return;
  const hit = p.arr.find(a=>a.b === t);
  if(hit){ p.arr = p.arr.filter(a=>a !== hit); if(mx.sl && typeof hit.s === 'number') p.slot = hit.s; render(); return; }
  const mine = a => !mx.sl || a.s === mx.k, have = p.arr.filter(mine).length;
  if(mx.max < 99 && have >= mx.max && mx.max > 1){ toast(`${mx.max} of ${mx.max} chosen: tap one to take it back, or ${mx.last ? 'Cast it' : 'Next target'}.`); return; }
  const add = any => { if(mx.max === 1) p.arr = p.arr.filter(a=>!mine(a)); const a = {b:t}; if(mx.sl) a.s = mx.k; if(any) a.any = any; p.arr.push(a);
    if(mx.sl && !mx.last && p.arr.filter(mine).length >= mx.max) p.slot = mx.k + 1; render(); };
  const sp = tgtSpec(c, mx.k), r = sp ? tgtCheck(sp, t) : {ok:true};
  if(r.ok && r.cok !== false) return add();
  const tn = unlink(tgName(t));
  modal(r.ok ? `${nm} won't do anything to that` : `${nm} can't target that`, `<span class="hint">${esc(unlink(r.ok ? `${nm} can target ${tn}, but ${r.cwhy}.` : `${nm} ${r.why}.`))}<br><br>${r.ok ? 'Target it anyway?' : 'Target anyway only if you have both agreed it\'s allowed.'}</span>`,
    [['Pick another target', ()=>{ closeModal(); render(); }, 'ghost'], ['Target anyway', ()=>{ closeModal(); add(r.ok ? 'anyway' : `anyway (it ${r.why})`); }, 'go']]); }
function preGo(force){ const p = M.pre, f = p && find(p.id); if(!f) return; const nm = unlink(cname(f.c)), mx = preMax(), sp = tgtSpec(f.c, mx.k);
  const have = p.arr.filter(a=>!mx.sl || a.s === mx.k).length;
  if(!force && !mx.upto){
    if(!have){ modal(`${nm}: no target?`, `<span class="hint">${esc(nm)} asks for ${esc(sp ? sp.phrase : 'a target')}. Without one it won't do what it says to its target.<br><br>Go on without a target only if you've both agreed it's allowed.</span>`,
        [['Choose a target', ()=>{ closeModal(); render(); }, 'ghost'], [mx.last ? 'Cast it anyway' : 'Skip this target', ()=>{ closeModal(); preGo(true); }, 'go']]); return; }
    if(mx.max > 1 && mx.max < 99 && have < mx.max){ modal(`${nm}: only ${have} of ${mx.max}?`, `<span class="hint">${esc(nm)} asks for ${mx.max} targets and ${have === 1 ? 'one is' : have + ' are'} chosen.</span>`,
        [['Choose another', ()=>{ closeModal(); render(); }, 'ghost'], [`Go on with ${have}`, ()=>{ closeModal(); preGo(true); }, 'go']]); return; } }
  if(!mx.last){ p.slot = mx.k + 1; render(); return; }
  M.preCast = {id:p.id, arr:p.arr.slice(), at:Date.now()}; M.pre = null; render(); playFromHand(p.id); }
/* once the spell is on the stack, its targets go on it (the desktop's arrows, logged as the desktop logs them) and its own target mode ends */
function preApply(){ const pc = M.preCast; if(!pc) return false; const f = find(pc.id);
  if(!f || (f.z !== 'st' && f.z !== 'hand')){ M.preCast = null; return false; }
  if(f.z === 'hand'){ if(!PAY && $('#modal').hidden && Date.now() - pc.at > 800) M.preCast = null; return false; }   /* the payment or a question was cancelled */
  M.preCast = null; const c = f.c; let sl = null; try { sl = tgtSlots(c); } catch(e){}
  G.me.arrows = G.me.arrows.filter(a=>a.a !== pc.id || a.blk);
  for(const a of pc.arr){ G.me.arrows.push(sl && typeof a.s === 'number' ? {a:pc.id, b:a.b, s:a.s} : {a:pc.id, b:a.b}); const tn = unlink(tgName(a.b));
    log(a.any ? `${G.me.name} targets ${tn} with ${cname(c)} ${a.any}.` : `${cname(c)} targets ${tn}${sl && sl.length > 1 ? ` (target ${(a.s || 0) + 1} of ${sl.length})` : ''}.`); }
  if(!pc.arr.length) log(`${cname(c)} is cast without a target.`);
  if(G.mode && G.mode.type === 'arrow' && G.mode.from === pc.id) G.mode = null;
  setTimeout(()=>{ try { changed(); } catch(e){} }, 0); return true; }
function prePaint(){ const p = M.pre, f = p && find(p.id), svg = $('#mPreArw'); document.querySelectorAll('.mcast').forEach(e=>e.remove()); HT.classList.toggle('mpre', !!f);
  if(!f){ svg.innerHTML = ''; svg.style.display = 'none'; return; }
  const c = f.c, d = cdata(c), mx = preMax(), sp = tgtSpec(c, mx.k), nm = unlink(cname(c)), have = p.arr.filter(a=>!mx.sl || a.s === mx.k).length;
  HT.classList.add('mtgt'); tgMark(p.id, p.arr, sp, a=>mx.sl && mx.sl.length > 1 ? `TARGET ${(a.s || 0) + 1}` : 'TARGET');
  /* the card, waiting in the stack column */
  const st = $('#stack'), cast = document.createElement('div'); cast.className = 'mcast'; cast.innerHTML = picHTML(c, true) + '<b>CASTING</b>'; st.appendChild(cast); cast.scrollIntoView({block:'nearest'});
  /* the strip */
  const strip = $('#mTgt'), go = $('#mTgtGo'), cnt = mx.max >= 99 ? `${have} chosen` : mx.max > 1 ? `${have} of ${mx.max} chosen` : '';
  strip.innerHTML = `<div class="in"><b>${esc(nm)}</b>${mx.sl && mx.sl.length > 1 ? `<span class="n">Target ${mx.k + 1} of ${mx.sl.length}</span>` : ''}${cnt ? `<span class="n">${cnt}</span>` : ''}<span class="c">tap ${esc(sp ? sp.phrase : 'its target')}${sp && sp.cond ? ` · ${esc(sp.cond.note)}` : ''}${mx.upto ? ' (or none)' : ''}${p.arr.length ? ' · tap one again to take it back' : ''}</span><button data-mpre="x">Cancel</button></div>`;
  strip.hidden = false; { const mr = $('#mid').getBoundingClientRect(); if(mr.height) Object.assign(strip.style, {top:(mr.top + mr.height / 2) + 'px', left:(mr.left + 6) + 'px', right:Math.max(0, innerWidth - mr.right + 6) + 'px'}); }
  /* the big button */
  if(mx.last){ go.innerHTML = `<b>Cast it</b>${d.mc ? `<small>pay ${mcHTML(d.mc)}</small>` : '<small>no mana to pay</small>'}`; go.classList.remove('none'); }
  else { const lbl = have || !mx.upto ? 'Next target' : `Skip target ${mx.k + 1}`; go.innerHTML = `<b>${esc(lbl)}</b><small>then target ${mx.k + 2} of ${mx.sl.length}</small>`; go.classList.remove('none'); }
  const r = $('#next').getBoundingClientRect(); if(r.width) Object.assign(go.style, {left:r.left + 'px', top:r.top + 'px', width:r.width + 'px', height:Math.max(48, r.height) + 'px'});
  go.hidden = false;
  /* lines from the card to its targets */
  const cr = cast.getBoundingClientRect(), x0 = cr.left, y0 = cr.top + cr.height / 2; let paths = '';
  for(const a of p.arr){ let el = document.querySelector(`#oppAv[data-pl="${a.b}"], #myAv[data-pl="${a.b}"]`) || [...document.querySelectorAll(`.card[data-id="${a.b}"]`)].find(e=>e.offsetParent && !e.closest('#myHand,#mLands'));
    if(!el){ const l = findAny(a.b); if(l && l.z === 'bf') el = document.querySelector(`.mlands[data-mlands="${l.mine ? 'me' : 'opp'}"]`); }
    if(!el) continue; const tr = el.getBoundingClientRect(), x1 = tr.left + tr.width / 2, y1 = tr.top + tr.height / 2, mx2 = (x0 + x1) / 2, my2 = Math.min(y0, y1) - 30;
    paths += `<path d="M${x0},${y0} Q${mx2},${my2} ${x1},${y1}"/><circle cx="${x1}" cy="${y1}" r="5"/>`; }
  svg.innerHTML = paths; svg.style.display = paths ? '' : 'none'; }
(function(){ const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); s.id = 'mPreArw'; s.style.display = 'none'; document.body.appendChild(s);
  $('#mTgtGo').onclick = ()=>{ if(M.pre) preGo(); else tgDone(); };
  $('#mTgt').addEventListener('click', e=>{ if(e.target.closest('[data-mpre="x"]')){ e.stopPropagation(); preEnd(); } });
  /* a player box is a target too */
  addEventListener('click', e=>{ if(!M.pre || M.look) return; const av = e.target.closest && e.target.closest('#oppAv,#myAv'); if(!av || e.target.closest('button,input,a')) return;
    e.stopPropagation(); e.preventDefault(); preTap(av.dataset.pl); }, true); })();

/* ---------- guided blocking (m0.6, the maintainer's design, step 2) ----------
   When I am attacked (blockStep) or I declare Practice's blocks against my attack (pblockStep), the table guides it: tap a blocker (orange ring,
   BLOCKER), then the attacker it blocks (blue ring, BLOCKED, an arrow joins them). While a blocker is chosen, the attackers it can block get a
   dashed blue outline; tapping the chosen blocker again lets it go; tapping a creature that already blocks takes its block back. A block the table
   thinks breaks a rule (flying, landwalk, …) asks first with Block anyway (logged), in the table's warn-don't-refuse spirit. The strip has Undo and
   Clear; the big button reads No blocks / Done blocking (N), which runs the desktop's own finish (its menace and must-block checks included).
   Blockers rearrange like paper (the maintainer): the row puts other permanents first, then blockers grouped under the attacker they block
   (attackers in their row's order, a small gap between groups), then creatures not blocking; cards slide to their new places. */
function blkCtx(){ if(!G.turn || !G.turn.n || G.mode) return null;
  if(blockStep()) return {mine:true, bs:G.me, as:G.opp, arr:()=>G.me.arrows, setArr:v=>{ G.me.arrows = v; },
    can:()=>blockersLeft(), done:()=>doneBlocking(), who:'you', issues:(b,a)=>blockIssues(b,a)};
  if(typeof pblockStep === 'function' && pblockStep()) return {mine:false, bs:G.opp, as:G.me, arr:()=>G.opp.arrows, setArr:v=>{ G.opp.arrows = v; },
    can:()=>dummyBlockers(), done:()=>pblockBtn('done'), who:'Practice', issues:(b,a)=>{ let r = []; asDummy(()=>{ r = blockIssues(b, a).map(x=>x.replace(/\byou control\b/g, 'Practice controls')); }); return r; }};
  return null; }
const isBlockerOf = (B, c) => !!c && (B.bs.bf||[]).some(x=>x.id === c.id) && isCreature(c) && !c.fd;
function blkSnap(B){ M.blk.hist.push(JSON.stringify(B.arr().filter(a=>a.blk))); if(M.blk.hist.length > 40) M.blk.hist.shift(); }
function blkSet(B, blks){ B.setArr([...B.arr().filter(a=>!a.blk), ...blks]); }
function blkTap(el){ const B = blkCtx(); if(!B) return; const id = el.dataset.id, a = findAny(id); if(!a) return; const c = a.c, nm = x=>unlink(cname(x));
  M.blk = M.blk || {sel:null, hist:[]};
  if(isBlockerOf(B, c)){
    if(M.blk.sel === id){ M.blk.sel = null; render(); return; }
    const mineB = B.arr().filter(x=>x.blk && x.a === id);
    if(mineB.length && !multiBlock(c)){ blkSnap(B); B.setArr(B.arr().filter(x=>!(x.blk && x.a === id))); log(`${B.mine ? G.me.name+"'s" : "Practice's"} ${nm(c)} no longer blocks.`); M.blk.sel = null; changed(); return; }
    if(c.tap){ toast(`${nm(c)} is tapped, so it can't block.`); return; }
    if(!B.can().some(x=>x.id === id)){ toast(`${nm(c)} is already blocking.`); return; }
    M.blk.sel = id; render(); return; }
  if(c.atk && (B.as.bf||[]).some(x=>x.id === id)){
    const sel = M.blk.sel && (B.bs.bf||[]).find(x=>x.id === M.blk.sel);
    if(!sel){ toast(`Tap one of ${B.mine ? 'your' : "Practice's"} untapped creatures first, then the attacker it blocks.`); return; }
    const go = force=>{ blkSnap(B); B.setArr(B.arr().filter(x=>!(x.blk && x.a === sel.id && (!multiBlock(sel) || x.b === id)))); B.arr().push({a:sel.id, b:id, blk:1});
      log(`${B.mine ? G.me.name+"'s" : "Practice's"} ${nm(sel)} blocks ${nm(c)}${force ? ` (blocked anyway: ${force})` : ''}.`); M.blk.sel = null; changed(); };
    const iss = B.issues(sel, c);
    if(iss.length){ modal(`${nm(sel)} can't block ${nm(c)}?`, `<span class="hint">${esc(unlink(iss.join('; ')))}.<br><br>Block anyway only if you've both agreed it's allowed; it goes in the log.</span>`,
      [['Pick another', ()=>{ closeModal(); render(); }, 'ghost'], ['Block anyway', ()=>{ closeModal(); go(unlink(iss.join('; '))); }, 'go']]); return; }
    go(); return; } }
function blkPaint(){ const B = blkCtx(), strip = $('#mBlk'), go = $('#mBlkGo'); HT.classList.toggle('mblk', !!B && !HT.classList.contains('mtgt'));
  document.querySelectorAll('.mbsel,.mbcan,.mbok,.mbatk,.mbon').forEach(el=>el.classList.remove('mbsel','mbcan','mbok','mbatk','mbon')); document.querySelectorAll('.mbtag').forEach(el=>el.remove());
  if(!B || HT.classList.contains('mtgt')){ strip.hidden = true; go.hidden = true; if(!B && M.blk){ M.blk = null; } return; }
  M.blk = M.blk || {sel:null, hist:[]}; if(M.blk.sel && !B.can().some(x=>x.id === M.blk.sel)) M.blk.sel = null;
  const sel = M.blk.sel && (B.bs.bf||[]).find(x=>x.id === M.blk.sel), blks = B.arr().filter(a=>a.blk), atks = (B.as.bf||[]).filter(c=>c.atk), canIds = new Set(B.can().map(c=>c.id));
  const tag = (el, t, cls) => { const s = document.createElement('span'); s.className = 'mbtag' + (cls ? ' '+cls : ''); s.textContent = t; el.appendChild(s); };
  for(const el of document.querySelectorAll('#myFront .card[data-id], #oppFront .card[data-id], #myBack .card[data-id], #oppBack .card[data-id]')){ if(el.dataset.z !== 'bf') continue; const id = el.dataset.id;
    const isB = blks.some(a=>a.a === id), nB = blks.filter(a=>a.b === id).length, at = atks.find(c=>c.id === id);
    if(id === M.blk.sel){ el.classList.add('mbsel'); tag(el, 'BLOCKER'); continue; }
    if(isB){ el.classList.add('mbon'); tag(el, 'BLOCKS'); continue; }
    if(at){ if(nB){ el.classList.add('mbatk'); tag(el, nB > 1 ? `BLOCKED ×${nB}` : 'BLOCKED', 'blue'); }
      if(sel){ let ok = false; try { ok = !B.issues(sel, at).length; } catch(e){} if(ok) el.classList.add('mbcan'); } continue; }
    if(!sel && canIds.has(id)) el.classList.add('mbok'); }
  const must = B.mine ? mustBlockNotes() : [], n = blks.length;
  const txt = sel ? `<b>${esc(unlink(cname(sel)))}</b><span class="c">now tap the attacker it blocks (tap it again to let go)</span>`
    : canIds.size ? `<b>${B.mine ? 'Blocking' : 'Practice blocks'}</b><span class="c">tap ${B.mine ? 'your creature' : "Practice's creature"}, then the attacker it blocks</span>`
    : `<b>${B.mine ? 'Blocking' : 'Practice blocks'}</b><span class="c">${n ? 'no more creatures can block' : `none of ${B.mine ? 'your' : "Practice's"} creatures can block`}</span>`;
  strip.innerHTML = `<div class="in">${txt}${must.map(x=>`<span class="c mm">${esc(unlink(x))}</span>`).join('')}${n || (M.blk.hist.length) ? `<span class="bb">${M.blk.hist.length ? '<button data-mb="undo">Undo</button>' : ''}${n ? '<button data-mb="clear">Clear</button>' : ''}</span>` : ''}</div>`;
  strip.hidden = false; { const mr = $('#mid').getBoundingClientRect(); if(mr.height) Object.assign(strip.style, {top:(mr.top + mr.height / 2) + 'px', left:(mr.left + 6) + 'px', right:Math.max(0, innerWidth - mr.right + 6) + 'px'}); }
  go.innerHTML = n ? `<b>Done blocking (${n})</b>` : `<b>No blocks</b>`; go.classList.toggle('none', !n);
  const r = $('#next').getBoundingClientRect(); if(r.width) Object.assign(go.style, {left:r.left + 'px', top:r.top + 'px', width:r.width + 'px', height:Math.max(48, r.height) + 'px'});
  go.hidden = false; }
(function(){ const s = document.createElement('div'); s.id = 'mBlk'; s.hidden = true; document.body.appendChild(s);
  s.addEventListener('click', e=>{ const b = e.target.closest('[data-mb]'); const B = blkCtx(); if(!b || !B) return; e.stopPropagation();
    if(b.dataset.mb === 'undo'){ const h = M.blk && M.blk.hist.pop(); if(h != null){ blkSet(B, JSON.parse(h)); log(`${B.mine ? G.me.name : 'Practice'}: the last block is undone.`); M.blk.sel = null; changed(); } }
    else if(b.dataset.mb === 'clear'){ blkSnap(B); blkSet(B, []); M.blk.sel = null; log(B.mine ? `${G.me.name} resets their blocks.` : "Practice's blocks are reset."); changed(); } });
  const g = document.createElement('button'); g.id = 'mBlkGo'; g.hidden = true; document.body.appendChild(g);
  g.onclick = ()=>{ const B = blkCtx(); if(!B) return; if(M.blk) M.blk.sel = null; B.done(); }; })();
/* blockers rearrange like paper: groups under their attackers, sliding into place */
function blkUnits(row){ return [...row.children].filter(u=>!u.classList.contains('mlands')).map(u=>{ const cs = u.matches('.card[data-id]') ? [u] : [...u.querySelectorAll('.card[data-id]')];
  const main = cs.find(e=>!e.classList.contains('under')) || cs[0]; return {u, id:main && main.dataset.id, ids:cs.map(e=>e.dataset.id)}; }); }
function blkArrange(){ const done = [];
  for(const [rowSel, side, other] of [['#myFront', G.me, G.opp], ['#oppFront', G.opp, G.me]]){ const row = $(rowSel); if(!row || !side || !other) continue;
    const blks = (side.arrows||[]).filter(a=>a.blk); row.querySelectorAll('.mbgap').forEach(u=>u.classList.remove('mbgap')); if(!blks.length) continue;
    const atkOrder = [...document.querySelectorAll(`${rowSel === '#myFront' ? '#oppFront' : '#myFront'} .card[data-id]`)].map(e=>e.dataset.id);
    const units = blkUnits(row), first = [], groups = new Map(), rest = [];
    for(const x of units){ const b = blks.find(a=>x.ids.includes(a.a)); const c = x.id && findAny(x.id);
      if(b){ const k = b.b; if(!groups.has(k)) groups.set(k, []); groups.get(k).push(x); } else if(c && isCreature(c.c)) rest.push(x); else first.push(x); }
    const keys = [...groups.keys()].sort((p, q)=>{ const i = atkOrder.indexOf(p), j = atkOrder.indexOf(q); return (i < 0 ? 999 : i) - (j < 0 ? 999 : j); });
    const order = [...first]; keys.forEach(k=>{ const g = groups.get(k); g[0].u.classList.add('mbgap'); order.push(...g); }); if(rest.length) rest[0].u.classList.add('mbgap'); order.push(...rest);
    if(order.some((x, i)=>units[i] !== x)){ order.forEach(x=>row.appendChild(x.u)); done.push(row); } }
  return done; }
const anyBlk = () => !!((G.me && (G.me.arrows||[]).some(a=>a.blk)) || (G.opp && (G.opp.arrows||[]).some(a=>a.blk)));
function blkSnapPos(){ const m = new Map(); for(const el of document.querySelectorAll('#myFront .card[data-id], #oppFront .card[data-id]')){ const r = el.getBoundingClientRect(); m.set(el.dataset.id, [r.left, r.top]); } return m; }
/* the desktop's own slide (tapAnim) was worked out for its order, not ours: in a rearranged row it is replaced by a slide from where each card was on screen */
/* The desktop drew the arrows before the rows were re-ordered, so they point where the cards were (the maintainer, m0.7: Ocelot Pride's block arrow
   stayed at its old spot). The arrows are hidden while the cards slide and drawn again once they have settled, then fade in. */
const BLK_SLIDE = 400;
function blkSlide(before, rows){ if(!rows.length) return; const still = typeof noMotion === 'function' && noMotion(); let moved = 0;
  for(const row of rows) for(const el of row.querySelectorAll('.card[data-id]')){ try { el.getAnimations().forEach(a=>a.cancel()); } catch(e){}
    const o = before && before.get(el.dataset.id); if(!o || still) continue; const r = el.getBoundingClientRect(), dx = o[0] - r.left, dy = o[1] - r.top;
    if(Math.abs(dx) < 2 && Math.abs(dy) < 2) continue; moved++; el.animate([{translate:`${dx}px ${dy}px`}, {translate:'0 0'}], {duration:BLK_SLIDE, easing:'ease-out'}); }
  const g = $('#arrowG'); clearTimeout(M.arT);
  if(!moved){ if(g){ g.style.opacity = ''; } drawArrows(); return; }
  if(g) g.style.opacity = '0';
  M.arT = setTimeout(()=>{ drawArrows(); const a = $('#arrowG'); if(!a) return; a.style.opacity = '';
    try { a.animate([{opacity:0}, {opacity:1}], {duration:180, easing:'ease-out'}); } catch(e){} }, BLK_SLIDE + 20); }

/* ---------- m0.8: the left rail fits (the maintainer: the city's blessing had gone missing) ----------
   The desktop's fitLeft (v5.08) measures how much #midRail overflows with the piles at full height. On a phone the two pile columns are
   already squeezed below their own content at full height, so that number came out far too small: the piles shrank only partway and the wins
   box and the city's blessing ended up under my piles. Here the whole rail is measured: both pile columns' natural heights, #midRail's
   content, the gaps and the padding, against the rail's height. */
fitLeft = function(){ FITL = 0; const L = $('#left'), mr = $('#midRail'); if(!L || !mr || !L.offsetParent) return;
  const piles = [...L.querySelectorAll('.piles .pile')]; if(!piles.length) return;
  L.style.removeProperty('--pileh'); const full = piles[0].offsetHeight, cs = getComputedStyle(L);
  const kids = [...L.children].filter(e => e.offsetParent || e === mr), gap = parseFloat(cs.rowGap) || 0;
  const room = L.clientHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom) - gap * Math.max(0, kids.length - 1);
  const need = kids.reduce((s, e) => s + (e === mr ? [...mr.children].filter(x => !x.hidden && getComputedStyle(x).display !== 'none')
      .reduce((t, x, i) => t + x.offsetHeight + (i ? parseFloat(getComputedStyle(mr).rowGap) || 0 : 0), 0) : e.scrollHeight), 0);
  const over = need - room; if(over > 0) L.style.setProperty('--pileh', Math.max(PILE_MIN, Math.floor(full - over / piles.length)) + 'px'); };

/* ---------- after every redraw ---------- */
const deskRender = render;
render = function(){ let pre = null; try { if(G && G.me && !$('#table').hidden && anyBlk()) pre = blkSnapPos(); } catch(e){}
  const r = deskRender.apply(this, arguments); try{ mAfter(pre); }catch(e){ console.error('phone layer', e); } return r; };
function mAfter(pre){ if($('#table').hidden) return;
  foldLands('#myBack', true); if(G.opp) foldLands('#oppBack', false);
  blkSlide(pre, blkArrange());
  paintHandBtn(); if(HT.classList.contains('mhand')){ if(!G.me.hand.length) tray(false); else paintHint(); }
  if(M.lands) paintLands();
  if(M.view){ const a = findAny(M.view.id) || PEEK.get(M.view.id); if(!a) closeView(); else if(!M.view.look && (a.z !== 'bf' || !a.mine)) closeView(); }
  if(M.pre){ const f = find(M.pre.id); if(!f || f.z !== 'hand') M.pre = null; else if(G.mode || PAY){ M.pre = null; toast(`${unlink(cname(f.c))} wasn't cast.`); } }
  preApply();
  { const f = mTgSrc(); if(f){ if(!M.tg || M.tg.from !== f.c.id){
      /* the table already chose the only possible target (Thought-Knot Seer's "target opponent" with one opponent): nothing to wait for */
      const mx = tgMax(G.mode), own = tgOwn(f.c.id), have = mx ? G.me.arrows.filter(a=>own(a) && (!mx.sl || a.s === mx.k)).length : 0;
      if(mx && mx.last && mx.max < 99 && have >= mx.max){ G.mode = null; setTimeout(()=>{ try { render(); } catch(e){} }, 0); }
      else M.tg = {from:f.c.id, plain:tgPlain(f), tq:!!G.mode.tq}; }
    if(M.tg && G.mode){ M.tg.slot = G.mode.slot || 0; if(G.mode.tq) M.tg.tq = true; } }
    else if(M.tg){ const s = find(M.tg.from); if(!s || s.z !== 'st' || M.tg.done) M.tg = null; } }
  tgPaint(); prePaint(); blkPaint(); modebarPhone();
  const se = $('#stack'), n = se.children.length; if(n !== M.stN){ se.scrollTop = se.scrollHeight; M.stN = n; } }
addEventListener('resize', ()=>{ try{ render(); }catch(e){} });

/* ---------- the front page ---------- */
(function(){ const lm = $('.lmain'); if(!lm) return; const n = document.createElement('p'); n.id = 'mNote';
  n.innerHTML = `<b>The phone table, an early test</b> (${MVERSION}). Hold your phone sideways. Practice alone is ready to try; playing a friend from a phone hasn't been tried yet. <a href="../">The desktop table</a> <button class="mnav" data-mnav="reload" title="Load the page again (picks up the newest version)">↻ Reload</button>`;
  lm.prepend(n); })();

/* ---------- home and reload (m0.9, the maintainer: added to the home screen, the phone page has no browser bar, so no back or refresh) ----------
   ⌂ Home goes to the front page (the desktop's Leave the table: the seat is kept and the front page offers Resume), ↻ Reload loads the page
   again and, from a table or the deck screen of an open table, takes you straight back to it (sessionStorage mt_mresume → the front page's
   own Resume button). In the ☰ sheet (Home replaces Leave the table), in the deck screen's top bar, and Reload on the front page. */
const mOpen = () => !!(G && G.me && (G.code || G.solo) && $('#lobby').hidden);
function mHome(){ if(!$('#lobby').hidden) return; const go = ()=>{ try{ save(); }catch(e){} location.href = location.pathname; };
  if(mOpen()) confirmBox('Go to the front page?', 'Your seat at this table is kept: the front page offers Resume to come back.', go); else go(); }
function mReload(){ if(mOpen()){ try{ save(); }catch(e){} try{ sessionStorage.setItem('mt_mresume', '1'); }catch(e){} } location.reload(); }
(function(){ const tb = $('#decks .topbar'); if(tb){ const w = document.createElement('span'); w.className = 'mnavs';
    w.innerHTML = '<button class="mnav" data-mnav="home" title="The front page">⌂ Home</button><button class="mnav" data-mnav="reload" title="Load the page again">↻</button>'; tb.appendChild(w); }
  document.addEventListener('click', e=>{ const b = e.target.closest && e.target.closest('[data-mnav]'); if(!b) return; e.preventDefault(); e.stopPropagation(); b.dataset.mnav === 'home' ? mHome() : mReload(); }, true);
  let r = null; try{ r = sessionStorage.getItem('mt_mresume'); sessionStorage.removeItem('mt_mresume'); }catch(e){}
  if(r){ const rb = $('#resumeBtn'); if(rb && !rb.hidden) setTimeout(()=>rb.click(), 0); } })();
