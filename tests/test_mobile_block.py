"""The phone table's guided blocking (phone layer m0.6): a practice game on a phone held sideways (844 x 390, touch), Practice with a deck
and taking turns. Practice attacks by taps on its bar; then the strip and the big button guide my blocks: eligible blockers outlined, a tapped
blocker ringed (BLOCKER) with the attackers it can block outlined in blue, an illegal pair (a flyer) asks first, blocks ringed and tagged, blockers
grouped under their attackers, a tapped blocker takes its block back, Undo and Clear, Done blocking. Then I declare Practice's blocks against my
attack the same way."""
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
    for h in ['**/svgs.scryfall.io/**', '**/backs.scryfall.io/**', '**/fonts.googleapis.com/**', '**/fonts.gstatic.com/**', '**/gc.zgo.at/**', '**/*.metered.live/**']: ctx.route(h, lambda r: r.abort())
    ctx.route('**/api.scryfall.com/**', lambda r: r.fulfill(status=200, content_type='application/json', body='{"data":[]}'))
J = lambda p, js: p.evaluate(js)
ST = """() => { const nm=e=>e.id || (findAny(e.dataset.id) ? cdata(findAny(e.dataset.id).c).n : '?'), q=s=>[...document.querySelectorAll(s)].map(nm);
  const bl=(side)=>(side.arrows||[]).filter(a=>a.blk).map(a=>cdata(findAny(a.a).c).n+'>'+cdata(findAny(a.b).c).n);
  return {strip:document.querySelector('#mBlk').hidden ? null : document.querySelector('#mBlk').innerText, go:document.querySelector('#mBlkGo').hidden ? null : document.querySelector('#mBlkGo').innerText,
    ok:q('.mbok'), sel:q('.mbsel'), can:q('.mbcan'), on:q('.mbon'), atk:q('.mbatk'), tags:[...document.querySelectorAll('.mbtag')].map(e=>e.textContent),
    mine:bl(G.me), prac:bl(G.opp), my:q('#myFront .card[data-id]'), their:q('#oppFront .card[data-id]'), gaps:[...document.querySelectorAll('.mbgap')].length,
    modal:document.querySelector('#modal').hidden ? null : document.querySelector('#modal').innerText, cs:G.turn.cs, bar:!document.querySelector('#blockBar').hidden && getComputedStyle(document.querySelector('#blockBar')).display!=='none'}; }"""
