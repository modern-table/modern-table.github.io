"""v5.38 / Draft v0.40: long messages go in pieces.
A player cast Kozilek's Command for 100 (100 Eldrazi Spawn, scry 100). PeerJS's JSON channel refuses any message of 16,300 bytes
or more, so the caster's board state (about 39 KB) never reached the friend: the friend's view froze on the spell, and after a
reload the state never arrived, as if no one had sat down. Checks: the friend sees all 100 tokens after the OK, later changes
still arrive, a reload on either side brings the big board back, the pieces round-trip any text, and a Game Night room view
with a long chat reaches a player.
MT_ROOT: serve another build's folder (a worktree of the old commit) to see the table checks fail there."""
import asyncio, os, subprocess, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import priority_test as PT
ROOT = os.environ.get('MT_ROOT') or PT.ROOT
res = []
def check(n, c, e=''): res.append(bool(c)); print('PASS' if c else 'FAIL', n, '' if c else e, flush=True)

class Env(PT.Env):
    async def start(self):
        PT.ROOT = ROOT
        return await super().start()

async def responsive(p, s=8):
    try:
        await asyncio.wait_for(p.evaluate('1'), s); return True
    except Exception:
        return False

async def wait_for(p, js, s=10):
    try:
        await p.wait_for_function(js, timeout=s * 1000); return True
    except Exception:
        return False

ROUND = """()=>{ const sent=[], c={send:m=>sent.push(JSON.parse(JSON.stringify(m)))};
  const big={t:'state', s:{name:'Zoë "the quoter" \\\\ — ✨', bf:Array.from({length:300}, (_,i)=>({id:'p1-'+i, n:'Éowyn’s “token” \\ud83d\\udc09 '+i, o:'Sacrifice this token: Add {C}.\\n\\t'}))}};
  big.s.lone='\\ud83d'+'x'+'\\udc09';
  pcSend(c, big); const small={t:'log', text:'hi'}; pcSend(c, small);
  const enc=new TextEncoder(), sizes=sent.map(m=>enc.encode(JSON.stringify(m)).length), got=[];
  for(const m of sent) pcRecv(c, m, x=>got.push(x));
  return {pieces:sent.filter(m=>m.t==='pc').length, max:Math.max(...sizes), same:got.length===2 && JSON.stringify(got[0])===JSON.stringify(big) && got[1].text==='hi',
    whole:enc.encode(JSON.stringify(big)).length}; }"""

