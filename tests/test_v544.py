"""v5.44 (the maintainer, 2026-11-26): a fetch land art option, Bear's Choice, half Zendikar and half Khans of Tarkir.
Zendikar printed the five enemy-colour fetches and Khans of Tarkir reprinted the five allied ones, so each of the ten comes from exactly one
of the two sets. The deck screen's land art box (Fetch tab) offers it; choosing it shows the ten from those sets, and a deck brought to the
table points its fetches at them (landArt). Scryfall is mocked with the real collector numbers."""
import json, os, re, socket, subprocess, sys, time, urllib.parse
from playwright.sync_api import sync_playwright
ROOT = os.environ.get('MT_ROOT') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def _free_port():
    s = socket.socket(); s.bind(('127.0.0.1', 0)); p = s.getsockname()[1]; s.close(); return p
PORT = _free_port()
srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(PORT), '--bind', '127.0.0.1'], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(0.8); res = []
def check(n, c, e=''): res.append(bool(c)); print('PASS' if c else 'FAIL', n, e)
ZEN = {'Arid Mesa': '211', 'Marsh Flats': '219', 'Misty Rainforest': '220', 'Scalding Tarn': '223', 'Verdant Catacombs': '229'}
KTK = {'Bloodstained Mire': '230', 'Flooded Strand': '233', 'Polluted Delta': '239', 'Windswept Heath': '248', 'Wooded Foothills': '249'}
ONS = {'Bloodstained Mire': '313', 'Flooded Strand': '316', 'Polluted Delta': '321', 'Windswept Heath': '328', 'Wooded Foothills': '330'}
PRINTS = {'zen': ZEN, 'ktk': KTK, 'ons': ONS}
def card(name, st, cn):
    return {'object': 'card', 'id': f'{st}-{cn}', 'name': name, 'set': st, 'collector_number': cn, 'type_line': 'Land', 'mana_cost': '', 'cmc': 0,
            'oracle_text': '{T}, Pay 1 life, Sacrifice this land: Search your library for a land card, put it onto the battlefield, then shuffle.',
            'image_uris': {'normal': f'https://cards.scryfall.io/normal/{st}-{cn}.jpg', 'large': f'https://cards.scryfall.io/large/{st}-{cn}.jpg', 'small': f'https://cards.scryfall.io/small/{st}-{cn}.jpg'},
            'legalities': {'modern': 'legal'}, 'colors': [], 'color_identity': []}
QUERIES = []
def search(route):
    u = urllib.parse.urlparse(route.request.url); q = urllib.parse.parse_qs(u.query).get('q', [''])[0]; QUERIES.append(q)
    sets = re.findall(r'e:(\w+)', q); names = re.findall(r'!"([^"]+)"', q)
    data = [card(n, st, cn) for st in sets for n, cn in PRINTS.get(st, {}).items() if n in names]
    route.fulfill(status=200, content_type='application/json', body=json.dumps({'object': 'list', 'has_more': False, 'data': data}))
SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="488" height="680"><rect width="488" height="680" rx="24" fill="#3b4a3f"/></svg>'
def block(ctx):
    ctx.route('**/cards.scryfall.io/**', lambda r: r.fulfill(status=200, content_type='image/svg+xml', body=SVG))
    for h in ['**/svgs.scryfall.io/**', '**/backs.scryfall.io/**', '**/fonts.googleapis.com/**', '**/fonts.gstatic.com/**', '**/gc.zgo.at/**', '**/*.metered.live/**', '**/*.workers.dev/**']: ctx.route(h, lambda r: r.abort())
    ctx.route('**/api.scryfall.com/**', lambda r: search(r) if '/cards/search' in r.request.url else r.fulfill(status=200, content_type='application/json', body='{"data":[]}'))
J = lambda p, js, *a: p.evaluate(js, *a)
BOX = "() => { const b=document.querySelector('#basicsBox'); const sel=b.querySelector('#basicsSel'); return {tab:(b.querySelector('[data-lt].on')||{}).textContent, opts:[...sel.options].map(o=>[o.value, o.textContent]), val:sel.value, imgs:[...b.querySelectorAll('.bbc')].map(e=>[e.title, e.style.backgroundImage]), note:(b.querySelector('.bbn')||{}).textContent}; }"
try:
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        ctx = br.new_context(viewport={'width': 1500, 'height': 900}); block(ctx); p = ctx.new_page()
        errs = []; p.on('pageerror', lambda e: errs.append(str(e)))
        p.goto(f'http://127.0.0.1:{PORT}/?r=s&nobake'); p.wait_for_timeout(1000)
        J(p, "() => { const s=document.getElementById('spl'); if(s) s.remove(); }")
        p.wait_for_selector('.drow', timeout=15000)
        p.locator('.drow').first.click(); p.wait_for_timeout(400)
        p.click('#basicsBox [data-lt="fetch"]'); p.wait_for_timeout(300)
        b = J(p, BOX)
        opt = [o for o in b['opts'] if o[0] == 'bear']
        check("the Fetch tab offers Bear's Choice", b['tab'] == 'Fetch' and len(opt) == 1 and opt[0][1].startswith("Bear's Choice"), b['opts'])
        check('as the last fetch style, after Expeditions', b['opts'][-1][0] == 'bear' and b['opts'][-2][0] == 'zne', [o[0] for o in b['opts']])
        p.select_option('#basicsSel', 'bear'); p.wait_for_timeout(2500)
        b = J(p, BOX)
        check('choosing it saves the setting', J(p, "() => (S.lands||{}).fetch") == 'bear' and J(p, "() => (store.get('mt_settings',{}).lands||{}).fetch") == 'bear')
        q = [x for x in QUERIES if 'e:zen' in x]
        check('it asks Scryfall for the fetches in Zendikar and Khans of Tarkir', len(q) >= 1 and 'e:ktk' in q[-1] and 'e:ons' not in q[-1], QUERIES)
        got = {n: im for n, im in b['imgs']}
        check('all ten pictures show', len(got) == 10 and all(got.values()), b['imgs'])
        check("Zendikar's five come from Zendikar", all(f'zen-{cn}' in got[n] for n, cn in ZEN.items()), got)
        check("the other five come from Khans of Tarkir", all(f'ktk-{cn}' in got[n] for n, cn in KTK.items()), got)
        check('the note says the deck uses this art', 'use this art' in (b['note'] or ''), b['note'])
        art = J(p, "async () => await landArt()")
        want = {n.lower(): f'id:zen-{cn}' for n, cn in ZEN.items()}; want.update({n.lower(): f'id:ktk-{cn}' for n, cn in KTK.items()})
        check('a deck brought to the table points every fetch at those printings', all(art.get(k) == v for k, v in want.items()), art)
        check('the other land families are untouched', not any(k in art for k in ['plains', 'hallowed fountain', 'meticulous archive']), list(art))
        J(p, "() => { S.lands.fetch='orig'; store.set('mt_settings', S); paintBasics(); }"); p.wait_for_timeout(1500)
        b = J(p, BOX); got = {n: im for n, im in b['imgs']}
        check("Originals still take Onslaught's five (ons before ktk)", all(f'ons-{cn}' in got[n] for n, cn in ONS.items()) and all(f'zen-{cn}' in got[n] for n, cn in ZEN.items()), got)
        check('NEWS has the line', J(p, "() => NEWS[0][0]===VERSION && /Bear's Choice/.test(NEWS[0][2])"))
        check('no page errors', not errs, errs)
        br.close()
finally:
    srv.terminate()
print(('ALL PASS' if all(res) else 'SOME FAILED') + f' ({sum(res)}/{len(res)})')
