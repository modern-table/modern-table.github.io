"""v5.43 / Draft v0.41 (the maintainer's design): Open tables.
A stand-in for the Worker (tables.moderntable-app.workers.dev) answers /list, /open, /beat and /close.
Checks: the front page's bands (version C: a band per mode with tables, the rest in one Quiet row), names shown as text, a Playtest name
fills the Join code, an event name goes to its page with ?join= (which fills the code there); the mode choice is remembered, the listing
box never is; a Quiet chip picks the mode and ticks the box; Open a table with the box ticked lists it (name, code, mode), without it
nothing is sent; a friend joining closes it as filled; the beat, and a listing the Worker dropped; the section stays hidden when the
Worker can't be reached; the bands scroll unless animations are off; Game Night: /draft/?host=1&list=1 lists a draft, /night/?host=1
hosts a Modern night, unticking closes it, the event starting closes it."""
import asyncio, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import priority_test as PT
ROOT = os.environ.get('MT_ROOT') or PT.ROOT
res = []
def check(n, c, e=''): res.append(bool(c)); print('PASS' if c else 'FAIL', n, '' if c else e, flush=True)

class Env(PT.Env):
    async def start(self):
        PT.ROOT = ROOT
        return await super().start()

class Fake:
    def __init__(self):
        self.t = {}; self.calls = []; self.down = False; self.n = 0
    def handle(self, path, body):
        self.calls.append((path, body))
        if path == '/list': return {'tables': [{'n': e['n'], 'c': c, 'm': e['m']} for c, e in self.t.items()]}
        c = body.get('c')
        if path == '/open':
            if c in self.t: return {'ok': False}
            self.n += 1; tok = 'tok%d' % self.n; self.t[c] = {'n': body.get('n'), 'm': body.get('m'), 'tok': tok}; return {'ok': True, 't': tok}
        e = self.t.get(c)
        if not e or e['tok'] != body.get('t'): return {'ok': False, 'gone': True}
        if path == '/close': del self.t[c]
        return {'ok': True}
    def seen(self, path): return [b for p, b in self.calls if p == path]

async def ctx(env, fake):
    c = await env.b.new_context(viewport={'width': 1500, 'height': 900}); env.ctxs.append(c)
    async def route(r):
        u = r.request.url
        if 'tables.moderntable-app.workers.dev' in u:
            if fake.down: await r.abort(); return
            path = '/' + u.split('workers.dev/', 1)[1].split('?')[0]
            body = {}
            if r.request.method == 'POST':
                try: body = json.loads(r.request.post_data or '{}')
                except Exception: body = {}
            await r.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'}, body=json.dumps(fake.handle(path, body)))
        elif u.startswith('http://127.0.0.1:') or u.startswith('data:') or u.startswith('blob:'): await r.continue_()
        elif 'api.scryfall.com' in u: await r.fulfill(status=200, content_type='application/json', body='{"data":[]}')
        else: await r.abort()
    await c.route('**/*', route)
    p = await c.new_page(); env.watch(p, 'p%d' % len(env.ctxs)); return p