async def main():
    env = await Env().start()
    try:
        a, b = await PT.table(env)
        # Ann casts Kozilek's Command for 100: tokens for her, scry 100 then draw (modes 1 and 2, both on herself)
        await a.evaluate("""()=>{ G.turn.phase=2; const c=mk(keyOf("kozilek's command")); c.x=100; c.md=[1,2]; c.tg=[]; G.me.st.push(c); changed(); }""")
        ok = await wait_for(b, "document.querySelector('#next').classList.contains('ok')")
        check("Bob is asked for his OK on Kozilek's Command", ok, (await PT.info(b))['text'])
        await b.click('#next')
        ok = await wait_for(a, "!document.querySelector('#modal').hidden && /scry/i.test(document.querySelector('#modal h3').textContent)", 15)
        check("Ann's page resolves it: 100 tokens and the scry window", ok and await a.evaluate("G.me.bf.filter(x=>x.tok).length") == 100, await a.evaluate("G.me.bf.length"))
        await a.evaluate("document.querySelector('#modal footer button.go').click()"); await a.wait_for_timeout(500)
        size = await a.evaluate("new TextEncoder().encode(JSON.stringify({t:'state', s:pub()})).length")
        check("Ann's board state is over PeerJS's 16,300-byte limit (so this checks the pieces)", size > 16300, size)
        ok = await wait_for(b, "(G.opp.bf||[]).filter(x=>x.tok).length===100", 10)
        check("Bob's page sees all 100 Eldrazi Spawn", ok, await b.evaluate("(G.opp.bf||[]).length"))
        check("Bob's page sees the spell gone from Ann's stack", await b.evaluate("(G.opp.st||[]).length===0"), await b.evaluate("(G.opp.st||[]).map(c=>c.k)"))
        check("Bob's page stays responsive", await responsive(b))
        nd = await b.evaluate("document.querySelectorAll('#oppFront .card, #oppBack .card').length")
        ms = await b.evaluate("(()=>{ const t=performance.now(); render(); return Math.round(performance.now()-t); })()")
        check("Bob's page draws Ann's 100 tokens, and a redraw is quick (%d ms)" % ms, nd >= 100 and ms < 1500, nd)
        # later changes still arrive
        await a.evaluate("()=>{ const t=G.me.bf.filter(x=>x.tok); for(const x of t.slice(0,3)) move(x.id,'gy',{silent:true}); changed(); }")
        ok = await wait_for(b, "(G.opp.bf||[]).filter(x=>x.tok).length===97", 10)
        check('later changes still reach Bob (3 sacrificed: 97 left)', ok, await b.evaluate("(G.opp.bf||[]).filter(x=>x.tok).length"))
        # Bob reloads: Ann's big board has to come back, and he must see her at the table
        await PT.resume(b, a)
        ok = await wait_for(b, "G.opp && (G.opp.bf||[]).filter(x=>x.tok).length===97", 15)
        check("after Bob reloads, Ann is at the table with her 97 tokens", ok, await b.evaluate("G.opp ? (G.opp.bf||[]).length : 'no opponent'"))
        check("after Bob's reload his microphone button is there (a friend at the table)", await b.evaluate("!!document.querySelector('#myAv .vcb')"))
        # Ann reloads
        await PT.resume(a, b)
        ok = await wait_for(b, "G.opp && (G.opp.bf||[]).filter(x=>x.tok).length===97", 15) and await wait_for(a, "G.me.bf.filter(x=>x.tok).length===97 && G.opp", 5)
        check('after Ann reloads, both pages still have the 97 tokens', ok)
        await a.evaluate("()=>{ G.me.bf=G.me.bf.filter(x=>!x.tok); changed(); }")
        ok = await wait_for(b, "(G.opp.bf||[]).filter(x=>x.tok).length===0", 10)
        check('a small state after a big one still arrives (tokens gone)', ok)
        # the pieces themselves
        r = await a.evaluate(ROUND)
        check('pcSend splits a big message into pieces each under 16,300 bytes, and pcRecv puts it back exactly (quotes, accents, emoji, a split surrogate)',
              r['pieces'] > 1 and r['max'] < 16300 and r['same'], r)
        await env.close_all()

        # Game Night: a room view with a long chat (120 messages of nearly 300 characters) reaches a player
        if os.path.exists(os.path.join(ROOT, 'night', 'index.html')):
            ca = await env.b.new_context(viewport={'width': 1500, 'height': 900}); cb = await env.b.new_context(viewport={'width': 1500, 'height': 900})
            env.ctxs += [ca, cb]
            for c in (ca, cb):
                async def route(r):
                    u = r.request.url
                    if u.startswith('http://127.0.0.1:') or u.startswith('data:') or u.startswith('blob:'): await r.continue_()
                    elif 'api.scryfall.com' in u: await r.fulfill(status=200, content_type='application/json', body='{"data":[]}')
                    else: await r.abort()
                await c.route('**/*', route)
            ra = await ca.new_page(); rb = await cb.new_page(); env.watch(ra, 'night host'); env.watch(rb, 'night player')
            await ra.goto(env.url('/night/', '&gnfast=1')); await ra.fill('#nameIn', 'Ann'); await ra.click('#nightBtn')
            await ra.wait_for_function('typeof CODE!=="undefined" && CODE && CODE.length>=4', timeout=20000)
            code = await ra.evaluate('CODE')
            await rb.goto(env.url('/night/', '&gnfast=1')); await rb.fill('#nameIn', 'Bob'); await rb.fill('#codeIn', code); await rb.click('#joinBtn')
            await rb.wait_for_function("typeof V!=='undefined' && V && V.seats && V.seats.length===2", timeout=30000)
            await ra.evaluate("()=>{ for(let i=0;i<150;i++) H.chat.push({n:'Ann', t:('Message '+i+' — ').padEnd(290,'é'), at:Date.now()}); sync(); }")
            vs = await ra.evaluate("new TextEncoder().encode(JSON.stringify(view(1))).length")
            ok = await wait_for(rb, "V && V.chat && V.chat.length===120 && /Message 149/.test(V.chat[119].t)", 10)
            check('Game Night: a room view of %d bytes (long chat) reaches the player' % vs, vs > 16300 and ok, await rb.evaluate("V && V.chat ? V.chat.length : null"))
            await rb.evaluate("act({t:'chat', text:'still here'})")
            ok = await wait_for(ra, "H.chat.some(x=>x.t==='still here')", 8)
            check("and the player's own messages still reach the host", ok)
        check('no page errors', not env.errors, env.errors[:3])
    finally:
        await env.stop()

asyncio.run(main())
print(('ALL PASS' if all(res) else 'SOME FAILED') + f' ({sum(res)}/{len(res)})')
