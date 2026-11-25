"""Phone layer m0.13 (the maintainer): the table code stays in view while waiting for a friend, and a log sits under the stack.
Checks: a host on a phone sees the code large in the opponent's box (it was hidden with the deck-name line), a tap copies it, it stays
through a redraw, and goes once "Skip the roll (practice alone)" is chosen; the desktop page is unchanged (no code box, no phone log);
in a practice game the log shows the latest lines with readable text, fills the column while the stack is empty, shares it half and half
while the stack holds something, follows new lines, and a tap opens the full log panel."""
import asyncio, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import priority_test as PT
ROOT = os.environ.get('MT_ROOT') or PT.ROOT
res = []
def check(n, c, e=''): res.append(bool(c)); print('PASS' if c else 'FAIL', n, '' if c else e, flush=True)

class Env(PT.Env):
    async def start(self):
        PT.ROOT = ROOT
        return await super().start()

async def ctx(env, phone=True):
    o = dict(viewport={'width': 844, 'height': 390}, has_touch=True, is_mobile=True, device_scale_factor=2) if phone else dict(viewport={'width': 1500, 'height': 900})
    c = await env.b.new_context(**o)
    try: await c.grant_permissions(['clipboard-read', 'clipboard-write'], origin='http://127.0.0.1:%d' % env.port)
    except Exception: pass
    async def route(r):
        u = r.request.url
        if u.startswith('http://127.0.0.1:') or u.startswith('data:') or u.startswith('blob:'): await r.continue_()
        elif 'api.scryfall.com' in u: await r.fulfill(status=200, content_type='application/json', body='{"data":[]}')
        else: await r.abort()
    await c.route('**/*', route); env.ctxs.append(c)
    p = await c.new_page(); env.watch(p, 'phone' if phone else 'desktop'); return p

CODE = """()=>{ const b=document.querySelector('#oppAv .mcode'); if(!b) return null; const r=b.getBoundingClientRect(), v=b.querySelector('b');
  return {t:v.textContent, fs:parseFloat(getComputedStyle(v).fontSize), r:[r.left, r.top, r.right, r.bottom], vis:r.width>0 && r.height>0}; }"""
GEO = """()=>{ const h=e=>e && getComputedStyle(e).display!=='none' ? Math.round(e.getBoundingClientRect().height) : 0, L=document.querySelector('#mLog'),
  b=L && L.querySelector('.mlb'), last=b && b.lastElementChild;
  return {log:h(L), stack:h(document.querySelector('#stackwrap')), stackList:h(document.querySelector('#stack')), fs:b ? parseFloat(getComputedStyle(b).fontSize) : 0,
    last:last ? last.textContent : '', lines:b ? b.children.length : 0, bottom:b ? Math.abs(b.scrollHeight - b.clientHeight - b.scrollTop) < 4 : false,
    head:(document.querySelector('#stackwrap h4')||{}).textContent, headAfter:getComputedStyle(document.querySelector('#stackwrap h4'), '::after').content}; }"""

