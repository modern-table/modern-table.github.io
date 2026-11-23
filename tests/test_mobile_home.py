"""The phone table, phone layer m0.9: Home and Reload for a phone page added to the home screen (no browser bar). The front page has
↻ Reload; the deck screen's top bar has ⌂ Home and ↻; the table's ☰ sheet starts with ⌂ Home (asks, keeps the seat, the front page
offers Resume) and ↻ Reload (back at the same table, the same game). Leave the table is no longer a separate row."""
import os, socket, subprocess, sys, time
from playwright.sync_api import sync_playwright
ROOT = os.environ.get('MT_ROOT') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def _free_port():
    s = socket.socket(); s.bind(('127.0.0.1', 0)); p = s.getsockname()[1]; s.close(); return p
PORT = _free_port()
srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(PORT), '--bind', '127.0.0.1'], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(0.8); res = []
def check(n, c, e=''): res.append(bool(c)); print('PASS' if c else 'FAIL', n, '' if c else e)
SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="488" height="680"><rect width="488" height="680" rx="24" fill="#3b4a3f"/></svg>'
def block(ctx):
    ctx.route('**/cards.scryfall.io/**', lambda r: r.fulfill(status=200, content_type='image/svg+xml', body=SVG))
    for h in ['**/svgs.scryfall.io/**', '**/backs.scryfall.io/**', '**/fonts.googleapis.com/**', '**/fonts.gstatic.com/**', '**/gc.zgo.at/**', '**/*.metered.live/**']: ctx.route(h, lambda r: r.abort())
    ctx.route('**/api.scryfall.com/**', lambda r: r.fulfill(status=200, content_type='application/json', body='{"data":[]}'))
J = lambda p, js: p.evaluate(js)
SCR = "() => ['lobby','decks','table'].find(s=>!document.getElementById(s).hidden)"
def nospl(p): J(p, "() => { const s=document.getElementById('spl'); if(s) s.remove(); }")
try:
  with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={'width': 844, 'height': 390}, is_mobile=True, has_touch=True, device_scale_factor=2); block(ctx)
    p = ctx.new_page(); errs = []; p.on('pageerror', lambda e: errs.append(str(e)))
    p.goto(f'http://127.0.0.1:{PORT}/m/'); p.wait_for_timeout(800); nospl(p)
    check('the front page has ↻ Reload by the phone note', p.locator('#mNote [data-mnav="reload"]').count() == 1)
    p.tap('#soloBtn'); p.wait_for_timeout(700)
    check('the deck screen has ⌂ Home and ↻ in its top bar, on screen', J(p, "() => { const h=document.querySelector('#decks .topbar [data-mnav=home]'), r=document.querySelector('#decks .topbar [data-mnav=reload]'); if(!h||!r) return false; const a=h.getBoundingClientRect(), c=r.getBoundingClientRect(); return a.width>20 && a.right<=innerWidth && c.right<=innerWidth && a.top>=0; }"))
    p.locator('#decks [data-mnav="home"]').tap(); p.wait_for_timeout(400)
    check('Home on the deck screen of a practice table asks first', J(p, "() => !document.querySelector('#modal').hidden && /front page/.test(document.querySelector('#modal').innerText)"))
    p.get_by_role('button', name='Cancel').tap(); p.wait_for_timeout(300)
    p.locator('.drow').first.tap(); p.wait_for_timeout(400)
    p.get_by_role('button', name='Play this deck').tap(); p.wait_for_timeout(1500)
    p.get_by_role('button', name='Random deck').first.tap(); p.wait_for_timeout(500)
    p.get_by_role('button', name='Start the game').first.tap(); p.wait_for_timeout(700)
    p.tap('[data-first="deal"]'); p.wait_for_timeout(600); p.tap('[data-first="keep"]'); p.wait_for_timeout(800)
    if p.locator('#modal:not([hidden])').count(): J(p, "() => closeModal()")
    J(p, "() => { G.me.life=13; changed(); }"); p.wait_for_timeout(300)
    hand0 = J(p, "() => G.me.hand.map(c=>c.id).join()")
    p.tap('#mMenu'); p.wait_for_timeout(400)
    rows = J(p, "() => [...document.querySelectorAll('#ctx button')].map(b=>b.textContent.trim())")
    check('the ☰ sheet starts with ⌂ Home and ↻ Reload; no separate Leave the table', rows[:2] == ['⌂ Home (the front page)', '↻ Reload (back to this table)'] and not any(r.startswith('Leave the table') for r in rows), rows)
    p.locator('#ctx button', has_text='↻ Reload').tap()
    p.wait_for_load_state('load'); p.wait_for_timeout(2000); nospl(p)
    r = J(p, "() => ['lobby','decks','table'].find(s=>!document.getElementById(s).hidden)")
    check('Reload comes straight back to the table, the same game (life 13, the same hand)', r == 'table' and J(p, "() => G.me.life") == 13 and J(p, "() => G.me.hand.map(c=>c.id).join()") == hand0, [r, J(p, "() => G.me && G.me.life")])
    p.tap('#mMenu'); p.wait_for_timeout(400)
    p.locator('#ctx button', has_text='⌂ Home').tap(); p.wait_for_timeout(400)
    check('Home from the table asks first (the seat is kept)', J(p, "() => !document.querySelector('#modal').hidden && /seat/.test(document.querySelector('#modal').innerText)"))
    p.get_by_role('button', name='Yes').tap(); p.wait_for_load_state('load'); p.wait_for_timeout(1500); nospl(p)
    check('…to the front page, which offers Resume', J(p, SCR) == 'lobby' and J(p, "() => !document.querySelector('#resumeBtn').hidden"))
    p.locator('#resumeBtn').tap(); p.wait_for_timeout(1500)
    check('Resume brings the game back', J(p, SCR) == 'table' and J(p, "() => G.me.life") == 13)
    p.locator('#mNote [data-mnav="reload"]').count()
    check('no page errors', not errs, errs)
    b.close()
finally:
    srv.terminate()
print(('ALL PASS' if all(res) else 'SOME FAILED') + f' ({sum(res)}/{len(res)})')
