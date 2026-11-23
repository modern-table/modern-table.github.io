"""v5.32: voice between two tables (two browsers, a local PeerServer, Chromium's fake microphone). Practice has no microphone.
At a table with a friend: the microphone button in my player box, an open line (the other page receives live audio and shows a
speaker in my box), muting releases the microphone and hides the speaker, unmuting reuses the call; voice notes as a setting
(record, send, the other page gets a play chip holding a WAV it can play), cancelling a recording sends nothing."""
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

ST = """()=>({btn:(document.querySelector('#myAv .vcb')||{}).className||null, opp:(document.querySelector('#oppAv .vci')||{}).className||null,
  chips:[...document.querySelectorAll('#oppAv .vnc')].map(b=>b.textContent+(b.classList.contains('new')?'*':'')), live:VC.live, oppLive:VC.oppLive, mic:!!VC.mic,
  tracks:(()=>{ const a=document.querySelector('#vcAudio'); return a && a.srcObject ? a.srcObject.getAudioTracks().length : 0; })()})"""
RX = """async()=>{ const c=VC.inc; if(!c || !c.peerConnection) return -1; let n=0; (await c.peerConnection.getStats()).forEach(r=>{ if(r.type==='inbound-rtp' && (r.kind==='audio'||r.mediaType==='audio')) n+=r.bytesReceived||0; }); return n; }"""

async def main():
    env = await Env().start()
    try:
        # Practice: no microphone
        p = await env.ctx('solo')
        await p.goto(env.url()); await p.wait_for_selector('#soloBtn'); await p.click('#soloBtn')
        await PT.pick_deck(p, 0)
        bt = p.get_by_role('button', name='Random deck')
        if await bt.count(): await bt.first.click()
        await p.wait_for_timeout(600)
        check('practice: no microphone button', await p.evaluate("()=>!document.querySelector('.vcb')"))
        await env.close_all()
        a, b = await PT.table(env)
        await a.wait_for_timeout(500)
        sa, sb = await a.evaluate(ST), await b.evaluate(ST)
        check('at a table with a friend both players get a microphone button, off', sa['btn'] == 'vcb' and sb['btn'] == 'vcb' and not sa['opp'] and not sb['opp'], [sa, sb])
        check('Settings has Voice (Open line / Voice notes), open line by default', await a.evaluate("()=>{ const r=SETROWS.find(r=>r.k==='voice'); return r && r.get()==='line' && Object.keys(r.o).join()==='line,notes'; }"))
        await a.click('#myAv .vcb'); await a.wait_for_timeout(2500)
        sa, sb = await a.evaluate(ST), await b.evaluate(ST)
        check("Ann turns her microphone on: her button is lit and holds the microphone", sa['live'] and sa['mic'] and 'on' in (sa['btn'] or ''), sa)
        check("Bob's page shows a speaker in Ann's box and plays her live audio", sb['oppLive'] and 'on' in (sb['opp'] or '') and sb['tracks'] == 1, sb)
        n1 = await b.evaluate(RX); await b.wait_for_timeout(1500); n2 = await b.evaluate(RX)
        check("audio keeps arriving at Bob's page", n2 > n1 > 0, [n1, n2])
        call1 = await a.evaluate("()=>VC.out && VC.out.connectionId")
        await a.click('#myAv .vcb'); await a.wait_for_timeout(1200)
        sa, sb = await a.evaluate(ST), await b.evaluate(ST)
        check('muting releases the microphone and hides the speaker on Bob\'s page', not sa['live'] and not sa['mic'] and sa['btn'] == 'vcb' and not sb['opp'], [sa, sb])
        await a.click('#myAv .vcb'); await a.wait_for_timeout(2000)
        sa, sb = await a.evaluate(ST), await b.evaluate(ST)
        n3 = await b.evaluate(RX); await b.wait_for_timeout(1200); n4 = await b.evaluate(RX)
        call2 = await a.evaluate("()=>VC.out && VC.out.connectionId")
        check('unmuting uses the same call, and audio flows again', sa['live'] and sb['oppLive'] and call1 == call2 and n4 > n3, [call1, call2, n3, n4])
        # Bob both ways: his own line while Ann talks
        await b.click('#myAv .vcb'); await b.wait_for_timeout(2000)
        check("Bob's microphone too: both hear each other", await a.evaluate("()=>VC.oppLive && document.querySelector('#vcAudio') && document.querySelector('#vcAudio').srcObject.getAudioTracks().length===1"))
        await b.click('#myAv .vcb'); await a.click('#myAv .vcb'); await a.wait_for_timeout(600)
        # voice notes
        await b.evaluate("()=>SETROWS.find(r=>r.k==='voice').set('notes')"); await b.wait_for_timeout(300)
        check('voice notes: the button records instead', 'note' in ((await b.evaluate(ST))['btn'] or ''))
        await b.click('#myAv .vcb'); await b.wait_for_timeout(1700)
        sb = await b.evaluate(ST)
        check('recording: a red button with a running time and a cancel', 'rec' in (sb['btn'] or '') and await b.evaluate("()=>!!document.querySelector('#myAv .vcb.x') && /0:0[1-9]/.test(document.querySelector('#myAv .vcb.rec b').textContent)"), sb)
        await b.click('#myAv .vcb.rec'); await b.wait_for_timeout(2500)
        sa, sb = await a.evaluate(ST), await b.evaluate(ST)
        check("tapping again sends it: Ann gets an unheard play chip; Bob's microphone is released", sa['chips'] and sa['chips'][-1].endswith('*') and '▶' in sa['chips'][-1] and not sb['mic'], [sa['chips'], sb])
        info = await a.evaluate("async()=>{ const n=VC.notes[VC.notes.length-1]; const bl=await (await fetch(n.url)).blob(); const h=new Uint8Array(await bl.slice(0,12).arrayBuffer()); return [n.mt, bl.size, String.fromCharCode(...h.slice(0,4))+String.fromCharCode(...h.slice(8,12)), new Audio().canPlayType('audio/wav')]; }")
        check('the note is a WAV of about 1.5 s at 12 kHz that this browser can play', info[0] == 'audio/wav' and 20000 < info[1] < 60000 and info[2] == 'RIFFWAVE' and info[3] != '', info)
        await a.click('#oppAv .vnc'); await a.wait_for_timeout(800)
        check('tapping the chip plays it (marked heard)', (await a.evaluate(ST))['chips'][-1].endswith('s'), (await a.evaluate(ST))['chips'])
        n_before = len(sa['chips'])
        await b.click('#myAv .vcb'); await b.wait_for_timeout(1200); await b.click('#myAv .vcb.x'); await b.wait_for_timeout(1500)
        check('cancelling a recording sends nothing and releases the microphone', len((await a.evaluate(ST))['chips']) == n_before and not (await b.evaluate(ST))['mic'])
        check('no page errors', not env.errors, env.errors[:3])
    finally:
        await env.stop()

asyncio.run(main())
print(('ALL PASS' if all(res) else 'SOME FAILED') + f' ({sum(res)}/{len(res)})')
