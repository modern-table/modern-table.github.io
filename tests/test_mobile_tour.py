"""The phone tour (phone layer m0.17, the maintainer: on the phone, make sure the steps to play are understood; the player does the taps).
How to play on a phone held sideways (844 x 390, touch): the staged board (turn 3, Boros Aggro against Practice's UR Aggro), each step outlines
what to tap in gold and waits until the player has done it, then goes on by itself. Run once by real taps on the outlines (the hand, a land,
Ocelot Pride, Plains, Pay, the stack, the trigger, the staged Bolt's OK, combat, attackers, Practice's block, damage, Ragavan's trigger), once
with Do it for me on every step. Taps outside the outlines are held off. The front page and the ☰ sheet open it; the desktop page is unchanged."""
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
    for h in ['**/svgs.scryfall.io/**', '**/backs.scryfall.io/**', '**/fonts.googleapis.com/**', '**/fonts.gstatic.com/**', '**/gc.zgo.at/**', '**/*.metered.live/**', '**/*.workers.dev/**', '**/*.nocookie.net/**']: ctx.route(h, lambda r: r.abort())
    ctx.route('**/api.scryfall.com/**', lambda r: r.fulfill(status=200, content_type='application/json', body='{"data":[]}'))
J = lambda p, js: p.evaluate(js)
CARD = """() => TOUR ? {i:TOUR.i, n:TOUR.list.length, from:TOUR.from, t:(document.querySelector('#tourCard h4')||{}).textContent, p:(document.querySelector('#tourCard p')||{}).textContent,
  rings:document.querySelectorAll('#mtrRings:not([hidden]) i').length, doit:!!document.querySelector('#tourCard [data-mtrdo]'), next:!!document.querySelector('#tourCard [data-tr=next]'),
  card:(()=>{ const r=document.querySelector('#tourCard').getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; })(),
  ringR:[...document.querySelectorAll('#mtrRings:not([hidden]) i')].map(i=>{ const r=i.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; })} : null"""
ST = """() => ({ph:G.turn.phase, n:G.turn.n, cs:G.turn.cs, life:G.me.life, olife:G.opp.life, en:G.me.ctr.energy, hand:G.me.hand.map(c=>cdata(c).n), bf:G.me.bf.map(c=>cdata(c).n+(c.tap?'*':'')),
  st:G.me.st.map(c=>cdata(c).n), atk:G.me.bf.filter(c=>c.atk).map(c=>cdata(c).n), blk:(G.opp.arrows||[]).filter(a=>a.blk).map(a=>cdata(findAny(a.a).c).n+'>'+cdata(findAny(a.b).c).n),
  deck:G.me.deck, odeck:G.opp.deck, cls:document.documentElement.className, pay:!document.querySelector('#payPanel').hidden})"""
def front(p):
    p.goto(f'http://127.0.0.1:{PORT}/m/'); p.wait_for_timeout(800)
    J(p, "() => { const s=document.getElementById('spl'); if(s) s.remove(); }")
def ring(p, i=0):
    bx = J(p, f"() => {{ const r=document.querySelectorAll('#mtrRings i')[{i}].getBoundingClientRect(); return [r.left+r.width/2, r.top+r.height/2]; }}")
    p.touchscreen.tap(bx[0], bx[1])
def wait_step(p, i0, ms=4000):
    t = time.time()
    while time.time() - t < ms/1000:
        c = J(p, CARD)
        if not c or c['i'] != i0:
            p.wait_for_timeout(600); return J(p, CARD)   # the new step settles: outlines drawn, the card in place
        p.wait_for_timeout(150)
    return J(p, CARD)
def overlap(a, b):
    return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
