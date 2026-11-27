"""The phone table (m/, phone layer m0.1): a practice game on a phone held sideways (844 x 390, touch).
Checks that the desktop page carries none of the phone layer, then plays through the phone's gestures: the lands tile, the card sheet,
LOOK, the hand tray, paying with the lands box beside the payment box, the stack, the menu sheet and its submenus, choosing attackers."""
import os, socket, subprocess, sys, time
from playwright.sync_api import sync_playwright
ROOT = os.environ.get('MT_ROOT') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def _free_port():
    s = socket.socket(); s.bind(('127.0.0.1', 0)); p = s.getsockname()[1]; s.close(); return p
PORT = _free_port()
srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(PORT), '--bind', '127.0.0.1'], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(0.8); res = []
def check(n, c, e=''): res.append(bool(c)); print('PASS' if c else 'FAIL', n, e)
SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="488" height="680"><rect width="488" height="680" rx="24" fill="#3b4a3f"/></svg>'
def block(ctx):
    ctx.route('**/cards.scryfall.io/**', lambda r: r.fulfill(status=200, content_type='image/svg+xml', body=SVG))
    for h in ['**/svgs.scryfall.io/**', '**/backs.scryfall.io/**', '**/fonts.googleapis.com/**', '**/fonts.gstatic.com/**', '**/gc.zgo.at/**', '**/*.metered.live/**']: ctx.route(h, lambda r: r.abort())
    ctx.route('**/api.scryfall.com/**', lambda r: r.fulfill(status=200, content_type='application/json', body='{"data":[]}'))
