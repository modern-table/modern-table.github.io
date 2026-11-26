/* The phone table (m/index.html only). It runs after the Modern Table's own script, reuses all of its rules and messages (so a phone can
   play a desktop), and changes only how the table is drawn and touched:
   - a tapped card opens larger with what you can do with it (its own menu, as buttons); LOOK reads a card instead (picture, text, right now)
   - your lands fold into one tile (a small picture per land, tapped ones turned); tapping it opens the lands box, which also opens while you pay
   - the hand is a fan of every card in the corner that opens into a tray; tapping a card there casts it, as a left click does on the desktop
   - menus open as a sheet with fingertip-sized rows; the hover enlargement is off
   - choosing targets has a strip that says what to tap, legal targets outlined in orange, and a Done button (m0.5)
   - blocking is guided: tap a blocker, then the attacker it blocks; blockers group under their attackers (m0.6) */
'use strict';
const MVERSION = 'm0.15';
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
    ['Energy and poison counters…', ()=>ctrMenu(0, 0, G.myId)],   /* m0.12: the player-box chips show only when a deck uses them (v5.37); a phone has no right-click */
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
  const se = $('#stack'), n = se.children.length; if(n !== M.stN){ se.scrollTop = se.scrollHeight; M.stN = n; }
  waitPaint(); mLogPaint(); }
addEventListener('resize', ()=>{ try{ render(); }catch(e){} });

/* ---------- the table code while waiting (m0.13, the maintainer: the code must stay in view until you choose to practice alone) ----------
   The desktop's waiting box says "Send them the code X" in its .dk line, which the phone hides with every deck name. While no one has joined
   a table I opened (no G.opp, not practice), the box shows the code large; a tap copies it. "Skip the roll (practice alone)" makes Practice
   the opponent, and the box becomes Practice's. */
function waitPaint(){ const av = $('#oppAv'); if(!av) return; const on = !G.opp && !G.solo && !!G.code; av.classList.toggle('mwait', on);
  if(!on || av.querySelector('.mcode')) return;
  av.innerHTML = `<div class="nm">Waiting for your friend</div><button class="mcode" data-mcode title="Tap to copy the code">Table code<b>${esc(G.code)}</b><i>tap to copy</i></button><div class="chips"><span class="pill" id="netPill2"></span></div>`;
  try{ renderNet(); }catch(e){} }
document.addEventListener('click', e=>{ const b = e.target.closest && e.target.closest('[data-mcode]'); if(!b) return; e.preventDefault(); e.stopPropagation();
  const c = G.code || ''; const ok = ()=>toast(`Table code ${c} copied: send it to your friend.`), no = ()=>toast(`Table code: ${c}`);
  try{ navigator.clipboard.writeText(c).then(ok, no); }catch(err){ no(); } }, true);

/* ---------- the log beside the stack (m0.13, the maintainer: the phone had no log in view) ----------
   #mLog sits under #stackwrap in the right column: the last lines of the game log, card names in brass, newest at the bottom. A tap opens the
   full log and chat panel. Sharing the space (the maintainer's pick of three prototypes, over always half and half and over the stack replacing
   the log): while the stack is empty it shrinks to its header ("Stack · empty") and the log fills the column; while it holds something, the
   two split the space half and half (CSS :has on #stackwrap). */
const MLOG_N = 40;
function mLogPaint(){ let el = $('#mLog'); if(!el){ const sw = $('#stackwrap'); if(!sw) return; el = document.createElement('div'); el.id = 'mLog';
    el.innerHTML = '<h4>Log</h4><div class="mlb"></div>'; el.title = 'Tap for the whole log and chat'; sw.after(el);
    /* only a touch that began on the log opens the panel: tapping the last stack card resolves it, the stack shrinks, and the click that
       ends that tap lands on the log */
    el.addEventListener('pointerdown', ()=>{ M.logDown = Date.now(); });
    el.addEventListener('click', e=>{ e.preventDefault(); e.stopPropagation(); if(!(Date.now() - (M.logDown||0) < 1500)) return; M.logDown = 0; HT.classList.add('mlog'); try{ renderLog(); }catch(err){} }); }
  const L = G.log || [], last = L[L.length-1], key = L.length + '|' + (last ? last.text : ''); if(key === M.logK) return; M.logK = key;
  const b = el.querySelector('.mlb');
  b.innerHTML = L.slice(-MLOG_N).map(l=>`<div class="${l.cls||''}">${(l.cls==='cm'||l.cls==='co') ? esc(l.text).replace(/^([^:]{1,40}:)/,'<b>$1</b>') : esc(l.text).replace(/\[\[([^|\]]*)\|[^\]]*\]\]/g,(_,n)=>`<span class="cn">${n}</span>`)}</div>`).join('');
  b.scrollTop = b.scrollHeight; }

