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
    p.evaluate("""() => { G.me.kept=G.me.dealt=true; G.me.bf=[]; G.me.st=[]; G.turn.n=4; G.turn.active=G.myId; G.turn.phase=2;
      window.bear=mk(null,{cu:{n:'Test Bear', t:'Creature — Bear', o:'', pt:'2/2'}}); G.me.bf.push(window.bear);
      window.bear.tkw={n:4,k:['battle cry']}; window.bear.bcry={n:4,k:2}; }""")
    p.evaluate("() => { changed(); }"); p.wait_for_timeout(400)
    key=p.evaluate("() => { const k=document.querySelector('#kwKey'); return k ? k.innerText.replace(/\\s+/g,' ') : null; }")
    hid=p.evaluate("() => { const k=document.querySelector('#kwKey'); return k ? k.hidden : 'missing'; }")
    check('keyword key lists battle cry', key and 'Battle cry' in key and hid is False, repr(key))
    check('no page errors', not errs, str(errs)[:200])
    b.close()
finally: srv.terminate()
print('ALL PASS' if res and all(res) else 'SOME FAILED', f'({sum(res)}/{len(res)})')