try:
  with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={'width': 844, 'height': 390}, is_mobile=True, has_touch=True, device_scale_factor=2); block(ctx)
    p = ctx.new_page(); errs = []; p.on('pageerror', lambda e: errs.append(str(e)))
    p.goto(f'http://127.0.0.1:{PORT}/m/'); p.wait_for_timeout(800)
    J(p, "() => { const s=document.getElementById('spl'); if(s) s.remove(); }")
    p.tap('#soloBtn'); p.wait_for_timeout(700); p.locator('.drow').first.tap(); p.wait_for_timeout(400)
    p.get_by_role('button', name='Play this deck').tap(); p.wait_for_timeout(1500)
    p.get_by_role('button', name='Random deck').tap(); p.wait_for_timeout(600)
    check('v5.30: Practice brings a deck (seven cards in hand)', J(p, "() => !!G.opp.deckSpec && G.opp.hand.length===7"))
    p.get_by_role('button', name='Start the game').first.tap(); p.wait_for_timeout(700)
    p.tap('[data-first="deal"]'); p.wait_for_timeout(600); p.tap('[data-first="keep"]'); p.wait_for_timeout(800)
    if p.locator('#modal:not([hidden])').count(): J(p, "() => closeModal()")
    J(p, """() => { const add=(n,side,o,z='bf')=>{ const c=mk(keyOf(n),o); side[z].push(c); return c; };
      G.me.bf=[]; G.me.hand=[]; for(const n of ['Mountain','Mountain']) add(n,G.me,{});
      add('Walking Ballista',G.me,{c:2}); add('Thought-Knot Seer',G.me,{}); add('Ragavan, Nimble Pilferer',G.me,{}); add('Eyetwitch',G.me,{});
      G.opp.bf=[]; add('Mountain',G.opp,{o:oppId()}); add('Ragavan, Nimble Pilferer',G.opp,{o:oppId()}); add('Flickerwisp',G.opp,{o:oppId()}); add('Moonshadow',G.opp,{o:oppId()}); add('Thought-Knot Seer',G.opp,{o:oppId()});
      G.opp.turns=true; changed(); dummyTurnStart(G.turn.n+1); }""")
    p.wait_for_timeout(600)
    for _ in range(4):
        if J(p, "() => G.turn.phase===3"): break
        p.locator('#pracBar [data-prb="next"]').tap(); p.wait_for_timeout(400)
    check("Practice's turn reaches combat by taps on its bar", J(p, "() => G.turn.active===oppId() && G.turn.phase===3"), J(p, "() => [G.turn.active, G.turn.phase]"))
    p.locator('#pracBar [data-prb="choose"]').tap(); p.wait_for_timeout(300)
    def card(name, side='me', i=0):
        cid = J(p, f"() => G.{side}.bf.filter(c=>cdata(c).n.startsWith({name!r}))[{i}].id")
        return p.locator(f'.card[data-id="{cid}"]').first
    for n in ['Ragavan', 'Flickerwisp', 'Moonshadow']: card(n, 'opp').tap(); p.wait_for_timeout(250)
    p.locator('#pracBar [data-prb="go"]').tap(); p.wait_for_timeout(700)
    s = J(p, ST)
    check('Practice attacks with three; my blocks are guided: the strip, No blocks, the desktop bar hidden', s['cs'] == 'blk' and s['strip'] and 'Blocking' in s['strip'] and s['go'] == 'No blocks' and not s['bar'], s)
    check('my untapped creatures are outlined as possible blockers', sorted(s['ok']) == sorted(['Walking Ballista', 'Thought-Knot Seer', 'Ragavan, Nimble Pilferer', 'Eyetwitch']), s['ok'])
    geo = J(p, "() => { const g=document.querySelector('#mBlkGo').getBoundingClientRect(), n=document.querySelector('#next').getBoundingClientRect(); return Math.abs(g.left-n.left)<2 && Math.abs(g.top-n.top)<2; }")
    check('the Done button sits over the big button', geo)
    card('Thought-Knot').tap(); p.wait_for_timeout(300); s = J(p, ST)
    check('tapping a creature chooses it as a blocker (BLOCKER); the attackers it can block get a blue outline, not the flyer', s['sel'] == ['Thought-Knot Seer'] and 'BLOCKER' in s['tags'] and sorted(s['can']) == ['Moonshadow', 'Ragavan, Nimble Pilferer'] and 'Thought-Knot Seer' in s['strip'], s)
    card('Flickerwisp', 'opp').tap(); p.wait_for_timeout(300); s = J(p, ST)
    check('tapping the flyer asks first (Pick another / Block anyway)', s['modal'] and 'flying' in s['modal'] and 'Block anyway' in s['modal'] and not s['mine'], s['modal'])
    p.get_by_role('button', name='Pick another').tap(); p.wait_for_timeout(300)
    card('Ragavan', 'opp').tap(); p.wait_for_timeout(120)
    hid = J(p, "() => document.querySelector('#arrowG').style.opacity")
    p.wait_for_timeout(600)
    ARW = """() => { const b=G.me.bf.find(c=>cdata(c).n==='Thought-Knot Seer'), a=anchor(b.id), ps=[...document.querySelectorAll('#arrowG path')].map(x=>x.getAttribute('d').match(/^M([\\d.-]+) ([\\d.-]+)/)).filter(Boolean).map(m=>[+m[1],+m[2]]);
      return {a, ps, ok:ps.some(q=>Math.hypot(q[0]-a[0], q[1]-a[1])<4), op:document.querySelector('#arrowG').style.opacity}; }"""
    aw = J(p, ARW)
    check('m0.7: while the blocker slides into its group the arrows are hidden', hid == '0', hid)
    check('m0.7: once it has settled, its block arrow starts from where the blocker is now (not its old spot), and the arrows show again', aw['ok'] and aw['op'] == '', aw)
    s = J(p, ST)
    check('tapping Ragavan blocks it: the blocker tagged BLOCKS, the attacker ringed blue and BLOCKED, Done blocking (1)', s['mine'] == ['Thought-Knot Seer>Ragavan, Nimble Pilferer'] and s['on'] == ['Thought-Knot Seer'] and s['atk'] == ['Ragavan, Nimble Pilferer'] and 'BLOCKED' in s['tags'] and s['go'] == 'Done blocking (1)', s)
    check('the blocker moves to the front of my row, apart from the creatures not blocking', s['my'][0] == 'Thought-Knot Seer' and s['gaps'] >= 2, s['my'])
    card('Walking').tap(); p.wait_for_timeout(250); card('Ragavan', 'opp').tap(); p.wait_for_timeout(500); s = J(p, ST)
    check('a second blocker on Ragavan: the two sit side by side, BLOCKED ×2', len(s['mine']) == 2 and set(s['my'][:2]) == {'Thought-Knot Seer', 'Walking Ballista'} and 'BLOCKED ×2' in s['tags'], s)
    card('Eyetwitch').tap(); p.wait_for_timeout(250); card('Flickerwisp', 'opp').tap(); p.wait_for_timeout(500); s = J(p, ST)
    check('Eyetwitch (flying) blocks Flickerwisp without a question', len(s['mine']) == 3 and not s['modal'] and 'Eyetwitch>Flickerwisp' in s['mine'], s)
    check('groups follow the attackers\' order', s['my'].index('Eyetwitch') > s['my'].index('Walking Ballista') if J(p, "() => { const o=[...document.querySelectorAll('#oppFront .card[data-id]')].map(e=>cdata(findAny(e.dataset.id).c).n); return o.indexOf('Ragavan, Nimble Pilferer') < o.indexOf('Flickerwisp'); }") else s['my'].index('Eyetwitch') < s['my'].index('Walking Ballista'), s['my'])
    card('Walking').tap(); p.wait_for_timeout(400); s = J(p, ST)
    check('tapping a blocker takes its block back', len(s['mine']) == 2 and not any(x.startswith('Walking') for x in s['mine']), s['mine'])
    p.locator('#mBlk [data-mb="undo"]').tap(); p.wait_for_timeout(400); s = J(p, ST)
    check('Undo puts it back', len(s['mine']) == 3, s['mine'])
    p.locator('#mBlk [data-mb="clear"]').tap(); p.wait_for_timeout(400); s = J(p, ST)
    check('Clear takes every block back; the row is back in its usual order', s['mine'] == [] and s['go'] == 'No blocks' and s['gaps'] == 0, s)
    p.locator('#mBlk [data-mb="undo"]').tap(); p.wait_for_timeout(400)
    p.locator('#mBlkGo').tap(); p.wait_for_timeout(500); s = J(p, ST)
    check('Done blocking ends the step (blocks kept), the strip goes', s['cs'] == 'blkd' and len(s['mine']) == 3 and s['strip'] is None and s['go'] is None, s)
    p.locator('#pracBar [data-prb="dmg"]').tap(); p.wait_for_timeout(800)
    sp = J(p, "() => document.querySelector('#modal').hidden ? null : document.querySelector('#modal').innerText")
    check('v5.30: the damage split for Ragavan (two blockers) names the cards plainly', sp and 'Ragavan, Nimble Pilferer: assign' in sp and '[[' not in sp, sp)
    if sp: p.get_by_role('button', name='Assign').tap(); p.wait_for_timeout(800)
    for _ in range(3):
        if J(p, "() => document.querySelector('#modal').hidden"): break
        bts = p.locator('#modal footer button.go')
        if bts.count(): bts.last.tap(); p.wait_for_timeout(500)
        else: break
    check("Practice's combat damage: unblocked Moonshadow hits me", J(p, "() => G.me.life < 20"), J(p, "() => G.me.life"))
    # Practice's blocks against my attack
    J(p, """() => { G.me.arrows=[]; G.opp.arrows=[]; for(const c of [...G.me.bf, ...G.opp.bf]){ c.atk=false; c.tap=false; c.dmg=0; }
      for(const c of G.me.bf) if(isCreature(c)) c.sick=false;
      G.turn=Object.assign({}, G.turn, {n:G.turn.n+1, active:G.myId, phase:3, cs:'blk'}); for(const c of G.me.bf) if(/Ragavan|Ballista/.test(cdata(c).n)){ c.atk=true; c.tap=true; } changed(); }""")
    p.wait_for_timeout(500); s = J(p, ST)
    check("my attack: Practice's blocks are guided too", s['strip'] and 'Practice blocks' in s['strip'] and set(s['ok']) == set(J(p, "() => G.opp.bf.filter(c=>isCreature(c) && !c.tap).map(c=>cdata(c).n)")) and 'Thought-Knot Seer' in s['ok'], s)
    card('Thought-Knot', 'opp').tap(); p.wait_for_timeout(250); card('Walking', 'me').tap(); p.wait_for_timeout(500); s = J(p, ST)
    check("Practice's Thought-Knot Seer blocks my Ballista, and moves to the front of its row", s['prac'] == ['Thought-Knot Seer>Walking Ballista'] and s['their'][0] == 'Thought-Knot Seer', s)
    p.locator('#mBlkGo').tap(); p.wait_for_timeout(500)
    check('Done blocking for Practice ends its step', J(p, "() => G.turn.cs==='blkd'"))
    check('no page errors', not errs, errs[:3])
    b.close()
finally:
    srv.kill()
print("ALL PASS" if res and all(res) else "SOME FAILED", f"({sum(res)}/{len(res)})"); sys.exit(0 if all(res) else 1)