/* ---------- held upright (m0.14, the maintainer: the plain "turn sideways" line felt empty): the splash's cards, name and rule, still ---------- */
(function(){ const d = document.createElement('div'); d.id = 'mTurn'; d.setAttribute('aria-live', 'polite');
  d.innerHTML = '<div class="mt-in"><div class="mt-cards"><i class="mt-c mt-b"></i><i class="mt-c mt-g"></i></div><div class="mt-t">Modern Table</div><i class="mt-r"></i>'
    + '<div class="mt-s"><span class="mt-ph" aria-hidden="true"></span>Turn your phone sideways to play.</div></div>';
  document.body.prepend(d); })();

/* ---------- the front page ---------- */
(function(){ const lm = $('.lmain'); if(!lm) return; const n = document.createElement('p'); n.id = 'mNote';
  n.innerHTML = `<b>The phone table · beta</b> (${MVERSION}). Hold your phone sideways. You can play friends on phones or computers with the same table code. Something feel off? <a href="${esc(feedbackUrl('Phone table'))}" target="_blank" rel="noopener">Send feedback</a> · <a href="../?desk=1" title="The computer layout, on this phone (remembered; the phone table link on that page brings you back)">The desktop table</a> <button class="mnav" data-mnav="reload" title="Load the page again (picks up the newest version)">↻ Reload</button>`;
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

/* ---------- the deck screen (m0.15, the maintainer's design in claude/mobile-design.md: "Deck screen", the Design canvas prototype) ----------
   The desktop's deck screen (tabs, land art, the editor) is hidden; #mDeck takes its place inside #decks. Left: This week's decks / My decks
   (17 px bold names, finish, event and date under each), a filter, and Paste a deck list at the bottom. Right: the chosen deck (name, counts with
   a warning under 60 or over 15 in the sideboard, Play this deck, Edit, Delete for my own), Main / Sideboard, and three views: Pictures (the
   default), Columns, List. A tap on a card reads it; while editing, the same sheet has − / + for the main deck and the sideboard, and a bar adds
   a card by name. Editing a weekly deck makes my copy, "<name> (edited)", in My decks at the first change; every change is saved at once (Undo
   takes the last one back). Paste: a name, the list, a running count (and the lines left out), Paste from clipboard, Open a file, Add deck; once
   added, the names are checked with Scryfall: a misspelling it recognizes is corrected in the saved list, one it doesn't is named.
   renderTab and viewDeck (function declarations in the page) are reassigned, so the page's own paths (a table's deck change, Game Night's
   newest deck, the saved list after a delete) all land here. Build from scratch and the land art are desktop only. */
const MD = { src: store.get('mt_mdsrc', 'tour') === 'saved' ? 'saved' : 'tour', sel:null, part:'main', view: ['pics','cols','list'].includes(store.get('mt_mdview','pics')) ? store.get('mt_mdview','pics') : 'pics',
  q:'', ed:null, paste:null, note:null, tok:0, sq:0, hits:[], tried:{} };
const mdSaved = () => store.get('mt_decks', []);
const mdK = (art, n) => (art && art[keyOf(n)]) || keyOf(n);
const mdP = k => ({id:'s:'+k, k});
function mdCur(){ const s = MD.sel; if(!s) return null;
  if(MD.ed) return {d:{main:[...MD.ed.main].filter(x=>x[1]>0), side:[...MD.ed.side].filter(x=>x[1]>0), art:MD.ed.art}, name:MD.ed.name, sub:'Editing', mine:true};
  if(s.kind === 'tour'){ const d = DECKS[s.i]; if(!d) return null; return {d:{main:d.main, side:d.side, art:{}}, name:d.arch, sub:`${d.place} · ${d.pilot} · ${d.ev}, ${mdShort(d.date)}`, link:deckLink(d)}; }
  if(s.kind === 'saved'){ const sv = mdSaved()[s.i]; if(!sv) return null; const d = parseDeck(sv.text); return {d, name:sv.name, sub: isLimited(d) ? 'Draft deck' : 'My deck', mine:true}; }
  return {d:s.d, name:s.name, sub:s.sub||''}; }
const mdLine = (art, [n,c]) => `${c} ${n}${art && art[keyOf(n)] ? ' ['+art[keyOf(n)]+']' : ''}`;
const mdText = d => d.main.map(x=>mdLine(d.art, x)).join('\n') + (d.side.length ? '\n\nSideboard\n'+d.side.map(x=>mdLine(d.art, x)).join('\n') : '');
function mdCap(n, art){ if(Object.keys(art||{}).length || BASIC_RE.test(n)) return Infinity; const e = DB[keyOf(n)], o = (e && e.o) || '';
  if(/A deck can have any number of cards named/i.test(o)) return Infinity; const m = o.match(/A deck can have up to (\w+) cards named/i); return m ? (NUMW2[m[1].toLowerCase()] || +m[1] || 4) : 4; }
function mdShort(date){ const m = String(date||'').match(/^(\d{4})-(\d\d)-(\d\d)$/); return m ? ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][+m[2]-1]+' '+(+m[3]) : String(date||''); }

(function(){ const dk = $('#decks'); if(!dk) return; const w = document.createElement('div'); w.id = 'mDeck'; dk.appendChild(w);
  w.addEventListener('click', mdClick); w.addEventListener('input', mdInput);
  const f = document.createElement('input'); f.type = 'file'; f.id = 'mdFile'; f.accept = '.txt,.dek,.dec,text/plain'; f.hidden = true; dk.appendChild(f);
  f.onchange = async ()=>{ const x = f.files[0]; f.value = ''; if(!x) return; const t = await x.text(); if(!MD.paste) MD.paste = {}; MD.paste.text = t; if(!MD.paste.name) MD.paste.name = x.name.replace(/\.\w+$/, ''); mdPaint(); };
  const v = $('#mView'); if(v) v.addEventListener('click', mdViewClick); })();
renderTab = function(){ const tb = $('#tabBody'); if(tb) tb.innerHTML = ''; mdPaint(); };
viewDeck = function(d, name, sub, link, canSave, savedIdx){ MD.paste = null; MD.ed = null;
  if(savedIdx != null){ MD.src = 'saved'; MD.sel = {kind:'saved', i:savedIdx}; }
  else { const i = DECKS.findIndex(x=>x.main === d.main); MD.sel = i >= 0 ? {kind:'tour', i} : {kind:'temp', d, name, sub}; if(i >= 0) MD.src = 'tour'; }
  mdPaint(); };

function mdRows(){ if(MD.src === 'tour'){ const q = MD.q.toLowerCase(); let s = '';
    DECKS.forEach((d,i)=>{ if(q && !(d.arch+' '+d.pilot+' '+d.ev+' '+d.main.map(x=>x[0]).join(' ')).toLowerCase().includes(q)) return;
      const on = !MD.paste && MD.sel && MD.sel.kind === 'tour' && MD.sel.i === i;
      s += `<button class="drow mdr${on?' on':''}" data-md="t${i}"><b class="an">${esc(d.arch)}</b><small>${esc(d.place)} · ${esc(d.ev)} · ${esc(mdShort(d.date))}</small></button>`; });
    return s || '<p class="mdhint">No decks match.</p>'; }
  const sv = mdSaved(); if(!sv.length) return '<p class="mdhint">Decks you paste or edit show up here, on this phone only.</p>';
  return sv.map((x,i)=>{ const d = parseDeck(x.text), on = !MD.paste && MD.sel && MD.sel.kind === 'saved' && MD.sel.i === i;
    return `<button class="drow mdr${on?' on':''}" data-md="s${i}"><b class="an">${esc(x.name)}</b><small>${deckCount(d.main)} main · ${deckCount(d.side)} sideboard${isLimited(d)?' · draft':''}</small></button>`; }).join(''); }

function mdPaint(){ const w = $('#mDeck'); if(!w) return; const tb = $('#tabBody'); if(tb && tb.innerHTML) tb.innerHTML = '';
  const nS = mdSaved().length, act = document.activeElement, keepQ = act && act.id === 'mdQ', keepF = act && act.id === 'mdFilt';
  const sc = (sel => { const x = w.querySelector(sel); return x ? x.scrollTop : 0; }), st0 = sc('.mdrows'), st1 = sc('.mdbody'), same = MD.lastSel === JSON.stringify([MD.src, MD.sel && MD.sel.kind, MD.sel && MD.sel.i, MD.part, MD.view]);
  w.innerHTML = `<div class="mdl"><div class="mdseg"><button data-mds="tour" class="${MD.src==='tour'?'on':''}">This week's decks</button><button data-mds="saved" class="${MD.src==='saved'?'on':''}">My decks${nS?` <i>${nS}</i>`:''}</button></div>
      ${MD.src==='tour' ? `<input id="mdFilt" class="mdfilt" placeholder="Filter: deck, player, event or card" value="${esc(MD.q)}" autocomplete="off" aria-label="Filter decks">` : ''}
      <div class="mdrows">${mdRows()}</div><button class="mdpaste${MD.paste?' on':''}" data-mdp>+ Paste a deck list</button></div>
    <div class="mdv">${MD.paste ? mdPasteHTML() : mdViewHTML()}</div>`;
  if(keepF){ const f = $('#mdFilt'); if(f){ f.focus(); f.setSelectionRange(f.value.length, f.value.length); } }
  if(keepQ){ const q = $('#mdQ'); if(q){ q.focus(); } }
  const rw = w.querySelector('.mdrows'); if(rw) rw.scrollTop = st0; const bd = w.querySelector('.mdbody'); if(bd && same) bd.scrollTop = st1;
  MD.lastSel = JSON.stringify([MD.src, MD.sel && MD.sel.kind, MD.sel && MD.sel.i, MD.part, MD.view]);
  const on = w.querySelector('.mdr.on'); if(on && !MD.keepScroll) on.scrollIntoView({block:'nearest'}); MD.keepScroll = false;
  if(MD.paste) mdCount(); else mdLoad(); }

function mdViewHTML(){ const cur = mdCur();
  if(!cur) return `<div class="mdempty"><h3>Pick a deck</h3><p>This week's decks are Modern tournament lists from the last two weeks. Tap one to see all 75 cards, then <b>Play this deck</b>.</p><p>Got your own list? <b>Paste a deck list</b> at the bottom left: any usual text format works, from MTGGoldfish, MTGTop8, Moxfield, Arena or MTGO.</p></div>`;
  const d = cur.d, nm = deckCount(d.main), ns = deckCount(d.side), w = deckIssues(d), ed = MD.ed;
  const note = MD.note && MD.sel && MD.note.i === MD.sel.i && MD.sel.kind === 'saved' ? `<div class="mdnote">${MD.note.html}</div>` : '';
  return `<div class="mdhd"><div class="mdti"><h3>${esc(cur.name)}</h3><span class="mdsub">${esc(ed ? 'Editing: every change is saved to My decks' : cur.sub)}</span>
      <span class="mdcnt${w.length?' bad':''}">${nm} main · ${ns} sideboard${w.length ? ' · '+esc(w.map(x=>/main/.test(x)?(isLimited(d)?'a draft deck needs 40':'needs 60'):'15 at most').join(', ')) : ''}</span></div>
    <div class="mdbt">${ed ? `<button data-mde="undo"${ed.hist.length?'':' disabled'}>Undo</button><button class="go" data-mde="done">Done</button>`
      : `<button class="go" id="mdPlay" data-mde="play">Play this deck</button><button data-mde="edit">Edit</button>${cur.mine && MD.sel.kind==='saved' ? '<button data-mde="del">Delete</button>' : ''}`}<span class="mdmsg" id="mdMsg"></span></div></div>${note}
  ${ed ? `<div class="mdaddw"><input id="mdQ" placeholder="Add a card to the ${MD.part==='main'?'main deck':'sideboard'}: type its name" autocomplete="off" autocapitalize="words" aria-label="Add a card"><div id="mdSug" hidden></div></div>` : ''}
  <div class="mdbar"><div class="mdseg sm"><button data-mdpt="main" class="${MD.part==='main'?'on':''}">Main <i>${nm}</i></button><button data-mdpt="side" class="${MD.part==='side'?'on':''}">Sideboard <i>${ns}</i></button></div>
    <div class="mdseg sm"><button data-mdw="pics" class="${MD.view==='pics'?'on':''}">Pictures</button><button data-mdw="cols" class="${MD.view==='cols'?'on':''}">Columns</button><button data-mdw="list" class="${MD.view==='list'?'on':''}">List</button></div>
    ${ed ? '<span class="mdtip">Tap a card for − / +</span>' : '<span class="mdtip">Tap a card to read it</span>'}</div>
  <div class="mdbody" id="mdBody">${mdBodyHTML(d)}</div>`; }

const mdOrd = c => isLand(c) ? 3 : isCreature(c) ? 0 : /\b(Instant|Sorcery)\b/.test(faceType(c)) ? 1 : 2;
function mdItems(d){ const list = MD.part === 'main' ? d.main : d.side;
  return list.filter(x=>x[1]>0).map(([n,c])=>({n, c, k:mdK(d.art, n)})).sort((a,b)=>{ const A = mdP(a.k), B = mdP(b.k);
    return (isLand(A)?1:0)-(isLand(B)?1:0) || (isLand(A)?0:manaValue(A))-(isLand(B)?0:manaValue(B)) || a.n.localeCompare(b.n); }); }
function mdTile(it, cls=''){ const e = DB[it.k], img = e && !e.tmp && e.img, ring = unlearned(mdP(it.k)) ? '<span class="unlr"></span>' : '';
  return `<button class="mdpic${cls}" data-mk="${esc(it.k)}" data-mn="${esc(it.n)}"><span class="mdim">${img ? `<img src="${esc(img)}" alt="${esc(it.n)}" loading="lazy" draggable="false" onerror="this.remove()">` : ''}<span class="mdtx"><b>${esc(e && !e.tmp ? e.n : it.n)}</b><i>${esc((e && e.t) || '')}</i></span>${ring}</span><b class="mdn">${it.c}</b></button>`; }
function mdBodyHTML(d){ const items = mdItems(d);
  if(!items.length) return `<p class="mdhint">${MD.part==='side' ? 'No sideboard.' : 'No cards yet.'}${MD.ed ? ' Add one with the bar above.' : ''}</p>`;
  if(MD.view === 'pics') return `<div class="mdpics">${items.map(it=>mdTile(it)).join('')}</div>`;
  if(MD.view === 'cols'){ const cols = new Map(); for(const it of items){ const c = mdP(it.k), key = isLand(c) ? 'L' : Math.min(7, manaValue(c)); if(!cols.has(key)) cols.set(key, []); cols.get(key).push(it); }
    const keys = [...cols.keys()].sort((a,b)=>(a==='L')-(b==='L') || a-b);
    return `<div class="mdcols">${keys.map(k=>{ const l = cols.get(k); return `<div class="mdcol"><div class="mdch">${k==='L' ? 'Lands' : (k>=7 ? '7+' : k)+' mana'} · <i>${l.reduce((a,x)=>a+x.c,0)}</i></div>${l.map(it=>mdTile(it, ' st')).join('')}</div>`; }).join('')}</div>`; }
  const groups = [['Creatures',0],['Instants and sorceries',1],['Other spells',2],['Lands',3]].map(([t,o])=>[t, items.filter(it=>mdOrd(mdP(it.k))===o)]).filter(g=>g[1].length);
  return `<div class="mdlist">${groups.map(([t,l])=>`<div class="mdlg"><h5>${t} <i>${l.reduce((a,x)=>a+x.c,0)}</i></h5>${l.map(it=>{ const e = DB[it.k];
    return `<button class="mdli" data-mk="${esc(it.k)}" data-mn="${esc(it.n)}"><b>${it.c}</b><span>${esc(e && !e.tmp ? e.n : it.n)}${unlearned(mdP(it.k)) ? ' <span class="unlr inl"></span>' : ''}</span><em>${e && e.mc ? mcHTML(e.mc) : ''}</em></button>`; }).join('')}</div>`).join('')}</div>`; }
function mdBody(){ const b = $('#mdBody'), cur = mdCur(); if(b && cur){ const st = b.scrollTop; b.innerHTML = mdBodyHTML(cur.d); b.scrollTop = st; } }
async function mdLoad(){ const cur = mdCur(); if(!cur) return; const my = ++MD.tok, ks = [...cur.d.main, ...cur.d.side].map(x=>mdK(cur.d.art, x[0]));
  const now = Date.now(), want = ks.filter(k=>!(DB[k] && !DB[k].tmp) && !(MD.tried[k] > now - 120000));   // a name Scryfall didn't know is asked again after 2 minutes, not at every repaint
  if(!want.length) return; want.forEach(k=>MD.tried[k] = now); const m = $('#mdMsg'); if(m) m.textContent = 'Loading card pictures…';
  try{ await ensureCards(want); }catch(e){}
  if(my !== MD.tok) return; const m2 = $('#mdMsg'); if(m2) m2.textContent = ks.some(k=>DB[k] && DB[k].tmp) && SCRY_DOWN ? 'Scryfall is not answering: cards show as text for now.' : ''; mdBody(); }

/* editing */
function mdEditStart(){ const cur = mdCur(); if(!cur || MD.ed) return;
  MD.ed = {main:new Map(cur.d.main), side:new Map(cur.d.side), art:Object.assign({}, cur.d.art||{}), name: MD.sel.kind === 'saved' ? cur.name : cur.name+' (edited)', idx: MD.sel.kind === 'saved' ? MD.sel.i : null, hist:[]};
  mdPaint(); }
function mdSnap(){ return {main:new Map(MD.ed.main), side:new Map(MD.ed.side)}; }
function mdStore(){ const e = MD.ed; if(!e) return; const d = {main:[...e.main].filter(x=>x[1]>0), side:[...e.side].filter(x=>x[1]>0), art:e.art}, text = mdText(d), sv = mdSaved();
  if(e.idx == null || !sv[e.idx]){ sv.unshift({name:e.name, text}); e.idx = 0; toast(`Saved to My decks as “${e.name}”.`); } else sv[e.idx] = {name:e.name, text};
  store.set('mt_decks', sv); MD.src = 'saved'; store.set('mt_mdsrc', 'saved'); MD.sel = {kind:'saved', i:e.idx}; }
function mdChange(n, part, by){ const e = MD.ed; if(!e) return false; const m = part === 'main' ? e.main : e.side, have = m.get(n)||0, tot = (e.main.get(n)||0)+(e.side.get(n)||0);
  if(by < 0 && !have) return false;
  if(by > 0 && tot >= mdCap(n, e.art)){ toast(`${n}: ${mdCap(n, e.art)} copies at most across the main deck and sideboard.`); return false; }
  e.hist.push(mdSnap()); if(e.hist.length > 60) e.hist.shift();
  const v = have + by; if(v > 0) m.set(n, v); else m.delete(n);
  mdStore(); return true; }
function mdUndo(){ const e = MD.ed; if(!e || !e.hist.length) return; const h = e.hist.pop(); e.main = h.main; e.side = h.side; mdStore(); mdPaint(); }

/* the card sheet: read it, or − / + while editing */
function mdCard(k, n){ const v = $('#mView'); if(!v) return; closeMenu(); const c = mdP(k), d = cdata(c), e = MD.ed;
  M.view = {id:null, deck:1}; v.classList.add('mdsheet');
  const row = (part, lbl)=>{ const m = part === 'main' ? e.main : e.side, x = m.get(n)||0;
    return `<div class="mdrow"><span>${lbl}</span><button data-mdv="${part}-" aria-label="One fewer"${x?'':' disabled'}>−</button><b>${x}</b><button data-mdv="${part}+" aria-label="One more">+</button></div>`; };
  const cap = e ? mdCap(n, e.art) : 4;
  const img = DB[k] && !DB[k].tmp && DB[k].img;
  v.innerHTML = `<div class="mpic"><div class="txt"><b>${esc(d.n || n)}</b><span>${esc(d.mc||'')}</span><i>${esc(d.t||'')}</i><span>${esc(d.o||'')}</span></div>${img ? `<img src="${esc(img)}" alt="${esc(d.n||n)}" draggable="false" onerror="this.remove()" style="position:relative;z-index:1">` : ''}</div>` + `<div class="mside"><button class="ghost mx" data-mdv="x">Close</button><h3>${esc(d.n || n)}</h3>
    <div class="mty">${esc([d.mc, d.t, d.pt, d.loy ? 'loyalty '+d.loy : ''].filter(Boolean).join(' · '))}</div>
    ${e ? `<div class="mded" data-mdn="${esc(n)}">${row('main','Main deck')}${row('side','Sideboard')}<div class="mhint">${cap===Infinity ? 'Any number of copies.' : `Up to ${cap} copies across both.`}</div></div>` : ''}
    <div class="mox">${esc(d.o || (DB[k] && DB[k].tmp ? 'The table hasn’t found this card on Scryfall yet: check its spelling.' : ''))}</div></div>`;
  v.hidden = false; }
function mdViewClick(e){ if(!M.view || !M.view.deck) return; const b = e.target.closest('[data-mdv]'); if(!b) return; e.stopPropagation();
  const k = b.dataset.mdv; if(k === 'x'){ closeView(); $('#mView').classList.remove('mdsheet'); return; }
  const box = b.closest('[data-mdn]'), n = box && box.dataset.mdn; if(!n) return;
  const [part, op] = [k.slice(0,-1), k.slice(-1)];
  if(mdChange(n, part, op === '+' ? 1 : -1)){ const kk = mdK(MD.ed.art, n); mdPaint(); mdCard(kk, n); } }
const mdCloseView0 = closeView;
closeView = function(){ const v = $('#mView'); if(v) v.classList.remove('mdsheet'); mdCloseView0(); };

/* adding a card by name */
async function mdSearch(q){ const my = ++MD.sq; let names = [];
  try{ const r = await sfetch('https://api.scryfall.com/cards/autocomplete?q='+encodeURIComponent(q)); if(r.ok){ const j = await r.json(); names = (j.data||[]).filter(Boolean); } }catch(e){}
  if(my !== MD.sq) return;
  if(!names.length){ const pq = plainName(q); names = [...new Set(Object.values(DB).filter(e=>e && !e.tmp && e.n && !/\bToken\b/.test(e.t||'') && plainName(e.n).includes(pq)).map(e=>e.n))]
    .sort((a,b)=>(plainName(a).startsWith(pq)?0:1)-(plainName(b).startsWith(pq)?0:1) || a.localeCompare(b)); }
  MD.hits = names.slice(0, 6); mdSug(); }
function mdSug(){ const el = $('#mdSug'), q = $('#mdQ'); if(!el || !q) return; const show = q.value.trim().length >= 2; el.hidden = !show; if(!show) return;
  el.innerHTML = MD.hits.length ? MD.hits.map(n=>`<button data-mda="${esc(n)}">${esc(n)}</button>`).join('') : '<span class="mdhint">Looking…</span>'; }
async function mdAdd(n){ if(!MD.ed) return; const q = $('#mdQ'); if(q){ q.value = ''; q.blur(); } MD.hits = [];
  try{ await ensureCards([n]); }catch(e){}
  if(mdChange(n, MD.part, 1)){ mdPaint(); mdCard(mdK(MD.ed.art, n), n); } else mdPaint(); }

/* pasting */
function mdPasteHTML(){ const p = MD.paste;
  return `<div class="mdpaste2"><div class="mdhd"><div class="mdti"><h3>Paste a deck list</h3><span class="mdsub">One card per line, like <b>4 Lightning Bolt</b>, then a line that says <b>Sideboard</b>. Lists from MTGGoldfish, MTGTop8, Moxfield, Arena and MTGO all work.</span></div></div>
    <div class="mdpf"><input id="mdPN" placeholder="Deck name" value="${esc(p.name||'')}" autocomplete="off" autocapitalize="words" aria-label="Deck name"><button data-mdpb="clip">Paste from clipboard</button><button data-mdpb="file">Open a file</button></div>
    <textarea id="mdPT" placeholder="4 Ragavan, Nimble Pilferer&#10;4 Lightning Bolt&#10;…&#10;&#10;Sideboard&#10;2 Blood Moon" aria-label="Deck list" autocapitalize="off" autocorrect="off" spellcheck="false">${esc(p.text||'')}</textarea>
    <div class="mdpb"><span id="mdPC" class="mdcnt"></span><button data-mdpb="x">Cancel</button><button class="go" data-mdpb="add" id="mdPAdd">Add deck</button></div></div>`; }
function mdCount(){ const el = $('#mdPC'), t = $('#mdPT'); if(!el || !t) return; MD.paste.text = t.value; const d = parseDeck(t.value), nm = deckCount(d.main), ns = deckCount(d.side), w = deckIssues(d);
  const add = $('#mdPAdd'); if(add) add.disabled = !nm;
  el.className = 'mdcnt' + (nm && w.length ? ' bad' : '');
  el.innerHTML = !t.value.trim() ? 'Paste or type the list.' : !nm ? 'No card lines found yet.'
    : `${nm} main · ${ns} sideboard${w.length ? ' · '+esc(w.map(x=>/main/.test(x)?'a deck needs 60':'15 at most in the sideboard').join(', ')) : ' ✓'}${d.skip.length ? ` <span class="mdskip" title="${esc(d.skip.join('\n'))}">· left out ${d.skip.length} line${d.skip.length>1?'s':''}: ${esc(d.skip.slice(0,2).join(', '))}${d.skip.length>2?', …':''}</span>` : ''}`; }
async function mdPasteAdd(){ const t = $('#mdPT'), nmEl = $('#mdPN'); if(!t) return; const d = parseDeck(t.value); if(!d.main.length){ toast('No card lines found in that text.'); return; }
  const name = (nmEl && nmEl.value.trim()) || 'My deck', sv = mdSaved(); sv.unshift({name, text:mdText(d)}); store.set('mt_decks', sv);
  MD.paste = null; MD.ed = null; MD.src = 'saved'; store.set('mt_mdsrc', 'saved'); MD.sel = {kind:'saved', i:0}; MD.part = 'main';
  MD.note = {i:0, html:'Checking the card names…'}; mdPaint(); mdCheck(name); }
async function mdCheck(name){ const sv0 = mdSaved(), i = sv0.findIndex(x=>x.name === name); if(i < 0) return; const d = parseDeck(sv0[i].text), names = [...d.main, ...d.side].map(x=>x[0]);
  const now = Date.now(); names.forEach(n=>MD.tried[mdK(d.art, n)] = now);
  try{ await ensureCards(names.map(n=>mdK(d.art, n))); }catch(e){}
  const fix = [], miss = []; let down = false;
  for(const n of new Set(names)){ const e = DB[mdK(d.art, n)]; if(!e || e.tmp){ if(SCRY_DOWN) down = true; else miss.push(n); continue; }
    if(!d.art[keyOf(n)] && plainName(e.n.split(' // ')[0]) !== plainName(n.split(' // ')[0]) && plainName(e.n) !== plainName(n)) fix.push([n, e.n]); }
  const sv = mdSaved(), j = sv.findIndex(x=>x.name === name); if(j < 0) return;
  if(fix.length){ const ren = new Map(fix), mv = l => { const m = new Map(); for(const [n,c] of l){ const t = ren.get(n) || n; m.set(t, (m.get(t)||0)+c); } return [...m]; };
    const d2 = {main:mv(d.main), side:mv(d.side), art:d.art}; sv[j] = {name, text:mdText(d2)}; store.set('mt_decks', sv);
    for(const [a,b] of fix){ const e = DB[keyOf(a)]; if(e && !DB[keyOf(b)]) DB[keyOf(b)] = e; } }
  const bits = [];
  if(fix.length) bits.push(`Corrected the spelling: ${fix.map(([a,b])=>`${esc(a)} → <b>${esc(b)}</b>`).join(', ')}.`);
  if(miss.length) bits.push(`Not found on Scryfall: <b>${miss.map(esc).join('</b>, <b>')}</b>. Check the spelling with <b>Edit</b>; until then ${miss.length>1?'they play':'it plays'} as text, by hand.`);
  if(down) bits.push('Scryfall is not answering, so the names could not be checked yet: cards show as text until it answers.');
  if(!bits.length) bits.push('All card names found ✓');
  MD.note = {i:j, html:bits.join(' ')}; if(MD.sel && MD.sel.kind === 'saved' && MD.sel.i === j && !MD.ed && !MD.paste) mdPaint(); }
async function mdClip(){ try{ const t = await navigator.clipboard.readText(); if(!t || !t.trim()){ toast('The clipboard is empty.'); return; }
    if(!MD.paste) MD.paste = {}; const nm = $('#mdPN'); MD.paste.name = nm ? nm.value : MD.paste.name; MD.paste.text = t; mdPaint(); }
  catch(e){ toast('This browser won’t share the clipboard: tap and hold in the box, then Paste.'); const t = $('#mdPT'); if(t) t.focus(); } }

function mdClick(e){ const t = e.target, q = s => t.closest(s);
  let b;
  if((b = q('[data-mds]'))){ MD.src = b.dataset.mds; store.set('mt_mdsrc', MD.src); mdPaint(); return; }
  if((b = q('[data-md]'))){ const k = b.dataset.md, i = +k.slice(1); if(MD.ed && !(k[0]==='s' && MD.ed.idx===i)) MD.ed = null; MD.paste = null; MD.part = 'main';
    MD.sel = {kind: k[0] === 't' ? 'tour' : 'saved', i}; MD.keepScroll = true; mdPaint(); return; }
  if(q('[data-mdp]')){ if(!MD.paste){ MD.paste = {}; MD.ed = null; } mdPaint(); const ta = $('#mdPT'); if(ta && !ta.value) ta.focus(); return; }
  if((b = q('[data-mdpb]'))){ const k = b.dataset.mdpb; if(k === 'x'){ MD.paste = null; mdPaint(); } else if(k === 'add') mdPasteAdd(); else if(k === 'clip') mdClip(); else if(k === 'file') $('#mdFile').click(); return; }
  if((b = q('[data-mdpt]'))){ MD.part = b.dataset.mdpt; mdPaint(); return; }
  if((b = q('[data-mdw]'))){ MD.view = b.dataset.mdw; store.set('mt_mdview', MD.view); mdPaint(); return; }
  if((b = q('[data-mda]'))){ mdAdd(b.dataset.mda); return; }
  if((b = q('[data-mk]'))){ mdCard(b.dataset.mk, b.dataset.mn); return; }
  if((b = q('[data-mde]'))){ const k = b.dataset.mde, cur = mdCur(); if(!cur) return;
    if(k === 'play') playDeck(cur.d, cur.name, b, $('#mdMsg'), mdEditStart);
    else if(k === 'edit') mdEditStart();
    else if(k === 'undo') mdUndo();
    else if(k === 'done'){ MD.ed = null; mdPaint(); }
    else if(k === 'del'){ const i = MD.sel.i; confirmBox(`Delete “${cur.name}”?`, 'It is removed from My decks on this phone.', ()=>{ closeModal(); const sv = mdSaved(); sv.splice(i, 1); store.set('mt_decks', sv); MD.sel = null; MD.note = null; mdPaint(); }); }
    return; } }
let mdSearchT = null;
function mdInput(e){ const t = e.target;
  if(t.id === 'mdFilt'){ MD.q = t.value; const r = $('#mDeck .mdrows'); if(r) r.innerHTML = mdRows(); return; }
  if(t.id === 'mdPT'){ mdCount(); return; }
  if(t.id === 'mdPN'){ if(MD.paste) MD.paste.name = t.value; return; }
  if(t.id === 'mdQ'){ clearTimeout(mdSearchT); const v = t.value.trim(); MD.hits = []; mdSug(); if(v.length >= 2) mdSearchT = setTimeout(()=>mdSearch(v), 300); } }
