"""v5.29: the weekly new cards of 2026-11-23 (Emrakul, Federation Outpost, Firespout, Iona, Valgavoth), ward, and the
likely-covered cards (Jetmir's Garden, Xander's Lounge, Mana Tithe, Pawpatch Formation). Practice game, baked card data."""
import os, socket, subprocess, sys, time
from playwright.sync_api import sync_playwright
ROOT = os.environ.get('MT_ROOT') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def _free_port():
    s = socket.socket(); s.bind(('127.0.0.1', 0)); p = s.getsockname()[1]; s.close(); return p
PORT = _free_port()
srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(PORT), '--bind', '127.0.0.1'], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(0.8)
results = []
def check(name, cond, extra=''):
    results.append((name, bool(cond))); print(('PASS' if cond else 'FAIL'), name, extra)
RESET = """() => { S.autoPay=false; G.me.hand=[]; G.me.bf=[]; G.me.st=[]; G.me.gy=[]; G.me.ex=[]; G.me.arrows=[]; G.me.mana=noMana(); G.me.life=20;
  G.opp.bf=[]; G.opp.st=[]; G.opp.ex=[]; G.opp.arrows=[]; G.turn.n=3; G.turn.active=G.myId; G.turn.phase=2; G.mode=null; G.me.lp=null; G.me.lpx=null; render(); }"""
