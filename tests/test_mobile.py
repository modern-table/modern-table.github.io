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
    bt = p.get_by_role('button', name='No deck')
    if bt.count(): bt.first.tap(); p.wait_for_timeout(500)
    p.get_by_role('button', name='Start the game').first.tap(); p.wait_for_timeout(700)
    for k in ['deal', 'keep']:
        if p.locator(f'[data-first="{k}"]').count(): p.tap(f'[data-first="{k}"]'); p.wait_for_timeout(600)
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
    tile = J(p, "() => { const t=document.querySelector('#myBack .mlands'); return t ? [t.querySelector('.mlh').innerText, t.querySelectorAll('.pip').length, t.querySelectorAll('.pip.t').length, t.querySelector('.mlu').innerText] : null; }")
    check('my lands fold into one tile: 5 lands, a pip each, the tapped one dim', tile and '5' in tile[0] and tile[1] == 5 and tile[2] == 1 and '4 untapped' in tile[3], tile)
    check('the land cards themselves are hidden on the board', J(p, "() => [...document.querySelectorAll('#myBack .card[data-id]')].filter(e=>isLand(find(e.dataset.id).c)).every(e=>getComputedStyle(e).display==='none')"))
    check("the opponent's lands fold too", J(p, "() => { const t=document.querySelector('#oppBack .mlands.opp'); return !!t && t.querySelectorAll('.pip').length===2; }"))
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
    check('the hand fan shows the count', J(p, "() => document.querySelector('#mHandBtn .hc').innerText==='3'"))
    p.tap('#mHandBtn'); p.wait_for_timeout(300)
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
    if J(p, "() => !!G.mode"): p.tap('#oppAv'); p.wait_for_timeout(400)
    if p.locator('#stack .card').count(): p.locator('#stack .card').first.tap(timeout=5000); p.wait_for_timeout(600)
    if p.locator('#modal:not([hidden])').count(): J(p, "() => closeModal()")
    # the lands box on its own
    p.tap('#myBack .mlands'); p.wait_for_timeout(300)
    check('tapping the tile opens the lands box', J(p, "() => !document.querySelector('#mLands').hidden && document.querySelectorAll('#mLands .card[data-z=bf]').length===6"))
    p.locator('#mLands [data-ml="x"]').tap(); p.wait_for_timeout(200)
    # the menu
    p.tap('#mMenu'); p.wait_for_timeout(300)
    mt = J(p, "() => document.querySelector('#ctx').hidden ? null : [...document.querySelectorAll('#ctx button')].map(b=>b.innerText)")
    check('☰ opens the menu sheet: phone items and the table menu, no tour', mt and 'Undo' in mt and 'Game log and chat' in mt and any('Concede' in x for x in mt) and not any('tour' in x.lower() for x in mt), mt)
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
    # fit
    fit = J(p, "() => { const r=document.querySelector('#next').getBoundingClientRect(), t=document.querySelector('#table').getBoundingClientRect(); return [r.bottom <= innerHeight, t.height <= innerHeight + 1, document.documentElement.scrollWidth <= innerWidth]; }")
    check('the table fits the screen, big button in reach', all(fit), fit)
    check('no page errors', not errs, errs[:3])
    b.close()
finally: srv.terminate()
print('ALL PASS' if res and all(res) else 'SOME FAILED', f'({sum(res)}/{len(res)})')
