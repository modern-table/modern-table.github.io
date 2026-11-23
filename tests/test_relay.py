"""v5.28 / Draft v0.38: the relay (Metered's Open Relay).
Both pages fetch the relay servers once at load into RELAY_CFG, which every Peer gets through peerOpts(); a failed fetch
leaves the plain STUN server and nothing breaks. relayKind() reads a connection's chosen candidate pair, and the
connection label says Connected directly / Connected through the relay.
The sandbox can't reach Metered, so the fetch is mocked; real relayed games are tested by hand on two devices."""
import json, os, socket, subprocess, sys, time
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

MOCK = [{'urls': 'stun:stun.relay.metered.ca:80'},
        {'urls': 'turn:standard.relay.metered.ca:80', 'username': 'u1', 'credential': 'c1'},
        {'urls': 'turns:standard.relay.metered.ca:443?transport=tcp', 'username': 'u1', 'credential': 'c1'}]
PJS_DEF = [{'urls': 'stun:stun.l.google.com:19302'}, {'urls': ['turn:eu-0.turn.peerjs.com:3478', 'turn:us-0.turn.peerjs.com:3478'], 'username': 'peerjs', 'credential': 'peerjsp'}]
STATS = """(kind) => { const rep = new Map();
  rep.set('T', {id:'T', type:'transport', selectedCandidatePairId:'P'});
  rep.set('P', {id:'P', type:'candidate-pair', localCandidateId:'L', remoteCandidateId:'R', state:'succeeded', nominated:true});
  rep.set('L', {id:'L', type:'local-candidate', candidateType: kind});
  rep.set('R', {id:'R', type:'remote-candidate', candidateType:'host'});
  return relayKind({getStats: () => Promise.resolve(rep)}); }"""

def ctx_for(b, relay):
    ctx = b.new_context(viewport={'width': 1500, 'height': 900})
    for h in ['**/cards.scryfall.io/**','**/svgs.scryfall.io/**','**/backs.scryfall.io/**','**/fonts.googleapis.com/**','**/fonts.gstatic.com/**','**/gc.zgo.at/**']:
        ctx.route(h, lambda r: r.abort())
    ctx.route('**/api.scryfall.com/**', lambda r: r.fulfill(status=200, content_type='application/json', body='{"data":[]}'))
    seen = []
    def metered(r):
        seen.append(r.request.url)
        if relay == 'ok': r.fulfill(status=200, content_type='application/json', body=json.dumps(MOCK))
        elif relay == '401': r.fulfill(status=401, content_type='application/json', body='{"error":"Invalid API Key"}')
        else: r.abort()
    ctx.route('**/*.metered.live/**', metered)
    return ctx, seen

