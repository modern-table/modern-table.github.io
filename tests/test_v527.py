"""v5.27: with an additional combat pending, the big button reads "Next: second combat" after the first combat."""
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
CHIPS = """() => [...document.querySelectorAll('#phases button')].map(b=>b.firstChild.textContent+(b.classList.contains('on')?'*':'')+(b.classList.contains('xc')?'~':''))"""
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
        for name in ['Random deck', 'Keep']:
            bt = p.get_by_role('button', name=name)
            if bt.count():
                try: bt.first.click(timeout=800)
                except Exception: pass
        p.wait_for_function('typeof G!=="undefined" && G.me && Array.isArray(G.me.bf)', timeout=10000)
        p.evaluate("""() => { G.me.kept=G.me.dealt=true; G.me.hand=[]; G.me.bf=[]; G.me.st=[]; G.me.gy=[]; G.me.mana=noMana(); G.turn.n=3; G.turn.active=G.myId; G.turn.phase=2; delete G.turn.cx; G.opp.bf=[]; render(); }""")

        NB = "() => document.querySelector('#next').textContent"
        p.evaluate("""() => { window.__f = mk(keyOf('Fear of Missing Out')); window.__f.hst=1; G.me.bf.push(window.__f);
            for(const cu of [{n:'Gy Land', t:'Land', o:''}, {n:'Gy Instant', t:'Instant', o:''}, {n:'Gy Sorcery', t:'Sorcery', o:''}, {n:'Gy Artifact', t:'Artifact', o:''}]) G.me.gy.push(mk(null,{cu}));
            G.turn.phase=3; render(); }""")
        check('first combat, nothing pending: Next: Main 2', p.evaluate(NB) == 'Next: Main 2', p.evaluate(NB))
        p.evaluate("() => { G.atkSel=new Set([window.__f.id]); atkCommit(); }"); p.wait_for_timeout(400)
        p.evaluate("""() => { const t=G.me.st[G.me.st.length-1]; t.tg=[window.__f.id]; resolve(t.id); }"""); p.wait_for_timeout(500)
        xs = p.evaluate("() => [G.me.xcomb, G.turn.n, G.turn.cs]")
        check('delirium trigger resolved: additional combat pending', xs[0] == xs[1], str(xs))
        # walk the first combat with real presses of the big button until it offers to leave combat
        seen = []
        for _ in range(6):
            txt = p.evaluate(NB); seen.append(txt)
            if txt.startswith('Next:'): break
            p.click('#next'); p.wait_for_timeout(400)
        check('after the first combat the button reads Next: second combat', p.evaluate(NB) == 'Next: second combat', str(seen))
        p.click('#next'); p.wait_for_timeout(400)
        st = p.evaluate("() => [G.turn.phase, G.turn.cx, G.me.xcomb||null]")
        check('pressing it begins the additional combat', st == [3, 2, None], str(st))
        p.evaluate("() => { G.me.bf.forEach(c=>c.atk=false); render(); }")
        check('in the additional combat: Next: Main 2 again', p.evaluate(NB) == 'Next: Main 2', p.evaluate(NB))
        p.click('#next'); p.wait_for_timeout(300)
        check('then Main 2', p.evaluate("() => G.turn.phase") == 4, str(p.evaluate("() => G.turn.phase")))
        check('no page errors', not errs, str(errs[:3]))
        b.close()
finally:
    srv.terminate()
fails = [n for n, ok in results if not ok]
print('ALL PASS' if not fails else 'SOME FAILED', f'({len(results)-len(fails)}/{len(results)})')
sys.exit(1 if fails else 0)
