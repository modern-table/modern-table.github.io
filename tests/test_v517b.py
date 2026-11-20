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
        p.evaluate("() => { G.me.mana=noMana(); addMana('RRRRR'); }")
        p.evaluate("() => castSpell(window.__r.id)"); p.wait_for_timeout(500)
        pay = p.evaluate("() => { const e=document.querySelector('#payPanel'); return e && !e.hidden ? (e.innerText||'') : ''; }")
        st = p.evaluate("() => G.me.st.map(x=>cdata(x).n).join(',')")
        check('main phase click: casts the creature, no bloodrush', ('Bloodrush' not in pay) and ('Rampager' in st or 'Cast' in pay), f'pay={pay[:120]!r} st={st}')
        p.evaluate("() => { const b=document.querySelector('#payPanel [data-pay=\"cancel\"]'); if(b) b.click(); G.me.st=[]; if(!G.me.hand.includes(window.__r)){ G.me.bf=G.me.bf.filter(x=>x!==window.__r); G.me.hand.push(window.__r); } }")
        p.evaluate("""() => { G.turn.phase=3; const bear=mk(null,{cu:{n:'Test Bear', t:'Creature — Bear', o:'', pt:'2/2'}}); bear.atk=true; G.me.bf.push(bear); window.__bear=bear; }""")
        p.evaluate("() => castSpell(window.__r.id)"); p.wait_for_timeout(500)
        pay = p.evaluate("() => { const e=document.querySelector('#payPanel'); return e && !e.hidden ? (e.innerText||'') : ''; }")
        body_ = p.inner_text('body')
        check('combat click: bloodrush window, no creature-cast or timing prompt', 'Bloodrush' in pay and 'Sorcery timing' not in body_, f'pay={pay[:120]!r}')
        p.evaluate("() => { window.__bear.tkw={n:G.turn.n, k:['battle cry']}; window.__bear.bcry={n:G.turn.n, k:1}; render(); }"); p.wait_for_timeout(300)
        fill = p.evaluate("() => { const s=[...document.querySelectorAll('.kc svg')].find(v=>v.innerHTML.includes('M3 9h3')); return s ? getComputedStyle(s).fill : null; }")
        check('battle cry chip renders white', fill in ('rgb(255, 255, 255)','#fff','#ffffff'), str(fill))
        check('no page errors', not errs, str(errs)[:300])
        b.close()
finally:
    srv.terminate()
print('ALL PASS' if all(ok for _, ok in results) else 'SOME FAILED', f'({sum(ok for _,ok in results)}/{len(results)})')
