"""v5.36 / phone layer m0.11 (the maintainer, 2026-11-24):
1. Atarka's Command cast from the opponent's exile (Ragavan's "until end of turn, you may cast that card") never asked for its modes: it went
   straight to payment and onto the stack with all four modes' text. A modal spell cast from the other player's exile now chooses its modes
   before paying (the mode cost counts), and the chosen modes are on the stack card when it arrives. Cancel casts nothing; a plain spell
   (Lightning Bolt) still goes straight to payment. Checked on the phone page (taps) and the desktop page (clicks).
2. The phone's Exiled by cards box: the card was about 18 px wide with its text in a thin column. Now the card is bigger with its button beside
   it and the text across the whole box below both; a tap on the card opens LOOK; the stack keeps room when something is on it."""
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
J = lambda p, js, *a: p.evaluate(js, *a)
MODAL = "() => document.querySelector('#modal').hidden ? null : document.querySelector('#modal').innerText"
def start(p, url, phone):
    p.goto(url); p.wait_for_timeout(800)
    J(p, "() => { const s=document.getElementById('spl'); if(s) s.remove(); }")
    act = (lambda sel: p.tap(sel)) if phone else (lambda sel: p.click(sel))
    act('#soloBtn'); p.wait_for_timeout(700); (p.locator('.drow').first.tap() if phone else p.locator('.drow').first.click()); p.wait_for_timeout(400)
    b = p.get_by_role('button', name='Play this deck'); (b.tap() if phone else b.click()); p.wait_for_timeout(1500)
    bt = p.get_by_role('button', name='Random deck')
    if bt.count(): (bt.first.tap() if phone else bt.first.click()); p.wait_for_timeout(500)
    b = p.get_by_role('button', name='Start the game').first; (b.tap() if phone else b.click()); p.wait_for_timeout(700)
    act('[data-first="deal"]'); p.wait_for_timeout(600); act('[data-first="keep"]'); p.wait_for_timeout(800)
    if p.locator('#modal:not([hidden])').count(): J(p, "() => closeModal()")
SCENE = """(name) => { G.turn.n=3; G.turn.active=G.myId; G.turn.phase=4; G.turn.passed=false; G.me.bf=[]; G.me.hand=[]; G.me.st=[]; G.opp.st=[]; G.me.mana=noMana(); G.opp.life=20;
  G.me.bf.push(mk(keyOf('Ragavan, Nimble Pilferer'))); G.opp.ex=G.opp.ex.filter(c=>!c.offer); const c=mk(keyOf(name),{o:oppId()}); G.opp.ex.push(c); c.offer=G.turn.n; changed(); return c.id; }"""
STATE = """() => ({st:G.me.st.map(c=>({n:cdata(c).n, md:c.md||null})), opex:G.opp.ex.filter(c=>c.offer).map(c=>cdata(c).n), pay:typeof PAY!=='undefined' && !!PAY,
  life:G.opp.life, log:[...document.querySelectorAll('#log > *')].map(e=>e.innerText).slice(-8)})"""
def modes_flow(p, phone, tag):
    act = (lambda loc: loc.tap()) if phone else (lambda loc: loc.click())
    J(p, SCENE, "Atarka's Command")
    p.wait_for_timeout(400)
    act(p.locator('#offers button[data-take]')); p.wait_for_timeout(600)
    m = J(p, MODAL) or ''
    check(f'{tag}: Cast it on Atarka\'s Command from Practice\'s exile asks for its modes first', 'Choose two' in m and "deals 3 damage to each opponent" in m and not J(p, STATE)['pay'], m[:160])
    # cancel: nothing is cast, the card stays offered
    act(p.locator('#modal footer button', has_text='Cancel')); p.wait_for_timeout(400)
    s = J(p, STATE)
    check(f'{tag}: Cancel casts nothing and the card stays in the box', not s['st'] and not s['pay'] and s['opex'] == ["Atarka's Command"], s)
    # again: asks again; choose 2 and 4
    act(p.locator('#offers button[data-take]')); p.wait_for_timeout(600)
    check(f'{tag}: a second Cast it asks again', 'Choose two' in (J(p, MODAL) or ''))
    act(p.locator('#mdList [data-m="2"]')); act(p.locator('#mdList [data-m="4"]')); p.wait_for_timeout(200)
    act(p.locator('#modal footer button.go')); p.wait_for_timeout(700)
    s = J(p, STATE); m = J(p, MODAL) or ''
    check(f'{tag}: after the modes, the payment window opens', s['pay'] or 'Paid another way' in m, (s, m[:120]))
    act(p.get_by_role('button', name='Paid another way').first); p.wait_for_timeout(900)
    s = J(p, STATE)
    check(f'{tag}: Atarka\'s Command is on my stack with modes 2 and 4', s['st'] == [{'n': "Atarka's Command", 'md': [2, 4]}], s)
    check(f'{tag}: the log names the chosen modes', any('chose for' in l and 'each opponent' in l and '+1/+1' in l for l in s['log']), s['log'])
    J(p, "() => resolve(G.me.st[0].id)"); p.wait_for_timeout(1200)
    s = J(p, STATE); pt = J(p, "() => { const c=G.me.bf.find(c=>cdata(c).n.startsWith('Ragavan')); return dynPT(c, G.myId); }")
    check(f'{tag}: it resolves with those modes: 3 damage and +1/+1 on Ragavan, no land question, no life-gain lock', s['life'] == 17 and pt and pt.get('p') == 3 and not J(p, MODAL) and not J(p, "() => G.opp.noGain===G.turn.n"), (s, pt))
    # a plain spell still goes straight to payment
    J(p, SCENE, 'Lightning Bolt'); p.wait_for_timeout(400)
    act(p.locator('#offers button[data-take]')); p.wait_for_timeout(600)
    m = J(p, MODAL) or ''
    check(f'{tag}: Lightning Bolt from the box goes straight to payment (no mode window)', 'Choose' not in m and (J(p, STATE)['pay'] or 'Paid another way' in m), m[:120])
    J(p, "() => { closeModal(); if(typeof payCancel==='function') try{ payCancel(); }catch(e){} }")
