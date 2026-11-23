"""The phone table's targeting (phone layer m0.5): a practice game on a phone held sideways (844 x 390, touch).
Lightning Bolt: the strip, legal targets outlined (creatures and both players, not the artifacts), a tap rings the target and the table waits
for Done; tapping another moves it, tapping it again takes it back; Done goes on. Fatal Push: No target asks first; an illegal tap explains.
Force of Vigor (up to two): two chosen, a third refused with a note, one taken back, Done. A trigger: No target marks it. Other modes get a
Cancel button and tap wording; toasts say tap."""
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
  return {mode:!!G.mode, strip:s.hidden ? null : s.innerText, go:g.hidden ? null : g.innerText, mtl:[...document.querySelectorAll('.mtl')].map(nm), mtc:[...document.querySelectorAll('.mtc')].map(nm),
    tags:[...document.querySelectorAll('.mttag')].map(e=>e.textContent), arrows:G.me.arrows.filter(a=>G.mode ? a.a===G.mode.from : true).map(a=>a.b==='p1'||a.b==='p2' ? a.b : cdata(findAny(a.b).c).n),
    modal:document.querySelector('#modal').hidden ? null : document.querySelector('#modal').innerText }; }"""
def card(p, name, side='opp', i=0):
    cid = J(p, f"() => G.{side}.bf.filter(c=>cdata(c).n.startsWith({name!r}))[{i}].id")
    return p.locator(f'.card[data-id="{cid}"]').first
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
    J(p, """() => { const add=(n,side,o,z='bf')=>{ const c=mk(keyOf(n),o); side[z].push(c); return c; };
      G.me.bf=[]; G.me.hand=[]; G.me.mana=noMana(); for(const n of ['Mountain','Mountain','Mountain']) add(n,G.me,{});
      G.opp.bf=[]; add('Mountain',G.opp,{o:oppId()}); add('Ragavan, Nimble Pilferer',G.opp,{o:oppId()}); add('Thought-Knot Seer',G.opp,{o:oppId()});
      add('Expedition Map',G.opp,{o:oppId()}); add('Expedition Map',G.opp,{o:oppId()}); add('Aether Spellbomb',G.opp,{o:oppId()});
      for(const n of ['Lightning Bolt','Fatal Push']) add(n,G.me,{},'hand'); G.me.mana.R=1; changed(); }""")
    p.wait_for_timeout(500)
    # 1. Lightning Bolt
    p.tap('#mHandBtn'); p.wait_for_timeout(300); p.locator('#myHand .card').nth(0).tap(); p.wait_for_timeout(700)
    s = J(p, ST)
    check('casting Lightning Bolt starts targeting: the strip names it and what it can target', s['mode'] and s['strip'] and 'Lightning Bolt' in s['strip'] and 'any target' in s['strip'], s['strip'])
    check('legal targets are outlined: both players and both creatures, not the artifacts or lands', set(s['mtl']) == {'oppAv', 'myAv', 'Ragavan, Nimble Pilferer', 'Thought-Knot Seer'}, s['mtl'])
    check('the big button reads No target', s['go'] and s['go'].startswith('No target'), s['go'])
    geo = J(p, "() => { const g=document.querySelector('#mTgtGo').getBoundingClientRect(), n=document.querySelector('#next').getBoundingClientRect(), s=document.querySelector('#mTgt').getBoundingClientRect(), m=document.querySelector('#mid').getBoundingClientRect(); return [Math.abs(g.left-n.left)<2 && Math.abs(g.top-n.top)<2, s.top <= m.bottom && s.bottom >= m.top, s.left >= m.left-1 && s.right <= m.right+1]; }")
    check('the Done button sits over the big button; the strip over the phase bar, inside the board', all(geo), geo)
    p.locator('#mTgtGo').tap(); p.wait_for_timeout(300)
    s = J(p, ST)
    check('No target with none chosen asks first (Choose a target / No target)', s['modal'] and 'no target' in s['modal'].lower() and 'Choose a target' in s['modal'], s['modal'])
    p.get_by_role('button', name='Choose a target').tap(); p.wait_for_timeout(300)
    check('Choose a target goes back to targeting', J(p, "() => !!G.mode && document.querySelector('#modal').hidden"))
    card(p, 'Ragavan').tap(); p.wait_for_timeout(400); s = J(p, ST)
    check('tapping Ragavan rings it with a TARGET tag; the table waits for Done', s['mode'] and s['mtc'] == ['Ragavan, Nimble Pilferer'] and s['tags'] == ['TARGET'] and s['arrows'] == ['Ragavan, Nimble Pilferer'] and s['go'].startswith('Done'), s)
    card(p, 'Thought-Knot').tap(); p.wait_for_timeout(400); s = J(p, ST)
    check('tapping another creature moves the target (one arrow, to Thought-Knot Seer)', s['mode'] and s['arrows'] == ['Thought-Knot Seer'] and s['mtc'] == ['Thought-Knot Seer'], s)
    card(p, 'Thought-Knot').tap(); p.wait_for_timeout(400); s = J(p, ST)
    check('tapping it again takes it back; still targeting, the button reads No target', s['mode'] and s['arrows'] == [] and s['go'].startswith('No target'), s)
    p.locator('#oppAv').tap(); p.wait_for_timeout(400); s = J(p, ST)
    check('tapping the opponent targets them (their box ringed)', s['mode'] and s['arrows'] == [J(p, '() => oppId()')] and 'oppAv' in s['mtc'], s)
    card(p, 'Expedition', 'opp').tap(); p.wait_for_timeout(400); s = J(p, ST)
    check("tapping an artifact explains why it can't be targeted (the old target stays)", bool(s['modal']) and "can't target" in s['modal'], s['modal'])
    p.get_by_role('button', name='Pick another target').tap(); p.wait_for_timeout(300); s = J(p, ST)
    check('Pick another target: back to targeting, still the opponent', s['mode'] and s['arrows'] == [J(p, '() => oppId()')], s)
    p.locator('#mTgtGo').tap(); p.wait_for_timeout(400); s = J(p, ST)
    check('Done ends targeting: strip and button gone, the arrow kept', not s['mode'] and s['strip'] is None and s['go'] is None and J(p, "() => G.me.arrows.some(a=>a.b===oppId()) && !M.tg"), s)
    p.locator('#stack .card').first.tap(); p.wait_for_timeout(600)
    check('resolving Bolt deals 3 to the opponent', J(p, "() => G.opp.life===17"), J(p, "() => G.opp.life"))
    # 2. Fatal Push: one target, picked and confirmed
    J(p, "() => { G.me.mana.B=1; changed(); }"); p.wait_for_timeout(200)
    p.tap('#mHandBtn'); p.wait_for_timeout(300); p.locator('#myHand .card').nth(0).tap(); p.wait_for_timeout(700)
    s = J(p, ST)
    check('Fatal Push: only the creatures are outlined', s['mode'] and set(s['mtl']) == {'Ragavan, Nimble Pilferer', 'Thought-Knot Seer'}, s['mtl'])
    card(p, 'Ragavan').tap(); p.wait_for_timeout(300); p.locator('#mTgtGo').tap(); p.wait_for_timeout(400)
    p.locator('#stack .card').first.tap(); p.wait_for_timeout(600)
    check('Fatal Push destroys Ragavan', J(p, "() => !G.opp.bf.some(c=>cdata(c).n.startsWith('Ragavan'))"))
    # 3. up to two: Force of Vigor
    J(p, "() => { const c=mk(keyOf('Force of Vigor'),{}); G.me.st.push(c); G.mode={type:'arrow', from:c.id}; changed(); }"); p.wait_for_timeout(400)
    s = J(p, ST)
    check('Force of Vigor: the artifacts are outlined, the strip counts 0 of 2 and says "or none"', set(s['mtl']) == {'Expedition Map', 'Aether Spellbomb'} and '0 of 2' in s['strip'] and 'or none' in s['strip'], s)
    card(p, 'Expedition', 'opp', 0).tap(); p.wait_for_timeout(300); card(p, 'Expedition', 'opp', 1).tap(); p.wait_for_timeout(300); s = J(p, ST)
    check('two chosen: 2 of 2, both tagged, still waiting for Done', s['mode'] and len(s['arrows']) == 2 and len(s['tags']) == 2 and '2 of 2' in s['strip'], s)
    card(p, 'Aether Spellbomb', 'opp').tap(); p.wait_for_timeout(300); s = J(p, ST)
    check('a third is refused with a note (still two)', s['mode'] and len(s['arrows']) == 2 and '2 of 2 chosen' in J(p, "() => document.querySelector('#toast').textContent"), s)
    card(p, 'Expedition', 'opp', 1).tap(); p.wait_for_timeout(300); card(p, 'Aether Spellbomb', 'opp').tap(); p.wait_for_timeout(300); s = J(p, ST)
    check('taking one back makes room for the Spellbomb', s['mode'] and sorted(s['arrows']) == ['Aether Spellbomb', 'Expedition Map'], s)
    p.locator('#mTgtGo').tap(); p.wait_for_timeout(400)
    check('Done ends it with two targets', J(p, "() => !G.mode && G.me.arrows.filter(a=>cdata(findAny(a.a).c).n==='Force of Vigor').length===2"))
    J(p, "() => { G.me.st=[]; G.me.arrows=[]; changed(); }"); p.wait_for_timeout(200)
    # 4. a trigger with no target
    J(p, "() => { const c=G.me.bf[0]; trigPush(c, 'It deals 1 damage to any target.'); changed(); }"); p.wait_for_timeout(400)
    s = J(p, ST)
    check('a trigger that targets starts targeting too', s['mode'] and s['strip'] and 'any target' in s['strip'], s['strip'])
    p.locator('#mTgtGo').tap(); p.wait_for_timeout(300); p.locator('#modal footer button', has_text='No target').tap(); p.wait_for_timeout(400)
    check('No target (confirmed) marks the trigger as having no target', J(p, "() => !G.mode && G.me.st.length===1 && G.me.st[0].ab.nt===1"), J(p, "() => [G.mode, G.me.st.map(c=>c.ab)]"))
    J(p, "() => { G.me.st=[]; changed(); }"); p.wait_for_timeout(200)
    # 5. other modes and toasts
    J(p, "() => startMode('attach', G.me.bf[0].id)"); p.wait_for_timeout(300)
    mb = J(p, "() => { const m=document.querySelector('#modebar'); return m.hidden ? null : m.innerText; }")
    check('other modes: the bar says tap and has a Cancel button', bool(mb) and mb.startswith('Tap ') and 'CANCEL' in mb.upper() and 'Esc' not in mb, mb)
    p.locator('#modebar [data-mesc]').tap(); p.wait_for_timeout(300)
    check('Cancel ends that mode', J(p, "() => !G.mode"))
    J(p, "() => toast('Click a creature you control (Esc to cancel).')")
    check('toasts say tap and drop the Esc hint', J(p, "() => document.querySelector('#toast').textContent") == 'Tap a creature you control.', J(p, "() => document.querySelector('#toast').textContent"))
    check('no page errors', not errs, errs[:3])
    b.close()
finally:
    srv.kill()
print("ALL PASS" if res and all(res) else "SOME FAILED", f"({sum(res)}/{len(res)})"); sys.exit(0 if all(res) else 1)