try:
  with sync_playwright() as pw:
    b = pw.chromium.launch()
    # ---- the desktop page has none of it
    dctx = b.new_context(viewport={'width': 1500, 'height': 900}); block(dctx); d = dctx.new_page()
    d.goto(f'http://127.0.0.1:{PORT}/'); d.wait_for_timeout(700)
    check('the desktop page keeps its own How to play (the tour does the beats, no phone steps)', J(d, "() => typeof MVERSION==='undefined' && !TOUR_STEPS.play.some(s=>s.do) && TOUR_STEPS.play.length===22"))
    dctx.close()
    ctx = b.new_context(viewport={'width': 844, 'height': 390}, is_mobile=True, has_touch=True); block(ctx)
    p = ctx.new_page(); errs = []; p.on('pageerror', lambda e: errs.append(str(e)))
    front(p)
    check('m0.17: the phone front page offers How to play', J(p, "() => { const b=document.querySelector('#mNote [data-mnav=tour]'); return !!b && /How to play/.test(b.textContent) && b.getBoundingClientRect().width>0; }") and J(p, "() => MVERSION==='m0.17'"))
    p.tap('#mNote [data-mnav=tour]'); p.wait_for_timeout(3500)
    c = J(p, CARD); s = J(p, ST)
    check('it stages the board: turn 3, Boros Aggro against UR Aggro, the intro card centred', c and c['from'] == 'play' and c['t'] == 'How to play' and s['n'] == 3 and s['deck'] == 'Boros Aggro' and s['odeck'] == 'UR Aggro' and c['next'], (c, s))
    p.tap('#tourCard [data-tr=next]'); c = wait_step(p, 0)
    check('Your hand: one gold outline, on the hand fan; Do it for me; no dimming and no Next', c['t'] == 'Your hand' and c['rings'] == 1 and c['doit'] and not c['next'] and J(p, "() => getComputedStyle(document.querySelector('#tourHole')).display==='none'"), c)
    fan = J(p, "() => { const r=document.querySelector('#mHandBtn').getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; }")
    check('the outline is around the fan, and the card doesn\'t cover it', overlap(c['ringR'][0], fan) > 0.8*(fan[2]-fan[0])*(fan[3]-fan[1]) and overlap(c['card'], fan) == 0, (c['ringR'], fan, c['card']))
    tile = J(p, "() => { const r=document.querySelector('#myBack .mlands').getBoundingClientRect(); return [r.left+r.width/2, r.top+r.height/2]; }")
    p.touchscreen.tap(tile[0], tile[1]); p.wait_for_timeout(500)
    check('a tap outside the outline is held off (the lands box stays shut) and the card nudges', J(p, "() => document.querySelector('#mLands').hidden !== false || getComputedStyle(document.querySelector('#mLands')).display==='none'") and J(p, "() => document.querySelector('#tourCard').classList.contains('mtrnudge')") and J(p, CARD)['t'] == 'Your hand')
    ring(p); c = wait_step(p, 1)
    check('tapping the fan opens the hand and the tour goes on by itself: Play a land, Snow-Covered Mountain outlined', c['t'] == 'Play a land' and 'mhand' in J(p, ST)['cls'] and c['rings'] == 1 and 'Snow-Covered Mountain' in c['p'], c)
    ring(p); c = wait_step(p, 2); s = J(p, ST)
    check('tapping the Mountain plays it: Cast a spell (open your hand again)', 'Snow-Covered Mountain' in s['bf'] and c['t'] == 'Cast a spell' and 'Open your hand' in c['p'], (s['bf'], c))
    ring(p); p.wait_for_timeout(500); c = J(p, CARD)
    check('tapping the fan again: the text says tap Ocelot Pride', c['t'] == 'Cast a spell' and c['p'].startswith('Tap Ocelot Pride'), c['p'])
    ring(p); c = wait_step(p, 3); s = J(p, ST)
    check('tapping Ocelot Pride opens the payment: Pay for it, Plains outlined in the lands box', s['pay'] and c['t'] == 'Pay for it' and 'Plains' in c['p'] and c['rings'] == 1, c)
    pr = J(p, "() => { const r=document.querySelector('#payPanel .sheet, #payPanel').getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; }")
    check('the card covers neither the outline nor the payment box', overlap(c['card'], c['ringR'][0]) == 0 and overlap(c['card'], pr) < 200, (c['card'], c['ringR'], pr))
    ring(p); p.wait_for_timeout(600); c = J(p, CARD); s = J(p, ST)
    check('tapping Plains taps it; the outline moves to Pay {W} and cast', 'Plains*' in s['bf'] and 'Pay {W} and cast' in c['p'] and c['rings'] == 1, (s['bf'], c['p']))
    ring(p); c = wait_step(p, 4); s = J(p, ST)
    check('Pay puts Ocelot Pride on the stack: The stack, its card outlined', s['st'] == ['Ocelot Pride'] and c['t'] == 'The stack' and c['rings'] == 1, (s['st'], c))
    stk = J(p, "() => { const r=document.querySelector('#stack').getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; }")
    check('the outline keeps inside the stack (not over the life box above it)', c['ringR'][0][1] >= stk[1] - 6, (c['ringR'], stk))
    ring(p); c = wait_step(p, 5, 5000); s = J(p, ST)
    check('tapping it resolves Ocelot Pride; Guide of Souls\' trigger: A trigger', 'Ocelot Pride' in s['bf'] and c['t'] == 'A trigger', (s, c))
    ring(p); c = wait_step(p, 6, 5000); s = J(p, ST)
    check('the trigger resolves (life 19, energy 1); Your friend\'s OK: the big button blue, outlined', s['life'] == 19 and s['en'] == 1 and c['t'] == "Your friend's OK" and J(p, "() => document.querySelector('#next').classList.contains('ok') && /OK: Lightning Bolt/.test(document.querySelector('#next').textContent)"), (s['life'], s['en'], c['t']))
    ring(p); c = wait_step(p, 7); s = J(p, ST)
    check('tapping OK resolves the staged Bolt (life 16) without moving the turn: To combat', s['life'] == 16 and s['ph'] == 2 and c['t'] == 'To combat', (s['life'], s['ph'], c['t']))
    ring(p); c = wait_step(p, 8); s = J(p, ST)
    check('the big button goes to combat: Attack, Choose attackers outlined', s['ph'] == 3 and c['t'] == 'Attack' and 'Choose attackers' in c['p'], (s['ph'], c))
    ring(p); p.wait_for_timeout(500); c = J(p, CARD)
    check('after Choose attackers: Ragavan and Guide of Souls outlined', c['rings'] == 2 and 'Ragavan' in c['p'], c)
    ring(p); p.wait_for_timeout(400); ring(p); p.wait_for_timeout(400); c = J(p, CARD)
    check('both chosen: the Attack button outlined', c['rings'] == 1 and J(p, "() => G.atkSel && G.atkSel.size===2"), c)
    ring(p); c = wait_step(p, 9); s = J(p, ST)
    check('Attack: both attack; Blocking (for Practice), Swiftspear outlined', sorted(s['atk']) == ['Guide of Souls', 'Ragavan, Nimble Pilferer'] and c['t'] == 'Blocking' and c['rings'] == 1, (s['atk'], c))
    ring(p); p.wait_for_timeout(500); c = J(p, CARD)
    check('Swiftspear chosen: Guide of Souls outlined', c['rings'] == 1 and c['p'].startswith('Now tap Guide of Souls'), c['p'])
    ring(p); p.wait_for_timeout(800); c = J(p, CARD)
    check('the block made: Done blocking outlined', J(p, ST)['blk'] == ['Monastery Swiftspear>Guide of Souls'] and 'Done blocking' in c['p'], (J(p, ST)['blk'], c['p']))
    ring(p); c = wait_step(p, 10); s = J(p, ST)
    check('Done blocking: Combat damage, the big button outlined', c['t'] == 'Combat damage' and s['cs'] == 'blkd', (c['t'], s['cs']))
    ring(p); c = wait_step(p, 11, 5000); s = J(p, ST)
    check('damage: Ragavan hit Practice (16 to 14) and triggered: Ragavan\'s trigger', s['olife'] == 14 and c['t'] == "Ragavan's trigger" and any('Ragavan' in x for x in s['st']), (s['olife'], c['t'], s['st']))
    ring(p); c = wait_step(p, 12, 5000); s = J(p, ST)
    oex = J(p, "() => G.opp.ex.filter(c=>c.offer).map(c=>[cdata(c).n, isLand(c)])")
    check('Ragavan exiled a spell (the tour puts one on top of Practice\'s library), so there is something to cast', len(oex) == 1 and not oex[0][1] and oex[0][0] != 'Lightning Bolt', oex)
    check('it resolves: a Treasure; Reading cards points at LOOK (spotlight and Next)', 'Treasure' in s['bf'] and not s['st'] and c['t'] == 'Reading cards' and c['next'] and not c['doit'], (s['bf'], c))
    p.tap('#tourCard [data-tr=next]'); p.wait_for_timeout(500); c = J(p, CARD)
    check('The menu, with Back to Reading cards', c['t'] == 'The menu' and J(p, "() => !!document.querySelector('#tourCard [data-tr=back]')"), c)
    p.tap('#tourCard [data-tr=next]'); p.wait_for_timeout(500); c = J(p, CARD)
    check('Your turn: the last card offers Practice with my own deck and Done', c['t'] == 'Your turn' and c['i'] == c['n'] - 1 and J(p, "() => /Practice with my own deck/.test(document.querySelector('#tourCard').innerText)"), c)
    p.tap('#tourCard [data-tr=next]'); p.wait_for_timeout(500)
    check('Done ends it: no card, no outlines, the hand closed', J(p, "() => !TOUR && !document.querySelector('#tourCard') && !document.querySelector('#mtrRings') && !document.documentElement.classList.contains('mhand')"))
    # ---- the ☰ sheet asks first in a game under way; then Do it for me all the way
    p.tap('#mMenu'); p.wait_for_timeout(400)
    row = p.locator('#ctx button', has_text='How to play')
    check('the ☰ sheet has How to play', row.count() == 1)
    row.first.tap(); p.wait_for_timeout(500)
    check('in a practice game the tour didn\'t set up, it starts at once (this board is the tour\'s)', J(p, "() => !!TOUR && TOUR.from==='play'"))
    J(p, "() => { tourEnd(true); G.tourBoard=false; }"); p.wait_for_timeout(300)
    p.tap('#mMenu'); p.wait_for_timeout(400); p.locator('#ctx button', has_text='How to play').first.tap(); p.wait_for_timeout(500)
    check('in another practice game it asks first (Not now / Set it up)', J(p, "() => !TOUR && /in place of this practice game/.test(document.querySelector('#modal').innerText)"))
    p.get_by_role('button', name='Set it up').tap(); p.wait_for_timeout(3500)
    p.tap('#tourCard [data-tr=next]'); p.wait_for_timeout(600)
    done_steps = []
    for _ in range(30):
        c = J(p, CARD)
        if not c or not c['doit']: break
        done_steps.append(c['t']); p.tap('#tourCard [data-mtrdo]'); wait_step(p, c['i'], 6000)
    c = J(p, CARD); s = J(p, ST)
    check('Do it for me runs every step the player does, in order', done_steps == ['Your hand', 'Play a land', 'Cast a spell', 'Pay for it', 'The stack', 'A trigger', "Your friend's OK", 'To combat', 'Attack', 'Blocking', 'Combat damage', "Ragavan's trigger"], done_steps)
    check('and the board comes out the same: Mountain and Ocelot Pride in, life 16, Practice 14, a Treasure, at Reading cards', c and c['t'] == 'Reading cards' and s['life'] == 16 and s['olife'] == 14 and 'Treasure' in s['bf'] and 'Ocelot Pride' in s['bf'], (c and c['t'], s))
    p.tap('#tourCard [data-tr=end]'); p.wait_for_timeout(300)
    check('Skip tour ends it', J(p, "() => !TOUR && !document.querySelector('#mtrRings')"))
    check('no page errors', not errs, errs)
finally:
    srv.terminate()
print('ALL PASS' if all(res) else 'SOME FAILED', f'({sum(res)}/{len(res)})')
sys.exit(0 if all(res) else 1)
