"""v5.34 (phone m0.10): once a friend has joined with the table code, the table offers to open the voice line.
Both pages show the offer naming the friend; Turn on my microphone opens the line in the same tap; Not now leaves it off and
says where the button is; the offer comes once per table code (a reload doesn't bring it back); turning the microphone on
from the player box answers it too; voice notes get Record a note; never in practice; on a phone it sits over the board,
clear of the right column, with touch-sized buttons."""
import asyncio, os, subprocess, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import priority_test as PT
res = []
def check(n, c, e=''): res.append(bool(c)); print('PASS' if c else 'FAIL', n, '' if c else e)

class Env(PT.Env):
    async def start(self):
        from playwright.async_api import async_playwright
        self.port, self.pport = PT.free_port(), PT.free_port()
        self.srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(self.port), '--bind', '127.0.0.1'], cwd=PT.ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        js = "const {PeerServer}=require('peer'); PeerServer({port:%d, path:'/', host:'127.0.0.1'});" % self.pport
        self.peer = subprocess.Popen(['node', '-e', js], cwd=PT.peer_dir(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.5)
        self.pw = await async_playwright().start()
        args = ['--disable-features=LocalNetworkAccessChecks,BlockInsecurePrivateNetworkRequests,PrivateNetworkAccessSendPreflights',
                '--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', '--autoplay-policy=no-user-gesture-required']
        self.b = await self.pw.chromium.launch(args=args)
        self.errors, self.ctxs, self.seed = [], [], 1000
        return self

OF = """()=>{ const e=document.querySelector('#vcOffer'); if(!e) return null; const r=e.getBoundingClientRect();
  return {t:e.textContent, btns:[...e.querySelectorAll('button')].map(b=>b.textContent), vis:!!(e.offsetParent || getComputedStyle(e).position==='fixed') && r.width>0,
    r:[r.left, r.top, r.right, r.bottom], z:+getComputedStyle(e).zIndex, bh:Math.min(...[...e.querySelectorAll('button')].map(b=>b.getBoundingClientRect().height))}; }"""

async def main():
    env = await Env().start()
    try:
        p = await env.ctx('solo')
        await p.goto(env.url()); await p.wait_for_selector('#soloBtn'); await p.click('#soloBtn')
        await PT.pick_deck(p, 0)
        bt = p.get_by_role('button', name='Random deck')
        if await bt.count(): await bt.first.click()
        await p.wait_for_timeout(800)
        check('practice: no voice offer', await p.evaluate(OF) is None)
        await env.close_all()

        a, b = await PT.table(env)
        await a.wait_for_timeout(600)
        oa, ob = await a.evaluate(OF), await b.evaluate(OF)
        check('both players get the offer, naming the friend', oa and ob and 'Talk to Bob?' in oa['t'] and 'Talk to Ann?' in ob['t'], [oa, ob])
        check('the offer has Turn on my microphone and Not now', oa and oa['btns'] == ['Turn on my microphone', 'Not now'], oa)
        av = await a.evaluate("()=>{ const r=document.querySelector('#myAv').getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; }")
        check("it doesn't cover my player box, and windows open above it", oa and (oa['r'][3] <= av[1] or oa['r'][2] <= av[0] or oa['r'][0] >= av[2]) and oa['z'] < 70, [oa, av])
        check('the microphone is still off until someone answers', not await a.evaluate('VC.live') and not await b.evaluate('VC.live'))
        await a.click('#vcOffer [data-vc="offer-yes"]'); await a.wait_for_timeout(2500)
        check("Ann's Turn on my microphone opens her line and the offer goes", await a.evaluate('VC.live && !!VC.mic') and await a.evaluate(OF) is None)
        ob = await b.evaluate(OF)
        check("Bob's offer now says Ann's microphone is on, and he hears her", ob and "Ann's microphone is on" in ob['t'] and await b.evaluate("()=>VC.oppLive && !!document.querySelector('#vcAudio').srcObject"), ob)
        await b.click('#vcOffer [data-vc="offer-no"]'); await b.wait_for_timeout(500)
        check("Bob's Not now: the offer goes, his microphone stays off, the log says where the button is",
              await b.evaluate(OF) is None and not await b.evaluate('VC.live') and 'microphone beside your name' in await b.evaluate("()=>document.querySelector('#log').textContent"))
        await PT.resume(b, a); await b.wait_for_timeout(1500); await a.wait_for_timeout(500)
        check('after Bob reloads the table, neither page asks again', await b.evaluate(OF) is None and await a.evaluate(OF) is None and await b.evaluate('VC.offerWant'))
        # the player box's own button answers it too
        await a.evaluate("()=>{ sessionStorage.removeItem(vcOfferKey()); VC.offerDone=false; VC.offerWant=true; render(); }"); await a.wait_for_timeout(300)
        check('(offer shown again for the next check)', await a.evaluate(OF) is not None)
        await a.click('#myAv .vcb'); await a.wait_for_timeout(2000); await a.evaluate('render()')
        check("turning the microphone on from the player box counts as an answer", await a.evaluate('VC.live') and await a.evaluate(OF) is None and await a.evaluate('vcOffered()'))
        await a.click('#myAv .vcb'); await a.wait_for_timeout(500)
        # voice notes
        await a.evaluate("()=>{ SETROWS.find(r=>r.k==='voice').set('notes'); sessionStorage.removeItem(vcOfferKey()); VC.offerDone=false; render(); }"); await a.wait_for_timeout(300)
        oa = await a.evaluate(OF)
        check('with voice notes the offer reads Record a note', oa and oa['btns'][0] == 'Record a note' and 'Voice notes are on' in oa['t'], oa)
        await a.click('#vcOffer [data-vc="offer-yes"]'); await a.wait_for_timeout(1500)
        check('Record a note starts recording', await a.evaluate('!!VC.rec') and await a.evaluate(OF) is None)
        await a.click('#myAv .vcb.x'); await a.wait_for_timeout(500)
        await env.close_all()

        # a phone guest
        a = await env.ctx('host')
        c = await env.b.new_context(viewport={'width': 844, 'height': 390}, has_touch=True, is_mobile=True, device_scale_factor=2)
        env.ctxs.append(c); c._old = None
        await c.add_init_script(PT.SEED_JS % 4242)
        b = await c.new_page(); b._name = 'phone'
        b.on('pageerror', lambda e: env.errors.append('phone: ' + str(e)))
        await a.goto(env.url()); await a.wait_for_selector('#hostBtn'); await a.fill('#nameIn', 'Ann'); await a.click('#hostBtn'); await PT.pick_deck(a, 0)
        code = await a.evaluate('G.code')
        await b.goto(env.url('/m/')); await b.wait_for_selector('#joinBtn'); await b.fill('#nameIn', 'Pat'); await b.fill('#codeIn', code); await b.click('#joinBtn'); await PT.pick_deck(b, 1)
        await b.wait_for_function("G.opp && G.conn && G.conn.open && !document.querySelector('#table').hidden", timeout=30000)
        await b.wait_for_function("!!document.querySelector('#vcOffer')", timeout=8000)
        ob = await b.evaluate(OF)
        geo = await b.evaluate("()=>{ const cs=getComputedStyle(document.documentElement); return {w:innerWidth, h:innerHeight, rr:parseFloat(cs.getPropertyValue('--rr'))||132, sl:parseFloat(cs.getPropertyValue('--sl'))||0}; }")
        check('on the phone the offer sits over the board, clear of the right column, inside the screen', ob and ob['r'][0] >= geo['sl'] and ob['r'][2] <= geo['w'] - geo['rr'] + 1 and ob['r'][1] >= 0 and ob['r'][3] <= geo['h'], [ob, geo])
        check('its buttons are touch-sized (40 px or more)', ob and ob['bh'] >= 40, ob)
        await b.tap('#vcOffer [data-vc="offer-yes"]'); await b.wait_for_timeout(2500)
        check("a tap on the phone's Turn on my microphone opens the line", await b.evaluate('VC.live') and await a.evaluate('VC.oppLive'))
        check('no page errors', not env.errors, env.errors[:3])
    finally:
        await env.stop()

asyncio.run(main())
print(('ALL PASS' if all(res) else 'SOME FAILED') + f' ({sum(res)}/{len(res)})')