async def main():
    env = await Env().start()
    try:
        # a host on a phone, nobody joined yet
        p = await ctx(env)
        await p.goto(env.url('/m/')); await p.wait_for_selector('#hostBtn'); await p.fill('#nameIn', 'Ben'); await p.click('#hostBtn')
        await PT.pick_deck(p, 0); await p.wait_for_timeout(1000)
        code = await p.evaluate('G.code'); cb = await p.evaluate(CODE)
        check('waiting for a friend: the table code shows in the opponent box', cb and cb['t'] == code and cb['vis'], cb)
        check('it is large (18 px or more) and inside the screen', cb and cb['fs'] >= 18 and cb['r'][2] <= 844 and cb['r'][3] <= 390, cb)
        await p.tap('#oppAv .mcode'); await p.wait_for_timeout(500)
        clip = await p.evaluate("navigator.clipboard.readText().catch(()=>null)")
        toast = await p.evaluate("document.querySelector('#toast').textContent")
        check('a tap copies the code (or at least shows it)', clip == code or code in toast, [clip, toast])
        await p.evaluate('render()'); await p.wait_for_timeout(200)
        check('the code stays after a redraw', (await p.evaluate(CODE) or {}).get('t') == code)
        await p.tap('#banner [data-first="skip"]'); await p.wait_for_timeout(800)
        check('after Skip the roll (practice alone) the box is Practice\'s, no code', await p.evaluate(CODE) is None and 'Practice' in await p.evaluate("document.querySelector('#oppAv').textContent"))
        await env.close_all()

        # the desktop page is unchanged
        d = await ctx(env, phone=False)
        await d.goto(env.url('/')); await d.wait_for_selector('#hostBtn'); await d.fill('#nameIn', 'Ann'); await d.click('#hostBtn')
        await PT.pick_deck(d, 0); await d.wait_for_timeout(800)
        check('desktop: the waiting box is the old one (code in its line), no phone code box, no phone log',
              await d.evaluate("!document.querySelector('#oppAv .mcode') && !document.querySelector('#mLog') && document.querySelector('#oppAv').textContent.includes('Send them the code')"))
        await env.close_all()

        # practice on a phone: the log
        p = await ctx(env)
        await p.goto(env.url('/m/')); await p.wait_for_selector('#soloBtn'); await p.click('#soloBtn'); await PT.pick_deck(p, 0)
        bt = p.get_by_role('button', name='Random deck')
        if await bt.count(): await bt.first.click()
        await p.wait_for_timeout(800)
        await p.evaluate("()=>{ closeModal(); G.me.kept=G.me.dealt=true; takeFirst(G.myId); }"); await p.wait_for_timeout(300)
        await p.evaluate("()=>{ closeModal(); G.turn.n=3; G.turn.active=G.myId; G.turn.phase=2; G.me.st=[]; for(let i=1;i<=12;i++) addLog('Test line '+i+' with [[Lightning Bolt|lightning bolt]] in it.','m'); changed(); }")
        await p.wait_for_timeout(400); g = await p.evaluate(GEO)
        check('the log shows under the stack with the newest line last, scrolled to the bottom', g['log'] > 0 and 'Test line 12 with Lightning Bolt in it.' == g['last'] and g['bottom'], g)
        check('its text is readable (12 px or more)', g['fs'] >= 12, g)
        check('the stack is empty: the log fills the column, the stack is just its header ("· empty")', g['log'] >= 120 and g['stackList'] == 0 and g['stack'] < 30 and 'empty' in g['headAfter'], g)
        check('card names in the log are marked', await p.evaluate("!!document.querySelector('#mLog .mlb .cn')"))
        await p.evaluate("()=>{ const c=mk(keyOf('Lightning Bolt')); c.ts=Date.now(); G.me.st.push(c); const t=mk(null,{tok:true, ts:Date.now()+1, ab:{id:'x', tr:1}, cu:{n:'Test: trigger', t:'Triggered ability', o:'Untap it.', img:''}}); G.me.st.push(t); addLog('Ben casts Lightning Bolt.','m'); changed(); }")
        await p.wait_for_timeout(400); g2 = await p.evaluate(GEO)
        check('two items on the stack: stack and log share the column, about half each', g2['stackList'] > 40 and g2['log'] > 60 and abs(g2['stack'] - g2['log']) < 20, g2)
        check('the new line arrived at the bottom', g2['last'] == 'Ben casts Lightning Bolt.' and g2['bottom'], g2)
        await p.evaluate("()=>{ G.me.st=[]; changed(); }"); await p.wait_for_timeout(300); g3 = await p.evaluate(GEO)
        check('the stack empties: the log fills the column again', g3['log'] >= 120 and g3['stackList'] == 0, g3)
        # a tap on the last stack card resolves it; the click that ends the tap must not open the log panel
        await p.evaluate("()=>{ const t=mk(null,{tok:true, ts:Date.now(), ab:{id:'x', tr:1}, cu:{n:'Test: trigger', t:'Triggered ability', o:'You gain 1 life.', img:''}}); G.me.st.push(t); changed(); }")
        await p.wait_for_timeout(400); await p.locator('#stack .card').first.tap(); await p.wait_for_timeout(700)
        check('tapping the last stack card resolves it without opening the log panel', await p.evaluate("G.me.st.length===0 && !document.documentElement.classList.contains('mlog')"))
        await p.tap('#mLog'); await p.wait_for_timeout(400)
        check('a tap on the log opens the full log and chat panel', await p.evaluate("document.documentElement.classList.contains('mlog') && document.querySelector('#log').textContent.includes('Ben casts Lightning Bolt.')"))
        check('no page errors', not env.errors, env.errors[:3])
    finally:
        await env.stop()

asyncio.run(main())
print(('ALL PASS' if all(res) else 'SOME FAILED') + f' ({sum(res)}/{len(res)})')
