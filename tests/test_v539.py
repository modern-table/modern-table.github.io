"""v5.39: an attacker stays blocked after its blocker leaves combat (CR 509.1h, 506.4).
A player's Wild Nacatl was blocked by a creature token; the token was sacrificed to Goblin Bombardment before combat damage,
and the Nacatl's damage went through to the player. The table decided "blocked" at damage time from the block arrows still on
the board, and the sacrificed blocker's arrow was gone. Checks: at a friend's table (priority on) the blocked attacker deals
no damage once its only blocker is sacrificed during the damage stop; an unblocked attacker in the same combat still hits;
trample still goes over to the player; Practice's blocks the same way; the next combat starts with nothing blocked.
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

TOK = "(a)=>{ const c=mk(null,{tok:true, cu:{n:a[0], t:'Token Creature — '+a[0], pt:a[1], o:'', img:'', cl:[]}}); G.me.bf.push(c); changed(); return c.id; }"
SAC = "(id)=>{ const f=find(id); log(`${G.me.name} sacrifices ${cname(f.c)} to Goblin Bombardment.`); move(id,'gy',{silent:true}); changed(); }"
CLOG = "()=>G.log.map(l=>String(l.text).replace(/\\[\\[([^|\\]]*)\\|[^\\]]*\\]\\]/g,'$1')).filter(t=>/^(First-strike damage|Combat damage):/.test(t)).slice(-1)[0]||''"

async def main():
    env = await Env().start()
    try:
        a, b = await PT.table(env)
        await PT.stage(a, b)                              # Test Ox 2/2 each, Main 2 Always
        nac = await a.evaluate(PT.PERM_JS, ['Wild Nacatl', 'Creature — Cat Warrior', '3/3'])
        tr = await a.evaluate(PT.PERM_JS, ['Test Rhino', 'Creature — Rhino', '4/4', 'Trample'])
        ox = await a.evaluate("G.me.bf.find(c=>cdata(c).n==='Test Ox').id")
        await a.wait_for_timeout(300)
        g1 = await b.evaluate(TOK, ['Goblin', '1/1']); g2 = await b.evaluate(TOK, ['Goblin', '1/1'])
        await b.evaluate("()=>{ const box=G.me.bf.find(c=>cdata(c).n==='Test Ox'); move(box.id,'gy',{silent:true}); changed(); }")
        await b.wait_for_timeout(400)
        await PT.press(a); await PT.settle(a, b)
        await a.evaluate("(ids)=>{ G.atkSel=new Set(ids); atkCommit(); }", [nac, tr, ox]); await a.wait_for_timeout(500)
        # Bob blocks the Nacatl with one Goblin token and the Rhino with the other; the Ox is unblocked
        await b.evaluate("([w,x])=>{ startMode('block', w); finishMode(x); }", [g1, nac]); await b.wait_for_timeout(250)
        await b.evaluate("([w,x])=>{ startMode('block', w); finishMode(x); }", [g2, tr]); await b.wait_for_timeout(250)
        await PT.press(b, 500)
        ia = await PT.info(a)
        check('Bob is done blocking: Ann may apply combat damage', ia['text'] == 'Apply combat damage', ia['text'])
        await PT.press(a, 500)
        ib = await PT.info(b)
        check('the damage stop: Bob is asked for his OK', ib['text'] == 'OK: Ann goes to combat damage', ib['text'])
        # during the stop Bob sacrifices both blocking tokens (Goblin Bombardment)
        await b.evaluate(SAC, g1); await b.evaluate(SAC, g2); await b.wait_for_timeout(700)
        check('both tokens are gone and their block arrows with them', await b.evaluate("([x,y])=>!G.me.bf.some(c=>c.id===x||c.id===y) && !G.me.arrows.some(a=>a.blk)", [g1, g2]))
        ib = await PT.info(b)
        if ib['text'] == 'OK: Ann goes to combat damage':
            await PT.press(b, 1200)
        await PT.settle(a, b); await a.wait_for_timeout(600)
        lb = (await PT.info(b))['life']; cl = await a.evaluate(CLOG)
        check('Bob takes 2 (the unblocked Ox) + 4 (the trampling Rhino), not the blocked Nacatl\'s 3: life 14', lb == 14, [lb, cl])
        check("the log says the Nacatl is blocked and its blockers are gone", 'Wild Nacatl is blocked and its blockers are gone, so it deals no damage' in cl, cl)
        check('the Rhino tramples over (its blocker gone)', 'Test Rhino deals 4 to Bob (trample)' in cl, cl)
        # next turn: Bob attacks Ann unblocked, nothing stale is blocked
        await PT.press(a); await PT.press(a); await PT.settle(a, b); await PT.press(a)
        await b.evaluate('T.trim()'); await PT.press(b, 600)
        bx = await b.evaluate(PT.PERM_JS, ['Test Ox', 'Creature — Ox', '2/2']); await b.wait_for_timeout(300)
        await PT.press(b); await PT.settle(a, b)
        await b.evaluate("(id)=>{ G.atkSel=new Set([id]); atkCommit(); }", bx); await b.wait_for_timeout(500)
        check("a new combat starts with no attacker recorded as blocked", not (await PT.info(b))['turn'].get('blkd'), (await PT.info(b))['turn'])
        await PT.press(a, 500); await PT.press(b, 500); await PT.settle(a, b); await a.wait_for_timeout(600)
        la = (await PT.info(a))['life']
        check('that unblocked Ox hits Ann: life 18', la == 18, la)
        await env.close_all()

        # Practice: I attack, Practice's token blocks, the token is sacrificed, then damage
        p = await env.ctx('solo')
        await p.goto(env.url()); await p.wait_for_selector('#soloBtn'); await p.click('#soloBtn')
        await PT.pick_deck(p, 0)
        bt = p.get_by_role('button', name='Random deck')
        if await bt.count(): await bt.first.click()
        await p.wait_for_timeout(800)
        await p.evaluate("()=>{ closeModal(); G.me.kept=G.me.dealt=true; takeFirst(G.myId); }"); await p.wait_for_timeout(500)
        await p.evaluate("()=>{ closeModal(); G.turn.n=3; G.turn.active=G.myId; G.turn.phase=2; G.me.bf=[]; G.me.hand=[]; G.opp.bf=[]; G.opp.life=20; changed(); }"); await p.wait_for_timeout(300)
        nac = await p.evaluate(PT.PERM_JS, ['Wild Nacatl', 'Creature — Cat Warrior', '3/3'])
        gt = await p.evaluate("()=>{ const c=mk(null,{tok:true, o:oppId(), cu:{n:'Goblin', t:'Token Creature — Goblin', pt:'1/1', o:'', img:'', cl:[]}}); G.opp.bf.push(c); changed(); return c.id; }")
        await p.evaluate("(id)=>{ G.turn.phase=3; G.turn.cs=undefined; G.atkSel=new Set([id]); atkCommit(); }", nac); await p.wait_for_timeout(300)
        await p.evaluate("()=>combatStep()"); await p.wait_for_timeout(300)
        await p.evaluate("([b,a])=>{ G.opp.arrows.push({a:b, b:a, blk:1}); pblockBtn('done'); }", [gt, nac]); await p.wait_for_timeout(300)
        await p.evaluate("(id)=>{ const i=G.opp.bf.findIndex(c=>c.id===id); G.opp.gy.push(G.opp.bf.splice(i,1)[0]); pruneArrows(); changed(); }", gt); await p.wait_for_timeout(300)
        await p.evaluate("()=>combatStep()"); await p.wait_for_timeout(800)
        lp = await p.evaluate('G.opp.life'); cl = await p.evaluate(CLOG)
        check("Practice: its blocking token sacrificed, the blocked Nacatl deals no damage (Practice stays at 20)", lp == 20, [lp, cl])
        check('no page errors', not env.errors, env.errors[:3])
    finally:
        await env.stop()

asyncio.run(main())
print(('ALL PASS' if all(res) else 'SOME FAILED') + f' ({sum(res)}/{len(res)})')
