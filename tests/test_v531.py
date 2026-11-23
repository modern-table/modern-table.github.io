"""v5.31: ward read inside a keyword list ("Flying, ward {2}": Colossal Skyturtle), and against Practice my abilities and triggers that
target a ward permanent ask too, not only my spells; a generic {N} ward cost opens the payment window. Practice game, baked card data."""
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
RESET = """() => { S.autoPay=false; G.me.hand=[]; G.me.bf=[]; G.me.st=[]; G.me.gy=[]; G.me.ex=[]; G.me.arrows=[]; G.me.mana=noMana(); G.me.life=20;
  G.opp.bf=[]; G.opp.st=[]; G.opp.ex=[]; G.opp.arrows=[]; G.turn.n=3; G.turn.active=G.myId; G.turn.phase=2; G.mode=null; G.me.lp=null; G.me.lpx=null; render(); }"""
try:
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context(viewport={'width': 1500, 'height': 900})
        for h in ['**/cards.scryfall.io/**','**/svgs.scryfall.io/**','**/backs.scryfall.io/**','**/fonts.googleapis.com/**','**/fonts.gstatic.com/**','**/gc.zgo.at/**','**/*.metered.live/**']:
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
        p.evaluate("() => { G.me.kept=G.me.dealt=true; }"); p.evaluate(RESET)
        LOG = "(n) => [...document.querySelectorAll('#log .le, #log div')].slice(-n).map(e=>e.textContent).join(' | ')"
        modal_open = lambda: p.evaluate("() => !document.querySelector('#modal').hidden")
        modal_text = lambda: p.evaluate("() => document.querySelector('#modal').hidden ? '' : document.querySelector('#modal').innerText")

        r = p.evaluate("() => [wardOf(mk(keyOf('colossal skyturtle'))), wardOf(mk(keyOf('sire of seven deaths'))), wardOf(mk(keyOf('kappa cannoneer'))), wardOf(mk(keyOf('valgavoth, terror eater'))), wardOf(mk(keyOf('thought-knot seer'))), kwOn(mk(keyOf('colossal skyturtle')),'flying')]")
        check('ward read inside a keyword list (Skyturtle {2}); the others unchanged; Skyturtle still flies', r == ['{2}', 'Pay 7 life', '{4}', 'Sacrifice three nonland permanents', None, True], str(r))
        # my spell at Practice's Skyturtle: a payment window for {2}
        p.evaluate("""() => { S.autoPay=true; G.me.bf=[mk(keyOf('mountain'))]; const t=mk(keyOf('colossal skyturtle'),{o:oppId()}); G.opp.bf=[t]; window.__t=t;
            const b=mk(keyOf('lightning bolt')); G.me.st.push(b); window.__b=b; G.me.arrows.push({a:b.id, b:t.id}); render(); }""")
        p.wait_for_timeout(900)
        t = modal_text() or p.evaluate("() => { const e=document.querySelector('#payPanel'); return e && !e.hidden ? e.innerText : ''; }")
        check("my Lightning Bolt at Practice's Colossal Skyturtle asks for its ward {2}", ('{2}' in t or '2' in t) and ('ward' in t.lower() or 'counter' in t.lower()), t[:200])
        check('the log says ward', 'ward ({2})' in p.evaluate(LOG, 4), p.evaluate(LOG, 4))
        # decline: countered
        for lbl in ["Don't pay", 'Let it be countered', 'Cancel']:
            bt = p.locator('#modal button, #payPanel button', has_text=lbl)
            if bt.count():
                bt.first.click(); break
        p.wait_for_timeout(600)
        check('not paying: the Bolt is countered', p.evaluate("() => (find(window.__b.id)||{}).z") in ('gy', 'ex', None), p.evaluate(LOG, 3))
        # a trigger of mine aimed at Practice's Sire of Seven Deaths: ward asks too
        p.evaluate(RESET)
        p.evaluate("""() => { const src=mk(keyOf('thought-knot seer')); G.me.bf=[src]; const s=mk(keyOf('sire of seven deaths'),{o:oppId()}); G.opp.bf=[s];
            const mkr=pushTrig(src, 'It deals 1 damage to any target.', 'trigger'); window.__m=mkr || G.me.st[G.me.st.length-1]; G.me.arrows.push({a:window.__m.id, b:s.id}); render(); }""")
        p.wait_for_timeout(900)
        t = modal_text()
        check("my trigger aimed at Practice's Sire of Seven Deaths asks: pay 7 life", '7 life' in t, t[:200] or p.evaluate(LOG, 3))
        if modal_open():
            p.locator('#modal button', has_text='Pay 7 life').click(); p.wait_for_timeout(500)
        r = p.evaluate("() => [G.me.life, (find(window.__m.id)||{}).z]")
        check('paying 7 life keeps the trigger on the stack', r == [13, 'st'], str(r))
        # Bonecrusher Giant still reacts to spells only
        p.evaluate(RESET)
        p.evaluate("""() => { const src=mk(keyOf('thought-knot seer')); G.me.bf=[src]; const g=mk(keyOf('bonecrusher giant'),{o:oppId()}); G.opp.bf=[g];
            const mkr=pushTrig(src, 'It deals 1 damage to any target.', 'trigger'); const m=mkr || G.me.st[G.me.st.length-1]; G.me.arrows.push({a:m.id, b:g.id}); render(); }""")
        p.wait_for_timeout(600)
        check("an ability aimed at Practice's Bonecrusher Giant doesn't set off its spell trigger", p.evaluate("() => G.me.life") == 20, p.evaluate(LOG, 3))
        check('no page errors', not errs, str(errs[:3]))
        b.close()
finally:
    srv.terminate()
n = len(results); k = sum(1 for _, ok in results if not ok)
print(f'ALL PASS ({n}/{n})' if not k else f'SOME FAILED ({k}/{n})')
