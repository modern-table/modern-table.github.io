import os, socket, subprocess, sys, time
from playwright.sync_api import sync_playwright
# MT_ROOT: the folder whose index.html is served (default: this repo). tests/run_all.py --rev REV points it at an older build.
ROOT = os.environ.get('MT_ROOT') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def _free_port():
    s = socket.socket(); s.bind(('127.0.0.1', 0)); p = s.getsockname()[1]; s.close(); return p
PORT = _free_port()
import json
srv=subprocess.Popen([sys.executable,'-m','http.server',str(PORT),'--bind','127.0.0.1'],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
time.sleep(0.8); res=[]
def check(n,c,e=''): res.append(bool(c)); print('PASS' if c else 'FAIL', n, e)
def start(p):
    p.click('#soloBtn'); p.wait_for_timeout(600); p.locator('.drow').first.click(); p.wait_for_timeout(400)
    p.get_by_role('button', name='Play this deck').click(); p.wait_for_timeout(1500)
    for nm in ['Random deck','Keep']:
        bt=p.get_by_role('button', name=nm)
        if bt.count():
            try: bt.first.click(timeout=800)
            except Exception: pass
    p.wait_for_function('typeof G!=="undefined" && G.me && Array.isArray(G.me.bf)', timeout=10000)
try:
  with sync_playwright() as pw:
    b=pw.chromium.launch(); ctx=b.new_context(viewport={'width':1500,'height':900})
    for h in ['**/cards.scryfall.io/**','**/svgs.scryfall.io/**','**/backs.scryfall.io/**','**/fonts.googleapis.com/**','**/fonts.gstatic.com/**']: ctx.route(h, lambda r: r.abort())
    ctx.route('**/api.scryfall.com/**', lambda r: r.fulfill(status=200, content_type='application/json', body='{"data":[]}'))
    p=ctx.new_page(); errs=[]; p.on('pageerror', lambda e: errs.append(str(e)))
    p.goto(f'http://127.0.0.1:{PORT}/'); p.wait_for_timeout(600)
    start(p)
    # mid-game state: turn 3, a surged Bushwhacker on the battlefield, a Naked Time-style entry tagged to this game
    p.evaluate("""() => { G.turn.n=3; G.me.bf=[]; G.me.hand=[]; const c=mk(keyOf('Reckless Bushwhacker')); c.surge=3; G.me.bf.push(c); G.me.wce=[{n:3,g:G.gid,src:'x',txt:'test'}]; save(); }""")
    bidv=p.evaluate("() => G.me.bf[0].id")
    gid1=p.evaluate("() => G.gid")
    p.reload(); p.wait_for_timeout(800)
    check('resume button shows after reload', p.locator('#resumeBtn').count()>0)
    p.click('#resumeBtn'); p.wait_for_timeout(1200)
    st=p.evaluate("(id)=>{const f=G.me.bf.find(x=>x.id===id); return {surge: f?f.surge:null, gid:G.gid, wce:(G.me.wce||[]).length}}", bidv)
    check('same game: surge kept after resume', st['surge']==3, str(st))
    check('same game: gid kept after resume', bool(gid1) and st['gid']==gid1, f"{st['gid']} vs {gid1}")
    check('same game: this game\'s entry kept', st['wce']==1, str(st))
    # new game in the resumed match: surge and game-tagged entries must not carry over
    p.evaluate("() => newGame(true)"); p.wait_for_timeout(300)
    leak=p.evaluate("() => { const c=G.me.lib.find(x=>x.k && /Bushwhacker/i.test(JSON.stringify(x))); return {surge:c?c.surge:null, wce:(G.me.wce||[]).length, gid:G.gid}}")
    check('new game after resume: no surge on library copies', leak['surge'] in (None,0), str(leak))
    check('new game after resume: no entries from last game', leak['wce']==0, str(leak))
    check('new game after resume: new game id', leak['gid']!=gid1)
    # legacy save with no game id: inject before the app loads (the app rewrites the session on load)
    ctx2=b.new_context(viewport={'width':1500,'height':900})
    for h in ['**/cards.scryfall.io/**','**/svgs.scryfall.io/**','**/backs.scryfall.io/**','**/fonts.googleapis.com/**','**/fonts.gstatic.com/**']: ctx2.route(h, lambda r: r.abort())
    ctx2.route('**/api.scryfall.com/**', lambda r: r.fulfill(status=200, content_type='application/json', body='{"data":[]}'))
    legacy=p.evaluate("() => { const s=JSON.parse(localStorage.getItem('mt_session')); delete s.gid; s.me.wce=[{n:3,src:'old',txt:'legacy'}]; if(s.dum) s.dum.wce=[{n:3,src:'old',txt:'legacy'}]; return JSON.stringify(s); }")
    ctx2.add_init_script("if(!sessionStorage.getItem('seeded')){ localStorage.setItem('mt_session', " + json.dumps(legacy) + "); sessionStorage.setItem('seeded','1'); }")
    p2=ctx2.new_page(); p2.goto(f'http://127.0.0.1:{PORT}/'); p2.wait_for_timeout(800)
    p2.click('#resumeBtn'); p2.wait_for_timeout(1200)
    lw=p2.evaluate("() => (G.me.wce||[]).length"); dw=p2.evaluate("() => G.opp && G.opp.dummy ? (G.opp.wce||[]).length : -1")
    check('legacy session (no game id): stale entry dropped', lw==0, f'wce={lw}')
    check('legacy session: practice opponent stale entry dropped', dw==0, f'dummy wce={dw}')
    p2.close(); ctx2.close()
    check('no page errors', not errs, str(errs)[:200])
    b.close()
finally: srv.terminate()
print('ALL PASS' if all(res) else 'SOME FAILED', f'({sum(res)}/{len(res)})')
