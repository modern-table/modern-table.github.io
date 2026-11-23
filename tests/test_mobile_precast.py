"""The phone table, phone layer m0.8: a practice game on a phone held sideways (844 x 390, touch).
1. The city's blessing shows in the left rail (it had slid under my piles: the desktop's fit rule measured too little on a phone).
2. Targets before paying (the maintainer's prototype): tapping Lightning Bolt doesn't pay; it waits in the stack column as CASTING, the strip
   says what to tap, legal targets are outlined, a tap rings one and draws a line, another moves it, Cancel puts the card back. Cast it pays
   (the payment window while the mana isn't there) and puts the spell on the stack with its target, without the m0.5 screen. Fatal Push's
   illegal target asks first, Cast it with none asks first. A creature spell still casts at once; Counterspell targets a spell on the stack."""
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
ST = """() => { const s=document.querySelector('#mTgt'), g=document.querySelector('#mTgtGo'), nm=e=>e.id || (findAny(e.dataset.id) ? cdata(findAny(e.dataset.id).c).n : '?');
  const tn=b=>b==='p1'||b==='p2' ? b : cdata(findAny(b).c).n;
  return {pre:typeof M!=='undefined' && M.pre ? M.pre.arr.map(a=>tn(a.b)) : null, mode:!!G.mode, strip:s.hidden ? null : s.innerText, go:g.hidden ? null : g.innerText,
    mtl:[...document.querySelectorAll('.mtl')].map(nm), mtc:[...document.querySelectorAll('.mtc')].map(nm), tags:[...document.querySelectorAll('.mttag')].map(e=>e.textContent),
    cast:!!document.querySelector('#stack .mcast'), lines:document.querySelectorAll('#mPreArw path').length, hand:G.me.hand.map(c=>cdata(c).n), st:G.me.st.map(c=>cdata(c).n),
    arrows:G.me.arrows.map(a=>cdata(findAny(a.a).c).n+'>'+tn(a.b)), pay:typeof PAY!=='undefined' && !!PAY,
    modal:document.querySelector('#modal').hidden ? null : document.querySelector('#modal').innerText }; }"""
def card(p, name, side='opp', i=0):
    cid = J(p, f"() => G.{side}.bf.filter(c=>cdata(c).n.startsWith({name!r}))[{i}].id")
    return p.locator(f'.card[data-id="{cid}"]').first
def hand(p, name):
    p.tap('#mHandBtn'); p.wait_for_timeout(300)
    cid = J(p, f"() => G.me.hand.find(c=>cdata(c).n.startsWith({name!r})).id")
    p.locator(f'#myHand .card[data-id="{cid}"]').tap(); p.wait_for_timeout(600)