try:
  with sync_playwright() as pw:
    b = pw.chromium.launch()
    # phone
    ctx = b.new_context(viewport={'width': 844, 'height': 390}, is_mobile=True, has_touch=True, device_scale_factor=2); block(ctx)
    p = ctx.new_page(); errs = []; p.on('pageerror', lambda e: errs.append(str(e)))
    start(p, f'http://127.0.0.1:{PORT}/m/', True)
    J(p, SCENE, "Atarka's Command"); p.wait_for_timeout(500)
    g = J(p, """() => { const o=document.querySelector('#offers .offer'), r=e=>{ const b=e.getBoundingClientRect(); return {l:b.left, r:b.right, t:b.top, b:b.bottom, w:b.width}; };
      return {box:r(document.querySelector('#offerwrap')), card:r(o.querySelector('.card')), txt:r(o.querySelector(':scope > span')), btn:r(o.querySelector('button')), right:r(document.querySelector('#right'))}; }""")
    check('phone: the exiled card is shown at a readable size (at least 50 px wide)', g['card']['w'] >= 50, g['card'])
    check('phone: Cast it sits beside the card', g['btn']['l'] >= g['card']['r'] - 1 and g['btn']['t'] < g['card']['b'] and g['btn']['b'] > g['card']['t'], (g['card'], g['btn']))
    check('phone: the text runs below the card and button, across the whole box', g['txt']['t'] >= g['card']['b'] - 1 and g['txt']['l'] <= g['card']['l'] + 1 and g['txt']['r'] >= g['btn']['r'] - 2 and g['txt']['w'] >= 100, g)
    check('phone: the box stays inside the right column', g['box']['l'] >= g['right']['l'] - 1 and g['box']['r'] <= g['right']['r'] + 1, g)
    # a tap on the card reads it
    p.locator('#offers .offer .card').first.tap(); p.wait_for_timeout(500)
    v = J(p, "() => document.querySelector('#mView').hidden ? null : document.querySelector('#mView').innerText")
    check('phone: a tap on the exiled card opens its LOOK view (picture and Oracle text)', v and "Atarka's Command" in v and 'Choose two' in v and not J(p, STATE)['pay'], (v or '')[:120])
    p.locator('#mView .mx').tap(); p.wait_for_timeout(300)
    p.tap('#mLook'); p.wait_for_timeout(200); p.locator('#offers .offer .card').first.tap(); p.wait_for_timeout(500)
    v = J(p, "() => document.querySelector('#mView').hidden ? null : document.querySelector('#mView').innerText")
    check('phone: with LOOK on, a tap on the exiled card reads it too', v and "Atarka's Command" in v, (v or '')[:80])
    p.tap('#mLook'); p.wait_for_timeout(300)
    # the stack keeps room while the box is up
    J(p, "() => { const s=mk(keyOf('Lightning Bolt')); s.ts=Date.now(); G.me.st.push(s); changed(); }"); p.wait_for_timeout(500)
    h = J(p, "() => { const r=document.querySelector('#stack .card').getBoundingClientRect(), w=document.querySelector('#stackwrap').getBoundingClientRect(); return {vis:Math.min(r.bottom,w.bottom)-Math.max(r.top,w.top), wrap:w.height}; }")
    check('phone: with a spell on the stack, the stack keeps room beside the box (its card is in view)', h['vis'] >= 40, h)
    J(p, "() => { G.me.st=[]; changed(); }")
    modes_flow(p, True, 'phone')
    check('phone: no page errors', not errs, errs[:3])
    ctx.close()
    # desktop
    ctx = b.new_context(viewport={'width': 1440, 'height': 900}); block(ctx)
    p = ctx.new_page(); errs = []; p.on('pageerror', lambda e: errs.append(str(e)))
    start(p, f'http://127.0.0.1:{PORT}/', False)
    modes_flow(p, False, 'desktop')
    check('desktop: no page errors', not errs, errs[:3])
    b.close()
finally:
    srv.terminate()
n = len(res); k = n - sum(res)
print(f'ALL PASS ({n}/{n})' if res and not k else f'SOME FAILED ({k}/{n})'); sys.exit(0 if res and not k else 1)
