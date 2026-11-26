"""Phone layer m0.16 (the maintainer's design in claude/mobile-design.md, "Trigger ordering"): the order panel on a phone. Checks, in a
practice game with three triggers held for ordering (G.ordHold, as ordWatch sets it at a friend's table): the panel fills the board beside
the right column with both buttons on screen; the cards are big (at least 84 px, all in view), each with a black number for its
resolution order (1 on the right) and its trigger text under it; a real touch drag (CDP touch events) moves the left card to the right
end, the numbers follow, and Add to stack puts them on the stack in that order (the dragged one on top) with the log line."""
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

SETUP = """(()=>{ closeModal(); const m=G.me, L=m.lib, a=L[0], b=L[1], d=L[2]; m.st.length=0;   // the sources stay in the library: no enter triggers of their own
  trigPush(a, 'Draw a card.', 't'); trigPush(b, 'Target creature gets +2/+2 until end of turn.', 't'); trigPush(d, 'You gain 3 life.', 't');
  m.st.forEach((x,i)=>{ x.ts=1000+i; }); G.ordHold={ids:new Set(m.st.map(x=>x.id)), base:5000, act:true}; render(); ordPanel(); })()"""
GEO = """(()=>{ const p=document.querySelector('#coPanel'), r=p.getBoundingClientRect(), cards=[...p.querySelectorAll('#coTr .card[data-id]')];
  return {panel:[r.left, r.top, r.right, r.bottom], rr:parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--rr'))||132,
    btns:[...p.querySelectorAll('header button')].map(b=>{ const q=b.getBoundingClientRect(); return [q.left, q.top, q.right, q.bottom]; }),
    cards:cards.map(c=>{ const q=c.getBoundingClientRect(), n=c.querySelector('.mordn'), cs=n&&getComputedStyle(n); return {x:q.left, y:q.top, w:q.width, h:q.height, r:q.right, b:q.bottom,
      n:n?n.textContent:'', bg:cs&&cs.backgroundColor, cap:(c.querySelector('.mocap')||{}).textContent||''}; })}; })()"""

async def main():
    env = await Env().start()
    try:
        c = await env.b.new_context(viewport={'width':844,'height':390}, screen={'width':844,'height':390}, has_touch=True, is_mobile=True, device_scale_factor=2)
        async def route(r):
            u = r.request.url
            if u.startswith('http://127.0.0.1:') or u.startswith('data:'): await r.continue_()
            elif 'api.scryfall.com' in u: await r.fulfill(status=200, content_type='application/json', body='{"data":[]}')
            else: await r.abort()
        await c.route('**/*', route); env.ctxs.append(c)
        p = await c.new_page(); env.watch(p, 'phone'); await p.goto(env.url('/m/')); await p.wait_for_selector('#soloBtn')
        await p.tap('#soloBtn'); await p.wait_for_timeout(700); await p.locator('.drow').first.tap(); await p.wait_for_timeout(300)
        await p.get_by_role('button', name='Play this deck').tap(); await p.wait_for_timeout(800)
        b = p.get_by_role('button', name='Random deck')
        if await b.count(): await b.first.tap(); await p.wait_for_timeout(800)
        await p.evaluate(SETUP); await p.wait_for_timeout(600)
        g = await p.evaluate(GEO)
        pl = g['panel']
        check('the panel fills the board beside the right column', pl[0] < 20 and pl[1] < 20 and pl[3] > 370 and pl[2] <= 844 - g['rr'] + 1 and pl[2] > 844 - g['rr'] - 20, g)
        check('both buttons are on screen', len(g['btns']) == 2 and all(x[2] <= pl[2] and x[3] <= 390 for x in g['btns']), g['btns'])
        cs = g['cards']
        check('three big cards, all in view', len(cs) == 3 and all(x['w'] >= 84 and x['r'] <= pl[2] and x['b'] <= 390 for x in cs), cs)
        check('black numbers for the order they resolve: 3, 2, 1 left to right', [x['n'] for x in cs] == ['3', '2', '1'] and all(x['bg'] == 'rgb(0, 0, 0)' for x in cs), cs)
        check('each card has its trigger text under it', cs[0]['cap'] == 'Draw a card.' and 'gain 3 life' in cs[2]['cap'], [x['cap'] for x in cs])
        # a real touch drag: the first card to the right end
        cdp = await c.new_cdp_session(p)
        x0, y0 = cs[0]['x'] + cs[0]['w']/2, cs[0]['y'] + cs[0]['h']/2
        x1 = cs[2]['r'] + 20
        async def touch(t, x, y): await cdp.send('Input.dispatchTouchEvent', {'type': t, 'touchPoints': ([] if t == 'touchEnd' else [{'x': x, 'y': y}])})
        await touch('touchStart', x0, y0)
        for i in range(1, 13): await touch('touchMove', x0 + (x1 - x0)*i/12, y0); await p.wait_for_timeout(25)
        mid = await p.evaluate("({drag:!!document.querySelector('#coTr .codrag'), gap:!!document.querySelector('#coTr .coinsa, #coTr .coins')})")
        await touch("touchEnd", x1, y0); await p.wait_for_timeout(900)   # Chrome makes no click for a tap within ~300 ms of the drag
        check('while dragging, the card lifts and a gap opens', mid['drag'] and mid['gap'], mid)
        g2 = await p.evaluate(GEO)
        check('after the drag: Draw a card is on the right with number 1', g2['cards'][2]['cap'] == 'Draw a card.' and [x['n'] for x in g2['cards']] == ['3', '2', '1'], [(x['cap'], x['n']) for x in g2['cards']])
        await p.tap('#coPanel [data-co="add"]'); await p.wait_for_timeout(400)
        st = await p.evaluate("({top:(()=>{ const s=[...G.me.st].sort((a,b)=>(a.ts||0)-(b.ts||0)); return cdata(s[s.length-1]).o; })(), panel:!!document.querySelector('#coPanel:not([hidden])'), log:G.log.slice(-3).map(x=>typeof x==='string'?x:(x.t||JSON.stringify(x))).join(' | '), hold:!!G.ordHold})")
        check('Add to stack: the dragged trigger is on top, the panel closes', 'Draw a card' in (st['top'] or '') and not st['panel'] and not st['hold'], st)
        check('the log says the order was chosen', 'in the order they chose' in st['log'], st['log'])
        check('no page errors', not env.errors, env.errors[:3])
    finally:
        await env.stop()

if __name__ == '__main__':
    asyncio.run(main())
    print(('ALL PASS' if all(res) else 'SOME FAILED') + f' ({sum(res)}/{len(res)})')