try:
  with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={'width': 844, 'height': 390}, is_mobile=True, has_touch=True, device_scale_factor=2); block(ctx)
    p = ctx.new_page(); errs = []; p.on('pageerror', lambda e: errs.append(str(e)))
    p.goto(f'http://127.0.0.1:{PORT}/m/'); p.wait_for_timeout(800)
    J(p, "() => { const s=document.getElementById('spl'); if(s) s.remove(); }")
    p.tap('#soloBtn'); p.wait_for_timeout(700); p.locator('.drow').first.tap(); p.wait_for_timeout(400)
    p.get_by_role('button', name='Play this deck').tap(); p.wait_for_timeout(1500)
    bt = p.get_by_role('button', name='Random deck')
    if bt.count(): bt.first.tap(); p.wait_for_timeout(500)
    p.get_by_role('button', name='Start the game').first.tap(); p.wait_for_timeout(700)
    p.tap('[data-first="deal"]'); p.wait_for_timeout(600); p.tap('[data-first="keep"]'); p.wait_for_timeout(800)
    if p.locator('#modal:not([hidden])').count(): J(p, "() => closeModal()")
    # 1. the city's blessing
    J(p, "() => { G.me.city=true; render(); }"); p.wait_for_timeout(400)
    geo = J(p, """() => { const r=s=>document.querySelector(s).getBoundingClientRect(), c=r('#cityBox'), w=r('#winsBox'), mp=r('#myPiles'), op=r('#oppPiles'), L=r('#left');
      return {city:[c.top,c.bottom], wins:[w.top,w.bottom], my:mp.top, opp:op.bottom, left:L.bottom, shown:!document.querySelector('#cityBox').hidden && c.height>20}; }""")
    check("the city's blessing shows in the left rail, between the piles (not under mine)", geo['shown'] and geo['city'][0] >= geo['opp'] - 1 and geo['city'][1] <= geo['my'] + 1 and geo['wins'][0] >= geo['opp'] - 1, geo)
    check("the city's blessing names its player", 'CITY' in J(p, "() => document.querySelector('#cityBox').innerText"), J(p, "() => document.querySelector('#cityBox').innerText"))
    J(p, "() => { G.me.city=false; render(); }")
    # 2. targets before paying
    J(p, """() => { const add=(n,side,o,z='bf')=>{ const c=mk(keyOf(n),o); side[z].push(c); return c; };
      G.me.bf=[]; G.me.hand=[]; G.me.mana=noMana(); for(const n of ['Mountain','Mountain','Swamp','Island','Island']) add(n,G.me,{});
      G.opp.bf=[]; add('Mountain',G.opp,{o:oppId()}); add('Ragavan, Nimble Pilferer',G.opp,{o:oppId()}); add('Thought-Knot Seer',G.opp,{o:oppId()}); add('Expedition Map',G.opp,{o:oppId()});
      for(const n of ['Lightning Bolt','Fatal Push','Counterspell','Ragavan, Nimble Pilferer']) add(n,G.me,{},'hand'); changed(); }""")
    p.wait_for_timeout(500)
    hand(p, 'Lightning Bolt'); s = J(p, ST)
    check('tapping Lightning Bolt chooses targets first: no payment, the card still in hand, CASTING in the stack column', s['pre'] == [] and not s['pay'] and 'Lightning Bolt' in s['hand'] and s['cast'] and not s['st'], s)
    check('the strip names it, says what to tap and has Cancel; the big button reads Cast it with the cost', s['strip'] and 'Lightning Bolt' in s['strip'] and 'any target' in s['strip'] and 'Cancel' in s['strip'] and s['go'] and s['go'].startswith('Cast it') and 'pay' in s['go'], [s['strip'], s['go']])
    check('legal targets are outlined: both players and both creatures, not the artifact', set(s['mtl']) == {'oppAv', 'myAv', 'Ragavan, Nimble Pilferer', 'Thought-Knot Seer'}, s['mtl'])
    card(p, 'Ragavan').tap(); p.wait_for_timeout(400); s = J(p, ST)
    check('tapping Ragavan rings it (TARGET) and draws a line from the card', s['pre'] == ['Ragavan, Nimble Pilferer'] and s['mtc'] == ['Ragavan, Nimble Pilferer'] and s['tags'] == ['TARGET'] and s['lines'] == 1, s)
    p.screenshot(path=os.environ.get('SHOT', '/tmp/precast.png'))
    p.locator('#oppAv').tap(); p.wait_for_timeout(400); s = J(p, ST)
    check('tapping the opponent moves the target to them', s['pre'] == [J(p, '() => oppId()')] and 'oppAv' in s['mtc'] and s['lines'] == 1, s)
    p.locator('#mHandBtn').tap(); p.wait_for_timeout(300); p.locator('#myHand .card').first.tap(); p.wait_for_timeout(300)
    check('another hand card is held off while choosing', J(p, "() => !!M.pre && G.me.st.length===0"))
    J(p, "() => { tray(false); }")
    p.locator('#mTgt [data-mpre="x"]').tap(); p.wait_for_timeout(400); s = J(p, ST)
    check('Cancel puts it back: no strip, no CASTING, Bolt in hand, no arrows', s['pre'] is None and s['strip'] is None and s['go'] is None and not s['cast'] and 'Lightning Bolt' in s['hand'] and not s['arrows'] and s['lines'] == 0, s)
    hand(p, 'Lightning Bolt'); card(p, 'Thought-Knot').tap(); p.wait_for_timeout(300)
    p.locator('#mTgtGo').tap(); p.wait_for_timeout(700); s = J(p, ST)
    check('Cast it without the mana opens the payment window; still no stack screen', s['pay'] and s['pre'] is None and not s['mode'] and s['go'] is None, s)
    mid = J(p, "() => G.me.bf.find(c=>cdata(c).n==='Mountain' && !c.tap).id")
    p.locator(f'#mLands .card[data-id="{mid}"]').tap(); p.wait_for_timeout(450)
    p.locator('#payPanel button:has-text("and cast")').first.tap(); p.wait_for_timeout(800); s = J(p, ST)
    check('paid: Bolt is on the stack aimed at Thought-Knot Seer, and the m0.5 targeting screen does not open', s['st'] == ['Lightning Bolt'] and 'Lightning Bolt>Thought-Knot Seer' in s['arrows'] and not s['mode'] and s['strip'] is None and not s['pay'], s)
    check('the log says what it targets', J(p, "() => [...document.querySelectorAll('#log *')].some(e=>/Lightning Bolt targets Thought-Knot Seer/.test(e.textContent))"))
    # Counterspell targets the spell on the stack
    J(p, "() => { G.me.mana.U=2; changed(); }"); p.wait_for_timeout(200)
    hand(p, 'Counterspell'); s = J(p, ST)
    check('Counterspell outlines the spell on the stack', s['pre'] == [] and s['mtl'] == ['Lightning Bolt'], s['mtl'])
    p.locator('#stack .card[data-z="st"]').first.tap(); p.wait_for_timeout(300); p.locator('#mTgtGo').tap(); p.wait_for_timeout(800); s = J(p, ST)
    check('Counterspell is cast aimed at Lightning Bolt', s['st'][-1:] == ['Counterspell'] and 'Counterspell>Lightning Bolt' in s['arrows'] and not s['mode'], s)
    J(p, "() => { G.me.st=[]; G.me.arrows=[]; changed(); }"); p.wait_for_timeout(300)
    # Fatal Push: none chosen asks, an illegal one asks
    J(p, "() => { G.me.mana.B=1; changed(); }"); p.wait_for_timeout(200)
    hand(p, 'Fatal Push'); p.locator('#mTgtGo').tap(); p.wait_for_timeout(300); s = J(p, ST)
    check('Cast it with no target asks first (Choose a target / Cast it anyway)', s['modal'] and 'no target' in s['modal'].lower() and 'Cast it anyway' in s['modal'], s['modal'])
    p.get_by_role('button', name='Choose a target').tap(); p.wait_for_timeout(300)
    card(p, 'Thought-Knot').tap(); p.wait_for_timeout(400); s = J(p, ST)
    check("Fatal Push on Thought-Knot Seer (mana value 4) asks first", bool(s['modal']) and ('Fatal Push' in s['modal']), s['modal'])
    p.get_by_role('button', name='Pick another target').tap(); p.wait_for_timeout(300)
    card(p, 'Ragavan').tap(); p.wait_for_timeout(300); p.locator('#mTgtGo').tap(); p.wait_for_timeout(800); s = J(p, ST)
    check('Fatal Push is cast at Ragavan (the mana was in the pool: no window)', s['st'] == ['Fatal Push'] and 'Fatal Push>Ragavan, Nimble Pilferer' in s['arrows'] and not s['pay'], s)
    p.locator('#stack .card[data-z="st"]').first.tap(); p.wait_for_timeout(700)
    check('it resolves: Ragavan is destroyed', J(p, "() => !G.opp.bf.some(c=>cdata(c).n.startsWith('Ragavan'))"))
    # a creature spell keeps casting at once
    J(p, "() => { G.me.mana.R=1; changed(); }"); p.wait_for_timeout(200)
    hand(p, 'Ragavan'); s = J(p, ST)
    check('a creature spell goes straight to its cast (Ragavan: the payment window with dash, no target screen)', s['pre'] is None and s['strip'] is None and not s['cast'] and (s['pay'] or 'Ragavan, Nimble Pilferer' in s['st']), s)
    check('no page errors', not errs, errs)
    b.close()
finally:
    srv.terminate()
print(('ALL PASS' if all(res) else 'SOME FAILED') + f' ({sum(res)}/{len(res)})')
