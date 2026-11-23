# A Reckless Bushwhacker surged in game 1 is drawn in game 2 and hard-cast: no surge trigger (fails on v5.20).
import os, socket, subprocess, sys, time
from playwright.sync_api import sync_playwright
# MT_ROOT: the folder whose index.html is served (default: this repo). tests/run_all.py --rev REV points it at an older build.
ROOT = os.environ.get('MT_ROOT') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def _free_port():
    s = socket.socket(); s.bind(('127.0.0.1', 0)); p = s.getsockname()[1]; s.close(); return p
PORT = _free_port()
srv=subprocess.Popen([sys.executable,'-m','http.server',str(PORT),'--bind','127.0.0.1'],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
time.sleep(0.8); res=[]
def check(n,c,e=''): res.append(bool(c)); print('PASS' if c else 'FAIL', n, e)
def pay(p): p.evaluate("() => { const b=document.querySelector('#payPanel [data-pay=\"pay\"]'); if(b) b.click(); }"); p.wait_for_timeout(400)
def drain(p):
    for _ in range(4): p.evaluate("() => { if(G.me.st.length) resolve(G.me.st[G.me.st.length-1].id); }"); p.wait_for_timeout(300)
try:
  with sync_playwright() as pw:
    b=pw.chromium.launch(); ctx=b.new_context(viewport={'width':1500,'height':900})
    for h in ['**/cards.scryfall.io/**','**/svgs.scryfall.io/**','**/backs.scryfall.io/**','**/fonts.googleapis.com/**','**/fonts.gstatic.com/**','**/gc.zgo.at/**']: ctx.route(h, lambda r: r.abort())
    ctx.route('**/api.scryfall.com/**', lambda r: r.fulfill(status=200, content_type='application/json', body='{"data":[]}'))
    p=ctx.new_page(); errs=[]; p.on('pageerror', lambda e: errs.append(str(e)))
    p.goto(f'http://127.0.0.1:{PORT}/'); p.wait_for_timeout(600)
    p.click('#soloBtn'); p.wait_for_timeout(600); p.locator('.drow').first.click(); p.wait_for_timeout(400)
    p.get_by_role('button', name='Play this deck').click(); p.wait_for_timeout(1500)
    for nm in ['Random deck','Keep']:
        bt=p.get_by_role('button', name=nm)
        if bt.count():
            try: bt.first.click(timeout=800)
            except Exception: pass
    p.wait_for_function('typeof G!=="undefined" && G.me && Array.isArray(G.me.bf)', timeout=10000)
    print('version', p.evaluate("() => VERSION"))
    # game 1, turn 3: cast a cheap spell, then surge Bushwhacker A
    p.evaluate("""() => { G.me.kept=G.me.dealt=true; G.me.bf=[]; G.me.st=[]; G.me.hand=[]; G.turn={active:G.myId,phase:2,n:3}; G.me.cast={n:1,is:0,nc:0};
      window.A=mk(keyOf('Reckless Bushwhacker')); G.me.hand.push(window.A); G.me.lib.push(window.A.__dummy||mk(keyOf('Mountain'))); G.me.mana=noMana(); addMana('RR'); }""")
    p.evaluate("() => { const w=castWays(window.A, window.A.id).find(x=>x.k==='surge'); w.run(); }"); p.wait_for_timeout(400); pay(p); drain(p)
    check('game 1: A was surged', p.evaluate("() => !!window.A.surge"))
    # game 2 in the same match
    p.evaluate("() => newGame(true)"); p.wait_for_timeout(400)
    p.evaluate("""() => { G.me.kept=G.me.dealt=true; const i=G.me.lib.indexOf(window.A); G.me.lib.splice(i,1); G.me.lib.unshift(window.A); G.turn={active:G.myId,phase:2,n:4}; G.me.bf=[]; G.me.st=[]; G.me.hand=[]; G.me.cast={n:0,is:0,nc:0}; draw(1, true); }""")
    check('game 2: A drawn into hand', p.evaluate("() => G.me.hand.includes(window.A)"))
    # another creature on the battlefield to receive the bonus, then hard cast A for {2}{R} paid RRG
    p.evaluate("""() => { const n=mk(keyOf('Reckless Bushwhacker')); G.me.bf.push(n); window.N=n; G.me.mana=noMana(); addMana('RRG'); }""")
    n0=p.evaluate("() => G.log.length")
    p.evaluate("() => castSpell(window.A.id)"); p.wait_for_timeout(400); pay(p); drain(p)
    logs=p.evaluate("(n0) => G.log.slice(n0).map(x=>x.text).join(' | ')", n0)
    check('game 2 hard cast: no surge trigger', 'trigger goes on the stack' not in logs, logs[-260:])
    check('game 2: the other creature did not gain haste', not p.evaluate("() => !!(window.N.tkw && window.N.tkw.k.includes('haste'))"))
    check('no page errors', not errs, str(errs)[:200])
    b.close()
finally: srv.terminate()
print('ALL PASS' if all(res) else 'SOME FAILED', f'({sum(res)}/{len(res)})')
