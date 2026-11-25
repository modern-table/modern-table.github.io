"""v5.37 / phone layer m0.12 (the maintainer, 2026-11-24):
1. How the table works gets two tabs (How to play, Keys) so it can say more and still fit a 1500x900 window without scrolling:
   voice at the table, Game Night, the stack chime, ordering your own triggers, dimmed hand cards, energy and poison by hand.
2. A friend clicked the "energy 0" chip in his player box by accident and didn't know why energy was on his battlefield. The energy and
   poison chips now show only when the count is above 0 or a deck at the table uses that counter; adding or removing one by hand is in
   the player box's right-click menu (and the phone's menu, which has no right-click)."""
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
FIT = """() => { const m=document.querySelector('#modal'), r=m.firstElementChild.getBoundingClientRect();
  return {top:r.top, bottom:r.bottom, scroll:[...m.querySelectorAll('*')].filter(e=>e.offsetParent && e.scrollHeight>e.clientHeight+1 && getComputedStyle(e).overflowY!=='visible').length,
    play:(document.querySelector('#modal [data-hp="play"]')||{}).hidden, keys:(document.querySelector('#modal [data-hp="keys"]')||{}).hidden, txt:m.innerText}; }"""
CHIPS = "() => ({me:[...document.querySelectorAll('#myAv [data-ctr]')].map(e=>e.dataset.ctr), opp:[...document.querySelectorAll('#oppAv [data-ctr]')].map(e=>e.dataset.ctr), en:G.me.ctr.energy, oppPo:G.opp.ctr.poison, marker:!!document.querySelector('#myBack .marker[data-ctr=\"energy\"]')})"
MENU = "() => [...document.querySelectorAll('#ctx button')].filter(b=>b.offsetParent).map(b=>b.innerText.trim())"
try:
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        ctx = br.new_context(viewport={'width': 1500, 'height': 900}); block(ctx); p = ctx.new_page()
        errs = []; p.on('pageerror', lambda e: errs.append(str(e)))
        start(p, f'http://127.0.0.1:{PORT}/?nobake', False)
        # 1. the help page
        J(p, '() => helpModal()'); p.wait_for_timeout(300)
        f = J(p, FIT)
        check('How the table works opens on How to play, with a Keys tab', f['play'] is False and f['keys'] is True and p.locator('#modal [data-ht="keys"]').count() == 1, (f['play'], f['keys']))
        check('it fits 1500x900 without scrolling', f['top'] >= 0 and f['bottom'] <= 900 and f['scroll'] == 0, (f['top'], f['bottom'], f['scroll']))
        t = f['txt']
        check('it tells about voice, Game Night, the chime, trigger order and dimmed cards', all(x in t for x in ['microphone beside your name', 'Game Night', 'a chime plays', 'choose their order', 'A dimmed card']), t[:200])
        check('and still about the OK and the stops, and energy and poison by hand', "their OK" in t and 'Click the turn for stops' in t and 'energy and poison counters' in t)
        p.click('#modal [data-ht="keys"]'); p.wait_for_timeout(200)
        f = J(p, FIT)
        check('Keys shows the shortcuts and hides How to play', f['keys'] is False and f['play'] is True and 'tap or untap' in f['txt'] and 'next phase, or OK' in f['txt'] and 'Automatic first' not in f['txt'], f['txt'][:120])
        check('the Keys tab fits too', f['top'] >= 0 and f['bottom'] <= 900 and f['scroll'] == 0)
        p.click('#modal [data-ht="play"]'); p.wait_for_timeout(150)
        check('How to play comes back', J(p, FIT)['play'] is False)
        J(p, '() => closeModal()')
        # 2. the chips
        src = J(p, "() => ({mine:G.me.energySrc, calc:[...G.me.lib, ...G.me.side, ...G.me.hand, ...G.me.bf].some(x=>ENERGYRE.test(cdata(x).o||''))})")
        check('loading a deck notes whether it uses energy', src['mine'] == src['calc'], src)
        J(p, "() => { G.me.energySrc=false; G.me.energySeen=false; G.me.poisonSrc=false; G.me.poisonSeen=false; Object.assign(G.opp, {energySrc:false, energySeen:false, poisonSrc:false, poisonSeen:false}); G.me.ctr={poison:0,energy:0}; G.opp.ctr={poison:0,energy:0}; render(); }")
        c = J(p, CHIPS)
        check('no energy or poison chips at 0 when no deck uses them', c['me'] == [] and c['opp'] == [], c)
        J(p, "() => { G.opp.energySrc=true; render(); }")
        c = J(p, CHIPS)
        check('either deck using energy brings back both energy chips (not poison)', c['me'] == ['energy'] and c['opp'] == ['energy'], c)
        J(p, "() => { G.opp.energySrc=false; render(); }")
        # right-click my player box
        p.click('#myAv .dk', button='right'); p.wait_for_timeout(250)
        m = J(p, MENU)
        check('right-clicking my player box offers Add an energy counter and Add a poison counter', 'Add an energy counter' in m and 'Add a poison counter' in m and not any('Remove' in x for x in m), m)
        p.locator('#ctx button', has_text='Add an energy counter').click(); p.wait_for_timeout(400)
        c = J(p, CHIPS)
        check('it adds one: the chip and the battlefield marker show', c['en'] == 1 and 'energy' in c['me'] and c['marker'], c)
        p.click('#myAv .dk', button='right'); p.wait_for_timeout(250)
        m = J(p, MENU)
        check('with energy, the menu offers Remove an energy counter', 'Remove an energy counter' in m, m)
        p.locator('#ctx button', has_text='Remove an energy counter').click(); p.wait_for_timeout(400)
        c = J(p, CHIPS)
        check('removing it takes the count back to 0 and the marker away (the chip stays: energy has been used at this table)', c['en'] == 0 and not c['marker'], c)
        # Practice's box
        p.click('#oppAv .dk', button='right'); p.wait_for_timeout(250)
        m = J(p, MENU)
        check("Practice's box offers a poison counter in its name", any(x.startswith('Add a poison counter (') for x in m), m)
        p.locator('#ctx button', has_text='Add a poison counter').click(); p.wait_for_timeout(600)
        c = J(p, CHIPS)
        check('Practice gets the poison counter and its chip shows', c['oppPo'] == 1 and 'poison' in c['opp'], c)
        # a click on the box itself no longer can add anything by accident when no deck uses the counters
        J(p, "() => { G.opp.ctr={poison:0,energy:0}; G.opp.poisonSeen=false; G.me.energySeen=false; G.me.ctr.energy=0; render(); }")
        p.click('#myAv .dk'); p.click('#myAv .mana', position={'x': 2, 'y': 2}); p.wait_for_timeout(300)
        check('clicking around my player box adds no energy', J(p, "() => G.me.ctr.energy") == 0)
        check('no page errors on the desktop', not errs, errs[:3])
        ctx.close()
        # 3. the phone
        ctx = br.new_context(viewport={'width': 844, 'height': 390}, has_touch=True, is_mobile=True); block(ctx); p = ctx.new_page()
        errs = []; p.on('pageerror', lambda e: errs.append(str(e)))
        start(p, f'http://127.0.0.1:{PORT}/m/?nobake', True)
        p.tap('#mMenu'); p.wait_for_timeout(400)
        row = p.locator('#ctx button', has_text='Energy and poison counters')
        check('the phone menu has Energy and poison counters…', row.count() == 1)
        if row.count():
            row.first.tap(); p.wait_for_timeout(400)
            m = J(p, MENU)
            check('it opens the same choices', 'Add an energy counter' in m and 'Add a poison counter' in m, m)
            p.locator('#ctx button', has_text='Add an energy counter').first.tap(); p.wait_for_timeout(500)
            check('and adds energy on the phone', J(p, "() => G.me.ctr.energy") == 1)
        check('no page errors on the phone', not errs, errs[:3])
        br.close()
finally:
    srv.terminate()
print('ALL PASS' if all(res) else 'SOME FAILED', f'({sum(res)}/{len(res)})')
sys.exit(0 if all(res) else 1)
