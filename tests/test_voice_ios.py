"""v5.33: voice on an iPhone. Safari plays sound only from an audio player that a tap has started; here a stand-in for that rule
(play() refused, or left hanging, unless the page is inside a tap or the same element was started by one) runs on Bob's page. Bob's
first tap at the table primes the player, so Ann's voice plays with no further tap and without Bob's own microphone; and when the
player is refused or stays silent anyway, "Tap to hear" appears beside Ann's name and any tap brings the sound in."""
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

STUB = """(()=>{ const P=HTMLMediaElement.prototype, o=P.play; window.__refused=0; Object.defineProperty(P, 'autoplay', {get(){ return false; }, set(){}, configurable:true});   /* autoplay obeys the same rule on an iPhone */
  P.play=function(){ if(this.__ok || (navigator.userActivation && navigator.userActivation.isActive)){ this.__ok=true; return o.call(this); }
    window.__refused++; return window.__hang ? new Promise(()=>{}) : Promise.reject(new DOMException('blocked', 'NotAllowedError')); }; })()"""
ST = """()=>{ const a=document.querySelector('#vcAudio'); return {playing:!!(a && a.srcObject && !a.paused), tap:!!document.querySelector('#oppAv .vci.tap'), spk:!!document.querySelector('#oppAv .vci.on'), mic:!!VC.mic, refused:window.__refused}; }"""

async def main():
    env = await Env().start()
    try:
        a = await env.ctx('host'); b = await env.ctx('guest')
        await b.context.add_init_script(STUB)
        await PT.sit(env, a, b); await PT.pregame(a, b)
        await b.click('#oppAv .life b'); await b.wait_for_timeout(6500)   # one tap at the table, then long enough for the tap's own permission to lapse
        await a.click('#myAv .vcb'); await a.wait_for_timeout(2500)
        s = await b.evaluate(ST)
        check("Ann's microphone on: Bob hears her without turning his own microphone on and without another tap", s['playing'] and s['spk'] and not s['mic'] and not s['tap'], s)
        # a fresh player no tap has started, and Safari staying silent instead of refusing
        # (Playwright's evaluate counts as a tap, so the play is started from a timer once that has lapsed)
        await b.evaluate("()=>{ const a=document.querySelector('#vcAudio'), st=a.srcObject; a.remove(); window.__hang=1; setTimeout(()=>vcPlay(st), 6000); }")
        await b.wait_for_timeout(8000)
        s = await b.evaluate(ST)
        check("when the phone still holds the sound back (silently): Tap to hear beside Ann's name", not s['playing'] and s['tap'], s)
        await b.click('#oppAv .life b'); await b.wait_for_timeout(800)
        s = await b.evaluate(ST)
        check('...and any tap brings the sound in (the button goes)', s['playing'] and not s['tap'], s)
        check('no page errors', not env.errors, env.errors[:3])
    finally:
        await env.stop()

asyncio.run(main())
print(('ALL PASS' if all(res) else 'SOME FAILED') + f' ({sum(res)}/{len(res)})')
