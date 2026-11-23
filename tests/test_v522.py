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
    setup="""() => { G.me.kept=G.me.dealt=true; G.me.bf=[]; G.me.st=[]; G.me.hand=[]; G.turn={active:G.myId,phase:2,n:3}; }"""
    # real surge still triggers and pumps another creature
    p.evaluate(setup); p.evaluate("""() => { G.me.cast={n:1,is:0,nc:0}; window.N=mk(keyOf('Reckless Bushwhacker')); G.me.bf.push(window.N); window.A=mk(keyOf('Reckless Bushwhacker')); G.me.hand.push(window.A); G.me.mana=noMana(); addMana('RR'); }""")
    n0=p.evaluate("() => G.log.length")
    p.evaluate("() => castWays(window.A, window.A.id).find(x=>x.k==='surge').run()"); p.wait_for_timeout(400); pay(p); drain(p)
    lg=p.evaluate("(n0) => G.log.slice(n0).map(x=>x.text).join(' | ')", n0)
    check('real surge cast: trigger goes on the stack', 'trigger goes on the stack' in lg, lg[-200:])
    check('real surge cast: the other creature is pumped', 'haste' in lg and 'no other creature' not in lg, lg[-160:])
    # a library card carrying a stale surge mark (old saved session), drawn and hard-cast: no trigger
    p.evaluate(setup); p.evaluate("""() => { G.me.cast={n:0,is:0,nc:0}; const c=mk(keyOf('Reckless Bushwhacker')); c.surge=2; c.bcry={n:3,k:2}; G.me.lib.unshift(c); window.B=c; draw(1,true); G.me.mana=noMana(); addMana('RRG'); }""")
    n0=p.evaluate("() => G.log.length")
    p.evaluate("() => castSpell(window.B.id)"); p.wait_for_timeout(400); pay(p); drain(p)
    lg=p.evaluate("(n0) => G.log.slice(n0).map(x=>x.text).join(' | ')", n0)
    check('stale mark drawn and hard-cast: no trigger', 'trigger goes on the stack' not in lg, lg[-200:])
    # new game: library cards keep only identity fields
    p.evaluate("() => newGame(true)"); p.wait_for_timeout(300)
    extra=p.evaluate("() => { const ok=new Set(['id','k','cu','o','comp','tap','fd','flip','c','att','atk']); return [...new Set(G.me.lib.flatMap(c=>Object.keys(c).filter(k=>!ok.has(k))))]; }")
    check('new game: library cards carry no leftover fields', not extra, str(extra))
    # new match clears per-game state and gets a new game id
    p.evaluate("() => { G.me.gwT=1; G.me.hasteNext=1; G.me.wce=[{n:1,g:G.gid,src:'x',txt:'y'}]; window.g0=G.gid; }")
    p.evaluate("() => { try{ newMatch(true); }catch(e){ window.nmErr=String(e); } closeModal && closeModal(); }"); p.wait_for_timeout(400)
    st=p.evaluate("() => ({gwT:G.me.gwT, hn:G.me.hasteNext, wce:(G.me.wce||[]).length, same:G.gid===window.g0, err:window.nmErr||null})")
    check('new match: per-game state cleared, new game id', st['gwT'] is None and st['hn'] is None and st['wce']==0 and not st['same'] and not st['err'], str(st))
    check('no page errors', not errs, str(errs)[:200])
    b.close()
finally: srv.terminate()
print('ALL PASS' if all(res) else 'SOME FAILED', f'({sum(res)}/{len(res)})')
