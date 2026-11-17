#!/usr/bin/env python3
"""Two-browser tests for priority and stops (v5.0), and for every wait that was there before it.

  python3 tools/priority_test.py                      all tests
  python3 tools/priority_test.py --only stack,stops   some of them (names: --list)
  python3 tools/priority_test.py --old old.html       the v4.137 page for the old-page tests
                                                      (default: git show <v4.137 commit>:index.html, if this clone has it)
  python3 tools/priority_test.py --real-wait          also sit through one real 20-second wait for Resolve anyway

What it needs: Playwright for Python with Chromium (or /usr/bin/google-chrome), Node, and the `peer` package
(a local PeerServer). The script installs `peer` into a temp folder the first time (npm i peer); set MT_PEER_DIR
to a folder that already has node_modules/peer to skip that. It serves the repo's built pages itself, so run
`python3 build.py` first: it reads index.html and night/index.html, not src/.

Each test opens its own browser contexts (one per player, so each has its own storage), a host and a guest at a
real table over the local PeerServer. Card data is the built-in data; Scryfall and every other outside address is
blocked. The page's own functions are used to set a scene (a card in hand, a creature on the battlefield), and the
real buttons, keys and clicks are used for whatever is being tested.

The tests, by name:
  stack     every stack decision in claude/priority-design.md: blue OK, who is asked, no Respond button, the caster
            can't resolve, Resolve anyway, resolves by itself, "I press Resolve", the band, the tab title, OK all N,
            Always OK, targets first, animations off
  stops     the grid, the defaults, the dashes, each stop, Go on anyway, own-turn stops, chips, privacy
  order     v5.02: two or more triggers at once open the ordering panel for their controller (either player), both
            buttons wait, the order holds, remembered orders skip the panel, identical triggers don't ask, APNAP
  auto      v5.01: Before attackers only when the active player can attack, Next skipping an empty combat on your own
            turn, Main 2 on Auto (an end-step card turns it on, with a note), the Main 2 box's cycle, the old saved
            stops moved to Auto, the grid's checkmarks centred
  waits     one scripted game through every older wait (mulligans, Done blocking, Start my turn, the cleanup discard,
            one-time pauses, the pact draw, turn control), run three times: on two v4.137 pages, on two new pages
            with Priority off, and with Priority on. The first two traces must be identical; the third must match
            them at every checkpoint once the OKs priority asks for have been given.
  match     game loss, sideboarding and its timer, the next game, the round clock running out, the end-of-round
            turns and "Is there a winner?", with Priority on and off
  toggle    the host turns it off and on mid-game, during a stack wait and during a stop; the guest can't
  oldpage   one player on the v4.137 page (either seat): no priority, said on screen; it starts when they reload
  reload    a reload in the middle of a stack wait (either player) and of a stop
  fullgame  a match from the roll to "wins the match 2-0" with Priority on, played with the real controls
  sound     v5.04/v5.05: the stack alert chimes once for the player asked (not the caster, not while aiming), once per
            batch of items, again after 10 s with no mouse or key on the page (never while the mouse moves), not after
            an OK, not for Always OK, not when Off; the Settings row plays a preview
  night     a Game Night match tab: priority runs there, and the table's host (not the event's) has the switch
  practice  a practice game is untouched
  pages     Settings rows, the help page still fits 1500x900, the tour and Explore know the new parts, NEWS

Exit code 0 when everything passed, 1 otherwise.
"""
import argparse, asyncio, json, os, re, shutil, socket, subprocess, sys, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD_COMMITS = ['fbbfc1f295b0507a0202cedec92e72c01a20d0c2', 'ee2bb59']      # v4.137
RESULTS = []          # (test, check, ok, info)
CUR = ['']


def ck(name, cond, info=''):
    RESULTS.append((CUR[0], name, bool(cond), info))
    print(('    ok    ' if cond else '    FAIL  ') + name + ('' if cond else '\n          -> ' + str(info)[:1500]), flush=True)
    return bool(cond)


def free_port():
    s = socket.socket(); s.bind(('127.0.0.1', 0)); p = s.getsockname()[1]; s.close(); return p


def peer_dir():
    d = os.environ.get('MT_PEER_DIR') or os.path.join(tempfile.gettempdir(), 'mt-peer')
    if not os.path.isdir(os.path.join(d, 'node_modules', 'peer')):
        os.makedirs(d, exist_ok=True)
        print('installing the peer package into', d, flush=True)
        subprocess.run(['npm', 'i', 'peer', '--prefix', d, '--silent', '--no-fund', '--no-audit'], check=True)
    return d


def old_page(path):
    if path:
        return open(path, encoding='utf-8').read()
    for c in OLD_COMMITS:
        r = subprocess.run(['git', '-C', ROOT, 'show', c + ':index.html'], capture_output=True)
        if r.returncode == 0 and b"const VERSION = 'v4.137'" in r.stdout:
            return r.stdout.decode('utf-8')
    return None


SEED_JS = """(()=>{ let s=%d; Math.random=()=>{ s=(Math.imul(s,1664525)+1013904223)>>>0; return s/4294967296; }; })()"""

# v5.01 changed two defaults: Before attackers asks only when the active player has something that can attack, and
# Main 2 on the opponent's turn is Auto (on while they have an "at the beginning of your end step" card). Most tests
# below were written for v5.0's stops, so stage() gives both players a creature that can attack and, on new pages,
# sets Main 2 to Always for both (v5.0's default). The 'auto' test checks the new defaults themselves.
STAGE_JS = "(m2)=>{ if(m2 && typeof setStops==='function'){ const st=myStops(); st.opp.m2=true; setStops(st); } return T.perm('Test Ox','Creature — Ox','2/2'); }"
PERM_JS = "(a)=>{ const c=mk(null,{cu:{n:a[0], t:a[1], pt:a[2]||'', o:a[3]||'', img:'', cl:[]}}); if(a[4]) c.sick=true; G.me.bf.push(c); changed(); return c.id; }"
BEACON = ['Test Beacon', 'Artifact', '', 'At the beginning of your end step, you gain 1 life.']
SKIP = 'Next: Main 2 (no attackers)'      # v5.01: the button on your own Main 1 when nothing can attack


async def stage(a, b, m2=True):
    for p in (a, b):
        await p.evaluate(STAGE_JS, m2)
    await a.wait_for_timeout(400)


# helpers put on the page after the game has started; they use only functions v4.137 already had
T_JS = r"""()=>{ S.autoPay=false; const un=t=>String(t).replace(/\[\[([^|\]]*)\|[^\]]*\]\]/g,'$1');
  window.T={
    give:(n,k)=>{ let id; for(let i=0;i<(k||1);i++){ const c=mk(keyOf(n)); G.me.hand.push(c); id=c.id; } changed(); return id; },
    perm:(n,t,pt)=>{ const c=mk(null,{cu:{n, t, pt:pt||'', o:'', img:'', cl:[]}}); G.me.bf.push(c); changed(); return c.id; },
    trig:(n,k)=>{ const out=[]; for(let i=0;i<(k||1);i++){ const t=mk(null,{tok:true, ts:Date.now(), ab:{id:'x', trig:1}, cu:{n:n+': trigger', t:'Triggered ability', o:'Untap it.', img:''}}); G.me.st.push(t); out.push(t.id); } changed(); return out; },
    trim:(k)=>{ let n=0; while(G.me.hand.length>(k==null?7:k)){ move(G.me.hand[0].id,'gy',{silent:true}); n++; } if(n) changed(); return n; },
    cast:(n,tgt)=>{ const c=mk(keyOf(n)); G.me.hand.push(c); castSpell(c.id); if(tgt) finishMode(tgt==='opp' ? oppId() : tgt==='me' ? G.myId : tgt); return c.id; },
    info:()=>{ const q=s=>document.querySelector(s), b=q('#next'), oa=q('#okAll'), hi=q('#prihint'), db=q('#drawBtn'), mo=q('#modal'), bn=q('#banner'), t=Object.assign({}, G.turn);
      return {text:b.textContent, dis:b.disabled, cls:b.className.split(' ').filter(x=>x==='ok'||x==='any'), okAll:oa && !oa.hidden ? oa.textContent : null, hint:hi && !hi.hidden ? hi.textContent : '', title:document.title,
        bands:[...document.querySelectorAll('#stack .band')].map(x=>x.textContent), owns:[...document.querySelectorAll('#stack .own')].map(x=>x.textContent),
        st:G.me.st.map(c=>cdata(c).n+(c.okd?'*':'')), ost:((G.opp&&G.opp.st)||[]).map(c=>cdata(c).n+(c.okd?'*':'')), life:G.me.life, olife:G.opp?G.opp.life:null, hand:G.me.hand.length,
        toast:q('#toast').style.opacity==='0' ? '' : q('#toast').textContent, log:G.log.slice(-8).map(l=>un(l.text)), turn:t,
        draw:db.hidden ? null : db.textContent+(db.disabled?' (disabled)':''), modal:mo.hidden ? null : ((mo.querySelector('h3')||{}).textContent||'?'), banner:bn.hidden ? null : ((bn.querySelector('h3')||{}).textContent||'?'),
        dash:[...document.querySelectorAll('#phases button')].map(x=>[...x.querySelectorAll('i.sd')].map(i=>i.className.replace('sd ','')).join('/')), atkBar:!q('#atkBar').hidden, blockBar:!q('#blockBar').hidden,
        wins:[G.me.wins||0, (G.opp&&G.opp.wins)||0], ver:VERSION}; } }; }"""


