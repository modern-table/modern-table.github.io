"""v5.30: Practice always brings a deck. The opening window offers only Choose its deck… and Random deck (no No deck, no Close);
Choose its deck… has Back, which returns to the offer; Random deck gives Practice a library and a hidden seven-card hand; the Practice
button still changes its deck. Fails on v5.29 (the window had No deck and could be closed)."""
import os, socket, subprocess, sys, time
from playwright.sync_api import sync_playwright
ROOT = os.environ.get('MT_ROOT') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def _free_port():
    s = socket.socket(); s.bind(('127.0.0.1', 0)); p = s.getsockname()[1]; s.close(); return p
PORT = _free_port()
srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(PORT), '--bind', '127.0.0.1'], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(0.8)
results = []
def check(name, cond, extra=''):
    results.append((name, bool(cond))); print(('PASS' if cond else 'FAIL'), name, extra)
try:
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context(viewport={'width': 1500, 'height': 900})
        for h in ['**/cards.scryfall.io/**','**/svgs.scryfall.io/**','**/backs.scryfall.io/**','**/fonts.googleapis.com/**','**/fonts.gstatic.com/**','**/gc.zgo.at/**','**/*.metered.live/**']:
            ctx.route(h, lambda r: r.abort())
        ctx.route('**/api.scryfall.com/**', lambda r: r.fulfill(status=200, content_type='application/json', body='{"data":[]}'))
        p = ctx.new_page(); errs = []; p.on('pageerror', lambda e: errs.append(str(e)))
        p.goto(f'http://127.0.0.1:{PORT}/'); p.wait_for_timeout(600)
        p.evaluate("() => { const s=document.getElementById('spl'); if(s) s.remove(); }")
        p.click('#soloBtn'); p.wait_for_timeout(600); p.locator('.drow').first.click(); p.wait_for_timeout(400)
        p.get_by_role('button', name='Play this deck').click(); p.wait_for_timeout(1500)
        info = p.evaluate("() => { const m=document.querySelector('#modal'); return m.hidden ? null : {t:m.querySelector('h3,h2,header') ? m.querySelector('h3,h2,header').innerText : m.innerText.split('\\n')[0], b:[...m.querySelectorAll('footer button')].map(x=>x.innerText.trim()), x:!!m.querySelector('.x, [data-close], button[aria-label=\"Close\"]') && getComputedStyle(m.querySelector('.x, [data-close], button[aria-label=\"Close\"]')).display!=='none'}; }")
        check("after Play this deck, the Practice's deck window opens", info and "Practice" in info['t'], str(info))
        check('it offers only Choose its deck… and Random deck (no No deck)', info and [x.lower() for x in info['b']] == ["choose its deck…", 'random deck'], str(info and info['b']))
        check('it has no Close button', info and not info['x'], str(info))
        p.keyboard.press('Escape'); p.wait_for_timeout(300)
        check('Esc does not close it without a choice', p.evaluate("() => !document.querySelector('#modal').hidden && !G.opp.deckSpec"))
        p.get_by_role('button', name='Choose its deck…').click(); p.wait_for_timeout(300)
        lst = p.evaluate("() => [...document.querySelectorAll('#modal footer button')].map(x=>x.innerText.trim())")
        check('Choose its deck… lists the decks with Back and Random deck', [x.lower() for x in lst] == ['back', 'random deck'] and p.evaluate("() => document.querySelectorAll('#modal [data-pdk]').length >= 10"), str(lst))
        p.get_by_role('button', name='Back').click(); p.wait_for_timeout(300)
        check('Back returns to the offer', p.evaluate("() => !document.querySelector('#modal').hidden && /Random deck/i.test(document.querySelector('#modal footer').innerText) && /Choose its deck/i.test(document.querySelector('#modal footer').innerText)"))
        p.get_by_role('button', name='Random deck').click(); p.wait_for_timeout(600)
        st = p.evaluate("() => ({spec:!!G.opp.deckSpec, name:G.opp.deck, lib:G.opp.lib.length, hand:G.opp.hand.length})")
        check('Random deck: Practice has a library and seven cards in hand', st['spec'] and st['hand'] == 7 and st['lib'] >= 30, str(st))
        mi = p.evaluate("() => { const r=[]; const m=menu; menu=(x,y,items)=>{ r.push(...items.filter(Boolean).map(i=>Array.isArray(i)?i[0]:'')); }; try{ practiceMenu(0,0); } finally { menu=m; } return r; }")
        check("the Practice button still changes its deck", any("Change Practice's deck" in x for x in mi), str(mi[:6]))
        check('no page errors', not errs, str(errs[:3]))
        b.close()
finally:
    srv.terminate()
n = len(results); k = sum(1 for _, ok in results if not ok)
print(f'ALL PASS ({n}/{n})' if not k else f'SOME FAILED ({k}/{n})')
