"""v5.40: the turn doesn't move on while something is on the stack (CR 500.2).
The maintainer's report: in a practice game Ragavan's combat damage trigger (Treasure, exile the top card) went on the stack, and Next
moved the turn on with the trigger still there. Checks: Practice (Next and the Main 2 phase chip both refused, the button reads
Resolve the stack first, clicking the trigger resolves it and makes the Treasure, then Next goes on); Practice's own turn (its Next
waits too); a friend's table with Priority on (the phase chip had skipped Ragavan's trigger while it waited for the OK); and with
Priority off (my trigger, then the friend's trigger, each holds the turn until it resolves).
MT_ROOT: serve another build's folder (a worktree of the old commit) to see the checks fail there."""
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

RAG = "()=>{ const c=mk(keyOf('Ragavan, Nimble Pilferer')); c.sick=false; G.me.bf.push(c); changed(); return c.id; }"
ST = "()=>({ph:G.turn.phase, cs:G.turn.cs||null, st:G.me.st.map(c=>cdata(c).n), ost:((G.opp&&G.opp.st)||[]).map(c=>cdata(c).n), btn:document.querySelector('#next').textContent, toast:document.querySelector('#toast').textContent, tre:G.me.bf.filter(c=>/Treasure/.test(cdata(c).n)).length, oex:((G.opp&&G.opp.ex)||[]).length})"
CHIP = "(i)=>document.querySelector(`#phases button[data-ph=\"${i}\"]`).click()"