class Env:
    async def start(self):
        from playwright.async_api import async_playwright
        self.port, self.pport = free_port(), free_port()
        self.srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(self.port), '--bind', '127.0.0.1'], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        js = "const {PeerServer}=require('peer'); PeerServer({port:%d, path:'/', host:'127.0.0.1'});" % self.pport
        self.peer = subprocess.Popen(['node', '-e', js], cwd=peer_dir(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.5)
        self.pw = await async_playwright().start()
        # a page Playwright serves by hand (the old v4.137 page) counts as coming from outside, and Chromium's local network
        # checks would then keep it away from the local PeerServer
        args = ['--disable-features=LocalNetworkAccessChecks,BlockInsecurePrivateNetworkRequests,PrivateNetworkAccessSendPreflights']
        try:
            self.b = await self.pw.chromium.launch(args=args)
        except Exception:
            self.b = await self.pw.chromium.launch(executable_path='/usr/bin/google-chrome', args=args)
        self.errors, self.ctxs, self.seed = [], [], 1000
        return self

    async def stop(self):
        try:
            await self.b.close(); await self.pw.stop()
        finally:
            self.srv.terminate(); self.peer.terminate()

    def url(self, path='/', extra=''):
        return 'http://127.0.0.1:%d%s?peerhost=127.0.0.1:%d&peersecure=0%s' % (self.port, path, self.pport, extra)

    async def ctx(self, name, old=None, seed=None):
        """A browser context for one player. old = the text of an older index.html to serve instead of the built one."""
        c = await self.b.new_context(viewport={'width': 1500, 'height': 900})
        self.ctxs.append(c)
        self.seed += 7
        await c.add_init_script(SEED_JS % (seed if seed is not None else self.seed))
        c._old = old

        async def route(r):
            u = r.request.url
            if c._old and re.match(r'^http://127\.0\.0\.1:%d/(\?.*)?$' % self.port, u):
                await r.fulfill(status=200, content_type='text/html; charset=utf-8', body=c._old)
            elif u.startswith('http://127.0.0.1:') or u.startswith('data:') or u.startswith('blob:'):
                await r.continue_()
            elif 'api.scryfall.com' in u:
                await r.fulfill(status=200, content_type='application/json', body='{"data":[]}')
            else:
                await r.abort()
        await c.route('**/*', route)
        p = await c.new_page()
        self.watch(p, name)
        return p

    def watch(self, p, name):
        p._name = name
        p.on('pageerror', lambda e, n=name: self.errors.append('%s [%s]: %s' % (n, CUR[0], e)))

    async def close_all(self):
        for c in self.ctxs:
            try:
                await c.close()
            except Exception:
                pass
        self.ctxs = []


async def ev(p, js, arg=None):
    return await p.evaluate(js, arg)


async def info(p):
    return await p.evaluate('T.info()')


async def pick_deck(p, i):
    await p.wait_for_selector('.drow', timeout=20000)
    await p.locator('.drow').nth(i).click(); await p.wait_for_timeout(250)
    await p.get_by_role('button', name='Play this deck').click()
    await p.wait_for_function('G.me && G.me.deck && !document.querySelector("#table").hidden', timeout=20000)


async def sit(env, a, b, hn='Ann', gn='Bob'):
    await a.goto(env.url()); await a.wait_for_selector('#hostBtn')
    await a.fill('#nameIn', hn); await a.click('#hostBtn'); await pick_deck(a, 0)
    code = await ev(a, 'G.code')
    await b.goto(env.url()); await b.wait_for_selector('#joinBtn')
    await b.fill('#nameIn', gn); await b.fill('#codeIn', code); await b.click('#joinBtn'); await pick_deck(b, 1)
    for p in (a, b):
        await p.wait_for_function('G.opp && G.opp.deck && G.conn && G.conn.open', timeout=30000)
    return code


async def banner_btns(p):
    return await ev(p, '[...document.querySelectorAll("#banner [data-first]")].filter(b=>!b.disabled).map(b=>b.dataset.first)')


async def pregame(a, b, first='host', mull=None):
    """Roll, companions, play or draw, opening hands, keep. first: who goes first. mull: a page that takes one mulligan."""
    mulled = False
    for _ in range(120):
        done = True
        for p in (a, b):
            s = await ev(p, '({n:G.turn.n, kept:!!G.me.kept, btm:G.me.btm||0})')
            if s['n'] and s['kept'] and not s['btm']:
                continue
            done = False
            if s['btm']:      # the London mulligan's bottom window
                if await p.locator('#mbGrid .card').count():
                    for i in range(s['btm']):
                        await p.locator('#mbGrid .card').nth(i).click()
                    await p.locator('#modal footer button.go').click()
                await p.wait_for_timeout(150); continue
            bt = await banner_btns(p)
            if 'rollboth' in bt and p is a: await p.click('#banner [data-first="rollboth"]')
            elif 'nocomp' in bt: await p.click('#banner [data-first="nocomp"]')
            elif 'play' in bt: await p.click('#banner [data-first="%s"]' % ('play' if (first == 'host') == (p is a) else 'draw'))
            elif 'deal' in bt: await p.click('#banner [data-first="deal"]')
            elif 'mull' in bt and p is mull and not mulled:
                await p.click('#banner [data-first="mull"]'); mulled = True
            elif 'keep' in bt: await p.click('#banner [data-first="keep"]')
            await p.wait_for_timeout(120)
        if done:
            break
        await a.wait_for_timeout(120)
    else:
        raise RuntimeError('the game did not start')
    await a.wait_for_timeout(400)
    for p in (a, b):
        await ev(p, 'closeModal()'); await ev(p, T_JS)


RETRIES = [0]


async def seat(env, old_a=None, old_b=None, seed=None):
    """Two players at one table. Now and then (about 1 in 10, v4.137 pages too) both pages say Connected but one never
    receives the other's state; such a table is closed and opened again, once, and counted in the summary."""
    for attempt in (1, 2):
        a = await env.ctx('host', old=old_a, seed=seed); b = await env.ctx('guest', old=old_b, seed=None if seed is None else seed + 1)
        try:
            await sit(env, a, b); return a, b
        except Exception:
            if attempt == 2:
                raise
            RETRIES[0] += 1; print('          (the table did not seat; opening it again)', flush=True)
            for c in (a.context, b.context):
                await c.close(); env.ctxs.remove(c)


async def table(env, old_a=None, old_b=None, first='host', seed=None):
    a, b = await seat(env, old_a, old_b, seed)
    await pregame(a, b, first)
    return a, b


async def press(p, ms=300, trim=True):
    """Click the big button if it can be clicked; says so if it can't. trim: first bring the hand down to seven
    (so that passing the turn doesn't open the cleanup discard, which has its own test)."""
    if trim:
        await p.evaluate("window.T && T.trim()")
    try:
        await p.click('#next', timeout=2500)
    except Exception:
        print('          (the big button was not clickable for %s: %s)' % (p._name, (await info(p))['text']), flush=True)
    await p.wait_for_timeout(ms)


async def settle(a, b, limit=12):
    """Give every OK priority is asking for (blue button on either page). Returns how many were given."""
    n = 0
    for _ in range(limit):
        hit = False
        for p in (a, b):
            if await ev(p, "document.querySelector('#next').classList.contains('ok') && !document.querySelector('#next').disabled"):
                await p.click('#next'); n += 1; hit = True; await p.wait_for_timeout(350)
        if not hit:
            await a.wait_for_timeout(250)
            if not any([await ev(p, "document.querySelector('#next').classList.contains('ok')") for p in (a, b)]):
                break
    return n


def strip(t):
    """A turn object without priority's own marks, for comparing with v4.137."""
    t = dict(t); t.pop('okd', None)
    return t


# ----------------------------------------------------------------------------------------------- stack
async def t_stack(env, A):
    a, b = await table(env)
    ck('both pages pass priority', await ev(a, 'priLive()') and await ev(b, 'priLive()') and await ev(a, 'G.oppPv') == 1)
    # targets first
    await ev(a, "T.cast('Lightning Bolt')"); await a.wait_for_timeout(450)
    ia, ib = await info(a), await info(b)
    ck('while the caster aims, nobody is asked yet', ia['text'] == 'Choose its target first' and ia['dis'] and ib['text'] == 'Ann is choosing a target' and ib['dis'] and ib['title'] == 'Modern Table', (ia['text'], ib['text'], ib['title']))
    await ev(a, 'finishMode(oppId())'); await a.wait_for_timeout(450)
    ia, ib = await info(a), await info(b)
    ck('blue button: "OK: <card> resolves"', ib['text'] == 'OK: Lightning Bolt resolves' and ib['cls'] == ['ok'] and not ib['dis'], ib)
    ck('the hint under it', ib['hint'] == 'Space works too. To respond instead, cast a spell from your hand.', ib['hint'])
    ck("the caster's button says who is being waited on", ia['text'] == "Waiting for Bob's OK" and ia['dis'] and 'Resolve anyway unlocks in' in ia['hint'], ia)
    ck('tab title changes for the player who is asked, only', ib['title'] == '● Your OK needed · Modern Table' and ia['title'] == 'Modern Table', (ia['title'], ib['title']))
    ck('band on the stack card', ib['bands'] == ['WAITING FORYOUR OK'] and ia['bands'] == ['WAITINGFOR BOB'] and ia['owns'] == ['ANN'] and ib['owns'] == ['ANN'], (ia['bands'], ib['bands'], ia['owns']))
    glow = await ev(b, "(()=>{ const n=getComputedStyle(document.querySelector('#next')), c=getComputedStyle(document.querySelector('#stack .card.askme')); return [n.animationName, c.animationName, n.backgroundColor]; })()")
    ck('the button and the card glow (pulse)', glow[0] == 'btnpulse' and glow[1] == 'okpulse' and glow[2] == 'rgb(127, 179, 255)', glow)
    await ev(b, "(()=>{ S.anim='off'; applyMotion(); })()"); await b.wait_for_timeout(150)
    glow = await ev(b, "(()=>{ const n=getComputedStyle(document.querySelector('#next')), c=getComputedStyle(document.querySelector('#stack .card.askme')); return [n.animationName, c.animationName, n.boxShadow!=='none', c.boxShadow!=='none']; })()")
    ck('with animations off the glow is static', glow == ['none', 'none', True, True], glow)
    await ev(b, "(()=>{ S.anim='on'; applyMotion(); })()")
    ck('no Respond button anywhere', not await ev(b, "[...document.querySelectorAll('button')].some(x=>/respond/i.test(x.textContent) && x.offsetParent)"))
    # the caster can't resolve
    await a.click('#stack .card'); await a.wait_for_timeout(200); ia = await info(a)
    ck("the caster can't resolve by clicking the card", ia['st'] == ['Lightning Bolt'] and "Waiting for Bob's OK" in ia['toast'], ia)
    await a.keyboard.press('Space'); await a.wait_for_timeout(200); ia = await info(a)
    ck("the caster's Space neither resolves nor moves the turn", ia['st'] == ['Lightning Bolt'] and ia['turn']['phase'] == 2, ia['turn'])
    await a.click('#stack .card', button='right'); await a.wait_for_timeout(200)
    await a.locator('#ctx button', has_text='Resolve').first.click(); await a.wait_for_timeout(250); ia = await info(a)
    ck("nor through the card's menu", ia['st'] == ['Lightning Bolt'], ia['st'])
    # OK with Space: resolves by itself
    await b.keyboard.press('Space'); await b.wait_for_timeout(800)
    ia, ib = await info(a), await info(b)
    ck('Space gives the OK and the spell resolves by itself', ia['st'] == [] and ib['life'] == 17 and any('Bob OKs Lightning Bolt.' in l for l in ia['log']), (ia['st'], ib['life'], ia['log']))
    ck('afterwards both buttons and the tab title are back', ia['text'].startswith('Next:') and ib['text'] == "Opponent's turn" and ib['title'] == 'Modern Table' and ia['bands'] == [] and ib['hint'] == '', (ia['text'], ib['text'], ib['title']))
    # Resolve anyway
    await ev(a, "T.cast('Lightning Bolt','opp')"); await a.wait_for_timeout(450)
    if A.real_wait:
        await a.wait_for_timeout(17000); ia = await info(a)
        ck('at 17 s it is still waiting', ia['text'] == "Waiting for Bob's OK" and ia['dis'], ia)
        await a.wait_for_timeout(3800)
    else:
        await ev(a, 'PRI.since-=18500'); await a.wait_for_timeout(600); ia = await info(a)
        ck('before 20 s it is still waiting', ia['text'] == "Waiting for Bob's OK" and ia['dis'], ia)
        await a.wait_for_timeout(1500)
    ia = await info(a)
    ck('after 20 s: Resolve anyway', ia['text'] == 'Resolve anyway' and not ia['dis'] and ia['cls'] == ['any'] and ia['hint'] == 'No answer from Bob yet. You can also keep waiting.', ia)
    await press(a, 600); ia, ib = await info(a), await info(b)
    ck('Resolve anyway resolves it and is logged for both', ia['st'] == [] and ib['life'] == 14 and any('Ann resolves Lightning Bolt anyway: no answer from Bob.' in l for l in ib['log']), (ib['life'], ib['log']))
    # to respond you cast; it follows whose item is on top, not whose turn it is
    bolt = await ev(a, "T.cast('Lightning Bolt','opp')"); await a.wait_for_timeout(450)
    await ev(b, "(id)=>T.cast('Counterspell', id)", bolt); await b.wait_for_timeout(600)
    ia, ib = await info(a), await info(b)
    ck("a response waits on the other player: the active player OKs the other's instant", ia['text'] == 'OK: Counterspell resolves' and ia['cls'] == ['ok'] and ib['text'] == "Waiting for Ann's OK", (ia['text'], ib['text']))
    ck('the response sits on top of the stack on both screens', ia['st'] == ['Lightning Bolt'] and ia['ost'] == ['Counterspell'] and ia['bands'] == ['WAITING FORYOUR OK'] and ia['owns'] == ['ANN', 'BOB'], (ia['st'], ia['ost'], ia['bands'], ia['owns']))
    await press(a, 900); ia, ib = await info(a), await info(b)
    ck('after the OK the Counterspell resolves and counters the Bolt', ia['st'] == [] and ib['st'] == [] and ib['life'] == 14, (ia['st'], ib['st'], ib['life']))
    # "I press Resolve"
    await ev(a, "(()=>{ S.priRes='click'; })()")
    await ev(a, "T.cast('Lightning Bolt','opp')"); await a.wait_for_timeout(450)
    await press(b, 500); ia, ib = await info(a), await info(b)
    ck('"I press Resolve": after the OK the button reads Resolve <spell>', ia['text'] == 'Resolve Lightning Bolt' and not ia['dis'] and ia['st'] == ['Lightning Bolt*'] and ia['bands'] == ['OK’D'] and "Bob OK'd it" in ia['hint'], ia)
    ck('and the other player waits', ib['text'] == 'Waiting for Ann' and ib['dis'] and ib['hint'] == "You OK'd it. Ann resolves it.", ib)
    await a.click('#stack .card'); await a.wait_for_timeout(200); ia = await info(a)
    ck('a click on the stack card does not resolve it then', ia['st'] == ['Lightning Bolt*'] and 'press Resolve on your button' in ia['toast'], ia)
    await ev(a, "T.cast('Lightning Bolt','opp')"); await a.wait_for_timeout(500); ia, ib = await info(a), await info(b)
    ck('casting something more takes back the earlier OK', ia['st'] == ['Lightning Bolt', 'Lightning Bolt'] and ib['text'] == 'OK: Lightning Bolt resolves', (ia['st'], ib['text']))
    await press(b, 450); await press(a, 600); ia, ib = await info(a), await info(b)
    ck('once it has resolved, the first one is asked about again', ia['st'] == ['Lightning Bolt'] and ib['text'] == 'OK: Lightning Bolt resolves' and ib['life'] == 11, (ia['st'], ib['text'], ib['life']))
    await press(b, 450); await a.keyboard.press('Space'); await a.wait_for_timeout(600); ia, ib = await info(a), await info(b)
    ck('Space on Resolve <spell> resolves it', ia['st'] == [] and ib['life'] == 8, (ia['st'], ib['life']))
    await ev(a, "(()=>{ S.priRes='auto'; })()")
    # OK all N
    await ev(b, "T.trig('Amulet of Vigor', 27)"); await b.wait_for_timeout(700); ia = await info(a)
    ck('27 triggers: OK all 27 is offered, with its hint', ia['okAll'] == 'OK all 27' and ia['text'] == 'OK: Amulet of Vigor trigger resolves' and ia['hint'] == 'Right-click a trigger on the stack to always OK it.', ia)
    await a.click('#okAll')
    await b.wait_for_function('G.me.st.length===0', timeout=30000); await b.wait_for_timeout(300); ia = await info(a)
    ck('OK all resolves the whole run, one log line', (await info(b))['st'] == [] and await ev(a, "G.log.filter(l=>/OKs all 27 on the stack/.test(l.text)).length") == 1)
    # Always OK
    await ev(b, "T.trig('Amulet of Vigor', 1)"); await b.wait_for_timeout(450)
    await a.click('#stack .card', button='right'); await a.wait_for_timeout(200)
    items = await ev(a, "[...document.querySelectorAll('#ctx button')].map(x=>x.textContent)")
    ck('right-click their stack item: Always OK <name>', items[:1] == ['Always OK Amulet of Vigor trigger'], items)
    await a.click('#ctx button'); await a.wait_for_timeout(1300); ia, ib = await info(a), await info(b)
    ck('it is then answered without a press', ib['st'] == [] and any('Ann OKs Amulet of Vigor: trigger (always OK).' in l for l in ia['log']), (ib['st'], ia['log']))
    await ev(b, "T.trig('Amulet of Vigor', 3)"); await b.wait_for_function('G.me.st.length===0', timeout=15000)
    ck('and so are the next ones', True)
    await a.click('#turnlbl'); await a.wait_for_timeout(200)
    row = await ev(a, "[...document.querySelectorAll('#ctx > button')].map(x=>x.textContent).find(x=>/^Always OK/.test(x))")
    ck('the turn menu lists it', row == 'Always OK: Amulet of Vigor triggerclick to clear', row)
    await a.locator('#ctx > button', has_text='Always OK').click(); await a.wait_for_timeout(200)
    await ev(b, "T.trig('Amulet of Vigor', 1)"); await b.wait_for_timeout(1200); ia = await info(a)
    ck('clearing the list asks again', ia['text'] == 'OK: Amulet of Vigor trigger resolves', ia['text'])
    await a.click('#stack .card.opp'); await a.wait_for_timeout(600)
    ck('a click on their waiting card gives the OK too', (await info(b))['st'] == [])
    # the other older buttons, with something on the stack: blocks and Start my turn
    bear = await ev(a, "T.perm('Test Bear','Creature — Bear','2/2')")
    await press(a); await settle(a, b)                       # to combat, Bob OKs "before attackers"
    await ev(a, "(id)=>{ G.atkSel=new Set([id]); atkCommit(); }", bear); await a.wait_for_timeout(500); ib = await info(b)
    ck('blocks: Done blocking is the button', ib['text'] == 'Done blocking' and ib['cls'] == [], ib)
    await ev(a, "T.cast('Lightning Bolt','opp')"); await a.wait_for_timeout(500); ib = await info(b)
    ck('a spell cast during blocks goes in front: blue OK', ib['text'] == 'OK: Lightning Bolt resolves' and ib['blockBar'], ib)
    await press(b, 700); ib = await info(b)
    ck('after it resolves, Done blocking is back', ib['text'] == 'Done blocking' and ib['life'] == 5, ib)
    await press(b); await press(a, 500); await press(a); await press(a); await settle(a, b); await press(a)      # done blocking, damage, main 2, (OK) end, pass
    ia, ib = await info(a), await info(b)
    ck('Start my turn after the pass', ib['text'] == 'Start my turn' and ia['text'] == 'Waiting for Bob' and ia['turn'].get('passed'), (ia['text'], ib['text'], ia['turn']))
    await ev(b, "T.cast('Lightning Bolt','opp')"); await b.wait_for_timeout(500); ia, ib = await info(a), await info(b)
    ck("an instant in the end-step window: the passer's button turns blue", ia['text'] == 'OK: Lightning Bolt resolves' and ib['text'] == "Waiting for Ann's OK", (ia['text'], ib['text']))
    await press(a, 700); ia, ib = await info(a), await info(b)
    ck('then Start my turn is back and works', ib['text'] == 'Start my turn' and ia['life'] == 17, (ib['text'], ia['life']))
    await ev(b, 'T.trim()'); await press(b, 600)
    ck('the next turn starts', (await info(b))['turn']['n'] == 2)


# ----------------------------------------------------------------------------------------------- stops
async def t_stops(env, A):
    a, b = await table(env)
    await stage(a, b, m2=False)                  # a creature each; Main 2 stays on Auto (no end-step card out)
    ia = await info(a)
    ck('dashes at the start: blue bright over Combat, empty over Main 2 (Auto, nothing out), muted over End; gold muted under the Next phases', ia['dash'] == ['a off/b off', 'a off/b off', 'a off/b fx', 'a on/b fx', 'a off/b fx', 'a fx/b fx'], ia['dash'])
    ck("the other page holds my stops (it stops its own turn there)", await ev(a, 'G.oppStops') == {'up': False, 'draw': False, 'm1': False, 'atk': True, 'm2': False, 'ea': True}, await ev(a, 'G.oppStops'))
    await press(a); ia, ib = await info(a), await info(b)
    ck('before attackers: the turn holds at the start of combat', ia['turn']['phase'] == 3 and ia['turn'].get('hold') == {'pid': 'p2', 'at': 'atk', 'ok': 1} and not ia['atkBar'], ia['turn'])
    ck('the other player: "OK: Ann declares attackers"', ib['text'] == 'OK: Ann declares attackers' and ib['cls'] == ['ok'] and ib['title'].startswith('● Your OK needed'), ib)
    ck('the active player waits', ia['text'] == "Waiting for Bob's OK" and ia['dis'] and ia['hint'].startswith('Go on anyway unlocks in'), ia)
    await a.click('#phases [data-ph="4"]'); await a.wait_for_timeout(200); ia = await info(a)
    ck('a phase chip does not get past the stop', ia['turn']['phase'] == 3 and "Waiting for Bob's OK" in ia['toast'], ia)
    await press(b); ia = await info(a)
    ck('the OK releases it: the attack bar is there', 'hold' not in ia['turn'] and ia['turn'].get('okd') == {'atk': 1} and ia['atkBar'] and ia['text'] == 'Next: Main 2' and any('Bob OKs: Ann declares attackers.' in l for l in ia['log']), ia)
    await b.click('#turnlbl'); await b.wait_for_timeout(200)
    for _ in range(2):
        await b.click('#ctx [data-stop="op:m2"]'); await b.wait_for_timeout(120)
    await b.keyboard.press('Escape'); await b.wait_for_timeout(300)
    ck('Bob sets Main 2 to Always: Auto → Off → Always', await ev(a, 'G.oppStops.m2') is True and await ev(b, 'myStops().opp.m2') is True)
    await press(a); await press(a); ia, ib = await info(a), await info(b)
    ck('Main 2: holds before the end step begins', ia['turn']['phase'] == 4 and ia['turn']['hold']['at'] == 'm2' and ib['text'] == 'OK: Ann goes to the end step' and any("Ann is ready to move on. Waiting for Bob's OK." in l for l in ib['log']), (ia['turn'], ib['text'], ib['log']))
    await b.keyboard.press('Space'); await b.wait_for_timeout(450); ia = await info(a)
    ck('Space gives the OK; the turn moves to the end step by itself', ia['turn']['phase'] == 5 and 'hold' not in ia['turn'] and ia['text'] == 'End turn', ia)
    await press(a); ia, ib = await info(a), await info(b)
    ck('End step: Start my turn is as before', ib['text'] == 'Start my turn' and ib['cls'] == [] and ia['text'] == 'Waiting for Bob', (ia['text'], ib['text']))
    await ev(b, 'T.trim()'); await press(b, 500); ib = await info(b)
    ck('upkeep, draw and Main 1 are off until checked: turn 2 runs to Main 1', ib['turn']['n'] == 2 and ib['turn']['phase'] == 2 and 'hold' not in ib['turn'], ib['turn'])
    # Go on anyway
    await press(b); await ev(b, 'PRI.since-=19500'); await b.wait_for_timeout(1000); ib = await info(b)
    ck('Go on anyway after 20 s', ib['text'] == 'Go on anyway' and ib['cls'] == ['any'], ib)
    await press(b); ia, ib = await info(a), await info(b)
    ck('it releases the stop and is logged', 'hold' not in ib['turn'] and ib['turn']['phase'] == 3 and any('Bob goes on anyway: no answer from Ann.' in l for l in ia['log']), (ib['turn'], ia['log']))
    # the grid
    await a.click('#turnlbl'); await a.wait_for_timeout(250)
    grid = await ev(a, "(()=>{ const g=document.querySelector('#ctx .sgrid'); return g ? {head:[...g.querySelectorAll('.h')].map(x=>x.textContent), rows:[...g.querySelectorAll(':scope > div:nth-child(3n+1):not(.h)')].map(x=>x.textContent), boxes:[...g.querySelectorAll('[data-stop]')].map(x=>x.dataset.stop+'='+x.classList.contains('on')), locks:[...g.querySelectorAll('.lock + small')].map(x=>x.textContent), rest:[...document.querySelectorAll('#ctx > button')].map(x=>x.textContent), usual:document.querySelector('#ctx [data-usual]').textContent} : null; })()")
    ck('turn menu: the grid, rows by phase, My turn / <opponent>’s turn', grid and grid['head'] == ['Before leaving', 'My turn', "Bob's turn"] and grid['rows'] == ['Upkeep', 'Draw', 'Main 1', 'Before attackers', 'Blocks', 'Main 2', 'End step'], grid)
    ck('defaults: before attackers on the opponent’s turn; Main 2 on Auto (unlit: nothing out)', grid and grid['boxes'] == ['me:up=false', 'op:up=false', 'me:draw=false', 'op:draw=false', 'op:m1=false', 'op:atk=true', 'op:m2=false'], grid and grid['boxes'])
    ck('already-there waits are shown checked and locked', grid and grid['locks'] == ['Next', 'Next', 'Done blocking', 'Next', 'End turn', 'Start my turn'] and await ev(a, "[...document.querySelectorAll('#ctx .sgrid .lock')].every(x=>x.tagName==='SPAN')"), grid and grid['locks'])
    ck('the one-time pauses and the rest of the menu are still there', grid and [x for x in grid['rest'] if x.startswith('Pause')] == ['Pause on my next upkeep (my turn stops there)', "Pause Bob's next upkeep", "Pause Bob's draw step (before the draw)", "Pause Bob's draw step (after the draw)"] and any('Take the turn' in x for x in grid['rest']) and any('control' in x for x in grid['rest']), grid and grid['rest'])
    for k in ('op:up', 'op:draw', 'op:m1', 'op:m2', 'op:m2'):
        await a.click('#ctx [data-stop="%s"]' % k); await a.wait_for_timeout(80)
    ck('the menu stays open while boxes are ticked', await ev(a, "!document.querySelector('#ctx').hidden && document.querySelectorAll('#ctx [data-stop].on').length===5"))
    await a.keyboard.press('Escape'); await a.wait_for_timeout(300); ia, ib = await info(a), await info(b)
    ck('the dashes follow the grid', ia['dash'] == ['a on/b off', 'a on/b off', 'a on/b fx', 'a on/b fx', 'a on/b fx', 'a fx/b fx'], ia['dash'])
    ck("stops are private: the other player's bar and menu show only their own", ib['dash'] == ['a off/b off', 'a off/b off', 'a off/b fx', 'a on/b fx', 'a on/b fx', 'a fx/b fx'] and await ev(b, 'G.oppStops.up && G.oppStops.m1'), ib['dash'])
    ck('they are kept in my settings', await ev(a, "JSON.parse(localStorage.getItem('mt_settings')).stops.opp") == {'up': True, 'draw': True, 'm1': True, 'atk': True, 'm2': True})
    # Bob finishes turn 2; Ann's turn 3; Bob's turn 4 meets Upkeep, Draw, Main 1
    await press(b); await press(b); await press(a); await press(b); await ev(a, 'T.trim()'); await press(a, 500)
    ck("turn 3 runs to Main 1 (Bob has no upkeep or draw stop)", (await info(a))['turn'] == {'active': 'p1', 'phase': 2, 'n': 3})
    await press(a); await press(b); await press(a); await press(a); await press(b); await press(a); await ev(b, 'T.trim()'); await press(b, 600)
    ia, ib = await info(a), await info(b)
    ck("Upkeep stop: the turn holds in the upkeep", ib['turn']['n'] == 4 and ib['turn']['phase'] == 0 and ib['turn']['hold']['at'] == 'up' and ia['text'] == 'OK: Bob leaves upkeep', (ib['turn'], ia['text']))
    h0 = ib['hand']
    await press(a, 500); ia, ib = await info(a), await info(b)
    ck('after the OK: the draw, then the Draw stop', ib['turn']['phase'] == 1 and ib['turn']['hold']['at'] == 'draw' and ib['hand'] == h0 + 1 and ia['text'] == 'OK: Bob leaves the draw step', (ib['turn'], ib['hand'], h0, ia['text']))
    await press(a, 500); ib = await info(b)
    ck('after the OK: Main 1', ib['turn']['phase'] == 2 and 'hold' not in ib['turn'] and ib['turn']['okd'] == {'up': 1, 'draw': 1}, ib['turn'])
    await press(b); ia, ib = await info(a), await info(b)
    ck('Main 1 stop', ib['turn']['phase'] == 2 and ib['turn']['hold']['at'] == 'm1' and ia['text'] == 'OK: Bob leaves Main 1', (ib['turn'], ia['text']))
    await press(a, 500); ia, ib = await info(a), await info(b)
    ck('then straight into the Before attackers stop', ib['turn']['phase'] == 3 and ib['turn']['hold']['at'] == 'atk' and ia['text'] == 'OK: Bob declares attackers', (ib['turn'], ia['text']))
    await press(a); await press(b); await press(b); await press(a); await press(b)
    # own-turn stops; back to the usual
    await a.click('#turnlbl'); await a.wait_for_timeout(200); await a.click('#ctx [data-usual]'); await a.wait_for_timeout(150)
    ck('Back to the usual stops (Main 2 back on Auto)', await ev(a, "[...document.querySelectorAll('#ctx [data-stop]')].map(x=>x.classList.contains('on'))") == [False, False, False, False, False, True, False] and await ev(a, 'myStops().auto'))
    await a.click('#ctx [data-stop="op:draw"]'); await a.keyboard.press('Escape')
    await b.click('#turnlbl'); await b.wait_for_timeout(200); await b.click('#ctx [data-stop="me:up"]'); await b.click('#ctx [data-stop="me:draw"]'); await b.click('#ctx [data-stop="op:atk"]'); await b.click('#ctx [data-stop="op:m2"]'); await b.keyboard.press('Escape'); await b.wait_for_timeout(200)
    await ev(a, 'T.trim()'); await press(a, 500); ia = await info(a)
    ck('with no stops of Bob’s, Ann plays her whole turn without waiting', ia['turn']['n'] == 5 and ia['turn']['phase'] == 2, ia['turn'])
    await press(a); await press(a); await press(a); await press(a); ia, ib = await info(a), await info(b)
    ck('she passes', ia['turn'].get('passed') and ib['text'] == 'Start my turn', (ia['turn'], ib['text']))
    await ev(b, 'T.trim()'); await press(b, 500); ib = await info(b)
    ck('own Upkeep stop (today’s "pause on my next upkeep", standing): my turn stops in my upkeep', ib['turn']['n'] == 6 and ib['turn']['phase'] == 0 and 'hold' not in ib['turn'] and ib['text'] == 'Next: Draw' and any('stops in the upkeep: they asked to stop here' in l for l in ib['log']), (ib['turn'], ib['text'], ib['log']))
    ck('gold dashes bright under Upkeep and Draw', ib['dash'][0] == 'a off/b on' and ib['dash'][1] == 'a off/b on' and ib['dash'][3] == 'a fx/b fx', ib['dash'])
    await press(b, 500); ib = await info(b)
    ck('own Draw stop: stops after the draw', ib['turn']['phase'] == 1 and 'hold' not in ib['turn'] and any('stops in the draw step' in l for l in ib['log']), (ib['turn'], ib['log']))
    await press(b, 500); ia, ib = await info(a), await info(b)
    ck("then the other player's Draw stop asks them", ib['turn']['phase'] == 1 and ib['turn']['hold']['at'] == 'draw' and ia['text'] == 'OK: Bob leaves the draw step', (ib['turn'], ia['text']))
    await press(a, 500)
    bea = await ev(b, PERM_JS, BEACON); await b.wait_for_timeout(600)
    ck("Ann's Main 2 Auto turns on for Bob's end-step card, with a note to Ann", any('Stop turned on: Main 2 on Bob' in l for l in (await info(a))['log']) and await ev(b, 'G.oppStops.m2'), (await info(a))['log'])
    await b.click('#phases [data-ph="5"]'); await b.wait_for_timeout(400); ia, ib = await info(a), await info(b)
    ck('clicking the End chip from Main 1 stops in Main 2 for the OK', ib['turn']['phase'] == 4 and ib['turn']['hold']['at'] == 'm2' and ia['text'] == 'OK: Bob goes to the end step', (ib['turn'], ia['text']))
    await ev(b, "(id)=>{ move(id,'gy',{silent:true}); changed(); }", bea); await b.wait_for_timeout(300)     # its end-step trigger isn't part of this test
    await press(a, 500); ib = await info(b)
    ck('and goes on to the end step after it', ib['turn']['phase'] == 5 and 'hold' not in ib['turn'], ib['turn'])
    # a one-time pause is untouched, and answers the standing stop at the same point
    await a.click('#turnlbl'); await a.wait_for_timeout(150); await a.click('#ctx [data-stop="op:up"]'); await a.keyboard.press('Escape')      # Ann: standing Upkeep stop on Bob's turns
    await ev(b, "askPause('up')"); await press(b); await ev(a, 'T.trim()'); await press(a, 600); ia, ib = await info(a), await info(b)
    ck('one-time pause: gold "Pass priority back", as before', ia['turn'].get('hold') == {'pid': 'p2', 'at': 'up'} and ib['text'] == 'Pass priority back' and ib['cls'] == [] and ia['text'] == 'Paused: Bob has priority' and ia['dis'], (ia['turn'], ib['text'], ia['text']))
    await press(b, 600); ia = await info(a)
    ck('passing it back continues the turn', ia['turn']['phase'] == 2 and 'hold' not in ia['turn'], ia['turn'])


# ----------------------------------------------------------------------------------------------- order (v5.02)
TRIGS_JS = """(L)=>{ const out=[]; for(const [n,o] of L){ const t=mk(null,{tok:true, ts:Date.now(), ab:{id:'x', tr:true}, cu:{n:n+': trigger', t:'Triggered ability', o, img:''}}); G.me.st.push(t); out.push(t.id); } changed(); return out; }"""
PANEL_JS = """(()=>{ const el=document.querySelector('#coPanel'); if(!el || el.hidden) return null; return {head:(el.querySelector('header b')||{}).textContent, cards:[...el.querySelectorAll('#coTr .card[data-id]')].map(x=>x.dataset.id), btns:[...el.querySelectorAll('[data-co]')].map(x=>x.textContent)}; })()"""
PAIR = [['Test Ocelot', 'You gain 1 life.'], ['Test Haliya', 'You gain 2 life.']]


async def drag_last_to_front(p):
    """Drag the rightmost card of the panel's row to the far left (the bottom of the stack)."""
    cs = p.locator('#coTr .card[data-id]'); n = await cs.count()
    a = await cs.nth(n - 1).bounding_box(); b = await cs.nth(0).bounding_box()
    await p.mouse.move(a['x'] + a['width'] / 2, a['y'] + a['height'] / 2); await p.mouse.down()
    for k in range(1, 9):
        await p.mouse.move(a['x'] + a['width'] / 2 + (b['x'] + 4 - a['x'] - a['width'] / 2) * k / 8, a['y'] + a['height'] / 2); await p.wait_for_timeout(20)
    await p.mouse.up(); await p.wait_for_timeout(200)


async def t_order(env, A):
    a, b = await table(env); await stage(a, b)
    ids = await ev(a, TRIGS_JS, PAIR); await a.wait_for_timeout(500); ia, ib = await info(a), await info(b); pa = await ev(a, PANEL_JS)
    ck('two triggers at once: the ordering panel opens for their controller', pa and pa['head'] == 'Order your triggers' and pa['cards'] == ids and pa['btns'] == ['Add to stack and remember this order', 'Add to stack'], pa)
    ck('meanwhile they are not on the stack for either player (held in the panel)', await ev(a, "document.querySelectorAll('#stack .card').length") == 0 and ib['ost'] == [] and await ev(a, 'priStack().length') == 0, (ia['st'], ib['ost']))
    ck('both big buttons wait', ia['text'] == 'Order your triggers' and ia['dis'] and ib['text'] == 'Ann is ordering triggers' and ib['dis'], (ia['text'], ib['text']))
    t0 = ia['turn']; await b.keyboard.press('Space'); await a.keyboard.press('Space'); await a.wait_for_timeout(300)
    ck('Space does nothing while ordering', (await info(a))['turn'] == t0)
    await drag_last_to_front(a)
    ck('dragging reorders the row', (await ev(a, PANEL_JS))['cards'] == [ids[1], ids[0]], await ev(a, PANEL_JS))
    await a.click('#coPanel [data-co="add"]'); await a.wait_for_timeout(600); ia, ib = await info(a), await info(b)
    ck('Add to stack: on the stack in that order (Ocelot on top)', ia['st'] == ['Test Haliya: trigger', 'Test Ocelot: trigger'] and ib['text'] == 'OK: Test Ocelot trigger resolves' and await ev(a, PANEL_JS) is None, (ia['st'], ib['text']))
    ck('logged for both', any('in the order they chose (top: Test Ocelot)' in l for l in ib['log']), ib['log'])
    l0 = ia['life']; await press(b, 700); ia = await info(a)
    ck('the top one resolves first', ia['life'] == l0 + 1 and ia['st'] == ['Test Haliya: trigger'], (ia['life'], ia['st']))
    await settle(a, b); ia = await info(a)
    ck('then the other', ia['life'] == l0 + 3 and ia['st'] == [], ia['life'])
    # remember
    ids = await ev(a, TRIGS_JS, PAIR); await a.wait_for_timeout(500); await drag_last_to_front(a)
    await a.click('#coPanel [data-co="addmem"]'); await a.wait_for_timeout(500); await settle(a, b)
    ck('Add and remember: the order is kept for the table', await ev(a, 'PRI.tord.length') == 1 and any('the order is remembered' in l for l in (await info(b))['log']))
    ids = await ev(a, TRIGS_JS, PAIR); await a.wait_for_timeout(500); ia = await info(a)
    ck('next time: no panel, the remembered order at once', await ev(a, PANEL_JS) is None and ia['st'] == ['Test Haliya: trigger', 'Test Ocelot: trigger'] and any('in the remembered order (top: Test Ocelot)' in l for l in ia['log']), (ia['st'], ia['log']))
    await settle(a, b)
    await a.click('#turnlbl'); await a.wait_for_timeout(200)
    row = await ev(a, "[...document.querySelectorAll('#ctx > button')].map(x=>x.textContent).find(x=>/^Trigger orders/.test(x))")
    ck('the turn menu lists it, in resolving order', row == 'Trigger orders: Test Ocelot first, then Test Haliyaclick to forget', row)
    await a.locator('#ctx > button', has_text='Trigger orders').click(); await a.wait_for_timeout(200)
    ck('a click forgets it', await ev(a, 'PRI.tord.length') == 0)
    await ev(a, TRIGS_JS, [PAIR[0], PAIR[0]]); await a.wait_for_timeout(500)
    ck('the same trigger twice: no panel', await ev(a, PANEL_JS) is None and len((await info(a))['st']) == 2)
    await settle(a, b)
    # the other player's triggers on Ann's turn
    bids = await ev(b, TRIGS_JS, [['Bob Spark', 'You gain 1 life.'], ['Bob Glow', 'You gain 2 life.']]); await b.wait_for_timeout(500); ia, ib = await info(a), await info(b)
    ck('the non-active player gets the panel too', (await ev(b, PANEL_JS) or {}).get('cards') == bids and ib['text'] == 'Order your triggers' and ia['text'] == 'Bob is ordering triggers', (ia['text'], ib['text']))
    t0 = ia['turn']; await press(a); ck("the active player's Next waits", (await info(a))['turn'] == t0)
    await b.click('#coPanel [data-co="add"]'); await b.wait_for_timeout(600); ia = await info(a)
    ck("Bob's go on the stack, Ann is asked", ia['ost'] == ['Bob Spark: trigger', 'Bob Glow: trigger'] and ia['text'] == 'OK: Bob Glow trigger resolves', (ia['ost'], ia['text']))
    await settle(a, b)
    # both at once (APNAP): whoever finishes ordering first, Bob's (the non-active player's) end up on top
    for first in ('ann', 'bob'):
        await ev(a, TRIGS_JS, PAIR); await ev(b, TRIGS_JS, [['Bob Spark', 'You gain 1 life.'], ['Bob Glow', 'You gain 2 life.']]); await a.wait_for_timeout(600)
        order = (a, b) if first == 'ann' else (b, a)
        for p in order:
            await p.click('#coPanel [data-co="add"]'); await p.wait_for_timeout(700)
        stk = await ev(a, "priStack().map(x=>cdata(x.c).n.replace(': trigger',''))"); stb = await ev(b, "priStack().map(x=>cdata(x.c).n.replace(': trigger',''))")
        ck('both order at once, %s first: Bob\'s on top of Ann\'s, the same on both screens' % ('Ann' if first == 'ann' else 'Bob'), stk == ['Test Ocelot', 'Test Haliya', 'Bob Spark', 'Bob Glow'] and stb == stk, (stk, stb))
        await settle(a, b, limit=20)
    # a real end step: two end-step permanents trigger together
    await ev(a, PERM_JS, ['End Cat', 'Enchantment', '', 'At the beginning of your end step, you gain 1 life.'])
    await ev(a, PERM_JS, ['End Warp', 'Enchantment', '', 'At the beginning of your end step, you gain 2 life.']); await a.wait_for_timeout(500)
    for _ in range(4):
        if (await info(a))['turn']['phase'] == 5: break
        await press(a, 400); await settle(a, b)
    await a.wait_for_timeout(500); pa = await ev(a, PANEL_JS)
    ck('at the beginning of the end step, both end-step triggers open the panel', (await info(a))['turn']['phase'] == 5 and pa and len(pa['cards']) == 2, ((await info(a))['turn'], pa))
    await a.click('#coPanel [data-co="add"]'); await a.wait_for_timeout(500); n = await settle(a, b)
    ck('and resolve after the OKs', n >= 2 and (await info(a))['st'] == [], n)


# ----------------------------------------------------------------------------------------------- auto (v5.01)
async def t_auto(env, A):
    a, b = await table(env)
    ia, ib = await info(a), await info(b)
    ck('Ann turn 1 Main 1, no creatures: button says Main 2 (no attackers)', ia['turn']['phase'] == 2 and ia['text'] == 'Next: Main 2 (no attackers)', ia['text'])
    ck("Ann's page holds Bob's stops: atk on, m2 off, Auto on", await ev(a, 'G.oppStops') == {'up': False, 'draw': False, 'm1': False, 'atk': True, 'm2': False, 'ea': True}, await ev(a, 'G.oppStops'))
    ck('dashes: blue over Combat bright, Main 2 empty', ia['dash'] == ['a off/b off', 'a off/b off', 'a off/b fx', 'a on/b fx', 'a off/b fx', 'a fx/b fx'], ia['dash'])
    await press(a); ia, ib = await info(a), await info(b)
    ck('Next goes straight to Main 2, no stop, logged', ia['turn']['phase'] == 4 and 'hold' not in ia['turn'] and ib['cls'] == [] and any('no creature that can attack' in l for l in ia['log']), (ia['turn'], ia['log']))
    await press(a); ia = await info(a)
    ck('no Main 2 stop by default: end step', ia['turn']['phase'] == 5 and 'hold' not in ia['turn'], ia['turn'])
    await press(a); await ev(b, 'T.trim()'); await press(b, 500); ib = await info(b)
    ck('Bob turn 2 Main 1', ib['turn']['n'] == 2 and ib['turn']['phase'] == 2, ib['turn'])
    await ev(b, PERM_JS, ['Test Bear', 'Creature — Bear', '2/2']); await b.wait_for_timeout(300); ib = await info(b)
    ck('with a creature that can attack: Next: Combat', ib['text'] == 'Next: Combat', ib['text'])
    await press(b); ia, ib = await info(a), await info(b)
    ck('before attackers stop holds when Bob can attack', ib['turn']['phase'] == 3 and ib['turn'].get('hold', {}).get('at') == 'atk' and ia['text'] == 'OK: Bob declares attackers', (ib['turn'], ia['text']))
    await press(a); ib = await info(b)
    ck('OK: attack bar', ib['atkBar'], ib)
    await ev(b, "atkNone()"); await b.wait_for_timeout(300); await press(b); ib = await info(b)
    ck('Bob end step (no Main 2 stop)', ib['turn']['phase'] == 5 and 'hold' not in ib['turn'], ib['turn'])
    await press(b); await ev(a, 'T.trim()'); await press(a, 500)
    # Ann turn 3: a summoning-sick creature, a defender, a tapped creature
    await ev(a, PERM_JS, ['Sick Bear', 'Creature — Bear', '2/2', '', 1])
    await ev(a, PERM_JS, ['Test Wall', 'Creature — Wall', '0/4', 'Defender'])
    tid = await ev(a, PERM_JS, ['Tapped Bear', 'Creature — Bear', '2/2']); await ev(a, "(id)=>{ find(id).c.tap=true; changed(); }", tid); await a.wait_for_timeout(300)
    ia = await info(a)
    ck('sick, defender and tapped creatures are not attackers', ia['text'] == 'Next: Main 2 (no attackers)', ia['text'])
    land = await ev(a, PERM_JS, ['Test Vault', 'Land', '', '{T}: Add {C}.\n{1}: This land becomes a 2/2 creature with all creature types until end of turn. It\'s still a land.']); await a.wait_for_timeout(250)
    ck('a land that can become a creature counts', (await info(a))['text'] == 'Next: Combat')
    await ev(a, "(id)=>{ move(id,'gy',{silent:true}); changed(); }", land)
    ct = await ev(a, PERM_JS, ['Test Banner', 'Enchantment', '', 'At the beginning of combat on your turn, you gain 1 life.']); await a.wait_for_timeout(250)
    ck('a beginning-of-combat trigger keeps combat', (await info(a))['text'] == 'Next: Combat')
    await ev(a, "(id)=>{ move(id,'gy',{silent:true}); changed(); }", ct); await a.wait_for_timeout(250)
    # the end-step card turns Bob's Main 2 stop on
    await ev(a, PERM_JS, BEACON); await a.wait_for_timeout(700)
    ia, ib = await info(a), await info(b)
    ck("Bob is told the stop turned on", any('Stop turned on: Main 2 on Ann' in l and 'Test Beacon' in l for l in ib['log']) and 'Stop turned on' in ib['toast'], (ib['log'], ib['toast']))
    ck("Ann's log doesn't say it (private)", not any('Stop turned on' in l for l in ia['log']))
    ck("Ann's page has Bob's Main 2 on", (await ev(a, 'G.oppStops'))['m2'] is True)
    ck("Bob's dash over Main 2 is bright", ib['dash'][4].startswith('a on'), ib['dash'])
    await press(a); ia = await info(a)
    ck('Ann still skips combat (no attackers)', ia['turn']['phase'] == 4, ia['turn'])
    await press(a); ia, ib = await info(a), await info(b)
    ck('Main 2 holds for Bob\'s OK', ia['turn'].get('hold', {}).get('at') == 'm2' and ib['text'] == 'OK: Ann goes to the end step', (ia['turn'], ib['text']))
    await press(b, 500); ia = await info(a)
    ck('after the OK: end step', ia['turn']['phase'] == 5 and 'hold' not in ia['turn'], ia['turn'])
    # Bob's grid: Auto with the card, then the cycle
    await b.click('#turnlbl'); await b.wait_for_timeout(250)
    g = lambda: ev(b, "(()=>{ const x=document.querySelector('#ctx [data-stop=\"op:m2\"]'); return [x.className, x.nextElementSibling.textContent]; })()")
    v = await g(); ck('grid: Main 2 Auto, lit, names the card', 'on' in v[0] and 'auto' in v[0] and v[1] == 'Auto: Test Beacon', v)
    await b.click('#ctx [data-stop="op:m2"]'); await b.wait_for_timeout(250); v = await g(); s = await ev(a, 'G.oppStops')
    ck('click: Off (sent: m2 off, Auto off)', 'on' not in v[0].split() and v[1] == 'Off' and s['m2'] is False and s['ea'] is False, (v, s))
    await b.click('#ctx [data-stop="op:m2"]'); await b.wait_for_timeout(250); v = await g(); s = await ev(a, 'G.oppStops')
    ck('click: Always', 'on' in v[0].split() and 'auto' not in v[0] and v[1] == 'Always' and s['m2'] is True, (v, s))
    await b.click('#ctx [data-stop="op:m2"]'); await b.wait_for_timeout(250); v = await g()
    ck('click: back to Auto', 'auto' in v[0] and v[1] == 'Auto: Test Beacon', v)
    ck('no "turned on" note for my own clicks', sum('Stop turned on' in l for l in (await info(b))['log']) == 1)
    # the checkmarks sit in the middle of their boxes
    off = await ev(b, """(()=>{ const out=[]; for(const x of document.querySelectorAll('#ctx .sgrid .box')){ if(!x.textContent) continue; const r=document.createRange(); r.selectNodeContents(x); const t=r.getBoundingClientRect(), o=x.getBoundingClientRect(); out.push([x.tagName, +(t.left+t.width/2-(o.left+o.width/2)).toFixed(1), +(t.top+t.height/2-(o.top+o.height/2)).toFixed(1)]); } return out; })()""")
    ck('every ✓ centred within 1.5 px (buttons and locked boxes)', off and all(abs(x[1]) <= 1.5 and abs(x[2]) <= 1.5 for x in off), off)
    await b.keyboard.press('Escape')
    # the card leaves: Auto drops the stop again
    await ev(a, "(()=>{ const c=G.me.bf.find(x=>cdata(x).n==='Test Beacon'); move(c.id,'gy',{silent:true}); changed(); })()"); await a.wait_for_timeout(700)
    ck("card gone: Ann's page has Main 2 off again", (await ev(a, 'G.oppStops'))['m2'] is False)
    await auto_saved(env, A)


async def auto_saved(env, A):
    p = await env.ctx('mig')
    await p.goto(env.url()); await p.wait_for_selector('#hostBtn', timeout=20000)
    await ev(p, "localStorage.setItem('mt_settings', JSON.stringify({name:'X', stops:{mine:{up:true, draw:false}, opp:{up:false, draw:false, m1:true, atk:true, m2:true}}}))")
    await p.reload(); await p.wait_for_selector('#hostBtn', timeout=20000); await p.wait_for_timeout(500)
    s = await ev(p, "JSON.parse(localStorage.getItem('mt_settings')).stops")
    ck('saved v5.0 stops: Main 2 back to Auto, the rest kept', s['opp']['m2'] is False and s['opp']['m1'] is True and s['mine']['up'] is True and s['v'] == 2 and await ev(p, 'myStops().auto') is True, s)


# ----------------------------------------------------------------------------------------------- waits
async def waits_run(env, mode, old):
    """One scripted game through every older wait. mode: 'old' (two v4.137 pages), 'off', 'on'. Returns (trace, OKs given)."""
    a, b = await table_for_waits(env, mode, old)
    T, oks = [], [0]

    async def snap(label, toast=False):
        oks[0] += await settle(a, b)
        ia, ib = await info(a), await info(b)
        row = {'at': label, 'a': [ia['text'], ia['dis']], 'b': [ib['text'], ib['dis']], 'turn': strip(ia['turn']), 'turn_b': strip(ib['turn']), 'draw': [ia['draw'], ib['draw']], 'modal': [ia['modal'], ib['modal']],
               'banner': [ia['banner'], ib['banner']], 'life': [ia['life'], ib['life']], 'bars': [ia['atkBar'], ia['blockBar'], ib['atkBar'], ib['blockBar']]}
        if toast:
            row['toast'] = [ia['toast'], ib['toast']]
        T.append(row); return ia, ib

    async def go(p):
        await press(p, trim=False); oks[0] += await settle(a, b)

    await snap('game started')
    # turn 1, Ann: attack with a creature, Bob has no blocker
    bear = await ev(a, "T.perm('Test Bear','Creature — Bear','2/2')")
    await go(a)
    await snap('combat, before attackers are declared')
    await ev(a, "(id)=>{ G.atkSel=new Set([id]); atkCommit(); }", bear); await a.wait_for_timeout(450)
    await snap('blocks: Done blocking / waiting for blocks')
    await go(b)
    await snap('blocks done: apply combat damage')
    await go(a)
    await snap('combat damage applied')
    await go(a); await go(a); await go(a)
    await snap('Ann passed: Start my turn', toast=True)
    # turn 2, Bob: attack into a blocker; a one-time pause is asked for Ann's upkeep; Bob ends with nine cards
    await ev(b, 'T.trim()'); await go(b)
    await snap('turn 2 started')
    bbear = await ev(b, "T.perm('Test Bear','Creature — Bear','2/2')")
    wall = await ev(a, "T.perm('Test Wall','Creature — Wall','0/4')")
    await go(b)
    await ev(b, "(id)=>{ G.atkSel=new Set([id]); atkCommit(); }", bbear); await b.wait_for_timeout(450)
    await ev(a, "([w,x])=>{ startMode('block', w); finishMode(x); }", [wall, bbear]); await a.wait_for_timeout(300)
    await snap('Ann has declared a block')
    await go(a)
    await snap('Ann is done blocking')
    await go(b)
    await snap('blocked damage applied')
    await ev(b, "askPause('up')"); await b.wait_for_timeout(200)
    await ev(b, "(()=>{ T.trim(0); T.give('Mountain', 9); })()"); await b.wait_for_timeout(300)
    await go(b); await go(b); await go(b)
    await snap('Bob passed with nine cards')
    await press(a, 600, trim=False)
    ia, ib = await snap('cleanup: Ann waits while Bob discards', toast=True)
    n = await b.locator('#dcGrid .card').count()
    for i in range(2):
        await b.locator('#dcGrid .card').nth(i).click()
    await b.locator('#modal footer button', has_text='Discard').click(); await b.wait_for_timeout(800)
    await snap('turn 3 started by itself; paused in the upkeep')
    await go(b)
    await snap('Bob passed priority back: Ann is in Main 1')
    # turn 3, Ann: nothing special; she will owe a pact; Ann asks to pause Bob's draw step before the draw
    await ev(a, "(()=>{ G.me.pacts=[{n:G.turn.n, cost:'{2}{G}{G}', name:\"Summoner's Pact\", img:''}]; changed(); })()")
    await ev(a, "askPause('pre')"); await a.wait_for_timeout(200)
    await ev(a, 'T.trim()'); await go(a); await go(a); await go(a); await go(a); await go(a)
    await snap('Ann passed turn 3')
    await ev(b, 'T.trim()'); await go(b)
    await snap('turn 4: paused in the draw step before the draw')
    hb = (await info(b))['hand']
    await go(a)
    ia, ib = await snap('passed back: Bob drew and is in Main 1')
    T[-1]['drew'] = ib['hand'] - hb
    await ev(b, "askPause('post')"); await b.wait_for_timeout(200)
    await ev(b, 'T.trim()'); await go(b); await go(b); await go(b); await go(b); await go(b)
    await snap('Bob passed turn 4')
    # turn 5, Ann: the pact trigger holds the upkeep; the pact draw gate
    await ev(a, 'T.trim()'); await go(a)
    await snap('turn 5: the pact trigger stops the upkeep')
    await press(a, 400)
    await snap('leaving the upkeep with the pact: Are you certain?')
    await a.locator('#modal footer button', has_text='Yes').click(); await a.wait_for_timeout(600)
    await snap('pact gate: Ann waits to draw, Bob is asked')
    await b.locator('#modal footer button', has_text='Let them draw').click(); await b.wait_for_timeout(600)
    await snap('Bob let her draw: Main 1, the pact trigger still on the stack')
    await a.click('#stack .card'); await a.wait_for_timeout(300)
    T.append({'at': 'the pact panel opens from the trigger', 'panel': await ev(a, "!document.querySelector('#pactPanel').hidden")})
    await a.click('#pactPanel [data-pk="exit"]'); await a.wait_for_timeout(400)
    await snap('pact closed')
    # still turn 5: Ann hands Bob control of this turn
    await ev(a, 'giveControl()'); await a.wait_for_timeout(500)
    await snap('Bob controls Ann’s turn')
    await press(b, 500)
    await snap('Bob pressed Next for her: combat')
    await press(b, 500); await press(b, 500)
    await snap('Bob moved her to the end step')
    await ev(a, 'T.trim()'); await press(b, 800)
    await snap('the controlled turn ended: Ann’s extra turn, paused after the draw')
    await go(b)
    await snap('passed back: Ann is in Main 1 of her extra turn')
    await env.close_all()
    return T, oks[0]


async def table_for_waits(env, mode, old):
    o = old if mode == 'old' else None
    a, b = await seat(env, o, o, seed=4242)
    if mode == 'off':
        await ev(a, 'priToggle(false)'); await a.wait_for_timeout(300)
    # mulligans: Bob takes one; while he decides, Ann can't start
    for _ in range(40):
        for p in (a, b):
            bt = await banner_btns(p)
            if 'rollboth' in bt and p is a: await p.click('#banner [data-first="rollboth"]')
            elif 'nocomp' in bt: await p.click('#banner [data-first="nocomp"]')
            elif 'play' in bt: await p.click('#banner [data-first="%s"]' % ('play' if p is a else 'draw'))
            elif 'deal' in bt: await p.click('#banner [data-first="deal"]')
            await p.wait_for_timeout(100)
        if await ev(a, 'G.turn.n && G.me.dealt') and await ev(b, 'G.turn.n && G.me.dealt'):
            break
    await a.click('#banner [data-first="keep"]'); await a.wait_for_timeout(300); await ev(a, 'closeModal()')
    await b.click('#banner [data-first="mull"]'); await b.wait_for_timeout(400)
    await a.keyboard.press('Space'); await a.wait_for_timeout(250)
    mw = await ev(a, "({toast:document.querySelector('#toast').textContent, banner:document.querySelector('#banner').textContent, turn:G.turn, btn:document.querySelector('#next').textContent})")
    mw['btn'] = mw['btn'].replace(SKIP, 'Next: Combat')       # v5.01 names the skip on the button (the board is staged later)
    table_for_waits.mull = mw
    await b.click('#banner [data-first="keep"]'); await b.wait_for_timeout(400)
    await b.locator('#mbGrid .card').first.click(); await b.locator('#modal footer button.go').click(); await b.wait_for_timeout(500)
    for p in (a, b):
        await ev(p, 'closeModal()'); await ev(p, T_JS)
    await stage(a, b, m2=(mode == 'on'))
    return a, b


async def t_waits(env, A):
    runs = {}
    for mode in (['old'] if A.oldhtml else []) + ['off', 'on']:
        print('    -- the scripted game, ' + {'old': 'two v4.137 pages', 'off': 'two new pages, Priority off', 'on': 'two new pages, Priority on'}[mode], flush=True)
        T, n = await waits_run(env, mode, A.oldhtml)
        runs[mode] = (T, n, table_for_waits.mull)
    if not A.oldhtml:
        ck('SKIPPED: no v4.137 page to compare with (give one with --old)', True)
    off, on = runs['off'], runs['on']
    mw = off[2]
    ck('mulligans: Ann cannot start while Bob decides', 'Waiting for Bob to finish their mulligan decisions' in mw['toast'] and 'Waiting for Bob to finish their mulligan decisions' in mw['banner'] and mw['turn']['phase'] == 2, mw)
    ck('mulligans: the same with Priority on', on[2]['toast'] == mw['toast'] and on[2]['turn'] == mw['turn'], on[2])
    by = {r['at']: r for r in off[0]}
    exp = [
        ('blocks: Done blocking / waiting for blocks', lambda r: r['b'] == ['Done blocking', False] and r['a'] == ["Waiting for Bob's blocks", True] and r['turn'].get('cs') == 'blk' and r['bars'][3]),
        ('blocks done: apply combat damage', lambda r: r['a'] == ['Apply combat damage', False] and r['turn'].get('cs') == 'blkd'),
        ('combat damage applied', lambda r: r['life'] == [20, 18]),
        ('Ann passed: Start my turn', lambda r: r['b'] == ['Start my turn', False] and r['a'] == ['Waiting for Bob', True] and r['turn'].get('passed')),
        ('Ann is done blocking', lambda r: r['b'] == ['Apply combat damage', False]),
        ('blocked damage applied', lambda r: r['life'] == [20, 18]),
        ('cleanup: Ann waits while Bob discards', lambda r: 'Waiting for Bob to discard down to seven cards' in r['toast'][0] and r['modal'][1] is not None and r['turn']['n'] == 2),
        ('turn 3 started by itself; paused in the upkeep', lambda r: r['turn']['n'] == 3 and r['turn'].get('hold') == {'pid': 'p2', 'at': 'up'} and r['b'] == ['Pass priority back', False] and r['a'] == ['Paused: Bob has priority', True]),
        ('Bob passed priority back: Ann is in Main 1', lambda r: r['turn'] == {'active': 'p1', 'phase': 2, 'n': 3}),
        ('turn 4: paused in the draw step before the draw', lambda r: r['turn'].get('hold') == {'pid': 'p1', 'at': 'pre'} and r['turn']['phase'] == 1 and r['a'] == ['Pass priority back', False]),
        ('passed back: Bob drew and is in Main 1', lambda r: r['turn']['phase'] == 2 and r['drew'] == 1),
        ('turn 5: the pact trigger stops the upkeep', lambda r: r['turn'] == {'active': 'p1', 'phase': 0, 'n': 5} and r['a'] == ['Next: Draw', False]),
        ('leaving the upkeep with the pact: Are you certain?', lambda r: r['modal'][0] == 'Are you certain?'),
        ('pact gate: Ann waits to draw, Bob is asked', lambda r: r['draw'][0] == 'Waiting for Bob… (disabled)' and r['modal'][1] == 'Pact trigger still on the stack' and r['turn']['phase'] == 1),
        ('Bob let her draw: Main 1, the pact trigger still on the stack', lambda r: r['turn']['phase'] == 2 and r['draw'][0] is None),
        ('the pact panel opens from the trigger', lambda r: r['panel'] is True),
        ('Bob controls Ann’s turn', lambda r: r['b'] == ['Next: Combat', False]),
        ('Bob pressed Next for her: combat', lambda r: r['turn']['phase'] == 3),
        ('Bob moved her to the end step', lambda r: r['turn']['phase'] == 5 and r['b'] == ['End their turn', False]),
        ('the controlled turn ended: Ann’s extra turn, paused after the draw', lambda r: r['turn']['n'] == 6 and r['turn'].get('hold') == {'pid': 'p2', 'at': 'post'} and r['b'] == ['Pass priority back', False]),
        ('passed back: Ann is in Main 1 of her extra turn', lambda r: r['turn'] == {'active': 'p1', 'phase': 2, 'n': 6}),
    ]
    for at, fn in exp:
        r = by.get(at)
        ck('Priority off · ' + at, r is not None and fn(r), r)
    if A.oldhtml:
        old = runs['old']
        same = old[0] == off[0]
        diff = next(((x, y) for x, y in zip(old[0], off[0]) if x != y), None) if not same else None
        ck('Priority off is v4.137: all %d checkpoints of the game are identical on two v4.137 pages and on two new pages with Priority off' % len(off[0]), same and len(old[0]) == len(off[0]), diff)
        ck('v4.137 mulligan wait identical', old[2] == off[2], (old[2], off[2]))
        ck('no OK was ever asked for with Priority off, or on v4.137', old[1] == 0 and off[1] == 0, (old[1], off[1]))
    same = on[0] == off[0]
    diff = next(((x, y) for x, y in zip(on[0], off[0]) if x != y), None) if not same else None
    ck('Priority on: the same game reaches the same %d checkpoints (every older wait unchanged) once the OKs are given' % len(off[0]), same, diff)
    ck('Priority on: OKs were asked for along the way (%d)' % on[1], on[1] >= 8, on[1])


# ----------------------------------------------------------------------------------------------- match
async def match_run(env, on):
    a, b = await table(env, seed=777)
    if not on:
        await ev(a, 'priToggle(false)'); await a.wait_for_timeout(300)
    R = {}
    # Ann loses game 1
    await ev(a, '(()=>{ G.me.life=0; changed(); })()'); await a.wait_for_timeout(1500)
    R['over'] = [(await info(a))['modal'], (await info(b))['modal']]
    R['live_over'] = await ev(a, 'priLive()')
    for p in (a, b):
        await p.locator('#modal footer button.go').click(); await p.wait_for_timeout(500)
    await a.wait_for_timeout(600)
    R['sb'] = [(await info(a))['modal'], (await info(b))['modal'], await ev(a, "!!document.querySelector('#sbClock')"), await ev(a, 'G.turn.n'), (await info(a))['wins'], (await info(b))['wins']]
    await a.locator('#modal footer button.go').click(); await a.wait_for_timeout(400)
    R['sb_wait'] = [(await info(a))['banner'], (await info(b))['modal']]
    await b.locator('#modal footer button.go').click(); await b.wait_for_timeout(600)
    await pregame(a, b, first='host')          # the loser (Ann) chooses: play
    await a.wait_for_timeout(300)
    await stage(a, b)
    R['game2'] = strip((await info(a))['turn'])
    R['live2'] = await ev(a, 'priLive()')
    await ev(a, "T.cast('Lightning Bolt','opp')"); await a.wait_for_timeout(500)
    R['bolt'] = [(await info(a))['text'], (await info(b))['text']]
    if on:
        await press(b, 700)
    else:
        await a.click('#stack .card'); await a.wait_for_timeout(500)
    R['bolt_done'] = (await info(b))['life']
    # the round clock runs out
    await ev(a, '(()=>{ G.mt.end=Date.now()+900; mtSend(); })()'); await a.wait_for_timeout(2600)
    R['time'] = [(await info(a))['modal'], (await info(b))['modal']]
    await a.locator('#modal footer button.go').click(); await a.wait_for_timeout(600)
    R['ext'] = [await ev(a, '!!(G.mt && G.mt.ext)'), await ev(b, '!!(G.mt && G.mt.ext)'), await ev(a, "document.querySelector('#turnSign').textContent"), (await info(b))['modal']]
    oks = 0
    for k in range(6):        # turn 0 and five more: each player passes in turn
        act, oth = (a, b) if (await ev(a, 'G.turn.active')) == 'p1' else (b, a)
        for _ in range(8):
            if await ev(act, 'G.turn.passed') or await ev(a, '!!(G.mt && G.mt.winq)'):
                break
            await ev(act, 'T.trim()'); await press(act, 250); oks += await settle(a, b)
        await a.wait_for_timeout(600)      # "Is there a winner?" comes a moment after the last pass: don't start another turn first
        if await ev(a, '!!(G.mt && G.mt.winq)'):
            break
        await ev(oth, 'T.trim()'); await press(oth, 500); oks += await settle(a, b)
    await a.wait_for_timeout(1200)
    R['winq'] = [(await info(a))['modal'], (await info(b))['modal'], await ev(a, 'G.turn.n')]
    R['oks'] = oks
    await a.locator('#modal footer button', has_text='We drew').click(); await a.wait_for_timeout(1500)
    R['over2'] = [await ev(a, 'G.mt.over'), (await info(a))['banner'], (await info(b))['banner'], await ev(a, 'priLive()')]
    await env.close_all()
    return R


async def t_match(env, A):
    off = await match_run(env, False)
    on = await match_run(env, True)
    ck('game loss: the game-over window for both', off['over'] == ['Bob wins the game', 'Bob wins the game'], off['over'])
    ck('sideboarding: both get the window with its 3:00 timer, the win is recorded', off['sb'][0] == 'Sideboarding' and off['sb'][1] == 'Sideboarding' and off['sb'][2] and off['sb'][3] == 0 and off['sb'][4] == [0, 1] and off['sb'][5] == [1, 0], off['sb'])
    ck('sideboarding: the one who is done waits for the other', off['sb_wait'][0] == 'Sideboarding' and off['sb_wait'][1] == 'Sideboarding', off['sb_wait'])
    ck('the next game starts with the loser choosing', off['game2'] == {'active': 'p1', 'phase': 2, 'n': 1}, off['game2'])
    ck('Priority off in game 2: a click resolves, nobody is asked', off['bolt'] == ['Next: Combat', "Opponent's turn"] and off['bolt_done'] == 17, (off['bolt'], off['bolt_done']))
    ck('Priority on in game 2: the spell waits for the OK', on['bolt'] == ["Waiting for Bob's OK", 'OK: Lightning Bolt resolves'] and on['bolt_done'] == 17, (on['bolt'], on['bolt_done']))
    ck('priority is not running while the game-over window is up', on['live_over'] is False and on['live2'] is True, (on['live_over'], on['live2']))
    ck('round clock at 0: both are asked about the end-of-round turns', off['time'] == ['Time', 'Time'], off['time'])
    ck('end-of-round turns: turn 0 sign, the other window closes', off['ext'][0] and off['ext'][1] and off['ext'][2].startswith('TURN 0') and off['ext'][3] is None, off['ext'])
    ck('after turn 5: Is there a winner?', off['winq'][0] == 'Is there a winner?' and off['winq'][1] == 'Is there a winner?', off['winq'])
    ck('the match ends on the answer', off['over2'][0] and off['over2'][1] == off['over2'][0], off['over2'])
    keys = ['over', 'sb', 'sb_wait', 'game2', 'time', 'ext', 'winq']
    diff = [(k, off[k], on[k]) for k in keys if off[k] != on[k]]
    ck('with Priority on every one of these is the same', not diff and on['over2'][:3] == off['over2'][:3], diff or (on['over2'], off['over2']))
    ck('with Priority on the end-of-round turns asked for OKs at the stops (%d), with it off for none' % on['oks'], on['oks'] >= 6 and off['oks'] == 0, (on['oks'], off['oks']))
    ck('priority stops when the match is over', on['over2'][3] is False)


# ----------------------------------------------------------------------------------------------- toggle
async def t_toggle(env, A):
    a, b = await table(env); await stage(a, b)
    await ev(b, "T.cast('Lightning Bolt','opp')"); await b.wait_for_timeout(500)
    ck('a spell is waiting for the host’s OK', (await info(a))['text'] == 'OK: Lightning Bolt resolves')
    # the guest can't
    await ev(b, 'settingsModal()'); await b.wait_for_timeout(250)
    row = await ev(b, "(()=>{ const r=document.querySelector('#setBody .setrow'); return {l:r.querySelector('.sl').childNodes[0].textContent, h:r.querySelector('small').textContent, b:[...r.querySelectorAll('button')].map(x=>x.textContent+(x.classList.contains('on')?'*':'')+(x.disabled?' disabled':''))}; })()")
    ck('the guest sees the row and its state, greyed out', row['l'] == 'Priority' and row['b'] == ['On* disabled', 'Off disabled'] and 'Only Ann, who opened this table, can change it.' in row['h'], row)
    await b.click('#setBody [data-set="pri"][data-v="off"]', force=True); await b.wait_for_timeout(200)
    ck('a click on it does nothing', await ev(b, 'priSet()') and await ev(a, 'priSet()'))
    ck('nor does the guest’s page calling the switch', await ev(b, 'priToggle(false)') is False and await ev(b, 'priSet()'))
    await ev(b, "G.conn.send({t:'pri', on:false})"); await b.wait_for_timeout(300)
    ck('nor a hand-made message from the guest’s page', await ev(a, 'priSet()') and await ev(a, 'priLive()') and (await info(a))['text'] == 'OK: Lightning Bolt resolves')
    # the host turns it off during the stack wait, from Settings
    await ev(a, 'settingsModal()'); await a.wait_for_timeout(250)
    row = await ev(a, "(()=>{ const r=document.querySelector('#setBody .setrow'); return {h:r.querySelector('small').textContent, b:[...r.querySelectorAll('button')].map(x=>x.textContent+(x.classList.contains('on')?'*':'')+(x.disabled?' disabled':''))}; })()")
    ck('the host’s row can be changed', row['b'] == ['On*', 'Off'] and 'You opened this table, so you choose for both players.' in row['h'], row)
    await a.click('#setBody [data-set="pri"][data-v="off"]'); await a.wait_for_timeout(500)
    rb = await ev(b, "[...document.querySelectorAll('#setBody .setrow')][0] ? [...document.querySelectorAll('#setBody .setrow')][0].querySelector('button.on').textContent : null")
    ck('the guest’s open Settings window follows', rb == 'Off', rb)
    for p in (a, b):
        await ev(p, 'closeModal()')
    ia, ib = await info(a), await info(b)
    ck('off during a stack wait: at once, the wait is gone on both pages', ia['text'] == "Opponent's turn" or ia['text'].startswith('Next'), ia['text'])
    ck('the table looks like v4.137 again: no band, no tags, no dashes, no hint', ia['bands'] == [] and ia['owns'] == [] and ib['owns'] == [] and ia['dash'] == [''] * 6 and ib['dash'] == [''] * 6 and ia['hint'] == '' and ib['hint'] == '' and ia['title'] == 'Modern Table', (ia, ib))
    ck('it is written to the log for both', any('Ann turned Priority off for this table.' in l for l in ia['log']) and any('Ann turned Priority off for this table.' in l for l in ib['log']), ib['log'])
    await b.click('#stack .card'); await b.wait_for_timeout(500)
    ck('the caster resolves with a click, as in v4.137', (await info(a))['life'] == 17 and (await info(b))['st'] == [])
    await b.click('#turnlbl'); await b.wait_for_timeout(200)
    ck('the turn menu is the old one', await ev(b, "!document.querySelector('#ctx .sgrid') && ![...document.querySelectorAll('#ctx button')].some(x=>/Always OK/.test(x.textContent))"))
    await b.keyboard.press('Escape')
    # on again mid-game, with a spell already on the stack
    await ev(b, "T.cast('Lightning Bolt','opp')"); await b.wait_for_timeout(400)
    await ev(a, 'priToggle(true)'); await a.wait_for_timeout(500); ia, ib = await info(a), await info(b)
    ck('on again mid-game: at once, the spell on the stack now waits', ia['text'] == 'OK: Lightning Bolt resolves' and ib['text'] == "Waiting for Ann's OK" and any('Ann turned Priority on for this table.' in l for l in ib['log']), (ia['text'], ib['text'], ib['log']))
    await press(a, 700)
    # off during a stop
    await press(a); ia, ib = await info(a), await info(b)
    ck('a stop is holding the turn', ia['turn'].get('hold', {}).get('at') == 'atk' and ib['text'] == 'OK: Ann declares attackers', (ia['turn'], ib['text']))
    await ev(a, 'priToggle(false)'); await a.wait_for_timeout(500); ia, ib = await info(a), await info(b)
    ck('off during a stop: the stop is released', 'hold' not in ia['turn'] and ia['atkBar'] and ia['text'] == 'Next: Main 2' and ib['text'] == "Opponent's turn", (ia['turn'], ia['text'], ib['text']))
    await press(a); await press(a); await press(a); ia, ib = await info(a), await info(b)
    ck('and the rest of the turn has no stops', ia['turn'].get('passed') and ib['text'] == 'Start my turn', (ia['turn'], ib['text']))
    await ev(a, 'priToggle(true)'); await a.wait_for_timeout(300)
    await ev(b, 'T.trim()'); await press(b, 500); await press(b); ia, ib = await info(a), await info(b)
    ck('on again: the next turn has its stops', ib['turn'].get('hold', {}).get('at') == 'atk' and ia['text'] == 'OK: Bob declares attackers', (ib['turn'], ia['text']))
    # the host turns it off while the OTHER player's turn is held at Main 2 (the release happens on the guest's page)
    await press(a); await press(b); await press(b); ib = await info(b)
    held = ib['turn'].get('hold', {}).get('at')
    await ev(a, 'priToggle(false)'); await a.wait_for_timeout(600); ib = await info(b)
    ck('off while the guest’s turn is held at Main 2: released, and the turn moves on to the end step', held == 'm2' and 'hold' not in ib['turn'] and ib['turn']['phase'] == 5, (held, ib['turn']))
    # a new table starts with it on again
    ck('the setting is kept with the table, not with the player', await ev(a, "JSON.parse(localStorage.getItem('mt_session')).pri.on") is False and await ev(a, "!('pri' in JSON.parse(localStorage.getItem('mt_settings')))"))


# ----------------------------------------------------------------------------------------------- oldpage
async def t_oldpage(env, A):
    if not A.oldhtml:
        ck('SKIPPED: no v4.137 page (give one with --old)', True); return
    NOTE = lambda n: "Priority is off at this table: %s's page is an older version. It turns on when they reload the page." % n
    # the guest is on the old page
    a, b = await table(env, old_b=A.oldhtml)
    ia = await info(a)
    ck('guest on v4.137: the page versions', ia['ver'].startswith('v5.') and (await info(b))['ver'] == 'v4.137', ia['ver'])
    ck('the table runs without priority', await ev(a, 'priLive()') is False and await ev(a, 'priSet()') is True and ia['dash'] == [''] * 6, ia['dash'])
    ck('and says so on screen, under the big button and in the log', ia['hint'] == NOTE('Bob') and await ev(a, "G.log.filter(l=>/Priority is off at this table/.test(l.text)).length") == 1, ia['hint'])
    await ev(a, 'settingsModal()'); await a.wait_for_timeout(200)
    h = await ev(a, "document.querySelector('#setBody .setrow small').textContent"); await ev(a, 'closeModal()')
    ck('Settings says so too', "Not running right now: Bob's page is an older version." in h, h)
    await ev(a, "T.cast('Lightning Bolt','opp')"); await a.wait_for_timeout(500); ia, ib = await info(a), await info(b)
    ck('a spell: no blue button, no band', ia['text'] == SKIP and ib['text'] == "Opponent's turn" and ia['bands'] == [] and ia['owns'] == [], (ia['text'], ib['text']))
    await a.click('#stack .card'); await a.wait_for_timeout(500)
    ck('a click resolves it, as in v4.137', (await info(b))['life'] == 17)
    await press(a); await press(a); await press(a); await press(a); ia, ib = await info(a), await info(b)
    ck('the turn has no stops', ia['turn'] == {'active': 'p1', 'phase': 5, 'n': 1, 'passed': True} and ib['text'] == 'Start my turn', (ia['turn'], ib['text']))
    await ev(b, 'T.trim()'); await press(b, 500); await press(b); await press(b); await press(b); await press(b)
    ck('the old page plays its turn as always', (await info(a))['text'] == 'Start my turn')
    # the old page reloads into the new one
    bctx = b.context; bctx._old = None
    await b.reload(); await b.wait_for_selector('#resumeBtn:not([hidden])', timeout=15000); await b.click('#resumeBtn')
    await b.wait_for_function('G.conn && G.conn.open && G.opp', timeout=40000); await ev(b, T_JS); await a.wait_for_timeout(800)
    ia, ib = await info(a), await info(b)
    ck('when they reload into v5.0, priority starts: the note is gone, the dashes are there', ib['ver'].startswith('v5.') and await ev(a, 'priLive()') and ia['hint'] == '' and ia['dash'][3] == 'a on/b fx', (ib['ver'], ia['hint'], ia['dash']))
    await ev(a, 'T.trim()'); await press(a, 500); await ev(a, "T.cast('Lightning Bolt','opp')"); await a.wait_for_timeout(600)
    ck('and a spell waits for the OK', (await info(b))['text'] == 'OK: Lightning Bolt resolves', (await info(b))['text'])
    await env.close_all()
    # the host is on the old page
    a, b = await table(env, old_a=A.oldhtml)
    ib = await info(b)
    ck('host on v4.137: no priority, and the guest is told', await ev(b, 'priLive()') is False and ib['hint'] == NOTE('Ann') and ib['dash'] == [''] * 6, ib)
    await ev(b, "T.cast('Lightning Bolt','opp')"); await b.wait_for_timeout(500)
    await b.click('#stack .card'); await b.wait_for_timeout(500)
    ck('a click resolves', (await info(a))['life'] == 17)
    await press(a); await press(a); await press(a); await press(a)
    ck('the old host plays its turn as always', (await info(b))['text'] == 'Start my turn')


# ----------------------------------------------------------------------------------------------- reload
async def resume(p, other):
    await p.reload(); await p.wait_for_selector('#resumeBtn:not([hidden])', timeout=15000); await p.click('#resumeBtn')
    try:
        await p.wait_for_function('G.conn && G.conn.open && G.opp && (G.oppPv||0)>=1', timeout=45000)
        await other.wait_for_function('G.conn && G.conn.open && (G.oppPv||0)>=1', timeout=45000)
    except Exception:
        for q in (p, other):
            print('          reload state', q._name, await q.evaluate("({net:G.net, conn:!!(G.conn&&G.conn.open), pv:G.oppPv, hello:G.oppHello, opp:!!G.opp})"))
        raise
    await ev(p, T_JS); await p.wait_for_timeout(700)


async def t_reload(env, A):
    a, b = await table(env); await stage(a, b)
    await ev(a, "T.cast('Lightning Bolt','opp')"); await a.wait_for_timeout(500)
    await resume(a, b); ia, ib = await info(a), await info(b)
    ck('the caster reloads mid-wait: the spell is still waiting', ia['st'] == ['Lightning Bolt'] and ia['text'] == "Waiting for Bob's OK" and ib['text'] == 'OK: Lightning Bolt resolves', (ia['st'], ia['text'], ib['text']))
    await press(b, 800)
    ck('the OK resolves it on the reloaded page', (await info(a))['st'] == [] and (await info(b))['life'] == 17)
    await ev(a, "T.cast('Lightning Bolt','opp')"); await a.wait_for_timeout(500)
    await resume(b, a); ia, ib = await info(a), await info(b)
    ck('the other player reloads mid-wait: asked again', ib['text'] == 'OK: Lightning Bolt resolves' and ib['title'].startswith('● Your OK needed') and ia['text'] == "Waiting for Bob's OK", (ia['text'], ib['text']))
    await press(b, 800)
    ck('and the OK works', (await info(b))['life'] == 14)
    await press(a); ib = await info(b)
    ck('a stop is holding', ib['text'] == 'OK: Ann declares attackers')
    await resume(a, b); ia, ib = await info(a), await info(b)
    ck('the active player reloads during a stop: still held', ia['turn'].get('hold', {}).get('at') == 'atk' and ia['text'] == "Waiting for Bob's OK" and ib['text'] == 'OK: Ann declares attackers', (ia['turn'], ia['text'], ib['text']))
    await press(b, 500); ia = await info(a)
    ck('the OK releases it', 'hold' not in ia['turn'] and ia['atkBar'], ia['turn'])
    await press(a); await press(a)
    await resume(b, a); ia, ib = await info(a), await info(b)
    ck('the holder reloads during a stop: asked again, and their stops reach the other page again', ib['text'] == 'OK: Ann goes to the end step' and await ev(a, 'G.oppStops && G.oppStops.m2'), (ib['text'],))
    await press(b, 500)
    ck('the turn goes on', (await info(a))['turn']['phase'] == 5)
    ck('the host’s switch survives the host’s reload', await ev(a, 'priSet()') and await ev(a, 'priToggle(false)') is True)
    await resume(a, b)
    ck('...also when it is off', await ev(a, 'priSet()') is False and await ev(b, 'priSet()') is False and (await info(b))['dash'] == [''] * 6)


# ----------------------------------------------------------------------------------------------- fullgame
async def t_fullgame(env, A):
    a, b = await seat(env)
    await pregame(a, b, first='host')
    for p in (a, b):
        await ev(p, 'S.autoPay=true'); await ev(p, "(()=>{ const st=myStops(); st.opp.m2=true; setStops(st); })()")
    oks = [0]

    async def ok():
        oks[0] += await settle(a, b)

    async def land_and(p, o, spell, target=None):
        """Play a Mountain from the hand, tap it, cast a one-mana spell with the real clicks."""
        await ev(p, "(()=>{ T.trim(5); T.give('Mountain'); })()"); await p.wait_for_timeout(200)
        await p.locator('#myHand .card').last.click(); await p.wait_for_timeout(300)                 # the land
        await ev(p, "(n)=>T.give(n)", spell); await p.wait_for_timeout(200)
        lands = p.locator('#myBack .card:not(.tap)')
        await lands.first.click(); await p.wait_for_timeout(250)                                      # tap for mana
        await p.locator('#myHand .card').last.click(); await p.wait_for_timeout(450)                  # cast
        if target == 'opp':
            await p.click('#oppAv'); await p.wait_for_timeout(350)
        elif target:
            await p.locator(target).first.click(); await p.wait_for_timeout(350)

    for game in (1, 2):
        # Ann (always on the play here): land, Monastery Swiftspear, attack
        await land_and(a, b, 'Monastery Swiftspear'); ib = await info(b)
        ck('game %d: the creature spell waits for the OK' % game, ib['text'] == 'OK: Monastery Swiftspear resolves', ib['text'])
        await ok(); await a.wait_for_timeout(300)
        ck('game %d: it enters the battlefield' % game, await ev(a, "G.me.bf.some(c=>cdata(c).n==='Monastery Swiftspear')"))
        await press(a); await ok()                                              # to combat; before attackers
        await a.locator('#atkBar button', has_text='Choose').first.click() if await a.locator('#atkBar button', has_text='Choose').count() else None
        sw = await ev(a, "G.me.bf.find(c=>cdata(c).n==='Monastery Swiftspear').id")
        await ev(a, "(id)=>{ G.atkSel=new Set([id]); atkCommit(); }", sw); await a.wait_for_timeout(500)
        ck('game %d: Bob is asked to block' % game, (await info(b))['text'] == 'Done blocking')
        await press(b); await press(a, 600)
        ck('game %d: combat damage' % game, (await info(b))['life'] == 19, (await info(b))['life'])
        await press(a); await press(a); await ok(); await press(a)
        ck('game %d: Ann passes' % game, (await info(b))['text'] == 'Start my turn')
        # Bob: land, Bolt the Swiftspear
        await ev(b, 'T.trim()'); await press(b, 600)
        await land_and(b, a, 'Lightning Bolt', '#oppFront .card'); ia = await info(a)
        ck('game %d: Bob’s Bolt waits for Ann' % game, ia['text'] == 'OK: Lightning Bolt resolves', ia['text'])
        await ok(); await a.wait_for_timeout(700)
        ck('game %d: the Swiftspear dies' % game, not await ev(a, "G.me.bf.some(c=>cdata(c).n==='Monastery Swiftspear')"))
        await press(b); await ok(); await press(b); await press(b); await ok(); await press(b)
        # Ann: burn Bob out, with Always OK on Bob's side after the first Bolt
        await ev(a, 'T.trim()'); await press(a, 600)
        await ev(a, 'S.autoPay=false')
        await ev(a, "T.cast('Lightning Bolt','opp')"); await a.wait_for_timeout(450)
        if game == 1:
            await b.click('#stack .card.opp', button='right'); await b.wait_for_timeout(200); await b.click('#ctx button'); await b.wait_for_timeout(900)
        else:
            await b.wait_for_timeout(1200)
        for i in range(6):
            if (await info(b))['life'] <= 0:
                break
            await ev(a, "T.cast('Lightning Bolt','opp')")
            await a.wait_for_function('G.me.st.length===0', timeout=10000); await a.wait_for_timeout(350)
        await ev(a, 'S.autoPay=true')
        await b.wait_for_function("!document.querySelector('#modal').hidden", timeout=10000); await a.wait_for_timeout(600)
        ck('game %d: Bob is at 0 and the game-over window is up for both' % game, (await info(b))['life'] <= 0 and (await info(a))['modal'] == 'Ann wins the game' and (await info(b))['modal'] == 'Ann wins the game', ((await info(b))['life'], (await info(a))['modal']))
        for p in (a, b):
            await p.locator('#modal footer button.go').click(); await p.wait_for_timeout(500)
        await a.wait_for_timeout(700)
        if game == 1:
            ck('sideboarding between the games', (await info(a))['modal'] == 'Sideboarding' and (await info(a))['wins'] == [1, 0], ((await info(a))['modal'], (await info(a))['wins']))
            for p in (a, b):
                await p.locator('#modal footer button.go').click(); await p.wait_for_timeout(400)
            await pregame(a, b, first='host')        # Bob lost and chooses: he lets Ann play
            for p in (a, b):
                await ev(p, 'S.autoPay=true')
            ck('game 2 starts, priority running', await ev(a, 'priLive()') and (await info(a))['turn']['n'] == 1)
    await a.wait_for_timeout(800); ia, ib = await info(a), await info(b)
    ck('the match is finished: Ann wins the match 2–0', ia['wins'] == [2, 0] and ia['banner'] == 'Ann wins the match 2–0' and ib['banner'] == 'Ann wins the match 2–0', (ia['wins'], ia['banner'], ib['banner']))
    ck('OKs were given all the way through (%d), some by Always OK' % oks[0], oks[0] >= 10 and await ev(b, "G.log.filter(l=>/always OK/.test(l.text)).length") >= 4, oks[0])
    ck('priority rests once the match is over', await ev(a, 'priLive()') is False)


# ----------------------------------------------------------------------------------------------- night
async def t_night(env, A):
    ca = await env.b.new_context(viewport={'width': 1500, 'height': 900}); cb = await env.b.new_context(viewport={'width': 1500, 'height': 900})
    env.ctxs += [ca, cb]
    for c in (ca, cb):
        async def route(r):
            u = r.request.url
            if u.startswith('http://127.0.0.1:') or u.startswith('data:') or u.startswith('blob:'): await r.continue_()
            elif 'api.scryfall.com' in u: await r.fulfill(status=200, content_type='application/json', body='{"data":[]}')
            else: await r.abort()
        await c.route('**/*', route)
    ra = await ca.new_page(); rb = await cb.new_page(); env.watch(ra, 'night room (event host)'); env.watch(rb, 'night room (player)')
    await ra.goto(env.url('/night/', '&gnfast=1')); await ra.fill('#nameIn', 'Ann'); await ra.click('#nightBtn')
    await ra.wait_for_function('typeof CODE!=="undefined" && CODE && CODE.length>=4', timeout=20000)
    code = await ra.evaluate('CODE')
    await rb.goto(env.url('/night/', '&gnfast=1')); await rb.fill('#nameIn', 'Bob'); await rb.fill('#codeIn', code); await rb.click('#joinBtn')
    for r in (ra, rb):
        await r.wait_for_selector('[data-dk]', timeout=30000)
        await r.locator('[data-dk]').nth(0 if r is ra else 1).click(); await r.click('#lockBtn'); await r.click('#lockYes'); await r.wait_for_timeout(500)
    await ra.wait_for_selector('#roundBtn:not([disabled])', timeout=15000); await ra.click('#roundBtn')
    tabs = []
    for r in (ra, rb):
        await r.wait_for_selector('[data-matchtab]', timeout=20000)
        async with r.context.expect_page() as pi:
            await r.locator('[data-matchtab]').first.click()
        t = await pi.value; env.watch(t, 'match tab'); tabs.append(t)
    for t in tabs:
        await t.wait_for_function('typeof G!=="undefined" && G.opp && G.opp.deck && G.conn && G.conn.open && G.me.deck', timeout=60000)
    roles = [await t.evaluate('G.myId') for t in tabs]
    h, g = (tabs[0], tabs[1]) if roles[0] == 'p1' else (tabs[1], tabs[0])
    ck('match tabs opened at the same table, one host side, one guest side', sorted(roles) == ['p1', 'p2'] and await h.evaluate('G.code') == await g.evaluate('G.code'), roles)
    ck('they are Game Night match tabs', await h.evaluate('!!NIGHT && nightSeat()') and await g.evaluate('!!NIGHT && nightSeat()'))
    await h.wait_for_function('!document.querySelector("#nightWait") || document.querySelector("#nightWait").hidden', timeout=20000)
    await pregame(h, g, first='host'); await stage(h, g)
    hn, gname = await h.evaluate('G.me.name'), await g.evaluate('G.me.name')
    ck('priority runs in the match tabs', await h.evaluate('priLive()') and await g.evaluate('priLive()'))
    await ev(h, "T.cast('Lightning Bolt','opp')"); await h.wait_for_timeout(500)
    ck('a spell waits for the OK there', (await info(g))['text'] == 'OK: Lightning Bolt resolves' and (await info(h))['text'] == "Waiting for %s's OK" % gname, ((await info(g))['text'], (await info(h))['text']))
    await press(g, 700)
    ck('and resolves after it', (await info(g))['life'] == 17)
    await press(h)
    ck('stops work there', (await info(g))['text'] == 'OK: %s declares attackers' % hn, (await info(g))['text'])
    # who has the switch: the table's host side (the first-named player of the pairing), not the event's host
    await ev(g, 'settingsModal()'); await g.wait_for_timeout(200)
    rowg = await ev(g, "(()=>{ const r=document.querySelector('#setBody .setrow'); return {h:r.querySelector('small').textContent, dis:[...r.querySelectorAll('button')].every(x=>x.disabled)}; })()"); await ev(g, 'closeModal()')
    ck('the table’s guest side sees Priority greyed out, naming the other player', rowg['dis'] and ('Only %s, who opened this table, can change it.' % hn) in rowg['h'], rowg)
    await ev(h, 'settingsModal()'); await h.wait_for_timeout(200)
    await h.click('#setBody [data-set="pri"][data-v="off"]'); await h.wait_for_timeout(500); await ev(h, 'closeModal()')
    ck('the table’s host side can turn it off; the stop is released', await g.evaluate('priSet()') is False and 'hold' not in (await info(h))['turn'] and (await info(g))['text'] == "Opponent's turn", ((await info(h))['turn'], (await info(g))['text']))
    ck('the event host is %s; at this table the switch belongs to %s (the p1 side of the pairing)' % ('Ann', hn), True)
    ck('the round clock is the event’s, as before', await h.evaluate('!!(G.mt && G.mt.end)') and await h.evaluate('!document.querySelector("#clockBox").hidden'))
    await ev(h, 'priToggle(true)'); await h.wait_for_timeout(300)
    # the result still goes back to the room
    await ev(g, '(()=>{ G.me.life=0; changed(); })()'); await g.wait_for_timeout(1500)
    for t in (h, g):
        await t.locator('#modal footer button.go').click(); await t.wait_for_timeout(500)
    await h.wait_for_timeout(800)
    for t in (h, g):
        if (await info(t))['modal'] == 'Sideboarding':
            await t.locator('#modal footer button.go').click(); await t.wait_for_timeout(300)
    await pregame(h, g, first='host')
    ck('game 2 at the Game Night table: priority running again', await h.evaluate('priLive()'))
    await ev(g, '(()=>{ G.me.life=0; changed(); })()'); await g.wait_for_timeout(1500)
    for t in (h, g):
        await t.locator('#modal footer button.go').click(); await t.wait_for_timeout(500)
    await h.wait_for_timeout(3500)
    ck('the match result (2–0) reaches the room for confirming', await h.evaluate('matchDone()') and await h.evaluate('G.nightSent===G.code'), await h.evaluate('[matchDone(), G.nightSent, G.code]'))


# ----------------------------------------------------------------------------------------------- practice
async def t_practice(env, A):
    p = await env.ctx('practice')
    await p.goto(env.url()); await p.wait_for_selector('#soloBtn'); await p.fill('#nameIn', 'Ann'); await p.click('#soloBtn'); await pick_deck(p, 0)
    await p.wait_for_timeout(500); await ev(p, 'closeModal()')
    for _ in range(20):
        bt = await banner_btns(p)
        if 'play' in bt: await p.click('#banner [data-first="play"]')
        elif 'deal' in bt: await p.click('#banner [data-first="deal"]')
        elif 'keep' in bt: await p.click('#banner [data-first="keep"]')
        await p.wait_for_timeout(150)
        if await ev(p, 'G.turn.n && G.me.kept'):
            break
    await ev(p, 'closeModal()'); await ev(p, T_JS)
    await ev(p, "(()=>{ S.stops={mine:{up:true, draw:true}, opp:{up:true, draw:true, m1:true, atk:true, m2:true}}; render(); })()")
    i = await info(p)
    ck('practice: priority is not running, no dashes, no hint', await ev(p, 'priLive()') is False and await ev(p, 'priTable()') is False and i['dash'] == [''] * 6 and i['hint'] == '', i)
    await ev(p, "T.cast('Lightning Bolt','opp')"); await p.wait_for_timeout(400); i = await info(p)
    ck('a spell: the button is unchanged, no band', i['text'] == SKIP and i['bands'] == [] and i['owns'] == [], i)
    await p.click('#stack .card'); await p.wait_for_timeout(400)
    ck('a click resolves it', (await info(p))['st'] == [] and (await info(p))['olife'] == 17)
    await ev(p, TRIGS_JS, PAIR); await p.wait_for_timeout(400)
    ck('two triggers at once in practice: no ordering panel (click whichever you like)', await ev(p, PANEL_JS) is None and await ev(p, '!G.ordHold') and len((await info(p))['st']) == 2)
    await ev(p, "(()=>{ G.me.st.length=0; changed(); })()")
    await p.click('#turnlbl'); await p.wait_for_timeout(200)
    ck('the turn menu is the old one', await ev(p, "!document.querySelector('#ctx .sgrid') && [...document.querySelectorAll('#ctx > button')].map(x=>x.textContent)[0]==='Pause on my next upkeep (my turn stops there)'"))
    await p.keyboard.press('Escape')
    await press(p); await press(p); await ev(p, 'T.trim()'); await press(p, 500); i = await info(p)      # Main 2 (no combat to go through), End, next turn
    ck('stops set at another table do nothing here: the next turn runs to Main 1', i['turn']['n'] == 2 and i['turn']['phase'] == 2 and 'hold' not in i['turn'], i['turn'])
    await ev(p, 'settingsModal()'); await p.wait_for_timeout(200)
    row = await ev(p, "(()=>{ const r=document.querySelector('#setBody .setrow'); return {h:r.querySelector('small').textContent, dis:[...r.querySelectorAll('button')].every(x=>x.disabled)}; })()"); await ev(p, 'closeModal()')
    ck('Settings: the Priority row is greyed out: "Practice games never use it."', row['dis'] and row['h'].endswith('Practice games never use it.'), row)
    ck('the host’s switch does nothing in practice', await ev(p, 'priToggle(false)') is False)


# ----------------------------------------------------------------------------------------------- pages
async def t_pages(env, A):
    a, b = await table(env)
    await ev(a, 'settingsModal()'); await a.wait_for_timeout(250)
    rows = await ev(a, "[...document.querySelectorAll('#setBody .setrow')].map(r=>r.querySelector('.sl').childNodes[0].textContent+': '+[...r.querySelectorAll('button')].map(x=>x.textContent+(x.classList.contains('on')?'*':'')).join(' / '))")
    ck('Settings: Priority row first, "My spells, after an OK" under Playing, the old rows unchanged', rows == ['Priority: On* / Off', 'Auto-draw: On* / Off', 'Auto-pay: On / Off*', 'My spells, after an OK: Resolve by themselves* / I press Resolve', 'Card menus: Short, side* / Short, same / Full', 'Tapped cards: 18° / 90°* / 90° with room', 'Animations: On* / Off / Follow my computer', 'Stack alert: Off / Quiet / Normal* / Loud', 'Streamer mode: Off* / Camera space / My camera'], rows)
    fit = await ev(a, "(()=>{ const m=document.querySelector('#modal .box')||document.querySelector('#modal'), r=m.getBoundingClientRect(); return [Math.round(r.top), Math.round(r.bottom), innerHeight, m.scrollHeight<=m.clientHeight+1]; })()")
    ck('the Settings window fits the screen with the Stack alert row (v5.04)', fit[0] >= 0 and fit[1] <= fit[2] and fit[3], fit)
    await a.click('#setBody [data-set="prires"][data-v="click"]'); await a.wait_for_timeout(200)
    ck('the Resolve setting is kept in my settings', await ev(a, "JSON.parse(localStorage.getItem('mt_settings')).priRes") == 'click')
    await a.click('#setBody [data-set="prires"][data-v="auto"]'); await ev(a, 'closeModal()')
    await ev(a, 'helpModal()'); await a.wait_for_timeout(300)
    fit = await ev(a, "(()=>{ const m=document.querySelector('#modal'), r=m.firstElementChild.getBoundingClientRect(); return {top:r.top, bottom:r.bottom, scroll:[...m.querySelectorAll('*')].filter(e=>e.scrollHeight>e.clientHeight+1 && getComputedStyle(e).overflowY!=='visible').length, txt:m.textContent}; })()")
    ck('the help page still fits a 1500×900 window without scrolling', fit['top'] >= 0 and fit['bottom'] <= 900 and fit['scroll'] == 0, (fit['top'], fit['bottom'], fit['scroll']))
    ck('and tells about the OK and the stops', 'their OK' in fit['txt'] and 'Click the turn for stops' in fit['txt'] and 'next phase, or OK' in fit['txt'])
    await ev(a, 'closeModal()')
    # Explore
    await ev(a, 'exploreStart()'); await a.wait_for_timeout(200)
    bx = await a.locator('#next').bounding_box(); await a.mouse.move(bx['x'] + 20, bx['y'] + 10); await a.wait_for_timeout(250)
    tx = await ev(a, "document.querySelector('#exCard').textContent")
    ck('Explore: the big button entry tells about the blue OK', 'turns blue when your OK is needed' in tx, tx)
    bx = await a.locator('#phases').bounding_box(); await a.mouse.move(bx['x'] + 30, bx['y'] + 10); await a.wait_for_timeout(250)
    tx = await ev(a, "document.querySelector('#exCard').textContent")
    ck('Explore: the phase bar entry tells about the dashes', 'small dashes mark your stops' in tx, tx)
    await a.keyboard.press('Escape')
    await ev(b, "T.trig('Amulet of Vigor', 2)"); await b.wait_for_timeout(500)
    await ev(a, 'exploreStart()'); await a.wait_for_timeout(200)
    bx = await a.locator('#okAll').bounding_box(); await a.mouse.move(bx['x'] + 20, bx['y'] + 10); await a.wait_for_timeout(250)
    tx = await ev(a, "document.querySelector('#exCard').textContent")
    ck('Explore: OK all has its own entry', tx.startswith('OK all'), tx)
    await a.keyboard.press('Escape'); await a.click('#okAll'); await b.wait_for_function('G.me.st.length===0', timeout=10000)
    ck('NEWS: the current version on top, v5.0 below it', await ev(a, "NEWS[0][0]===VERSION && NEWS.some(n=>n[0]==='v5.0' && /passes priority/.test(n[2]))"))
    await env.close_all()
    # the tour (a practice game): every step of the table tour shows, the new one among them
    p = await env.ctx('tour')
    await p.goto(env.url()); await p.wait_for_selector('#soloBtn'); await p.fill('#nameIn', 'Ann'); await p.click('#soloBtn'); await pick_deck(p, 0)
    await p.wait_for_timeout(500); await ev(p, 'closeModal()')
    await ev(p, "tourStart('table')"); await p.wait_for_timeout(500)
    seen = []
    for _ in range(40):
        if not await ev(p, '!!TOUR'):
            break
        seen.append(await ev(p, "(document.querySelector('#tourCard h4')||document.querySelector('#tourCard b')||{}).textContent||''"))
        await p.keyboard.press('ArrowRight'); await p.wait_for_timeout(250)
    ck('the tour: "Passing priority" comes after "The big button"', 'Passing priority' in seen and seen.index('Passing priority') == seen.index('The big button') + 1, seen)
    ck('the tour runs to its end', not await ev(p, '!!TOUR') and len(seen) >= 12, seen)


async def t_sound(env, A):
    a, b = await table(env)
    n = lambda p: ev(p, 'SND.n||0')
    async def wiggle(p, secs):
        for i in range(int(secs / 1.5)):
            await p.mouse.move(300 + (i % 2) * 40, 300); await p.wait_for_timeout(1500)
    ck('the Stack alert defaults to Normal', await ev(b, "S.snd||'mid'") == 'mid')
    await ev(a, "T.cast('Lightning Bolt')"); await a.wait_for_timeout(900)
    ck('no chime while the caster is still choosing a target', await n(a) == 0 and await n(b) == 0, (await n(a), await n(b)))
    await ev(a, 'finishMode(oppId())'); await a.wait_for_timeout(250)
    ck('not at once (an Always OK answer gets its moment first)', await n(b) == 0, await n(b))
    await a.wait_for_timeout(500)
    ck('one chime for the player asked, none for the caster', await n(b) == 1 and await n(a) == 0, (await n(a), await n(b)))
    await b.wait_for_timeout(3000)
    ck('no repeat while the reminder time runs', await n(b) == 1, await n(b))
    await b.wait_for_timeout(6800)
    ck('after 10 s with no sign of the player it chimes once more', await n(b) == 2, await n(b))
    await b.wait_for_timeout(3000)
    ck('and only once more', await n(b) == 2, await n(b))
    await press(b, 900)
    ck('the OK resolves it; no chime from that', await ev(a, 'G.me.st.length') == 0 and await n(b) == 2, (await ev(a, 'G.me.st.length'), await n(b)))
    # v5.05: the player is at the table (mouse moving): no reminder; once they go quiet, 10 s later it comes
    await b.wait_for_timeout(4500)
    await ev(a, "T.cast('Lightning Bolt','opp')"); await a.wait_for_timeout(1000)
    ck('a new spell (a new wait) chimes again', await n(b) == 3, await n(b))
    await wiggle(b, 13.5)
    ck('v5.05: mouse moving on the table for 13 s: no reminder', await n(b) == 3, await n(b))
    await b.mouse.move(360, 320)
    await b.wait_for_timeout(8500)
    ck('8.5 s after the mouse stopped: still quiet', await n(b) == 3, await n(b))
    await b.wait_for_timeout(2200)
    ck('10 s after the mouse stopped: the reminder', await n(b) == 4, await n(b))
    await press(b, 900)
    # v5.05: a batch of triggers chimes once; the next one waits silently, then reminds after 10 quiet seconds
    await b.wait_for_timeout(4500); nb = await n(b)
    await ev(a, "T.trig('Amulet of Vigor', 3)"); await a.wait_for_timeout(1000)
    ck('v5.05: three triggers at once: one chime', await n(b) == nb + 1, await n(b) - nb)
    await press(b, 1500); ib = await info(b)
    ck('after OKing the top one, the next waits on the player', ib['cls'] == ['ok'] and len(ib['ost']) == 2, (ib['cls'], ib['ost']))
    ck('v5.05: the next trigger of the batch does not chime', await n(b) == nb + 1, await n(b) - nb)
    await b.wait_for_timeout(9500)
    ck('v5.05: left unattended 10 s, it chimes (half volume)', await n(b) == nb + 2, await n(b) - nb)
    await settle(a, b)
    ck('the batch is done', await ev(a, 'G.me.st.length') == 0 and await n(b) == nb + 2, (await ev(a, 'G.me.st.length'), await n(b) - nb))
    # a response: the caster is asked about it
    await b.wait_for_timeout(4500)
    bolt = await ev(a, "T.cast('Lightning Bolt','opp')"); await a.wait_for_timeout(900)
    await ev(b, "(id)=>T.cast('Counterspell', id)", bolt); await b.wait_for_timeout(1000)
    ck("the other player's response chimes for the active player", await n(a) == 1, await n(a))
    await settle(a, b)
    # Always OK doesn't chime
    await b.wait_for_timeout(4500)
    await ev(b, "PRI.aok.add('Amulet of Vigor trigger')"); nb = await n(b)
    await ev(a, "T.trig('Amulet of Vigor')"); await a.wait_for_timeout(1500)
    ck('Always OK answers it without a chime', await n(b) == nb and await ev(a, 'G.me.st.length') == 0, (await n(b), await ev(a, 'G.me.st.length')))
    await ev(b, 'PRI.aok.clear()')
    # Off
    await b.wait_for_timeout(4500)
    await ev(b, "(()=>{ S.snd='off'; })()"); nb = await n(b)
    await ev(a, "T.cast('Lightning Bolt','opp')"); await a.wait_for_timeout(1000)
    ck('Off: no chime', await n(b) == nb, await n(b))
    await press(b, 900); await ev(b, "(()=>{ S.snd='mid'; })()")
    # the Settings row
    await ev(b, 'settingsModal()'); await b.wait_for_timeout(200); nb = await n(b)
    labels = await ev(b, "[...document.querySelectorAll('[data-set=snd]')].map(x=>x.textContent)")
    ck('Settings has a Stack alert row: Off / Quiet / Normal / Loud', labels == ['Off', 'Quiet', 'Normal', 'Loud'], labels)
    await b.click('[data-set=snd][data-v=low]'); await b.wait_for_timeout(200)
    ck('choosing Quiet saves it and plays a preview', await ev(b, 'S.snd') == 'low' and await n(b) == nb + 1, (await ev(b, 'S.snd'), await n(b)))
    await b.click('[data-set=snd][data-v=off]'); await b.wait_for_timeout(200)
    ck('choosing Off plays nothing', await ev(b, 'S.snd') == 'off' and await n(b) == nb + 1, (await ev(b, 'S.snd'), await n(b)))
    ck('the audio was really made (an AudioContext exists)', await ev(b, '!!SND.ac'))

TESTS = [('stack', t_stack), ('stops', t_stops), ('order', t_order), ('auto', t_auto), ('waits', t_waits), ('match', t_match), ('toggle', t_toggle), ('oldpage', t_oldpage), ('reload', t_reload),
         ('fullgame', t_fullgame), ('sound', t_sound), ('night', t_night), ('practice', t_practice), ('pages', t_pages)]


async def main():
    ap = argparse.ArgumentParser(description='Two-browser tests for priority and stops (v5.0).')
    ap.add_argument('--only', default='', help='comma-separated test names')
    ap.add_argument('--old', default='', help='a v4.137 index.html for the old-page tests')
    ap.add_argument('--real-wait', action='store_true', help='sit through one real 20-second wait')
    ap.add_argument('--list', action='store_true')
    A = ap.parse_args()
    if A.list:
        print(' '.join(n for n, _ in TESTS)); return 0
    A.oldhtml = old_page(A.old)
    if not A.oldhtml:
        print('NOTE: no v4.137 page found (git show failed and no --old): the old-page tests and the v4.137 comparison are skipped.')
    want = [x for x in A.only.split(',') if x]
    env = await Env().start()
    t0 = time.time()
    try:
        for name, fn in TESTS:
            if want and name not in want:
                continue
            CUR[0] = name; print('\n== ' + name, flush=True)
            try:
                await fn(env, A)
            except Exception as e:
                import traceback
                ck('the test ran to its end', False, ''.join(traceback.format_exception(e))[-1800:])
            await env.close_all()
        CUR[0] = 'all'; print('\n== page errors', flush=True)
        ck('no page errors in any browser, in any test', not env.errors, env.errors[:10])
    finally:
        await env.stop()
    bad = [(t, n, i) for t, n, ok, i in RESULTS if not ok]
    by = {}
    for t, n, ok, i in RESULTS:
        by.setdefault(t, [0, 0]); by[t][0] += 1; by[t][1] += ok
    print('\n' + '=' * 60)
    for t, (n, k) in by.items():
        print('  %-9s %3d of %3d' % (t, k, n))
    print('  TOTAL     %3d of %3d passed in %d s' % (len(RESULTS) - len(bad), len(RESULTS), time.time() - t0))
    if RETRIES[0]:
        print('  (%d table(s) did not seat on the first try and were opened again)' % RETRIES[0])
    for t, n, i in bad:
        print('  FAILED  [%s] %s' % (t, n))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
