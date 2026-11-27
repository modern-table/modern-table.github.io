"""v5.45 (the maintainer, 2026-11-24 and 11-26): the tour becomes three tours.
1. Getting started (front page link): the front page and the deck screen, then a practice game with the deck chosen; its last card offers
   How to play. Open tables (the mode buttons, List my table) are named on the Open a table step.
2. How to play (front page link, ☰ Take the tour, the help page): a staged board, turn 3, the tour-only Boros Aggro against Practice's UR Aggro,
   with live beats: a land played, Ocelot Pride through the payment window, Guide of Souls' trigger, Practice's Lightning Bolt with the blue OK
   (staged), an attack, Practice's block, Ragavan's damage trigger and the Exiled by cards box. At a practice game already under way it asks
   first; walking the table instead never changes the game.
3. The deck editor tour, from "Tour the deck editor" on the deck screen."""
import os, socket, subprocess, sys, time
from playwright.sync_api import sync_playwright
ROOT = os.environ.get('MT_ROOT') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def _free_port():
    s = socket.socket(); s.bind(('127.0.0.1', 0)); p = s.getsockname()[1]; s.close(); return p
PORT = _free_port()
srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(PORT), '--bind', '127.0.0.1'], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(0.8); res = []
def check(n, c, e=''): res.append(bool(c)); print('PASS' if c else 'FAIL', n, e)
SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="488" height="680"><rect width="488" height="680" rx="24" fill="#3b4a3f"/></svg>'
def block(ctx):
    ctx.route('**/cards.scryfall.io/**', lambda r: r.fulfill(status=200, content_type='image/svg+xml', body=SVG))
    for h in ['**/svgs.scryfall.io/**', '**/backs.scryfall.io/**', '**/fonts.googleapis.com/**', '**/fonts.gstatic.com/**', '**/gc.zgo.at/**', '**/*.metered.live/**', '**/*.workers.dev/**']: ctx.route(h, lambda r: r.abort())
    ctx.route('**/api.scryfall.com/**', lambda r: r.fulfill(status=200, content_type='application/json', body='{"data":[]}'))
J = lambda p, js, *a: p.evaluate(js, *a)
CARD = "() => TOUR ? {t:(document.querySelector('#tourCard h4')||{}).textContent, b:[...document.querySelectorAll('#tourCard button')].map(b=>b.textContent), from:TOUR.from, n:TOUR.list.length, i:TOUR.i} : null"
ST = """() => ({ph:G.turn.phase, n:G.turn.n, life:G.me.life, olife:G.opp && G.opp.life, en:G.me.ctr.energy, st:G.me.st.map(c=>cdata(c).n), ost:((G.opp&&G.opp.st)||[]).map(c=>cdata(c).n),
  hand:G.me.hand.map(c=>cdata(c).n), bf:G.me.bf.map(c=>cdata(c).n+(c.tap?'*':'')), obf:((G.opp&&G.opp.bf)||[]).map(c=>cdata(c).n), deck:G.me.deck, odeck:G.opp&&G.opp.deck,
  btn:document.querySelector('#next').textContent, ok:document.querySelector('#next').classList.contains('ok'), pay:!document.querySelector('#payPanel').hidden,
  oex:((G.opp&&G.opp.ex)||[]).filter(c=>c.offer).map(c=>cdata(c).n), offers:document.querySelectorAll('#offers [data-take]').length, arrows:((G.opp&&G.opp.arrows)||[]).length,
  hole:(()=>{ const h=document.querySelector('#tourHole'); return h ? h.getBoundingClientRect().width : -1; })(), log:[...document.querySelectorAll('#log > *')].map(e=>e.innerText).slice(-4)})"""
def nxt(p, wait=1300):
    p.click('#tourCard [data-tr=next]'); p.wait_for_timeout(wait)
def front(p):
    p.goto(f'http://127.0.0.1:{PORT}/'); p.wait_for_timeout(900)
    J(p, "() => { const s=document.getElementById('spl'); if(s) s.remove(); }")
