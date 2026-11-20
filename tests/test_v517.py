import os, socket, subprocess, sys, time
from playwright.sync_api import sync_playwright
# MT_ROOT: the folder whose index.html is served (default: this repo). tests/run_all.py --rev REV points it at an older build.
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
        for h in ['**/cards.scryfall.io/**','**/svgs.scryfall.io/**','**/backs.scryfall.io/**','**/fonts.googleapis.com/**','**/fonts.gstatic.com/**']:
            ctx.route(h, lambda r: r.abort())
        ctx.route('**/api.scryfall.com/**', lambda r: r.fulfill(status=200, content_type='application/json', body='{"data":[]}'))
        p = ctx.new_page(); errs = []
        p.on('pageerror', lambda e: errs.append(str(e)))
        p.goto(f'http://127.0.0.1:{PORT}/'); p.wait_for_timeout(600)
        p.click('#soloBtn'); p.wait_for_timeout(600)
        p.locator('.drow').first.click(); p.wait_for_timeout(400)
        p.get_by_role('button', name='Play this deck').click(); p.wait_for_timeout(1500)
        for name in ['No deck', 'Keep']:
            bt = p.get_by_role('button', name=name)
            if bt.count():
                try: bt.first.click(timeout=800)
                except Exception: pass
        p.wait_for_function('typeof G!=="undefined" && G.me && Array.isArray(G.me.bf)', timeout=10000)
        p.evaluate("""() => { G.me.kept=G.me.dealt=true; G.me.hand=[]; G.me.bf=[]; G.me.st=[]; G.turn.n=1; G.turn.active=G.myId; G.turn.phase=2; window.__r = mk(keyOf('Ghor-Clan Rampager')); G.me.hand.push(window.__r); }""")
        # A: main phase, no attacker -> only the creature cost, no bloodrush
        a = p.evaluate("""() => { const c=window.__r; return {br: brIdx(c), ht: handTimeWhy(c), ways: castWays(c, c.id).map(w=>w.k)}; }""")
        check('main phase: bloodrush not offered', a['br'] == -1 and 'bloodrush' not in a['ways'], str(a))
        check('main phase: card not dimmed', a['ht'] is None, str(a['ht']))
        # B: my combat with my attacker -> bloodrush only, no sorcery-timing warning
        p.evaluate("""() => { G.turn.phase=3; const bear=mk(null,{cu:{n:'Test Bear', t:'Creature — Bear', o:'', pt:'2/2'}}); bear.atk=true; G.me.bf.push(bear); window.__bear=bear; }""")
        b_ = p.evaluate("""() => { const c=window.__r; return {br: brIdx(c), ht: handTimeWhy(c), ways: castWays(c, c.id).map(w=>w.k)}; }""")
        check('combat with attacker: bloodrush ready', b_['br'] == 0, str(b_))
        check('combat with attacker: card not dimmed', b_['ht'] is None, str(b_['ht']))
        check('combat with attacker: bloodrush offered', 'bloodrush' in b_['ways'], str(b_['ways']))
        p.evaluate("""() => { window.__r.id; castSpell(window.__r.id); }""")
        p.wait_for_timeout(500)
        body = p.inner_text('body')
        check('combat with attacker: no sorcery-timing warning', 'Sorcery timing' not in body)
        pay = p.evaluate("() => { const e=document.querySelector('#payPanel'); return e ? (e.innerText||'') : null; }")
        check('combat with attacker: payment window opens for bloodrush', pay is not None and 'Bloodrush' in pay and 'Cast as a creature' not in pay, str(pay)[:160])
        # C: battle cry chip
        p.evaluate("() => { const x=window.__bear; x.tkw={n:G.turn.n, k:['battle cry']}; x.bcry={n:G.turn.n, k:1}; }")
        c1 = p.evaluate("() => kcsHTML(window.__bear, true)")
        p.evaluate("() => { window.__bear.bcry={n:G.turn.n, k:2}; }")
        c2 = p.evaluate("() => kcsHTML(window.__bear, true)")
        check('battle cry chip: icon drawn (white fill via CSS)', 'M3 9h3l10-5v16L6 15H3z' in c1)
        check('battle cry chip: one instance has no count', 'kcn' not in c1)
        check('battle cry chip: two instances show x2', '×2' in c2 and 'kcn' in c2)
        check('no page errors', not errs, str(errs)[:300])
        b.close()
finally:
    srv.terminate()
print('ALL PASS' if all(ok for _, ok in results) else 'SOME FAILED', f'({sum(ok for _,ok in results)}/{len(results)})')
