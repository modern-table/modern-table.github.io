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
        p.evaluate("""() => { S.autoPay=true; G.me.kept=G.me.dealt=true; G.me.hand=[]; G.me.bf=[]; G.me.st=[]; G.me.mana=noMana(); G.me.life=20; G.turn.n=1; G.turn.active=G.myId; G.turn.phase=2; window.__w = mk(keyOf('Street Wraith')); G.me.hand.push(window.__w); window.__t = mk('troll of khazad-dum'); G.me.hand.push(window.__t); }""")
        ways = p.evaluate("() => castWays(window.__w, window.__w.id).map(w=>w.k)")
        check('Street Wraith: cycling is a way in the payment window', 'cycling' in ways, str(ways))
        # A: left click in main phase -> payment window with the cycling row
        p.evaluate("() => castSpell(window.__w.id)"); p.wait_for_timeout(400)
        pay = p.evaluate("() => { const e=document.querySelector('#payPanel'); return e && !e.hidden ? e.innerText : ''; }")
        check('left click opens the payment window', 'Cast Street Wraith' in pay, pay[:200])
        check('window offers Pay 2 life and cycle it', 'Pay 2 life and cycle it' in pay, pay[:300])
        if os.environ.get('MT_SHOT'): p.locator('#payPanel').screenshot(path=os.environ['MT_SHOT'])
        p.evaluate("() => { const b=[...document.querySelectorAll('#payPanel [data-pay^=\"alt:\"]')].find(x=>/cycle it/.test(x.textContent)); b.click(); }"); p.wait_for_timeout(300)
        st = p.evaluate("() => ({life:G.me.life, zone:(find(window.__w.id)||{}).z, top:(G.me.st[G.me.st.length-1]||{cu:{}}).cu.n, pact:!document.querySelector('#pactPanel').hidden, pay:!document.querySelector('#payPanel').hidden})")
        check('cycling from the window: card in graveyard, 2 life paid, ability on stack, no second panel', st['zone']=='gy' and st['life']==18 and st['top']=='Street Wraith: cycling' and not st['pact'] and not st['pay'], str(st))
        # B: Troll (Swampcycling {1}) with no mana: row shown but disabled; with {B} in pool it cycles
        p.evaluate("() => { G.me.st=[]; castSpell(window.__t.id); }"); p.wait_for_timeout(300)
        row = p.evaluate("() => { const b=[...document.querySelectorAll('#payPanel [data-pay^=\"alt:\"]')].find(x=>/swampcycle it/.test(x.textContent)); return b ? {t:b.textContent, dis:b.disabled, note:b.parentElement.innerText} : null; }")
        check('Troll: Pay {1} and swampcycle it, disabled without mana', row and 'Pay {1} and swampcycle it' in row['t'] and row['dis'], str(row))
        check('Troll: note says search for a Swamp card', row and 'Swamp card' in row['note'], str(row))
        p.evaluate("() => { G.me.mana.B=1; paintPay(); }"); p.wait_for_timeout(200)
        p.evaluate("() => { const b=[...document.querySelectorAll('#payPanel [data-pay^=\"alt:\"]')].find(x=>/swampcycle it/.test(x.textContent)); b.click(); }"); p.wait_for_timeout(300)
        st2 = p.evaluate("() => ({zone:(find(window.__t.id)||{}).z, pool:G.me.mana.B, top:(G.me.st[G.me.st.length-1]||{cu:{}}).cu.n})")
        check('Troll cycles from the window, paying {1}', st2['zone']=='gy' and st2['pool']==0 and st2['top'].endswith(': swampcycling'), str(st2))
        # C: out of timing (opponent's turn) -> the warning offers to cycle
        p.evaluate("() => { G.me.st=[]; G.me.life=20; window.__w2 = mk(keyOf('Street Wraith')); G.me.hand.push(window.__w2); G.turn.active=oppId(); G.turn.phase=2; castSpell(window.__w2.id); }"); p.wait_for_timeout(400)
        body = p.inner_text('body')
        check('opponent turn: Sorcery timing warning shown', 'Sorcery timing' in body)
        btn = p.get_by_role('button', name='Pay 2 life and cycle it')
        check('warning offers Pay 2 life and cycle it', btn.count()==1)
        if btn.count(): btn.first.click(); p.wait_for_timeout(300)
        st3 = p.evaluate("() => ({life:G.me.life, zone:(find(window.__w2.id)||{}).z, top:(G.me.st[G.me.st.length-1]||{cu:{}}).cu.n})")
        check('cycled from the warning', st3['zone']=='gy' and st3['life']==18 and st3['top']=='Street Wraith: cycling', str(st3))
        # E: Rampager still gets no cycling row; cards without cycling unchanged
        w2 = p.evaluate("() => castWays(mk(keyOf('Ghor-Clan Rampager')), 'x').map(w=>w.k)")
        check('non-cycler: no cycling row', 'cycling' not in w2, str(w2))
        # F: dimming (Ben): a cycler is never dimmed; a plain creature still is on the opponent's turn
        dim = p.evaluate("""() => { G.me.st=[]; G.turn.active=oppId(); G.turn.phase=2; const w=mk(keyOf('Street Wraith')), b=mk(null,{cu:{n:'Test Bear', t:'Creature — Bear', o:'', mc:'{1}{G}', pt:'2/2'}}), t=mk(keyOf('ketria triome')); return {w:handTimeWhy(w), b:!!handTimeWhy(b), t:handTimeWhy(t)}; }""")
        check("opponent's turn: Street Wraith not dimmed", dim['w'] is None, str(dim))
        check("opponent's turn: Triome not dimmed", dim['t'] is None, str(dim))
        check("opponent's turn: a creature without cycling still dimmed", dim['b'], str(dim))
        # G: Triome left click (real click on the hand card)
        TRI = """() => { closePay(); closeModal(); G.me.st=[]; G.me.hand=[]; G.me.bf=[]; G.me.gy=[]; G.me.mana=noMana(); G.me.lp=null; G.turn.n=3; G.turn.active=G.myId; G.turn.phase=2; window.__tr=mk(keyOf('ketria triome')); G.me.hand.push(window.__tr); render(); }"""
        LANDS = """() => { for(let i=0;i<3;i++){ const l=mk(null,{cu:{n:'Test Forest', t:'Basic Land — Forest', o:''}}); G.me.bf.push(l); } render(); }"""
        def click_tri():
            p.locator(f'#myHand [data-id="{p.evaluate("() => window.__tr.id")}"]').first.click(); p.wait_for_timeout(350)
        def paytxt(): return p.evaluate("() => { const e=document.querySelector('#payPanel'); return e && !e.hidden ? e.innerText : ''; }")
        def zone(): return p.evaluate("() => (find(window.__tr.id)||{}).z")
        p.evaluate(TRI); click_tri()
        check('main, no mana sources: left click plays the Triome', zone()=='bf' and paytxt()=='', f"{zone()} {paytxt()[:80]}")
        p.evaluate(TRI); p.evaluate(LANDS); click_tri(); t=paytxt()
        check('main, 3 lands: window offers cycle and play as land', 'Pay {3} and cycle it' in t and 'Play it as a land' in t, t[:300])
        if os.environ.get('MT_SHOT2'): p.locator('#payPanel').screenshot(path=os.environ['MT_SHOT2'])
        p.evaluate("() => [...document.querySelectorAll('#payPanel [data-pay^=\"alt:\"]')].find(x=>/Play it as a land/.test(x.textContent)).click()"); p.wait_for_timeout(300)
        lp = p.evaluate("() => landsPlayed(G.me)")
        check('Play it as a land: on the battlefield, counts as the land play', zone()=='bf' and lp==1 and paytxt()=='', f"{zone()} lp={lp}")
        p.evaluate(TRI); p.evaluate(LANDS); p.evaluate("() => { G.me.mana.G=3; render(); }"); click_tri()
        p.evaluate("() => document.querySelector('#payPanel [data-pay=\"pay\"]').click()"); p.wait_for_timeout(300)
        st4 = p.evaluate("() => ({z:(find(window.__tr.id)||{}).z, pool:G.me.mana.G, top:(G.me.st[G.me.st.length-1]||{cu:{}}).cu.n, lp:landsPlayed(G.me)})")
        check('Pay {3} and cycle it: Triome cycled, {3} paid, no land play used', st4['z']=='gy' and st4['pool']==0 and st4['top']=='Ketria Triome: cycling' and st4['lp']==0, str(st4))
        # land play already used -> cycling window only
        p.evaluate(TRI); p.evaluate(LANDS); p.evaluate("() => { G.me.lp={n:G.turn.n, k:1}; render(); }"); click_tri(); t=paytxt()
        check('land play used: cycling window without the land row', 'cycle it' in t and 'Play it as a land' not in t and zone()=='hand', t[:200])
        # opponent's turn, no mana at all -> cycling window waits (not the land timing warning)
        p.evaluate(TRI); p.evaluate("() => { G.turn.active=oppId(); render(); }"); click_tri(); t=paytxt()
        check("opponent's turn: cycling window, no land row, no timing warning", 'cycle it' in t and 'Play it as a land' not in t and 'Playing a land' not in p.inner_text('body'), t[:200])
        p.evaluate("() => document.querySelector('#payPanel [data-pay=\"cancel\"]').click()"); p.wait_for_timeout(200)
        check('Cancel keeps the Triome in hand', zone()=='hand' and paytxt()=='', zone())
        check('no page errors', not errs, str(errs)[:300])
        b.close()
finally:
    srv.terminate()
print('ALL PASS' if all(ok for _, ok in results) else 'SOME FAILED', f'({sum(ok for _,ok in results)}/{len(results)})')