async def main():
    env = await Env().start()
    fake = Fake()
    fake.t = {'BLMWRZ': {'n': 'Theo', 'm': 'playtest', 'tok': 'x'}, 'WPLKJH': {'n': 'Sam', 'm': 'draft', 'tok': 'y'}, 'QQQQQQ': {'n': '<b>Bo</b>', 'm': 'playtest', 'tok': 'z'}}
    try:
        a = await ctx(env, fake)
        await a.goto(env.url('/')); await a.wait_for_selector('#otab:not([hidden])', timeout=8000)
        bands = await a.evaluate("[...document.querySelectorAll('.otband')].map(b=>b.dataset.otb)")
        check('a band for each mode with tables (Playtest, Draft)', bands == ['playtest', 'draft'], bands)
        quiet = await a.evaluate("[...document.querySelectorAll('.otq')].map(b=>b.dataset.otq)")
        check('the empty modes sit in the Quiet row', quiet == ['casual', 'match', 'night', 'sealed', 'cube'], quiet)
        lab = await a.evaluate("document.querySelector('.otband .otlab').textContent")
        check('the band is labeled', 'Playtest' in lab, lab)
        t = await a.evaluate("(()=>{const k=[...document.querySelectorAll('.otk')].find(x=>x.dataset.otc==='QQQQQQ'); return {txt:k.textContent, el:!!k.querySelector('b b')}})()")
        check('names are shown as text, never as markup', '<b>Bo</b>' in t['txt'] and not t['el'], t)
        k = await a.evaluate("document.querySelector('.otk[data-otc=BLMWRZ]').textContent")
        check('an entry reads Name · CODE', 'Theo' in k and 'BLMWRZ' in k and '·' in k, k)
        anim = await a.evaluate("getComputedStyle(document.querySelector('.otrun')).animationName")
        check('the band scrolls', anim == 'otscroll', anim)
        await a.evaluate("document.body.classList.add('nomo')")
        check('not with animations off', await a.evaluate("getComputedStyle(document.querySelector('.otrun')).animationName") == 'none')
        await a.hover('.otband[data-otb=playtest] .ottrk')
        check('pointing at a band pauses it', await a.evaluate("getComputedStyle(document.querySelector('.otrun')).animationPlayState") == 'paused')
        await a.click('.otk[data-otc=BLMWRZ]')   # (animations still off: Playwright waits for a still button)
        st = await a.evaluate("({c:document.querySelector('#codeIn').value, m:document.querySelector('#lobbyMsg').textContent})")
        check('clicking a Playtest name fills the Join code', st['c'] == 'BLMWRZ' and 'Theo' in st['m'], st)
        await a.evaluate("document.body.classList.remove('nomo')")
        await a.click('.otk[data-otc=WPLKJH]', force=True); await a.wait_for_timeout(1500)
        pa = await a.evaluate("location.pathname + location.search")
        check('an event name goes to its page', pa.startswith('/draft/'), pa)
        code = await a.evaluate("document.querySelector('#codeIn').value")
        check('which fills the code there', code == 'WPLKJH', code)

        await a.goto(env.url('/')); await a.wait_for_selector('#otab:not([hidden])')
        on = await a.evaluate("document.querySelector('#hostOpts .on').dataset.tm")
        check('Casual is chosen at first', on == 'casual', on)
        await a.click('#hostOpts [data-tm=match]'); await a.check('#lstChk')
        await a.reload(); await a.wait_for_selector('#otab:not([hidden])')
        st = await a.evaluate("({m:document.querySelector('#hostOpts .on').dataset.tm, l:document.querySelector('#lstChk').checked})")
        check('the mode is remembered, the listing box is not', st == {'m': 'match', 'l': False}, st)
        await a.click('.otq[data-otq=casual]')
        st = await a.evaluate("({m:document.querySelector('#hostOpts .on').dataset.tm, l:document.querySelector('#lstChk').checked, f:document.querySelector('#hostBtn').classList.contains('flash')})")
        check('a Quiet chip picks its mode, ticks the box and points at Open a table', st == {'m': 'casual', 'l': True, 'f': True}, st)

        await a.fill('#nameIn', 'Ann'); await a.click('#hostBtn'); await a.wait_for_timeout(1200)
        op = fake.seen('/open')
        code = await a.evaluate("G.code")
        check('Open a table with the box ticked lists it', len(op) == 1 and op[0] == {'c': code, 'n': 'Ann', 'm': 'casual'}, op)
        lst = await a.evaluate("LST")
        check('the listing is kept on this page', lst and lst['c'] == code and lst['t'], lst)
        check('and noted in the log', await a.evaluate("G.log.some(l=>/listed in Open tables/.test(l.text||''))"))
        await a.evaluate("lstTick()"); await a.wait_for_timeout(300)
        check('the beat', fake.seen('/beat') and fake.seen('/beat')[-1].get('c') == code, fake.seen('/beat'))

        b = await ctx(env, fake)
        await b.goto(env.url('/')); await b.wait_for_selector('#hostBtn')
        n0 = len(fake.seen('/open'))
        await b.fill('#nameIn', 'Cal'); await b.click('#hostBtn'); await b.wait_for_timeout(1000)
        check('without the box nothing is listed', len(fake.seen('/open')) == n0, fake.seen('/open'))

        g = await ctx(env, fake)
        await g.goto(env.url('/')); await g.wait_for_selector('#codeIn')
        await g.fill('#nameIn', 'Bob'); await g.fill('#codeIn', code); await g.click('#joinBtn')
        await a.wait_for_function("!LST", timeout=15000)
        cl = fake.seen('/close')
        check('a friend joining closes it as filled', cl and cl[-1] == {'c': code, 't': lst['t'], 'why': 'filled'}, cl)
        check('the table is gone from the list', code not in fake.t, list(fake.t))

        # a listing the Worker has dropped
        c2 = await ctx(env, fake)
        await c2.goto(env.url('/')); await c2.wait_for_selector('#hostBtn')
        await c2.check('#lstChk'); await c2.click('#hostBtn'); await c2.wait_for_timeout(1000)
        code2 = await c2.evaluate("G.code"); del fake.t[code2]
        await c2.evaluate("lstTick()"); await c2.wait_for_timeout(300)
        st = await c2.evaluate("({l:LST, t:document.querySelector('#toast').textContent})")
        check('a listing the Worker dropped is forgotten, with a note', st['l'] is None and 'ended' in st['t'], st)

        fake.down = True
        d = await ctx(env, fake)
        await d.goto(env.url('/')); await d.wait_for_timeout(1500)
        check('the section stays hidden when the Worker can\'t be reached', await d.evaluate("document.querySelector('#otab').hidden"))
        check('and the front page still works', await d.evaluate("!!document.querySelector('#hostBtn') && !document.querySelector('#lobby').hidden"))
        fake.down = False

        # Game Night
        h = await ctx(env, fake)
        await h.goto(env.url('/draft/', '&host=1&list=1')); await h.wait_for_timeout(2000)
        op = fake.seen('/open')[-1]
        hc = await h.evaluate("H.code")
        check('Draft: ?host=1&list=1 hosts and lists the draft', op.get('m') == 'draft' and op.get('c') == hc, op)
        check('the host sees the box ticked', await h.evaluate("!!document.querySelector('#dlstChk') && document.querySelector('#dlstChk').checked"))
        check('a host message in the chat', await h.evaluate("H.chat.some(m=>/listed in Open tables/.test(m.t))"))
        await h.evaluate("H.phase='draft'; render()"); await h.wait_for_timeout(300)
        cl = fake.seen('/close')[-1]
        check('the event starting closes it', cl.get('c') == hc and cl.get('why') == 'started', cl)
        n = await ctx(env, fake)
        await n.goto(env.url('/night/', '&host=1')); await n.wait_for_timeout(2000)
        st = await n.evaluate("({m:H.mode, box:!!document.querySelector('#dlstChk'), ticked:!!(document.querySelector('#dlstChk')||{}).checked})")
        check('Game Night: ?host=1 hosts a Modern night, the box offered, not ticked', st == {'m': 'modern', 'box': True, 'ticked': False}, st)
        await n.check('#dlstChk'); await n.wait_for_timeout(600)
        nc = await n.evaluate("H.code")
        check('ticking it lists the night', fake.seen('/open')[-1] == {'c': nc, 'n': 'Player', 'm': 'night'}, fake.seen('/open')[-1])
        await n.uncheck('#dlstChk'); await n.wait_for_timeout(400)
        check('unticking closes it', fake.seen('/close')[-1].get('c') == nc and nc not in fake.t, fake.seen('/close')[-1])
        await a.screenshot(path='/tmp/v543_a.png')
        check('no page errors', not env.errors, env.errors[:3])
    finally:
        await env.stop()

asyncio.run(main())
print(('ALL PASS' if all(res) else 'SOME FAILED') + f' ({sum(res)}/{len(res)})')
