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
    for nm in ['No deck','Keep']:
      bt=p.get_by_role('button', name=nm)
      if bt.count():
        try: bt.first.click(timeout=800)
        except Exception: pass
    p.wait_for_function('typeof G!=="undefined" && G.me && Array.isArray(G.me.bf)', timeout=10000)
    p.evaluate("""() => { G.me.kept=G.me.dealt=true; }""")
    # a friend's revealed hand: card ids that exist in none of my zones
    p.evaluate("""() => { const k=keyOf('Thoughtseize'); window.RVC=[{id:'zz1', k, cu:null},{id:'zz2', k:keyOf('Lightning Bolt'), cu:null}];
      openReveal(RVC, 'friend', 'Friend', {src:'Thoughtseize', desc:'nonland ', wc:''}); }""")
    p.wait_for_timeout(300)
    p.hover('#rvGrid .card[data-id="zz1"]'); p.wait_for_timeout(250)
    z=p.evaluate("() => { const z=document.querySelector('#zoom'); return {vis:!z.hidden, txt:z.innerText, w:z.getBoundingClientRect().width}; }")
    check('Thoughtseize window: hovering a revealed card enlarges it', z['vis'] and 'Thoughtseize' in z['txt'], repr(z)[:160])
    check('default size is the old 300 px', abs(z['w']-300)<2, z['w'])
    p.mouse.move(5,5); p.wait_for_timeout(150)
    p.hover('#rvGrid .card[data-id="zz2"]'); p.wait_for_timeout(250)
    t=p.evaluate("() => document.querySelector('#zoom').innerText")
    check('second card enlarges too', 'Lightning Bolt' in t, t[:60])
    p.evaluate("() => closeModal()")
    # the handview window (a friend Thoughtseizes themselves)
    p.evaluate("""() => onMsg({t:'handview', who:'Friend', src:'Thoughtseize', cards:[{id:'zz3', k:keyOf('Lightning Bolt'), cu:null}]})""")
    p.wait_for_timeout(500)
    p.hover('#modal .card[data-id="zz3"]'); p.wait_for_timeout(250)
    t=p.evaluate("() => { const z=document.querySelector('#zoom'); return z.hidden ? '' : z.innerText; }")
    check('handview window enlarges too', 'Lightning Bolt' in t, t[:60])
    p.evaluate("() => { G.hvOpen=false; closeModal(); }")
    # the setting
    p.evaluate("() => settingsModal()"); p.wait_for_timeout(200)
    row=p.locator('[data-set="zoom"]').count()
    check('Settings has Card enlargement with four sizes', row==4, row)
    p.click('[data-set="zoom"][data-v="l"]'); p.wait_for_timeout(150)
    saved=p.evaluate("() => JSON.parse(localStorage.getItem('mt_settings')||'{}').zoom")
    check('choice is saved', saved=='l', saved)
    p.evaluate("() => closeModal()")
    p.set_viewport_size({'width':1500,'height':1200})
    sizes={}
    for v,want in [('s',240),('l',380),('xl',460)]:
      p.evaluate(f"() => {{ S.zoom='{v}'; openReveal(RVC, 'friend', 'Friend', {{src:'Thoughtseize', desc:'nonland ', wc:''}}); }}"); p.wait_for_timeout(250)
      p.mouse.move(5,5); p.wait_for_timeout(100); p.hover('#rvGrid .card[data-id="zz1"]'); p.wait_for_timeout(250)
      sizes[v]=p.evaluate("() => { const r=document.querySelector('#zoom').getBoundingClientRect(); return [r.width, r.bottom, innerHeight]; }")
      check(f'size {v} is {want} px wide and fits the window', abs(sizes[v][0]-want)<2 and sizes[v][1]<=sizes[v][2], sizes[v])
      p.evaluate("() => closeModal()")
    # real-sized pictures for the fit check (Scryfall's are 488 x 680)
    svg='<svg xmlns="http://www.w3.org/2000/svg" width="488" height="680"><rect width="488" height="680" fill="#345"/></svg>'
    ctx.route('**/cards.scryfall.io/**', lambda r: r.fulfill(status=200, content_type='image/svg+xml', body=svg))
    p.set_viewport_size({'width':1500,'height':700})
    p.evaluate("() => { S.zoom='xl'; openReveal(RVC, 'friend', 'Friend', {src:'Thoughtseize', desc:'nonland ', wc:''}); }"); p.wait_for_timeout(250)
    p.mouse.move(5,5); p.wait_for_timeout(100); p.hover('#rvGrid .card[data-id="zz1"]'); p.wait_for_timeout(900)
    r=p.evaluate("() => { const r=document.querySelector('#zoom').getBoundingClientRect(); return [r.width, r.top, r.bottom, innerHeight]; }")
    check('extra large shrinks to fit a short window', r[0]<460 and r[1]>=0 and r[2]<=r[3], r)
    check('no page errors', not errs, str(errs)[:200])
    b.close()
finally: srv.terminate()
print('ALL PASS' if res and all(res) else 'SOME FAILED', f'({sum(res)}/{len(res)})')