try:
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        ctx = br.new_context(viewport={'width': 1500, 'height': 900}); block(ctx); p = ctx.new_page()
        errs = []; p.on('pageerror', lambda e: errs.append(str(e)))
        front(p)
        tl = J(p, "() => { const t=document.querySelector('#tourLine'); return {shown:!t.hidden, txt:t.innerText, links:[...t.querySelectorAll('a')].map(a=>a.id)}; }")
        check('the front page offers both tours: Getting started and How to play', tl['shown'] and tl['links'] == ['tourLink', 'tourPlayLink'] and 'Getting started' in tl['txt'] and 'How to play' in tl['txt'], tl)
        # ---- 1. Getting started
        p.click('#tourLink'); p.wait_for_timeout(900)
        seen = []; c = J(p, CARD)
        for _ in range(16):
            c = J(p, CARD)
            if not c or c['t'] == "You're at the table": break
            seen.append(c['t']); nxt(p)
        check('Getting started walks the front page and the deck screen', seen[:2] == ['Getting started', 'Your name'] and 'Open a table' in seen and 'Choose your deck' in seen and 'Look before you play' in seen, seen)
        check('it has no deck-editor steps (those are their own tour)', not any(x in seen for x in ['Add a card', 'Change the counts', 'Save and play']), seen)
        s = J(p, ST)
        check('it ends at a practice table, the game started with a tournament deck and a hand of seven', c and c['t'] == "You're at the table" and s['n'] == 1 and len(s['hand']) == 7 and s['deck'], (c, s['n'], len(s['hand']), s['deck']))
        check('its last card offers How to play', c and 'How to play' in c['b'] and 'Done' in c['b'], c)
        p.click('#tourCard [data-tr=play]'); p.wait_for_timeout(3500)
        c = J(p, CARD); s = J(p, ST)
        check('How to play from there stages the board: turn 3, Boros Aggro against UR Aggro', c and c['from'] == 'play' and c['t'] == 'How to play' and s['n'] == 3 and s['ph'] == 2 and s['deck'] == 'Boros Aggro' and s['odeck'] == 'UR Aggro', (c, s['n'], s['deck'], s['odeck']))
        check('the staged board: two lands, Ragavan and Guide of Souls; Practice two lands, Swiftspear and DRC', sorted(s['bf']) == sorted(['Sacred Foundry', 'Plains', 'Ragavan, Nimble Pilferer', 'Guide of Souls']) and sorted(s['obf']) == sorted(['Steam Vents', 'Mountain', 'Monastery Swiftspear', "Dragon's Rage Channeler"]), (s['bf'], s['obf']))
        check('and a hand with a land and Ocelot Pride, life 18 to 16, no game-start box', 'Snow-Covered Mountain' in s['hand'] and 'Ocelot Pride' in s['hand'] and s['life'] == 18 and s['olife'] == 16 and J(p, "() => document.querySelector('#banner').hidden"), s)
        # ---- 2. How to play's beats
        steps = {}
        for _ in range(30):
            c = J(p, CARD)
            if not c: break
            steps[c['t']] = J(p, ST)
            if c['t'] == 'Your turn': steps['_last'] = c; break
            nxt(p)
        g = lambda t: steps.get(t) or {}
        check('Playing a land: Snow-Covered Mountain went onto the battlefield', 'Snow-Covered Mountain' in g('Playing a land').get('bf', []) and 'Snow-Covered Mountain' not in g('Playing a land').get('hand', ['Snow-Covered Mountain']), g('Playing a land').get('bf'))
        check('Paying for a spell: the payment window is open for Ocelot Pride and spotlighted', g('Paying for a spell').get('pay') and g('Paying for a spell').get('hole', 0) > 50 and 'Ocelot Pride' in g('Paying for a spell').get('hand', []), {k:g('Paying for a spell').get(k) for k in ['pay','hole','hand']})
        check('The stack: Plains tapped, Ocelot Pride on the stack', g('The stack').get('st') == ['Ocelot Pride'] and 'Plains*' in g('The stack').get('bf', []) and not g('The stack').get('pay'), g('The stack'))
        check("Triggers: Ocelot Pride entered and Guide of Souls' trigger is on the stack", g('Triggers').get('st') == ['Guide of Souls: trigger'] and 'Ocelot Pride' in g('Triggers').get('bf', []), g('Triggers').get('st'))
        check('You: the trigger gave 1 life and an energy', g('You').get('life') == 19 and g('You').get('en') == 1 and g('You').get('st') == [], g('You'))
        check("Your OK: Practice's Lightning Bolt on its stack, aimed at me, and the big button blue with OK", g('Your OK').get('ost') == ['Lightning Bolt'] and g('Your OK').get('ok') and g('Your OK').get('btn') == 'OK: Lightning Bolt resolves' and g('Your OK').get('arrows') == 1, g('Your OK'))
        check('Game log: the Bolt resolved for 3, the button is back to normal', g('Game log and chat').get('life') == 16 and g('Game log and chat').get('ost') == [] and not g('Game log and chat').get('ok') and any('Lightning Bolt deals 3 damage' in l for l in g('Game log and chat').get('log', [])), g('Game log and chat'))
        check('Attacking: combat, Ragavan and Guide of Souls tapped as attackers', g('Attacking').get('ph') == 3 and 'Ragavan, Nimble Pilferer*' in g('Attacking').get('bf', []) and 'Guide of Souls*' in g('Attacking').get('bf', []), g('Attacking').get('bf'))
        check('Blocking: Swiftspear blocks Guide of Souls, the button goes to damage', 'combat damage' in g('Blocking').get('btn', '') and any('Swiftspear' in l and 'blocks' in l for l in g('Blocking').get('log', [])), (g('Blocking').get('btn'), g('Blocking').get('log')))
        check("Combat damage: Ragavan hit for 2 and its trigger is on the stack", g('Combat damage').get('olife') == 14 and g('Combat damage').get('st') == ['Ragavan: combat damage trigger'], g('Combat damage'))
        check('Exiled by cards: a Treasure, and the exiled card offered in the box', 'Treasure' in g('Exiled by cards').get('bf', []) and len(g('Exiled by cards').get('oex', [])) == 1 and g('Exiled by cards').get('offers') == 1, {k:g('Exiled by cards').get(k) for k in ['oex','offers','bf']})
        last = steps.get('_last')
        check('the last card offers Practice with my own deck', last and 'Practice with my own deck' in last['b'] and 'Done' in last['b'], last)
        check('the turn menu, the turn, the big button and tools are covered on the way', all(t in steps for t in ['The turn menu', 'The turn', 'The big button', 'Tools', 'Nothing is final', 'The table menu']), list(steps))
        # Back doesn't run a beat twice
        p.click('#tourCard [data-tr=back]'); p.wait_for_timeout(700); p.click('#tourCard [data-tr=next]'); p.wait_for_timeout(700)
        s = J(p, ST)
        check('going Back and forward again changes nothing', s['life'] == 16 and s['olife'] == 14 and s['bf'].count('Treasure') == 1, s)
        p.click('#tourCard [data-tr=decks]'); p.wait_for_timeout(900)
        s = J(p, ST)
        check('Practice with my own deck starts a fresh practice game at the deck screen', not J(p, '() => !!TOUR') and J(p, "() => !document.querySelector('#decks').hidden") and s['n'] == 0 and not s['deck'], (s['n'], s['deck']))
        # ---- a practice game under way: ☰ Take the tour asks first; walking the table changes nothing
        p.locator('#tabBody [data-d]').first.click(); p.wait_for_timeout(500); p.get_by_role('button', name='Play this deck').click(); p.wait_for_timeout(1500)
        bt = p.get_by_role('button', name='Random deck')
        if bt.count(): bt.first.click(); p.wait_for_timeout(500)
        J(p, "() => { closeModal(); G.me.kept=G.me.dealt=true; takeFirst(G.myId); }"); p.wait_for_timeout(400)
        before = J(p, "() => [G.me.deck, G.turn.n, G.me.hand.length, G.me.lib.length]")
        p.click('#menuBtn'); p.wait_for_timeout(300); p.locator('#ctx button', has_text='Take the tour').click(); p.wait_for_timeout(500)
        m = J(p, "() => document.querySelector('#modal').hidden ? '' : document.querySelector('#modal').innerText")
        check('☰ Take the tour in a practice game under way asks before replacing it', 'in place of this practice game' in m and 'Walk this table instead' in m and 'Set it up' in m, m[:160])
        p.click('#modal button:has-text("Walk this table instead")'); p.wait_for_timeout(700)
        c = J(p, CARD); t = []
        for _ in range(25):
            c = J(p, CARD)
            if not c: break
            t.append(c['t']); nxt(p, 350)
        after = J(p, "() => [G.me.deck, G.turn.n, G.me.hand.length, G.me.lib.length]")
        check('walking the table goes to its end, with Passing priority after The big button', 'Passing priority' in t and t.index('Passing priority') == t.index('The big button') + 1 and not J(p, '() => !!TOUR'), t)
        check('and leaves the practice game exactly as it was', before == after, (before, after))
        # the help page's Take the tour: the same question
        J(p, '() => helpModal()'); p.wait_for_timeout(300); p.locator('#modal button', has_text='Take the tour').click(); p.wait_for_timeout(500)
        m = J(p, "() => document.querySelector('#modal').hidden ? '' : document.querySelector('#modal').innerText")
        check("the help page's Take the tour opens How to play the same way", 'in place of this practice game' in m, m[:100])
        J(p, '() => closeModal()')
        # ---- 3. the deck editor tour
        J(p, '() => showDecks()'); p.wait_for_timeout(500); p.locator('#tabBody [data-d]').first.click(); p.wait_for_timeout(500)
        check('the deck screen has Tour the deck editor beside Modify this deck', p.locator('#edTourLink').count() == 1 and p.locator('#edTourLink').is_visible())
        p.click('#edTourLink'); p.wait_for_timeout(700)
        et = []; opened = False
        for _ in range(8):
            c = J(p, CARD)
            if not c: break
            et.append(c['t']); opened = opened or J(p, "() => !!document.querySelector('#edQ')"); nxt(p, 700)
        check('the deck editor tour opens the editor and walks it', et[:4] == ['The deck editor', 'Add a card', 'Change the counts', 'Save and play'] and opened, et)
        check('and closes the editor at the end, back on the deck screen', not J(p, "() => !!document.querySelector('#edQ')") and J(p, "() => !document.querySelector('#decks').hidden"))
        # ---- How to play straight from the front page
        front(p)
        J(p, "() => document.querySelector('#tourPlayLink').click()"); p.wait_for_timeout(3500)
        s = J(p, ST); c = J(p, CARD)
        check('How to play from the front page goes straight to the staged board', c and c['t'] == 'How to play' and s['n'] == 3 and s['deck'] == 'Boros Aggro' and J(p, "() => !document.querySelector('#table').hidden"), (c, s['n']))
        J(p, '() => tourEnd()'); p.wait_for_timeout(300)
        check('ending it early leaves a normal button (no staged OK)', not J(p, "() => document.querySelector('#next').classList.contains('ok')") and J(p, '() => G.okDemo') is None)
        check('NEWS has the line', J(p, "() => NEWS[0][0] === VERSION && /Getting started/.test(NEWS[0][2]) && /How to play/.test(NEWS[0][2]) && /deck editor/.test(NEWS[0][2])"))
        check('no page errors', not errs, errs[:3])
        br.close()
finally:
    srv.terminate()
print('ALL PASS' if all(res) else 'SOME FAILED', f'({sum(res)}/{len(res)})')
sys.exit(0 if all(res) else 1)