J = lambda p, js: p.evaluate(js)
try:
  with sync_playwright() as pw:
    b = pw.chromium.launch()
    # 1. the desktop page has no phone layer in it
    dctx = b.new_context(viewport={'width': 1400, 'height': 850}); block(dctx); d = dctx.new_page(); derr = []; d.on('pageerror', lambda e: derr.append(str(e)))
    d.goto(f'http://127.0.0.1:{PORT}/'); d.wait_for_timeout(700)
    check('desktop page: no phone layer', J(d, "() => !document.documentElement.classList.contains('mob') && !document.getElementById('mjs') && !document.getElementById('mcss') && !document.getElementById('mTop')"))
    check('desktop page: no errors', not derr, derr[:2])
    dctx.close()
    # 2. the phone page
    ctx = b.new_context(viewport={'width': 844, 'height': 390}, is_mobile=True, has_touch=True, device_scale_factor=2); block(ctx)
    p = ctx.new_page(); errs = []; p.on('pageerror', lambda e: errs.append(str(e)))
    p.goto(f'http://127.0.0.1:{PORT}/m/'); p.wait_for_timeout(800)
    J(p, "() => { const s=document.getElementById('spl'); if(s) s.remove(); }")
    check('phone page: html.mob, its own title, the phone note', J(p, "() => document.documentElement.classList.contains('mob') && document.title.includes('phone') && !!document.getElementById('mNote')"))
    check('phone page: the coin picture is found one folder up', J(p, "() => document.getElementById('mcss') && [...document.scripts].some(s=>s.textContent.includes(\"'../img/coin-flip.webp'\"))"))
    p.tap('#soloBtn'); p.wait_for_timeout(700); p.locator('.drow').first.tap(); p.wait_for_timeout(400)
    p.get_by_role('button', name='Play this deck').tap(); p.wait_for_timeout(1500)
    bt = p.get_by_role('button', name='Random deck')
    if bt.count(): bt.first.tap(); p.wait_for_timeout(500)
    p.get_by_role('button', name='Start the game').first.tap(); p.wait_for_timeout(700)
    p.tap('[data-first="deal"]'); p.wait_for_timeout(600)
    p.tap('[data-first="mull"]'); p.wait_for_timeout(600); p.tap('[data-first="keep"]'); p.wait_for_timeout(800)
    fitw = J(p, "() => { const m=document.querySelector('#modal'); if(m.hidden) return null; const s=m.querySelector('.sheet').getBoundingClientRect(); return [s.right <= innerWidth, s.bottom <= innerHeight, [...m.querySelectorAll('footer button')].every(b=>b.getBoundingClientRect().right <= innerWidth)]; }")
    check('m0.2: the mulligan window (put a card on the bottom) fits the screen, its buttons in reach', fitw and all(fitw), fitw)
    p.tap('#mLook'); p.wait_for_timeout(150); p.locator('#modal .card[data-id]').first.tap(); p.wait_for_timeout(300)
    check('m0.2: LOOK reads a card inside a window', J(p, "() => !document.querySelector('#mView').hidden && !document.querySelector('#modal').hidden"))
    p.locator('#mView .mpic').tap(); p.wait_for_timeout(200); p.tap('#mLook'); p.wait_for_timeout(150)
    p.locator('#modal .card[data-id]').first.tap(); p.wait_for_timeout(300)
    p.locator('#modal footer button.go').last.tap(); p.wait_for_timeout(600)
    check('the mulligan finishes by taps (one card on the bottom)', J(p, "() => G.me.hand.length===6 && !G.me.btm"), J(p, "() => [G.me.hand.length, G.me.btm]"))
    if p.locator('#modal:not([hidden])').count(): J(p, "() => closeModal()")
    check('a practice game starts by taps', J(p, "() => G.turn.n===1 && G.turn.active===G.myId"))
    J(p, """() => { const add=(n,side,o,z='bf')=>{ const c=mk(keyOf(n), o); side[z].push(c); return c; };
      G.me.bf=[]; G.me.hand=[]; G.me.mana=noMana(); G.me.lp=null;
      for(const n of ["Urza's Tower","Urza's Mine","Urza's Power Plant",'Forest','Sacred Foundry']) add(n, G.me, {});
      G.me.bf[4].tap=true;
      for(const n of ['Mountain','Sacred Foundry']) add(n, G.opp, {o:oppId()});
      add('Ragavan, Nimble Pilferer', G.opp, {o:oppId()});
      add('Walking Ballista', G.me, {c:2});
      for(const n of ['Thought-Knot Seer','Forest','Expedition Map']) add(n, G.me, {}, 'hand');
      changed(); }""")
    p.wait_for_timeout(500)
    # lands tile
    tile = J(p, "() => { const t=document.querySelector('#myBack .mlands'); return t ? [t.querySelector('.mlh').innerText, t.querySelectorAll('.ml').length, t.querySelectorAll('.ml.t').length, t.querySelectorAll('.ml img').length] : null; }")
    check('m0.2: my lands fold into one tile of land pictures: 5 lands, 5 pictures, the tapped one turned', tile and '5' in tile[0] and '4 untapped' in tile[0] and tile[1] == 5 and tile[2] == 1 and tile[3] == 5, tile)
    check('the land cards themselves are hidden on the board', J(p, "() => [...document.querySelectorAll('#myBack .card[data-id]')].filter(e=>isLand(find(e.dataset.id).c)).every(e=>getComputedStyle(e).display==='none')"))
    check("the opponent's lands fold too", J(p, "() => { const t=document.querySelector('#oppBack .mlands.opp'); return !!t && t.querySelectorAll('.ml').length===2; }"))
    # the card sheet
    p.locator('#myFront .card').first.tap(); p.wait_for_timeout(400)
    sh = J(p, "() => { const v=document.querySelector('#mView'); return v.hidden ? null : [v.querySelector('h3').innerText, [...v.querySelectorAll('.mact button')].map(b=>b.innerText)]; }")
    check('tapping my creature opens it larger with its actions (Tap first, its abilities, Manual handling)', sh and sh[0] == 'Walking Ballista' and sh[1][0] == 'Tap' and any('Activate' in x for x in sh[1]) and any('Manual handling' in x for x in sh[1]), sh)
    check('the sheet has no second "Right now" button', sh and not any(x.startswith('Right now') for x in sh[1]), sh)
    p.locator('#mView .mact button.sub').first.tap(); p.wait_for_timeout(200)
    sub = J(p, "() => [...document.querySelectorAll('#mView .mact button')].map(b=>b.innerText)")
    check('Manual handling opens in place, with a Back row', sub and sub[0].startswith('‹ Back') and any('graveyard' in x.lower() for x in sub), sub[:4])
    p.locator('#mView .mact button.back').tap(); p.wait_for_timeout(200)
    p.locator('#mView .mact button.prim').tap(); p.wait_for_timeout(400)
    check('Tap taps it and closes the sheet', J(p, "() => document.querySelector('#mView').hidden && G.me.bf.find(c=>cdata(c).n==='Walking Ballista').tap===true"))
    J(p, "() => { G.me.bf.find(c=>cdata(c).n==='Walking Ballista').tap=false; changed(); }"); p.wait_for_timeout(200)
    # LOOK
    p.tap('#mLook'); p.wait_for_timeout(150)
    check('LOOK glows when on', J(p, "() => document.documentElement.classList.contains('look') && document.querySelector('#mLook').getAttribute('aria-pressed')==='true'"))
    p.locator('#oppFront .card').first.tap(); p.wait_for_timeout(400)
    lk = J(p, "() => { const v=document.querySelector('#mView'); return v.hidden ? null : [v.querySelector('h3').innerText, (v.querySelector('.mox')||{}).innerText||'', (v.querySelector('.mnow')||{}).innerText||'']; }")
    check("LOOK on the opponent's creature: name, Oracle text and right now", lk and lk[0].startswith('Ragavan') and 'Treasure' in lk[1] and '2/1' in lk[2], lk)
    p.locator('#mView .mpic').tap(); p.wait_for_timeout(300)
    check('tapping the picture closes it and LOOK stays on', J(p, "() => document.querySelector('#mView').hidden && M.look"))
    p.locator('#myFront .card').first.tap(); p.wait_for_timeout(300)
    check('with LOOK on, tapping my creature reads it (no actions)', J(p, "() => !document.querySelector('#mView').hidden && !document.querySelector('#mView .mact')"))
    p.tap('#mLook'); p.wait_for_timeout(200)
    check('pressing LOOK again closes the view and turns it off', J(p, "() => document.querySelector('#mView').hidden && !M.look && !document.documentElement.classList.contains('look')"))
    # the hand
    FAN = """() => { const b=document.querySelector('#mHandBtn'), bd=document.querySelector('#board').getBoundingClientRect(); const fs=[...b.querySelectorAll('.fc')];
      const rs=fs.map(f=>f.getBoundingClientRect()); const steps=rs.slice(1).map((r,i)=>(r.left-rs[i].left)/rs[i].width);
      return {n:fs.length, hc:b.querySelector('.hc').innerText, ids:fs.map(f=>f.dataset.hid).join()===G.me.hand.map(c=>c.id).join(),
        inview:rs.every(r=>r.left>=bd.left-1 && r.right<=innerWidth-128 && r.bottom<=innerHeight+1 && r.top>=0),
        corner: Math.abs((b.getBoundingClientRect().left+b.getBoundingClientRect().right)/2 - (bd.left+bd.right)/2) < 3 && b.getBoundingClientRect().bottom > bd.bottom-20,
        minshow: steps.length ? Math.min(...steps) : 1, width: Math.round(b.getBoundingClientRect().width), half: Math.round(bd.width*.5)}; }"""
    hs = J(p, FAN)
    check('m0.4: the hand is a fan centred at the bottom of the board with every card (3), in hand order, all in view', hs and hs['n'] == 3 and hs['hc'] == '3' and hs['ids'] and hs['inview'] and hs['corner'], hs)
    check('m0.3: less overlap than m0.1: at least 45% of each card shows', hs and hs['minshow'] >= .45, hs)
    J(p, """() => { for(let i=0;i<6;i++) G.me.hand.push(mk(keyOf('Forest'),{o:G.myId})); changed(); render(); }""")
    p.wait_for_timeout(200); h9 = J(p, FAN)
    check('m0.3: a nine-card hand still fits (all nine, at most half the board wide, in view)', h9 and h9['n'] == 9 and h9['inview'] and h9['width'] <= h9['half'], h9)
    J(p, """() => { G.me.hand.splice(3); changed(); render(); }"""); p.wait_for_timeout(200)
    p.tap('#mLook'); p.wait_for_timeout(150); p.locator('#mHandBtn .fc').nth(2).tap(); p.wait_for_timeout(300)
    check('m0.3: with LOOK on, tapping a card in the fan reads it', J(p, "() => !document.querySelector('#mView').hidden && !document.documentElement.classList.contains('mhand')"))
    p.tap('#mLook'); p.wait_for_timeout(200)
    p.locator('#mHandBtn .fc').nth(1).tap(); p.wait_for_timeout(300)
    check('tapping the fan opens the tray with the cards', J(p, "() => document.documentElement.classList.contains('mhand') && getComputedStyle(document.querySelector('#myHand')).display==='flex' && document.querySelectorAll('#myHand .card').length===3"))
    names = J(p, "() => G.me.hand.map(c=>cdata(c).n)")
    p.locator('#myHand .card').nth(names.index('Forest')).tap(); p.wait_for_timeout(500)
    check('tapping a land in the tray plays it (land for turn) and closes the tray', J(p, "() => G.me.bf.filter(c=>cdata(c).n==='Forest').length===2 && G.me.lp && G.me.lp.n===1 && !document.documentElement.classList.contains('mhand')"))
    # casting and paying
    p.tap('#mHandBtn'); p.wait_for_timeout(300); names = J(p, "() => G.me.hand.map(c=>cdata(c).n)")
    p.locator('#myHand .card').nth(names.index('Thought-Knot Seer')).tap(); p.wait_for_timeout(700)
    check('casting opens the payment box with the lands box beside it', J(p, "() => !document.querySelector('#payPanel').hidden && !document.querySelector('#mLands').hidden && document.documentElement.classList.contains('mpay')"))
    geo = J(p, "() => { const a=document.querySelector('#mLands').getBoundingClientRect(), b=document.querySelector('#payPanel').getBoundingClientRect(); return [a.right <= b.left + 1, b.bottom <= innerHeight, document.querySelector('#mLands .mlg').scrollHeight <= document.querySelector('#mLands .mlg').clientHeight + 1]; }")
    check('lands on the left, payment on the right, every land in view', all(geo), geo)
    for i in range(6):
        un = J(p, "() => [...document.querySelectorAll('#mLands .card[data-z=bf]:not(.tap)')].map(e=>cdata(findAny(e.dataset.id).c).n)")
        if not un: break
        p.locator('#mLands .card[data-z=bf]:not(.tap)').first.tap(); p.wait_for_timeout(450)
        if p.locator('#ctx:not([hidden])').count(): p.locator('#ctx button').first.tap(); p.wait_for_timeout(450)
        if J(p, "() => (G.me.mana.C||0)+(G.me.mana.G||0) >= 4"): break
    check('tapping lands in the box adds their mana', J(p, "() => (G.me.mana.C||0)+(G.me.mana.G||0) >= 4"), J(p, "() => JSON.stringify(G.me.mana)"))
    p.locator('#payPanel button:has-text("and cast")').first.tap(); p.wait_for_timeout(600)
    check('paying puts the spell on the stack and the lands box goes away', J(p, "() => G.me.st.some(c=>cdata(c).n==='Thought-Knot Seer') && document.querySelector('#payPanel').hidden && document.querySelector('#mLands').hidden && !document.documentElement.classList.contains('mpay')"))
    p.locator('#stack .card').first.tap(timeout=5000); p.wait_for_timeout(700)
    check('tapping the stack card resolves it', J(p, "() => G.me.bf.some(c=>cdata(c).n==='Thought-Knot Seer')"))
    check("m0.5: Thought-Knot Seer's trigger asks for its target with the targeting strip", J(p, "() => !!G.mode && !document.querySelector('#mTgt').hidden && document.querySelector('#mTgt').innerText.includes('opponent')"))
    p.tap('#oppAv'); p.wait_for_timeout(400)
    check('m0.5: the table waits for Done after the target is tapped', J(p, "() => !!G.mode && document.querySelector('#mTgtGo').innerText.startsWith('Done')"))
    p.tap('#mTgtGo'); p.wait_for_timeout(400)
    if p.locator('#stack .card').count(): p.locator('#stack .card').first.tap(timeout=5000); p.wait_for_timeout(600)
    if p.locator('#modal:not([hidden])').count(): J(p, "() => closeModal()")
    # the lands box on its own
    p.tap('#myBack .mlands'); p.wait_for_timeout(300)
    check('tapping the tile opens the lands box', J(p, "() => !document.querySelector('#mLands').hidden && document.querySelectorAll('#mLands .card[data-z=bf]').length===6"))
    p.locator('#mLands [data-ml="x"]').tap(); p.wait_for_timeout(200)
    # the menu
    p.tap('#mMenu'); p.wait_for_timeout(300)
    mt = J(p, "() => document.querySelector('#ctx').hidden ? null : [...document.querySelectorAll('#ctx button')].map(b=>b.innerText)")
    check('☰ opens the menu sheet: phone items and the table menu; the phone\'s own tour (m0.17), not the desktop\'s Take the tour or Explore', mt and 'Undo' in mt and 'Game log and chat' in mt and any('Concede' in x for x in mt) and [x for x in mt if 'tour' in x.lower()] == ['How to play (a 3-minute tour)'] and not any('Take the tour' in x or 'Explore' in x for x in mt), mt)
    p.tap('#mBackdrop', position={'x': 20, 'y': 20}); p.wait_for_timeout(200)
    check('tapping beside it closes it', J(p, "() => document.querySelector('#ctx').hidden && document.querySelector('#mBackdrop').hidden"))
    p.tap('#mMenu'); p.wait_for_timeout(200); p.locator('#ctx button:has-text("Game log and chat")').tap(); p.wait_for_timeout(200)
    check('the game log opens beside the right column', J(p, "() => document.documentElement.classList.contains('mlog') && getComputedStyle(document.querySelector('#logwrap')).display==='flex'"))
    p.tap('#mLogX'); p.wait_for_timeout(150)
    # combat: choosing attackers goes through the table's own taps
    p.tap('#next'); p.wait_for_timeout(600)
    if p.locator('#atkBar button:has-text("Choose attackers")').count():
        p.locator('#atkBar button:has-text("Choose attackers")').tap(); p.wait_for_timeout(300)
    p.locator('#myFront .card').first.tap(); p.wait_for_timeout(300)
    check('in declare attackers a tap chooses the attacker (no sheet)', J(p, "() => G.atkSel && G.atkSel.size===1 && document.querySelector('#mView').hidden"))
    # m0.2: Arena of Glory's exert mana pays a creature and gives it haste; Mutavault's box button reads Abilities
    J(p, "() => { G.atkSel=null; setTurn({...G.turn, phase:2, passed:false}); }"); p.wait_for_timeout(300)
    J(p, """() => { const add=(n,z='bf')=>{ const c=mk(keyOf(n), {}); G.me[z].push(c); return c; };
      G.me.bf=[]; G.me.hand=[]; G.me.st=[]; G.me.mana=noMana(); G.me.smana=[];
      for(const n of ['Arena of Glory','Mountain','Mutavault']) add(n);
      add('Ragavan, Nimble Pilferer','hand'); changed(); }""")
    p.wait_for_timeout(400)
    LN = "() => [...document.querySelectorAll('#mLands .card[data-z=bf]')].map(e=>cdata(findAny(e.dataset.id).c).n)"
    p.tap('#myBack .mlands'); p.wait_for_timeout(300); ln = J(p, LN)
    mb = J(p, "() => [...document.querySelectorAll('#mLands .mlc')].map(m=>(m.querySelector('.card[data-z=bf]') ? cdata(findAny(m.querySelector('.card[data-z=bf]').dataset.id).c).n : '')+':'+((m.querySelector('.mlm')||{}).innerText||''))")
    check('m0.2: in the lands box Mutavault offers Abilities, a Mountain only ⋯', 'Mutavault:Abilities' in mb and 'Mountain:⋯' in mb, mb)
    p.locator('#mLands .card[data-z=bf]').nth(ln.index('Mountain')).tap(); p.wait_for_timeout(400)
    p.locator('#mLands .card[data-z=bf]').nth(ln.index('Arena of Glory')).tap(); p.wait_for_timeout(400)
    am = J(p, "() => [...document.querySelectorAll('#ctx button')].map(b=>b.innerText)")
    check('tapping Arena of Glory offers its exert ability, as the desktop does', any('exerts' in x for x in am), am)
    p.locator('#ctx button').filter(has_text='exerts').first.tap(); p.wait_for_timeout(500)
    check('exerting it spends the Mountain\'s Red and adds two Red that give haste', J(p, "() => (G.me.smana||[]).filter(s=>s.rider==='haste').length===2 && G.me.bf.find(c=>cdata(c).n==='Arena of Glory').exert"), J(p, "() => JSON.stringify(G.me.smana)"))
    p.tap('#mLands [data-ml="x"]'); p.wait_for_timeout(200)
    p.tap('#mHandBtn'); p.wait_for_timeout(300); p.locator('#myHand .card').first.tap(); p.wait_for_timeout(700)
    pp = J(p, "() => { const e=document.querySelector('#payPanel'); return e.hidden ? null : [e.scrollHeight <= e.clientHeight + 1, e.getBoundingClientRect().bottom <= innerHeight, !!e.querySelector('[data-pay^=\"sp:\"]')]; }")
    check('m0.2: casting Ragavan opens the whole payment box (no part cut off) with the special mana to choose', pp and all(pp), pp)
    p.locator('#payPanel [data-pay^="sp:"]').first.tap(); p.wait_for_timeout(300)
    p.locator('#payPanel button').filter(has_text='Pay {R} and cast').first.tap(); p.wait_for_timeout(600)
    p.locator('#stack .card').first.tap(timeout=5000); p.wait_for_timeout(600)
    check('paid with that mana, Ragavan enters with haste', J(p, "() => { const c=G.me.bf.find(c=>cdata(c).n.startsWith('Ragavan')); return !!c && !!c.hst; }"))
    # m0.4: other mana (Treasures) in the box while paying
    J(p, """() => { G.me.bf=[]; G.me.hand=[]; G.me.st=[]; G.me.mana=noMana(); G.me.smana=[];
      const T=()=>mk(null,{cu:{n:'Treasure', t:'Token Artifact — Treasure', o:'{T}, Sacrifice this artifact: Add one mana of any color.'}, tok:1});
      G.me.bf.push(mk(keyOf('Mountain')), T(), T()); G.me.hand.push(mk(keyOf('Thought-Knot Seer'))); changed(); }""")
    p.wait_for_timeout(300); p.tap('#mHandBtn'); p.wait_for_timeout(300); p.locator('#myHand .card').first.tap(); p.wait_for_timeout(700)
    tb = J(p, "() => { const o=document.querySelectorAll('#mLands .mlo'); const l=document.querySelector('#mLands'); return [!document.querySelector('#payPanel').hidden, !l.hidden, o.length, (l.querySelector('.mlcnt')||{}).innerText, [...o].every(e=>e.getBoundingClientRect().bottom<=innerHeight+1)]; }")
    check('m0.4: while paying, the box shows Treasures under the lands (two grouped as one with ×2, in view)', tb and tb[0] and tb[1] and tb[2] == 1 and tb[3] == '×2' and tb[4], tb)
    p.locator('#mLands .mlo .card').first.tap(); p.wait_for_timeout(400)
    tm = J(p, "() => [...document.querySelectorAll('#ctx button')].map(b=>b.innerText)")
    check('m0.4: tapping a Treasure there offers its mana, as a desktop click does', any('Sacrifice, add Red' in x for x in tm), tm)
    p.locator('#ctx button').filter(has_text='Sacrifice, add Red').first.tap(); p.wait_for_timeout(400)
    check('m0.4: the Treasure is sacrificed for Red and the box now shows one', J(p, "() => (G.me.mana.R===1 || G.me.st.length===1 || !G.me.hand.length) && G.me.bf.filter(c=>cdata(c).n==='Treasure').length===1 && (document.querySelector('#mLands').hidden || !document.querySelector('#mLands .mlcnt'))"), J(p, "() => [JSON.stringify(G.me.mana), G.me.bf.map(c=>cdata(c).n)]"))
    J(p, "() => { if(!document.querySelector('#payPanel').hidden) { const b=[...document.querySelectorAll('#payPanel button')].find(b=>/Cancel/.test(b.innerText)); if(b) b.click(); } closeLands(); }"); p.wait_for_timeout(300)
    # m0.4: screen edges (the phone's own safe-area insets stood in for: Chromium reports none)
    J(p, "() => { window.__env={l:47,r:47,b:21}; window.__side='l'; envInsets=()=>window.__env; camSide=()=>window.__side; applyEdges(); }"); p.wait_for_timeout(300)
    ed = J(p, "() => { const t=document.querySelector('#table').getBoundingClientRect(); return [Math.round(t.left), Math.round(innerWidth-t.right), Math.round(innerHeight-t.bottom)]; }")
    check('m0.4: camera on the left: the table starts 47 px in on that side only (the other side and the bottom stay)', ed == [47, 0, 0], ed)
    J(p, "() => { window.__side='r'; applyEdges(); }"); p.wait_for_timeout(300)
    ed = J(p, "() => { const t=document.querySelector('#table').getBoundingClientRect(); return [Math.round(t.left), Math.round(innerWidth-t.right)]; }")
    check('m0.4: turned the other way, the space moves to the right', ed == [0, 47], ed)
    J(p, "() => { window.__side=null; window.__env={l:0,r:0,b:0}; applyEdges(); settingsModal(); }"); p.wait_for_timeout(300)
    rows = J(p, "() => [...document.querySelectorAll('#setBody .setg')].map(g=>g.querySelector('h5').innerText)")
    check('m0.4: Settings opens with a Phone section first', rows and rows[0].lower() == 'phone', rows)
    p.locator('#setBody [data-set="mcam"][data-v="8"]').tap(); p.wait_for_timeout(200); p.locator('#setBody [data-set="mbot"][data-v="12"]').tap(); p.wait_for_timeout(300)
    ed = J(p, "() => { const t=document.querySelector('#table').getBoundingClientRect(); return [Math.round(t.left), Math.round(innerWidth-t.right), Math.round(innerHeight-t.bottom), S.mCam, S.mBot]; }")
    check('m0.4: a manual margin of 8 on the camera side and 12 at the bottom moves the table in by that much', ed == [8, 0, 12, 8, 12], ed)
    J(p, "() => { closeModal(); S.mCam=0; S.mBot=0; applyEdges(); }"); p.wait_for_timeout(300)
    # fit
    fit = J(p, "() => { const r=document.querySelector('#next').getBoundingClientRect(), t=document.querySelector('#table').getBoundingClientRect(); return [r.bottom <= innerHeight, t.height <= innerHeight + 1, document.documentElement.scrollWidth <= innerWidth]; }")
    check('the table fits the screen, big button in reach', all(fit), fit)
    check('no page errors', not errs, errs[:3])
    b.close()
finally: srv.terminate()
print('ALL PASS' if res and all(res) else 'SOME FAILED', f'({sum(res)}/{len(res)})')