try:
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        # 1. Modern Table, relay answers
        ctx, seen = ctx_for(b, 'ok'); p = ctx.new_page(); errs = []
        p.on('pageerror', lambda e: errs.append(str(e)))
        p.goto(f'http://127.0.0.1:{PORT}/'); p.wait_for_timeout(1200)
        st = p.evaluate("() => ({st: typeof RELAY_ST==='undefined' ? null : RELAY_ST, cfg: typeof peerOpts==='function' ? peerOpts().config : null})")
        check('Modern Table asks Metered for the relay servers once', len(seen) == 1 and 'moderntable.metered.live/api/v1/turn/credentials?apiKey=' in (seen[0] if seen else ''), str(seen))
        check('relay ready', st['st'] == 'ready', str(st['st']))
        ice = (st['cfg'] or {}).get('iceServers') or []
        check('peerOpts() carries the relay: STUN first, then Metered\'s servers with their credentials, PeerJS\'s defaults last',
              ice[:1] == [{'urls': 'stun:stun.l.google.com:19302'}] and ice[-1] == PJS_DEF[1] and ice[1:4] == MOCK and any(s.get('urls') == 'turn:standard.relay.metered.ca:80' and s.get('username') == 'u1' and s.get('credential') == 'c1' for s in ice), json.dumps(ice)[:200])
        same = p.evaluate("() => peerOpts().config === RELAY_CFG && (()=>{ history.replaceState(null,'','?peerhost=127.0.0.1:9000&peersecure=0'); const o=peerOpts(); history.replaceState(null,'','/'); return o.config === RELAY_CFG && o.host==='127.0.0.1' && o.port===9000 && o.secure===false; })()")
        check('every Peer gets the same config object (also with ?peerhost)', same)
        check('relayKind: a relay candidate reads relay', p.evaluate(STATS, 'relay') == 'relay')
        check('relayKind: host / srflx candidates read direct', p.evaluate(STATS, 'srflx') == 'direct' and p.evaluate(STATS, 'host') == 'direct')
        check('relayKind: no connection reads nothing', p.evaluate("() => relayKind(null)") == '')
        # the label, in a practice game's table view
        p.click('#soloBtn'); p.wait_for_timeout(600)
        p.locator('.drow').first.click(); p.wait_for_timeout(400)
        p.get_by_role('button', name='Play this deck').click(); p.wait_for_timeout(1500)
        lbl = p.evaluate("""() => { const t=k=>{ G.net='connected'; G.via=k; renderNet(); const e=document.querySelector('#netPill1'); return [e.textContent, e.title]; };
            const r = {relay:t('relay'), direct:t('direct'), none:t('')}; setNet('joining'); r.cleared = G.via; setNet('solo'); return r; }""")
        check('label: Connected through the relay, with an explanation', lbl['relay'][0] == 'Connected through the relay' and 'relay server' in lbl['relay'][1], str(lbl['relay']))
        check('label: Connected directly', lbl['direct'][0] == 'Connected directly' and lbl['direct'][1] == '', str(lbl['direct']))
        check('label: plain Connected until the route is known', lbl['none'][0] == 'Connected', str(lbl['none']))
        check('leaving connected forgets the route', lbl['cleared'] == '', repr(lbl['cleared']))
        check('no page errors (relay answered)', not errs, str(errs)[:300])
        ctx.close()

        # 2. Modern Table, relay unreachable / refused: plain STUN, no errors
        for how in ['abort', '401']:
            ctx, seen = ctx_for(b, how); p = ctx.new_page(); errs = []
            p.on('pageerror', lambda e: errs.append(str(e)))
            p.goto(f'http://127.0.0.1:{PORT}/'); p.wait_for_timeout(1200)
            st = p.evaluate("() => ({st: RELAY_ST, ice: peerOpts().config.iceServers})")
            check(f'relay {how}: falls back to PeerJS\'s default servers (as before v5.28)', st['st'] == 'failed' and st['ice'] == PJS_DEF, json.dumps(st))
            t0 = time.time(); p.evaluate("() => relayReady()"); waited = time.time() - t0
            check(f'relay {how}: a guest dials at once', waited < 1.0, f'{waited:.2f}s')
            check(f'relay {how}: no page errors', not errs, str(errs)[:300])
            ctx.close()

        # 3. ?norelay skips the fetch
        ctx, seen = ctx_for(b, 'ok'); p = ctx.new_page()
        p.goto(f'http://127.0.0.1:{PORT}/?norelay'); p.wait_for_timeout(900)
        check('?norelay: no fetch, PeerJS defaults', not seen and p.evaluate("() => RELAY_ST") == 'failed', str(seen))
        ctx.close()

        # 4. a slow relay: a guest waits at most about 3 s
        ctx = b.new_context()
        ctx.route('**/*.metered.live/**', lambda r: None)   # never answered (left pending)
        p = ctx.new_page(); p.goto(f'http://127.0.0.1:{PORT}/'); p.wait_for_timeout(300)
        t0 = time.time(); p.evaluate("() => relayReady()"); waited = time.time() - t0
        check('relay never answers: the guest dials after about 3 s', 2.5 < waited < 4.5, f'{waited:.2f}s')
        ctx.close()

        # 5. Draft Table and Game Night pages
        for path, name in [('draft/', 'Draft Table'), ('night/', 'Game Night')]:
            ctx, seen = ctx_for(b, 'ok'); p = ctx.new_page(); errs = []
            p.on('pageerror', lambda e: errs.append(str(e)))
            p.goto(f'http://127.0.0.1:{PORT}/{path}'); p.wait_for_timeout(1200)
            st = p.evaluate("() => ({st: typeof RELAY_ST==='undefined' ? null : RELAY_ST, same: typeof peerOpts==='function' && peerOpts().config === RELAY_CFG, ice: typeof RELAY_CFG==='undefined' ? [] : RELAY_CFG.iceServers})")
            check(f'{name}: relay ready and in peerOpts()', st['st'] == 'ready' and st['same'] and any(s.get('username') == 'u1' for s in st['ice']), json.dumps(st)[:200])
            lbl = p.evaluate("""() => { CODE=CODE||'TEST'; NET='connected'; VIA='relay'; drawTop(); const a=document.querySelector('#netPill').textContent;
                VIA='direct'; drawTop(); const d=document.querySelector('#netPill').textContent;
                NET='open'; VIA=''; conns.set('x', {_via:'relay'}); conns.set('y', {_via:'direct'}); drawTop(); const h=document.querySelector('#netPill').textContent;
                conns.clear(); drawTop(); const h0=document.querySelector('#netPill').textContent; NET=''; drawTop(); return {a, d, h, h0}; }""")
            check(f'{name}: guest label', lbl['a'] == 'Connected through the relay' and lbl['d'] == 'Connected directly', str(lbl))
            check(f'{name}: host label counts players through the relay', lbl['h'] == 'Hosting · 1 through the relay' and lbl['h0'] == 'Hosting', str(lbl))
            check(f'{name}: no page errors', not errs, str(errs)[:300])
            ctx.close()
        b.close()
finally:
    srv.terminate()
print('ALL PASS' if all(ok for _, ok in results) else 'SOME FAILED', f'({sum(ok for _,ok in results)}/{len(results)})')
