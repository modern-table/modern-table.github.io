"""v5.26: an additional combat phase (Fear of Missing Out with delirium) gets its own Combat chip on the phase bar;
a creature whose only change is counters (Moonshadow's six -1/-1) shows its current power/toughness box."""
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
        for name in ['No deck', 'Keep']:
            bt = p.get_by_role('button', name=name)
            if bt.count():
                try: bt.first.click(timeout=800)
                except Exception: pass
        p.wait_for_function('typeof G!=="undefined" && G.me && Array.isArray(G.me.bf)', timeout=10000)
        p.evaluate("""() => { G.me.kept=G.me.dealt=true; G.me.hand=[]; G.me.bf=[]; G.me.st=[]; G.me.gy=[]; G.me.mana=noMana(); G.turn.n=3; G.turn.active=G.myId; G.turn.phase=2; delete G.turn.cx; G.opp.bf=[]; render(); }""")

        # --- Moonshadow: six -1/-1 counters -> 1/1 shown
        p.evaluate("""() => { window.__m = mk(keyOf('Moonshadow')); G.me.bf.push(window.__m); entered(window.__m); render(); }""")
        p.wait_for_timeout(300)
        ms = p.evaluate("""() => { const e=document.querySelector(`#myBf [data-id="${window.__m.id}"], [data-id="${window.__m.id}"]`); const d=e&&e.querySelector('.badge.dpt'); return {c:window.__m.c, pt:d?d.textContent:null, pen:!!(e&&e.querySelector('.pen.ctrn'))}; }""")
        check('Moonshadow enters with six -1/-1 counters', ms['c'] == -6, str(ms))
        check('Moonshadow shows its current P/T 1/1', ms['pt'] == '1/1', str(ms))
        check('Moonshadow still shows its -1/-1 pennant', ms['pen'], str(ms))
        p.evaluate("""() => { window.__m.c=-5; render(); }""")
        pt2 = p.evaluate("""() => { const d=document.querySelector(`[data-id="${window.__m.id}"] .badge.dpt`); return d&&d.textContent; }""")
        check('a counter removed: 2/2', pt2 == '2/2', str(pt2))
        # +1/+1 counters alone show it too; a plain creature still has no box
        p.evaluate("""() => { window.__r = mk(keyOf('Ragavan, Nimble Pilferer')); window.__r.c=2; G.me.bf.push(window.__r); window.__o = mk(keyOf('Ocelot Pride')); G.me.bf.push(window.__o); render(); }""")
        rv = p.evaluate("""() => { const q=id=>{ const d=document.querySelector(`[data-id="${id}"] .badge.dpt`); return d&&d.textContent; }; return {rag:q(window.__r.id), oce:q(window.__o.id)}; }""")
        check('Ragavan with two +1/+1 counters shows 4/3', rv['rag'] == '4/3', str(rv))
        check('Ocelot Pride with nothing on it has no P/T box', rv['oce'] is None, str(rv))
        if os.environ.get('MT_SHOT1'): p.locator(f'[data-id="{p.evaluate("() => window.__m.id")}"]').screenshot(path=os.environ['MT_SHOT1']+'.moon.png')
        p.evaluate("() => { G.me.bf=[]; render(); }")

        # --- Fear of Missing Out: the real trigger, attacking with delirium
        ch0 = p.evaluate(CHIPS)
        check('phase bar: one Combat chip normally', ch0.count('Combat') == 1, str(ch0))
        p.evaluate("""() => { const T=['Ragavan, Nimble Pilferer','Fear of Missing Out']; window.__f = mk(keyOf('Fear of Missing Out')); window.__f.hst=1; G.me.bf.push(window.__f);
            for(const cu of [{n:'Gy Land', t:'Land', o:''}, {n:'Gy Instant', t:'Instant', o:''}, {n:'Gy Sorcery', t:'Sorcery', o:''}, {n:'Gy Artifact', t:'Artifact', o:''}]) G.me.gy.push(mk(null,{cu}));
            G.turn.phase=3; render(); G.atkSel=new Set([window.__f.id]); atkCommit(); }""")
        p.wait_for_timeout(500)
        # the trigger asks for a target creature: Fear of Missing Out itself
        st = p.evaluate("() => G.me.st.map(c=>cdata(c).n)")
        check('attack puts the delirium trigger on the stack', any('Fear of Missing Out' in x for x in st), str(st))
        p.evaluate("""() => { const t=G.me.st[G.me.st.length-1]; if(t){ t.tg=[window.__f.id]; } }""")
        p.evaluate("() => resolve(G.me.st[G.me.st.length-1].id)"); p.wait_for_timeout(600)
        for _ in range(3):
            pk = p.locator(f'[data-id="{p.evaluate("() => window.__f.id")}"]').locator('visible=true')
            if p.evaluate("() => !!document.querySelector('#pickPanel:not([hidden])')"):
                p.evaluate("() => { const e=document.querySelector('#pickPanel:not([hidden]) [data-pick]'); e&&e.click(); }"); p.wait_for_timeout(300)
        xs = p.evaluate("() => ({x:G.me.xcomb, n:G.turn.n, by:G.me.xcby, pub:pub().xcomb})")
        check('trigger resolved: additional combat recorded for this turn', xs['x'] == xs['n'], str(xs))
        check('the other page is sent the pending combat (pub)', xs['pub'] == xs['n'], str(xs))
        ch1 = p.evaluate(CHIPS)
        check('first combat: two Combat chips, the first lit, the second dashed', ch1[3:5] == ['Combat*', 'Combat~'] and ch1[5] == 'Main 2', str(ch1))
        if os.environ.get('MT_SHOT1'): p.locator('#mid').screenshot(path=os.environ['MT_SHOT1'])
        p.set_viewport_size({'width': 1280, 'height': 800}); p.wait_for_timeout(300)
        ov = p.evaluate("() => { const m=document.querySelector('#mid'), r=document.querySelector('#phases').getBoundingClientRect(), t=document.querySelector('.tools').getBoundingClientRect(); return {sw:m.scrollWidth, cw:m.clientWidth, gap:t.left-r.right}; }")
        check('1280 px wide: the bar still fits with the extra chip', ov['sw'] <= ov['cw'] and ov['gap'] >= 0, str(ov))
        p.set_viewport_size({'width': 1500, 'height': 900}); p.wait_for_timeout(200)
        tip = p.evaluate("() => document.querySelectorAll('#phases button')[4].title")
        check('the coming chip names the source', 'Fear of Missing Out' in tip, tip)
        # finish the first combat's damage, then go to the additional combat by clicking its chip
        p.evaluate("() => { G.me.bf.forEach(c=>c.atk=false); G.me.arrows=[]; const t={...G.turn}; delete t.cs; G.turn=t; render(); }")
        p.locator('#phases button').nth(4).click(); p.wait_for_timeout(400)
        ch2 = p.evaluate(CHIPS); cx = p.evaluate("() => [G.turn.phase, G.turn.cx, G.me.xcomb]")
        check('clicking the dashed chip begins the additional combat', cx[0] == 3 and cx[1] == 2 and cx[2] is None, str(cx))
        check('additional combat: second Combat chip lit, first not', ch2[3:5] == ['Combat', 'Combat*'], str(ch2))
        log = p.evaluate("() => G.log.slice(-6).map(l=>l.text).join(' | ')")
        check('log says an additional combat begins', 'begins an additional combat phase' in log, log[-300:])
        # Main 2: both combats still shown, Main 2 lit
        p.evaluate("() => { G.me.bf.forEach(c=>c.atk=false); nextPhase(); }"); p.wait_for_timeout(300)
        ch3 = p.evaluate(CHIPS)
        check('Main 2: two Combat chips kept, Main 2 lit', ch3.count('Combat') == 2 and 'Main 2*' in ch3, str(ch3))
        # next turn: back to one
        p.evaluate("() => { setTurn({active:G.myId, phase:0, n:G.turn.n+1}); render(); }"); p.wait_for_timeout(200)
        ch4 = p.evaluate(CHIPS)
        check('next turn: one Combat chip', ch4.count('Combat') == 1, str(ch4))
        # opponent's turn: their pending additional combat shows on my bar too
        p.evaluate("() => { setTurn({active:oppId(), phase:3, n:G.turn.n+1}); G.opp.xcomb=G.turn.n; G.opp.xcby='Fear of Missing Out'; render(); }")
        ch5 = p.evaluate(CHIPS)
        check("opponent's pending additional combat shows a dashed chip", ch5[3:5] == ['Combat*', 'Combat~'], str(ch5))
        p.evaluate("() => { setTurn({...G.turn, cx:2}); G.opp.xcomb=0; render(); }")
        ch6 = p.evaluate(CHIPS)
        check("opponent's additional combat under way: second chip lit", ch6[3:5] == ['Combat', 'Combat*'], str(ch6))
        if os.environ.get('MT_SHOT'): p.locator('#phases').screenshot(path=os.environ['MT_SHOT'])
        check('no page errors', not errs, str(errs[:3]))
        b.close()
finally:
    srv.terminate()
fails = [n for n, ok in results if not ok]
print('ALL PASS' if not fails else 'SOME FAILED', f'({len(results)-len(fails)}/{len(results)})')
sys.exit(1 if fails else 0)