async def main():
    env = await Env().start()
    try:
        # ---- Practice: Ragavan connects, its trigger is on the stack
        p = await env.ctx('solo')
        await p.goto(env.url()); await p.wait_for_selector('#soloBtn'); await p.click('#soloBtn')
        await PT.pick_deck(p, 0)
        bt = p.get_by_role('button', name='Random deck')
        if await bt.count(): await bt.first.click()
        await p.wait_for_timeout(800)
        await p.evaluate("()=>{ closeModal(); G.me.kept=G.me.dealt=true; takeFirst(G.myId); }"); await p.wait_for_timeout(500)
        await p.evaluate("()=>{ closeModal(); G.turn.n=3; G.turn.active=G.myId; G.turn.phase=2; G.me.bf=[]; G.me.hand=[]; G.me.st=[]; G.opp.bf=[]; G.opp.life=20; changed(); }"); await p.wait_for_timeout(300)
        rag = await p.evaluate(RAG)
        await p.evaluate("(id)=>{ G.turn.phase=3; G.turn.cs=undefined; G.atkSel=new Set([id]); atkCommit(); }", rag); await p.wait_for_timeout(300)
        for _ in range(4):
            s = await p.evaluate(ST)
            if s['st']: break
            await p.click('#next'); await p.wait_for_timeout(400)
        s = await p.evaluate(ST)
        check("Practice: Ragavan deals combat damage and its trigger is on the stack", s['st'] == ['Ragavan: combat damage trigger'] and s['ph'] == 3, s)
        check("the button reads Resolve the stack first", s['btn'] == 'Resolve the stack first', s['btn'])
        await p.click('#next'); await p.wait_for_timeout(400); s = await p.evaluate(ST)
        check("Next doesn't leave combat while the trigger is on the stack", s['ph'] == 3 and s['st'] == ['Ragavan: combat damage trigger'], s)
        check("a toast says why", 'is still on the stack' in s['toast'] and 'resolve it' in s['toast'], s['toast'])
        await p.keyboard.press('Space'); await p.wait_for_timeout(300)
        await p.evaluate(CHIP, 4); await p.wait_for_timeout(300); s = await p.evaluate(ST)
        check("neither does Space or the Main 2 phase chip", s['ph'] == 3 and len(s['st']) == 1, s)
        await p.click('#stack .card'); await p.wait_for_timeout(800)
        for _ in range(3):
            if await p.evaluate("!document.querySelector('#modal').hidden"):
                await p.evaluate("closeModal()"); await p.wait_for_timeout(200)
        s = await p.evaluate(ST)
        check("clicking the trigger resolves it: a Treasure", s['st'] == [] and s['tre'] == 1, s)
        await p.click('#next'); await p.wait_for_timeout(400); s = await p.evaluate(ST)
        check("then Next moves on to Main 2", s['ph'] == 4, s)
        # Practice's own turn: its Next waits for the stack too
        await p.evaluate("()=>{ G.turn={active:oppId(), phase:2, n:4}; const t=mk(null,{tok:true, o:oppId(), ts:Date.now(), ab:{id:'x', tr:true}, cu:{n:'Test: trigger', t:'Triggered ability', o:'Untap it.', img:''}}); G.opp.st.push(t); changed(); }"); await p.wait_for_timeout(300)
        await p.evaluate("()=>dummyNext()"); await p.wait_for_timeout(300); s = await p.evaluate(ST)
        check("Practice's turn: its Next waits while its trigger is on the stack", s['ph'] == 2 and s['ost'] == ['Test: trigger'], s)
        await p.evaluate("()=>{ G.opp.st=[]; changed(); dummyNext(); }"); await p.wait_for_timeout(300)
        check("and goes on once the stack is empty", (await p.evaluate(ST))['ph'] == 3)
        await env.close_all()

        # ---- a friend's table, Priority on: Ragavan's trigger waits for Bob's OK; the phase chip must not skip it
        a, b = await PT.table(env)
        await PT.stage(a, b)
        rag = await a.evaluate(RAG)
        await b.evaluate("()=>{ G.me.bf=G.me.bf.filter(c=>!isCreature(c)); changed(); }"); await b.wait_for_timeout(400)
        await PT.press(a); await PT.settle(a, b)
        await a.evaluate("(id)=>{ G.atkSel=new Set([id]); atkCommit(); }", rag); await a.wait_for_timeout(500)
        await PT.press(b, 500)                                        # Done blocking
        await PT.press(a, 500)                                        # Apply combat damage: the damage stop asks Bob
        ib = await PT.info(b)
        if ib['text'].startswith('OK: Ann goes to'):
            await PT.press(b, 900)                                    # Bob's OK for the damage step only
        s = await a.evaluate(ST)
        check("friend's table: Ragavan's trigger is on Ann's stack, waiting for Bob", s['st'] == ['Ragavan: combat damage trigger'] and s['ph'] == 3, s)
        await a.evaluate(CHIP, 4); await a.wait_for_timeout(400); s = await a.evaluate(ST)
        check("Ann's Main 2 chip doesn't move the turn past the trigger", s['ph'] == 3 and s['st'] == ['Ragavan: combat damage trigger'], s)
        await PT.press(a, 300); s = await a.evaluate(ST)
        check("nor does her button", s['ph'] == 3 and len(s['st']) == 1, s)
        await PT.settle(a, b); await a.wait_for_timeout(900); s = await a.evaluate(ST)
        check("Bob's OK resolves it: a Treasure, and Bob's top card exiled", s['st'] == [] and s['tre'] == 1, s)
        await PT.press(a, 500); s = await a.evaluate(ST)
        check("then Ann's Next goes to Main 2", s['ph'] == 4, s)

        # ---- the host turns Priority off: a trigger still holds the turn
        await a.evaluate("()=>priToggle(false)"); await a.wait_for_timeout(500)
        await a.evaluate("()=>{ const t=mk(null,{tok:true, ts:Date.now(), ab:{id:'x', tr:true}, cu:{n:'Test: trigger', t:'Triggered ability', o:'Untap it.', img:''}}); G.me.st.push(t); changed(); }"); await a.wait_for_timeout(400)
        s = await a.evaluate(ST)
        check("Priority off: the button reads Resolve the stack first", s['btn'] == 'Resolve the stack first', s)
        await PT.press(a, 400); s = await a.evaluate(ST)
        check("Priority off: Ann's Next doesn't end Main 2 with her trigger on the stack", s['ph'] == 4 and s['st'] == ['Test: trigger'], s)
        await a.evaluate("()=>{ resolve(G.me.st[0].id); }"); await a.wait_for_timeout(400)
        await b.evaluate("()=>{ const t=mk(null,{tok:true, ts:Date.now(), ab:{id:'x', tr:true}, cu:{n:'Bob Test: trigger', t:'Triggered ability', o:'Untap it.', img:''}}); G.me.st.push(t); changed(); }"); await b.wait_for_timeout(700)
        await PT.press(a, 400); s = await a.evaluate(ST)
        check("Bob's trigger on the stack holds Ann's turn too, and says Bob resolves it", s['ph'] == 4 and s['ost'] == ['Bob Test: trigger'] and 'Bob resolves it' in s['toast'], s)
        await b.evaluate("()=>{ resolve(G.me.st[0].id); }"); await b.wait_for_timeout(700)
        await PT.press(a, 400); s = await a.evaluate(ST)
        check("once it resolves, Ann's Next moves to the end step", s['ph'] == 5, s)
        check('no page errors', not env.errors, env.errors[:3])
    finally:
        await env.stop()

asyncio.run(main())
print(('ALL PASS' if all(res) else 'SOME FAILED') + f' ({sum(res)}/{len(res)})')