try:
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context(viewport={'width': 1500, 'height': 900})
        for h in ['**/cards.scryfall.io/**','**/svgs.scryfall.io/**','**/backs.scryfall.io/**','**/fonts.googleapis.com/**','**/fonts.gstatic.com/**','**/gc.zgo.at/**','**/*.metered.live/**']:
            ctx.route(h, lambda r: r.abort())
        ctx.route('**/api.scryfall.com/**', lambda r: r.fulfill(status=200, content_type='application/json', body='{"data":[]}'))
        p = ctx.new_page(); errs = []
        p.on('pageerror', lambda e: errs.append(str(e)))
        p.goto(f'http://127.0.0.1:{PORT}/'); p.wait_for_timeout(600)
        p.click('#soloBtn'); p.wait_for_timeout(600)
        p.locator('.drow').first.click(); p.wait_for_timeout(400)
        p.get_by_role('button', name='Play this deck').click(); p.wait_for_timeout(1500)
        for name in ['Random deck', 'Keep']:
            bt = p.get_by_role('button', name=name)
            if bt.count():
                try: bt.first.click(timeout=800)
                except Exception: pass
        p.wait_for_function('typeof G!=="undefined" && G.me && Array.isArray(G.me.bf)', timeout=10000)
        p.evaluate("() => { G.me.kept=G.me.dealt=true; }"); p.evaluate(RESET)
        LOG = "(n) => [...document.querySelectorAll('#log .le, #log div')].slice(-n).map(e=>e.textContent).join(' | ')"
        modal_open = lambda: p.evaluate("() => !document.querySelector('#modal').hidden")
        modal_text = lambda: p.evaluate("() => document.querySelector('#modal').hidden ? '' : document.querySelector('#modal').innerText")

        # ---- Emrakul: keywords, annihilator, protection, graveyard shuffle
        r = p.evaluate("""() => { const e=mk(keyOf('emrakul, the aeons torn')); G.me.bf.push(e); window.__e=e; for(let i=0;i<7;i++) G.opp.bf.push(mk(keyOf('thought-knot seer'),{o:oppId()})); render();
            return [annihilatorN(e), kwOn(e,'flying'), protColSpell(e)]; }""")
        check('Emrakul: annihilator 6, flying seen on the long keyword line, protection read', r == [6, True, True], str(r))
        p.evaluate("() => { G.turn.phase=3; G.atkSel=new Set([window.__e.id]); atkCommit(); }"); p.wait_for_timeout(400)
        st = p.evaluate("() => G.me.st.map(x=>x.cu&&x.cu.o)")
        check('Emrakul attacks: annihilator trigger on the stack', 'Each opponent sacrifices 6 permanents.' in st, str(st))
        p.evaluate("() => { const t=G.me.st.find(x=>/sacrifices 6/.test(x.cu.o)); resolve(t.id); }"); p.wait_for_timeout(1200)
        check('annihilator 6: Practice sacrifices six of its seven permanents', p.evaluate("() => G.opp.bf.length") == 1, str(p.evaluate("() => G.opp.bf.length")))
        p.evaluate(RESET)
        r = p.evaluate("""() => { const e=mk(keyOf('emrakul, the aeons torn'),{o:oppId()}), t=mk(keyOf('thought-knot seer'),{o:oppId()}); G.opp.bf.push(e,t);
            const bolt=mk(keyOf('lightning bolt')), kc=mk(keyOf("kozilek's command")); G.me.st.push(bolt); render(); const sb=tgtSpec(bolt);
            return [tgtCheck(sb,e.id).ok, tgtCheck(sb,e.id).why||'', tgtCheck(sb,t.id).ok, protFrom(e, bolt), protFrom(e, kc), protFrom(e, {ab:{id:'x'}, cu:{n:'x'}})]; }""")
        check('a red spell can\'t target Emrakul (protection), another creature it can', r[0] is False and 'protection' in r[1] and r[2] is True, str(r))
        check('colourless spells and abilities aren\'t stopped', r[3] is True and r[4] is False and r[5] is False, str(r))
        p.evaluate(RESET)
        p.evaluate("""() => { const e=mk(keyOf('emrakul, the aeons torn')); G.me.hand.push(e); window.__e=e; for(let i=0;i<3;i++) G.me.gy.push(mk(keyOf('lightning bolt'))); window.__lib0=G.me.lib.length; render(); move(e.id,'gy'); }""")
        p.wait_for_timeout(300)
        st = p.evaluate("() => G.me.st.map(x=>x.cu&&x.cu.o)")
        check('Emrakul put into the graveyard (from the hand): its trigger goes on the stack', st == ['You shuffle your graveyard into your library.'], str(st))
        p.evaluate("() => resolve(G.me.st[G.me.st.length-1].id)"); p.wait_for_timeout(800)
        r = p.evaluate("() => [G.me.gy.length, G.me.lib.length-window.__lib0, G.me.lib.some(x=>x.id===window.__e.id)]")
        check('…and resolving shuffles the graveyard (Emrakul too) into the library', r == [0, 4, True], str(r))

        # ---- Iona
        p.evaluate(RESET)
        r = p.evaluate("""() => { const i=mk(keyOf('iona, shield of emeria'),{o:oppId()}); i.chosen='Red'; G.opp.bf.push(i); const f=mk(keyOf('firespout')), w=mk(keyOf('consign to memory')), tk=mk(keyOf('thought-knot seer'));
            const a=[castLock(f,'hand'), castLock(w,'hand'), castLock(tk,'hand')]; i.chosen='Blue'; a.push(castLock(w,'hand')); G.me.bf.push(Object.assign(mk(keyOf('iona, shield of emeria')),{chosen:'Blue'})); G.opp.bf=[]; a.push(castLock(w,'hand')); return a; }""")
        check('Iona (red): a red/green spell is locked, blue and colourless aren\'t', bool(r[0]) and 'red' in r[0] and r[1] is None and r[2] is None, str(r))
        check('Iona (blue): a blue spell is locked; my own Iona doesn\'t lock me', bool(r[3]) and r[4] is None, str(r))

        # ---- Federation Outpost
        p.evaluate(RESET)
        p.evaluate("""() => { for(const n of ["jetmir's garden","xander's lounge"]) G.me.bf.push(mk(keyOf(n))); const o=mk(keyOf('federation outpost')); G.me.hand.push(o); window.__o=o; window.__l=G.me.life; render(); playFromHand(o.id); }""")
        p.wait_for_timeout(500)
        t = modal_text()
        check('Outpost with two other lands: enters untapped and asks for its mode', not p.evaluate("() => !!window.__o.tap") and 'You gain 2 life.' in t and 'Surveil 1.' in t, t[:120])
        p.locator('#modal').get_by_text('You gain 2 life.').click(); p.wait_for_timeout(200)
        bt = p.locator('#modal button', has_text='Put it on the stack')
        if bt.count(): bt.first.click()
        p.wait_for_timeout(400)
        st = p.evaluate("() => G.me.st.map(x=>x.cu&&x.cu.o)")
        check('the chosen mode goes on the stack', st == ['You gain 2 life.'], str(st))
        p.evaluate("() => resolve(G.me.st[G.me.st.length-1].id)"); p.wait_for_timeout(600)
        check('…and resolves: +2 life', p.evaluate("() => G.me.life-window.__l") == 2)
        p.evaluate(RESET)
        p.evaluate("""() => { const o=mk(keyOf('federation outpost')); G.me.hand.push(o); window.__o=o; render(); playFromHand(o.id); }"""); p.wait_for_timeout(500)
        check('Outpost with no other lands: enters tapped, no trigger', p.evaluate("() => !!window.__o.tap && !G.me.st.length") and not modal_open())

        # ---- Firespout
        p.evaluate(RESET)
        p.evaluate("""() => { window.__g=mk(keyOf('thought-knot seer'),{o:oppId()}); window.__e=mk(keyOf('emrakul, the aeons torn'),{o:oppId()}); window.__k=mk(keyOf('kappa cannoneer')); window.__v=mk(keyOf('valgavoth, terror eater'));
            G.opp.bf.push(window.__g, window.__e); G.me.bf.push(window.__k, window.__v); const f=mk(keyOf('firespout')); G.me.hand.push(f); window.__f=f; render(); castSpellNow(f.id, {}); }""")
        p.wait_for_timeout(400)
        t = modal_text()
        check('Firespout cast without auto-pay asks which of {R} / {G} was spent', 'which mana did you spend' in t and '{R} and {G}' in t, t[:100])
        p.locator('#modal button', has_text='{G} only').click(); p.wait_for_timeout(300)
        check('…recorded on the spell', p.evaluate("() => window.__f.sp1") == ['G'])
        p.evaluate("() => resolve(window.__f.id)"); p.wait_for_timeout(1500)
        r = p.evaluate("() => [window.__g.dmg||0, window.__e.dmg||0, window.__k.dmg||0, window.__v.dmg||0]")
        check('{G} only: 3 to my flyer (Valgavoth), none to fliers with protection (Emrakul) or creatures without flying', r == [0, 0, 0, 3], str(r))
        p.evaluate("""() => { G.me.st=[]; G.me.gy=[]; [window.__g,window.__e,window.__k,window.__v].forEach(x=>delete x.dmg); const f=mk(keyOf('firespout')); G.me.hand.push(f); window.__f=f; render(); castSpellNow(f.id, {}); }""")
        p.wait_for_timeout(400); p.locator('#modal button', has_text='{R} only').click(); p.wait_for_timeout(300)
        p.evaluate("() => resolve(window.__f.id)"); p.wait_for_timeout(1500)
        r = p.evaluate("() => [window.__g.dmg||0, window.__e.dmg||0, window.__k.dmg||0, window.__v.dmg||0]")
        check('{R} only: 3 to each creature without flying (both sides), none to fliers', r == [3, 0, 3, 0], str(r))
        p.evaluate("""() => { S.autoPay=true; G.me.st=[]; G.me.gy=[]; const f=mk(keyOf('firespout')); G.me.hand.push(f); window.__f=f; G.me.mana=noMana(); G.me.mana.R=1; G.me.mana.C=2; render(); castSpell(f.id, {}); }""")
        p.wait_for_timeout(600)
        r = p.evaluate("() => [find(window.__f.id).z, window.__f.sp1]")
        check('auto-pay with {R} in the pool: cast without asking, {R} recorded as spent', r == ['st', ['R']] and not modal_open(), str(r))
        r = p.evaluate("() => { const f=mk(keyOf('firespout')); G.me.hand.push(f); castSpellNow(f.id, {nm:1}); return [find(f.id).z, f.sp1]; }")
        check('a free cast: nothing spent, no question', r == ['st', []] and not modal_open(), str(r))

        # ---- Valgavoth: graveyard replacement, playing the exiled cards, ward
        p.evaluate(RESET)
        r = p.evaluate("""() => { const v=mk(keyOf('valgavoth, terror eater'),{o:oppId()}); G.opp.bf.push(v); window.__v=v; const b=mk(keyOf('lightning bolt')); G.me.hand.push(b); move(b.id,'gy'); const t=mk(keyOf('thought-knot seer')); G.me.bf.push(t); move(t.id,'gy');
            const tk=mk(null,{tok:true, cu:{n:'Food', t:'Token Artifact — Food', o:''}}); G.me.bf.push(tk); move(tk.id,'gy');
            return [find(b.id).z, find(b.id).c.by && find(b.id).c.by.vg, find(b.id).c.by && find(b.id).c.by.pid===oppId(), find(t.id).z]; }""")
        check('opponent\'s Valgavoth: my cards going to my graveyard from anywhere are exiled with it instead', r == ['ex', 1, True, 'ex'], str(r))
        r = p.evaluate("""() => { G.opp.bf=[]; const v=mk(keyOf('valgavoth, terror eater')); G.me.bf.push(v); const b=mk(keyOf('lightning bolt')); G.me.hand.push(b); move(b.id,'gy'); return find(b.id).z; }""")
        check('my own Valgavoth doesn\'t exile my cards', r == 'gy', r)
        # a removal spell that kills the opponent's Valgavoth stays in my graveyard (resolution order)
        p.evaluate(RESET)
        p.evaluate("""() => { const v=mk(keyOf('valgavoth, terror eater'),{o:oppId()}); G.opp.bf.push(v); window.__v=v; G.me.bf.push(mk(keyOf('thought-knot seer')), mk(keyOf('kappa cannoneer')), mk(keyOf('ocelot pride')));
            const c=mk(keyOf('pawpatch formation')); G.me.hand.push(c); window.__p=c; render(); castSpellNow(c.id, {md:[1]}); }""")
        p.wait_for_timeout(300)
        r = p.evaluate("() => { const sp=tgtSpec(window.__p), t=mk(keyOf('thought-knot seer'),{o:oppId()}); G.opp.bf.push(t); const a=[tgtCheck(sp, window.__v.id).ok, tgtCheck(sp, t.id).ok]; G.opp.bf.pop(); return a; }")
        check('Pawpatch Formation\'s "target creature with flying" refuses a creature without flying', r == [True, False], str(r))
        p.evaluate("() => { G.mode=null; G.stSeen=new Set([window.__p.id+'>'+window.__v.id]); G.me.arrows.push({a:window.__p.id, b:window.__v.id}); resolve(window.__p.id); }"); p.wait_for_timeout(1200)
        r = p.evaluate("() => [(findAny(window.__v.id)||{}).z, (find(window.__p.id)||{}).z]")
        check('a removal spell that destroys the opponent\'s Valgavoth goes to the graveyard, not exile', r == ['gy', 'gy'], str(r))
        # countered while Valgavoth is still there: exiled at once
        p.evaluate(RESET)
        r = p.evaluate("""() => { const v=mk(keyOf('valgavoth, terror eater'),{o:oppId()}); G.opp.bf.push(v); const b=mk(keyOf('lightning bolt')); G.me.st.push(b); counterMine(b.id, false, 'Test'); return (find(b.id)||{}).z; }""")
        check('a countered spell of mine is exiled with the opponent\'s Valgavoth', r == 'ex', r)
        # exile box and casting for life (Practice needs a deck to hand the card over)
        p.evaluate(RESET)
        p.evaluate("async () => { await dummyDeck(parseDeck('60 Thought-Knot Seer'), 'Test'); }"); p.wait_for_timeout(800)
        p.evaluate("""() => { G.me.st=[]; G.opp.st=[]; const v=mk(keyOf('valgavoth, terror eater')); G.me.bf.push(v); window.__mv=v; const c=mk(keyOf('thought-knot seer'),{o:oppId()}); c.by={id:v.id, pid:G.myId, n:'Valgavoth, Terror Eater', mode:'play', vg:1}; G.opp.ex=[c]; window.__c=c; G.me.life=20; render(); }""")
        p.wait_for_timeout(300)
        box = p.evaluate("() => [...document.querySelectorAll('#offerwrap .offer')].map(e=>e.innerText.replace(/\\s+/g,' ')).join(' / ')")
        check('exile box: "may play it during their turn (pay 4 life)", button "Cast it (4 life)"', 'during their turn (pay 4 life)' in box and 'Cast it (4 life)' in box, box)
        p.locator('[data-take]').first.click(); p.wait_for_timeout(400)
        check('casting asks to pay life equal to its mana value', 'Pay 4 life' in modal_text(), modal_text()[:120])
        p.locator('#modal button', has_text='Pay 4 life').click(); p.wait_for_timeout(1500)
        r = p.evaluate("() => [G.me.life, (findAny(window.__c.id)||{}).z, (findAny(window.__c.id)||{}).mine]")
        check('…4 life paid, the card is on my stack', r == [16, 'st', True], str(r))
        p.evaluate("""() => { G.me.st=[]; const c=mk(keyOf('lightning bolt'),{o:oppId()}); c.by={id:window.__mv.id, pid:G.myId, n:'Valgavoth, Terror Eater', mode:'play', vg:1}; G.opp.ex=[c]; G.turn.active=oppId(); render(); }""")
        p.locator('[data-take]').first.click(); p.wait_for_timeout(400)
        t = modal_text()
        check('on the opponent\'s turn it warns (only during your turn) with a Play anyway', 'only during your turn' in t and 'Play anyway' in t, t[:160])
        p.locator('#modal button', has_text="Don't").click(); p.wait_for_timeout(200)
        r = p.evaluate("() => { const v=mk(keyOf('valgavoth, terror eater')); G.me.bf.push(v); G.turn.active=G.myId; const t=[]; return /You may play cards exiled with/i.test(frontText(v)) && !/pay life equal to its mana value/i.test(frontText(v)); }")
        check('Tibalt\'s "play cards exiled with" check doesn\'t take Valgavoth\'s text', r is False, str(r))
        # ward
        p.evaluate(RESET)
        r = p.evaluate("() => [wardOf(mk(keyOf('valgavoth, terror eater'))), wardOf(mk(keyOf('kappa cannoneer'))), wardOf(mk(keyOf('sire of seven deaths'))), wardOf(mk(keyOf('thought-knot seer'))), wardPhrase('Sacrifice three nonland permanents'), wardPhrase('{4}'), wardPhrase('Pay 7 life')]")
        check('ward costs read (Valgavoth, Kappa Cannoneer, Sire of Seven Deaths)', r == ['Sacrifice three nonland permanents', '{4}', 'Pay 7 life', None, 'sacrifices three nonland permanents', 'pays {4}', 'pays 7 life'], str(r))
        p.evaluate("""() => { G.me.bf=[mk(keyOf('thought-knot seer')), mk(keyOf('kappa cannoneer'))]; const v=mk(keyOf('valgavoth, terror eater'),{o:oppId()}); G.opp.bf=[v]; window.__v=v; const b=mk(keyOf('lightning bolt')); G.me.st.push(b); window.__b=b; G.me.arrows.push({a:b.id, b:v.id}); render(); }""")
        p.wait_for_timeout(800)
        check('my spell targets Practice\'s Valgavoth with only two nonland permanents: countered', p.evaluate("() => (find(window.__b.id)||{}).z") in ('gy', 'ex') and not modal_open(), p.evaluate(LOG, 3))
        p.evaluate("""() => { G.me.st=[]; G.me.gy=[]; G.me.ex=[]; G.me.bf=[mk(keyOf('thought-knot seer')), mk(keyOf('kappa cannoneer')), mk(keyOf('ocelot pride')), mk(keyOf("jetmir's garden"))]; const b=mk(keyOf('lightning bolt')); G.me.st.push(b); window.__b=b; G.me.arrows.push({a:b.id, b:window.__v.id}); render(); }""")
        p.wait_for_timeout(800)
        t = modal_text()
        check('with three: asked to sacrifice three nonland permanents (no log markup in the window)', 'sacrifice three nonland permanents' in t and '[[' not in t, t[:160])
        p.locator('#modal button', has_text='Sacrifice them').click(); p.wait_for_timeout(600)
        for _ in range(4):
            if not modal_open(): break
            p.locator('#modal .grid .card').first.click(); p.wait_for_timeout(300)
            bt = p.locator('#modal button.go')
            if modal_open() and bt.count(): bt.first.click(); p.wait_for_timeout(300)
        p.wait_for_timeout(400)
        r = p.evaluate("() => [(find(window.__b.id)||{}).z, G.me.bf.map(x=>cdata(x).n)]")
        check('…sacrificed, the spell stays on the stack, the land is kept', r == ['st', ["Jetmir's Garden"]], str(r))
        p.evaluate(RESET)
        p.evaluate("""() => { const k=mk(keyOf('kappa cannoneer')); G.me.bf.push(k); G.tgSeen=new Set(); G.tgSrc=new Set(); const ob=mk(keyOf('lightning bolt'),{o:oppId()}); window.__ob=ob;
            onMsg({t:'state', s:Object.assign({}, G.opp, {dummy:false, st:[ob], arrows:[{a:ob.id, b:k.id}]})}); }""")
        p.wait_for_timeout(600)
        r = p.evaluate("() => G.me.st.map(x=>[x.cu&&x.cu.o, x.ab&&x.ab.csp===window.__ob.id])")
        check('an opponent\'s spell targets my Kappa Cannoneer: ward {4} trigger on my stack, pointing at their spell', r == [['Counter that spell or ability unless its controller pays {4}.', True]], str(r))

        # ---- likely covered: tri-cycling lands, Mana Tithe, Pawpatch Formation
        p.evaluate(RESET)
        r = p.evaluate("""() => ["jetmir's garden","xander's lounge"].map(n=>{ const c=mk(keyOf(n)); G.me.bf.push(c); const r=[manaAbilities(c).map(a=>a.out).join(''), !!cyclingOf(c), (landEntry(c)||{}).kind]; G.me.bf.pop(); return r; })""")
        check('Jetmir\'s Garden / Xander\'s Lounge: three colours, cycling, enter tapped', r == [['RGW', True, 'tapped'], ['UBR', True, 'tapped']], str(r))
        p.evaluate("""() => { window.__h=G.me.hand.length; const c=mk(keyOf('pawpatch formation')); G.me.hand.push(c); window.__p=c; render(); castSpellNow(c.id, {md:[3]}); }""")
        p.wait_for_timeout(300); p.evaluate("() => resolve(window.__p.id)"); p.wait_for_timeout(1000)
        r = p.evaluate("() => [G.me.hand.length-window.__h, G.me.bf.map(x=>cdata(x).n+(x.tok?':tok':''))]")
        check('Pawpatch Formation, third mode: draws a card and makes a Food token', r == [1, ['Food:tok']], str(r))
        p.evaluate("""() => { G.me.st=[]; G.opp.st=[]; window.__sent=[]; const s0=send; send=(m)=>{ window.__sent.push(m); return s0(m); }; window.__s0=s0; const t=mk(keyOf('mana tithe')); G.me.st.push(t); const ob=mk(keyOf('lightning bolt'),{o:oppId()}); G.opp.st.push(ob); window.__t=t; window.__ob=ob; G.me.arrows.push({a:t.id, b:ob.id}); render(); resolve(t.id); }""")
        p.wait_for_timeout(1500)
        r = p.evaluate("() => { send=window.__s0; return window.__sent.filter(m=>m.t==='counter').map(m=>[m.id===window.__ob.id, m.pay]); }")
        check('Mana Tithe asks the opponent to pay {1} or have their spell countered', r == [[True, 1]], str(r))
        check('no page errors', not errs, str(errs[:3]))
        b.close()
finally:
    srv.terminate()
n = len(results); k = sum(1 for _, ok in results if not ok)
print(f'ALL PASS ({n}/{n})' if not k else f'SOME FAILED ({k}/{n})')
