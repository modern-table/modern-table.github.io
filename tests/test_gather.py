import os, socket, subprocess, sys, time
from playwright.sync_api import sync_playwright
# MT_ROOT: the folder whose index.html is served (default: this repo). tests/run_all.py --rev REV points it at an older build.
ROOT = os.environ.get('MT_ROOT') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def _free_port():
    s = socket.socket(); s.bind(('127.0.0.1', 0)); p = s.getsockname()[1]; s.close(); return p
PORT = _free_port()
srv=subprocess.Popen([sys.executable,'-m','http.server',str(PORT),'--bind','127.0.0.1'],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
time.sleep(0.8); res=[]
def check(n,c,e=''): res.append(c); print('PASS' if c else 'FAIL', n, e)
def drain(p):
    for _ in range(4):
        p.evaluate("() => { if(G.me.st.length) resolve(G.me.st[G.me.st.length-1].id); }"); p.wait_for_timeout(350)
try:
  with sync_playwright() as pw:
    b=pw.chromium.launch(); ctx=b.new_context(viewport={'width':1500,'height':900})
    for h in ['**/cards.scryfall.io/**','**/svgs.scryfall.io/**','**/backs.scryfall.io/**','**/fonts.googleapis.com/**','**/fonts.gstatic.com/**']: ctx.route(h, lambda r: r.abort())
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
    # game 1: surge a Bushwhacker on turn 3, let its trigger resolve
    p.evaluate("""() => { G.me.kept=G.me.dealt=true; G.me.bf=[]; G.me.st=[]; G.me.hand=[]; G.me.cast={n:1,is:0,nc:0}; G.turn.n=3; G.turn.phase=2; G.turn.active=G.myId;
      window.bush=mk(keyOf('Reckless Bushwhacker')); G.me.hand.push(window.bush); G.me.mana=noMana(); addMana('RRRRR'); }""")
    p.evaluate("() => { const w=castWays(window.bush, window.bush.id).find(x=>x.k==='surge'); w && w.run(); }"); p.wait_for_timeout(500)
    p.evaluate("() => { const b=document.querySelector('#payPanel [data-pay=\"pay\"]'); if(b) b.click(); }"); p.wait_for_timeout(500)
    drain(p)
    check('game 1: the surged copy carries surge', p.evaluate("() => !!window.bush.surge"))
    # new game in the same match: cards return to the library
    p.evaluate("() => { gather(); }"); p.wait_for_timeout(300)
    where=p.evaluate("() => G.me.lib.includes(window.bush) ? 'lib' : 'elsewhere'")
    leaked=p.evaluate("() => window.bush.surge || null")
    check('card back in library', where=='lib', where)
    check('new game: no surge flag left on the card', leaked is None, f'surge={leaked}')
    # a copy hard-cast in the new game must not trigger
    p.evaluate("""() => { G.gid=gameId(); G.turn={active:G.myId,phase:2,n:3}; G.me.bf=[]; G.me.st=[]; G.me.lib=G.me.lib.filter(x=>x!==window.bush); G.me.hand=[window.bush]; G.me.cast={n:0,is:0,nc:0}; G.me.mana=noMana(); addMana('RRG'); }""")
    n0=p.evaluate("() => G.log.length")
    p.evaluate("() => castSpell(window.bush.id)"); p.wait_for_timeout(400)
    p.evaluate("() => { const b=document.querySelector('#payPanel [data-pay=\"pay\"]'); if(b) b.click(); }"); p.wait_for_timeout(400)
    drain(p)
    logs=p.evaluate("(n0) => G.log.slice(n0).map(x=>x.text).join(' | ')", n0)
    check('new game hard cast: no enter trigger', 'trigger goes on the stack' not in logs, logs[-200:])
    check('no page errors', not errs, str(errs)[:200])
    b.close()
finally: srv.terminate()
print('ALL PASS' if all(res) else 'SOME FAILED', f'({sum(res)}/{len(res)})')
