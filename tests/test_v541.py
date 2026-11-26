"""v5.41 / phone layer m0.14 (the maintainer): phones opening the table go to the phone table, which is now a beta.
Checks: a phone opening / lands on /m/ with ?t=/&r= kept; ?desk=1 keeps the phone on the desktop page and remembers it (a later / stays);
?phone=1 forgets it; a desktop browser stays on /; the phone front page carries the beta note, Send feedback and a ../?desk=1 link; the desktop
front page links to the phone table, the phone page hides that line; held upright, the phone shows the Modern Table screen (name, cards, the
turn line) over everything, and sideways it's gone."""
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

async def ctx(env, phone=True, w=844, h=390):
    o = dict(viewport={'width': w, 'height': h}, screen={'width': w, 'height': h}, has_touch=True, is_mobile=True, device_scale_factor=2) if phone \
        else dict(viewport={'width': 1500, 'height': 900})
    c = await env.b.new_context(**o)
    async def route(r):
        u = r.request.url
        if u.startswith('http://127.0.0.1:') or u.startswith('data:') or u.startswith('blob:'): await r.continue_()
        elif 'api.scryfall.com' in u: await r.fulfill(status=200, content_type='application/json', body='{"data":[]}')
        else: await r.abort()
    await c.route('**/*', route); env.ctxs.append(c)
    p = await c.new_page(); env.watch(p, 'phone' if phone else 'desktop'); return p

async def path(p):
    await p.wait_for_timeout(700)
    return await p.evaluate("location.pathname + location.search")

async def main():
    env = await Env().start()
    try:
        p = await ctx(env)
        await p.goto(env.url('/')); pa = await path(p)
        check('a phone opening / goes to /m/', pa.startswith('/m/'), pa)
        await p.goto(env.url('/?t=ABCD&r=g')); pa = await path(p)
        check('the table link is kept (?t=ABCD&r=g)', pa.startswith('/m/') and 't=ABCD' in pa and 'r=g' in pa, pa)
        await p.goto(env.url('/m/')); await p.wait_for_selector('#mNote')
        note = await p.evaluate("(()=>{const n=document.querySelector('#mNote'); return {t:n.textContent, fb:[...n.querySelectorAll('a')].map(a=>a.getAttribute('href'))}})()")
        check('the phone front page says beta', 'beta' in note['t'].lower(), note)
        check('it has Send feedback (the form) and The desktop table (../?desk=1)', any('docs.google.com/forms' in (h or '') for h in note['fb']) and '../?desk=1' in note['fb'], note)
        check('the old "hasn\'t been tried yet" wording is gone', "hasn't been tried" not in note['t'])
        check('the phone page hides the desktop\'s phone-table line', await p.evaluate("getComputedStyle(document.querySelector('#phLine')).display") == 'none')
        check('sideways: no turn-sideways screen', await p.evaluate("getComputedStyle(document.querySelector('#mTurn')).display") == 'none')
        await p.goto(env.url('/?desk=1')); pa = await path(p)
        check('?desk=1 keeps the phone on the desktop page', pa.startswith('/?') or pa == '/', pa)
        await p.goto(env.url('/')); pa = await path(p)
        check('and is remembered: / stays on the desktop page', not pa.startswith('/m/'), pa)
        check('the desktop page links to the phone table', await p.evaluate("(document.querySelector('#phLine a')||{}).getAttribute?.('href')") == '/m/?phone=1')
        await p.click('#phLine a'); pa = await path(p)
        check('that link opens the phone table', pa.startswith('/m/'), pa)
        await p.goto(env.url('/')); pa = await path(p)
        check('and forgets the desktop choice: / goes to /m/ again', pa.startswith('/m/'), pa)
        await env.close_all()

        d = await ctx(env, phone=False)
        await d.goto(env.url('/?t=ABCD&r=g')); pa = await path(d)
        check('a desktop browser stays on /', not pa.startswith('/m/'), pa)
        check('the desktop shows the phone-table line', await d.evaluate("getComputedStyle(document.querySelector('#phLine')).display") != 'none')
        await env.close_all()

        u = await ctx(env, w=390, h=844)
        await u.goto(env.url('/m/')); await u.wait_for_timeout(800)
        t = await u.evaluate("""(()=>{const e=document.querySelector('#mTurn'), cs=getComputedStyle(e), r=e.getBoundingClientRect();
          const top=document.elementFromPoint(195, 600); return {d:cs.display, txt:e.textContent, full:r.width>=389 && r.height>=843, over:e.contains(top),
          cards:e.querySelectorAll('.mt-c').length, fs:parseFloat(getComputedStyle(e.querySelector('.mt-t')).fontSize)}})()""")
        check('held upright: the Modern Table screen covers the page', t['d'] != 'none' and t['full'] and t['over'], t)
        check('it carries the name, the two cards and the turn line', 'Modern Table' in t['txt'] and 'sideways' in t['txt'] and t['cards'] == 2 and t['fs'] >= 30, t)
        await u.screenshot(path='/tmp/v541_portrait.png')
        await u.set_viewport_size({'width': 844, 'height': 390}); await u.wait_for_timeout(300)
        check('turned sideways it goes away', await u.evaluate("getComputedStyle(document.querySelector('#mTurn')).display") == 'none')
        check('no page errors', not env.errors, env.errors[:3])
    finally:
        await env.stop()

asyncio.run(main())
print(('ALL PASS' if all(res) else 'SOME FAILED') + f' ({sum(res)}/{len(res)})')
