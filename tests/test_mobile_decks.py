"""Phone layer m0.15 / v5.42 (the maintainer's deck screen design in claude/mobile-design.md): the phone's own deck screen, and pasting that's
forgiving. Checks: the desktop's deck screen is replaced on the phone (and untouched on the desktop page); This week's decks lists every
deck with a 17 px name and finish, event and date; a deck opens on the right with its counts, Pictures by default (a count circle per card),
Sideboard, Columns and List; the filter finds a card; a tap reads a card; Edit makes "<name> (edited)" in My decks at the first change,
− / + and the four-copy cap, moving a card to the sideboard warns past 15, Undo, adding a card by name; Paste a deck list reads site
headers, foil marks and curly quotes, counts as you type and lists what it left out, Paste from clipboard, Add deck saves it and checks
the names (a misspelling corrected in the saved list, an unknown card named); Play this deck from a short pasted deck asks about
playtesting and sits down; Delete. Also parseDeck on its own: Arena, MTGO .dek, "16 Creatures" counts, a headed list with no sideboard."""
import asyncio, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import priority_test as PT
ROOT = os.environ.get('MT_ROOT') or PT.ROOT
res = []
def check(n, c, e=''): res.append(bool(c)); print('PASS' if c else 'FAIL', n, '' if c else e, flush=True)

class Env(PT.Env):
    async def start(self):
        PT.ROOT = ROOT
        return await super().start()

def card(name, t='Instant', mc='{R}', o=''):
    return {'object':'card', 'id':'00000000-0000-4000-8000-%012d' % (abs(hash(name)) % 10**12), 'name':name, 'mana_cost':mc, 'type_line':t,
            'oracle_text':o, 'set':'tst', 'legalities':{'modern':'legal'}, 'colors':['R'], 'image_uris':{'normal':'https://cards.scryfall.io/x/%s.jpg' % name.replace(' ', '_')}}
KNOWN = {'lightning bolt': card('Lightning Bolt', o='Lightning Bolt deals 3 damage to any target.'), 'lightning helix': card('Lightning Helix', mc='{R}{W}'),
         'goblin guide': card('Goblin Guide', t='Creature — Goblin Scout', o='Haste')}

async def ctx(env, phone=True):
    o = dict(viewport={'width': 844, 'height': 390}, screen={'width': 844, 'height': 390}, has_touch=True, is_mobile=True, device_scale_factor=2) if phone else dict(viewport={'width': 1500, 'height': 900})
    c = await env.b.new_context(**o)
    try: await c.grant_permissions(['clipboard-read', 'clipboard-write'], origin='http://127.0.0.1:%d' % env.port)
    except Exception: pass
    async def route(r):
        u = r.request.url
        if u.startswith('http://127.0.0.1:') or u.startswith('data:') or u.startswith('blob:'): await r.continue_(); return
        if 'api.scryfall.com/cards/collection' in u:
            ids = json.loads(r.request.post_data or '{}').get('identifiers', []); data, nf = [], []
            for i in ids:
                k = (i.get('name') or '').lower()
                (data.append(KNOWN[k]) if k in KNOWN else nf.append(i))
            await r.fulfill(status=200, content_type='application/json', body=json.dumps({'data':data, 'not_found':nf})); return
        if 'api.scryfall.com/cards/named' in u:
            if 'lightnig' in u.lower(): await r.fulfill(status=200, content_type='application/json', body=json.dumps(KNOWN['lightning bolt']))
            else: await r.fulfill(status=404, content_type='application/json', body='{"object":"error"}')
            return
        if 'api.scryfall.com/cards/autocomplete' in u:
            await r.fulfill(status=200, content_type='application/json', body=json.dumps({'data':['Lightning Bolt', 'Lightning Helix']})); return
        if 'api.scryfall.com' in u: await r.fulfill(status=200, content_type='application/json', body='{"data":[]}'); return
        await r.abort()
    await c.route('**/*', route); env.ctxs.append(c)
    p = await c.new_page(); env.watch(p, 'phone' if phone else 'desktop'); return p

PARSE = """()=>{ const r = {};
  r.arena = parseDeck('Deck\\n4 Lightning Bolt (2X2) 117\\n1 Wear/Tear (STX) 1\\n\\nSideboard\\n2 Blood Moon (FDN) 3 *F*');
  r.dek = parseDeck('<Deck><Cards CatID="1" Quantity="4" Sideboard="false" Name="Lightning Bolt" /><Cards CatID="2" Quantity="2" Sideboard="true" Name="Wear/Tear" /></Deck>');
  r.heads = parseDeck('Creatures (4)\\n4 Goblin Guide\\n\\nInstants (4)\\n4 Lightning Bolt\\n\\nLands (20)\\n20 Mountain');
  r.counts = parseDeck('4 Lightning Bolt\\n16 Creatures\\n60 cards\\nTotal: $123');
  r.plain = parseDeck('4 Lightning Bolt\\n\\n2 Blood Moon');
  return r; }"""

async def main():
    env = await Env().start()
    try:
        # parseDeck on its own (the desktop page shares it)
        d = await ctx(env, phone=False)
        await d.goto(env.url('/')); await d.wait_for_selector('#soloBtn')
        r = await d.evaluate(PARSE)
        check('Arena list: set and number and the *F* foil mark dropped, Wear/Tear as a split card', r['arena']['main'] == [['Lightning Bolt', 4], ['Wear // Tear', 1]] and r['arena']['side'] == [['Blood Moon', 2]], r['arena'])
        check('MTGO .dek file read, sideboard included', r['dek']['main'] == [['Lightning Bolt', 4]] and r['dek']['side'] == [['Wear // Tear', 2]], r['dek'])
        check('a list with section headers and blank lines keeps every card in the main deck', r['heads']['main'] == [['Goblin Guide', 4], ['Lightning Bolt', 4], ['Mountain', 20]] and not r['heads']['side'] and len(r['heads']['skip']) == 3, r['heads'])
        check('"16 Creatures", "60 cards" and a price line are left out and listed', r['counts']['main'] == [['Lightning Bolt', 4]] and len(r['counts']['skip']) == 3, r['counts'])
        check('a plain list still puts the part after a blank line in the sideboard', r['plain']['side'] == [['Blood Moon', 2]], r['plain'])
        await d.click('#soloBtn'); await d.wait_for_timeout(600)
        dk = await d.evaluate("({mdeck: getComputedStyle(document.querySelector('#mDeck')||document.body).display, wrap: getComputedStyle(document.querySelector('.deckwrap')).display, has: !!document.querySelector('#mDeck')})")
        check('the desktop page keeps its own deck screen (no phone one)', not dk['has'] and dk['wrap'] != 'none', dk)
        await env.close_all()

        p = await ctx(env)
        await p.goto(env.url('/m/')); await p.wait_for_selector('#soloBtn'); await p.tap('#soloBtn'); await p.wait_for_timeout(800)
        g = await p.evaluate("""(()=>{ const rows=[...document.querySelectorAll('#mDeck .drow')], b=rows[0] && rows[0].querySelector('b');
          return {n:rows.length, decks:DECKS.length, fs:b?parseFloat(getComputedStyle(b).fontSize):0, fw:b?getComputedStyle(b).fontWeight:'', sub:rows[0]?rows[0].querySelector('small').textContent:'',
            wrap:getComputedStyle(document.querySelector('.deckwrap')).display, tabBody:document.querySelector('#tabBody').children.length}; })()""")
        check('the phone deck screen replaces the desktop one', g['wrap'] == 'none' and g['tabBody'] == 0, g)
        check("This week's decks lists every deck, 17 px bold names", g['n'] == g['decks'] and g['fs'] == 17 and int(g['fw']) >= 700, g)
        check('each row has finish, event and a short date', g['sub'].count('·') == 2 and 'Challenge' in g['sub'] or g['sub'].count('·') == 2, g['sub'])
        await p.locator('.drow').first.tap(); await p.wait_for_timeout(500)
        h = await p.evaluate("""(()=>{ const pics=[...document.querySelectorAll('#mdBody .mdpic')], n=pics[0] && pics[0].querySelector('.mdn'), cs=n && getComputedStyle(n);
          return {name:document.querySelector('.mdti h3').textContent, want:DECKS[0].arch, cnt:document.querySelector('.mdti .mdcnt').textContent, pics:pics.length,
            sum:pics.reduce((a,x)=>a+ +x.querySelector('.mdn').textContent,0), bg:cs&&cs.backgroundColor, col:cs&&cs.color, round:cs&&cs.borderRadius, play:!!document.querySelector('#mdPlay')}; })()""")
        check('a deck opens on the right: name, 60 main · 15 sideboard, Play this deck', h['name'] == h['want'] and '60 main · 15 sideboard' in h['cnt'] and h['play'], h)
        check('Pictures by default: every card once, black circle with a white count, adding up to 60', h['pics'] > 8 and h['sum'] == 60 and h['bg'] == 'rgb(0, 0, 0)' and h['col'] == 'rgb(255, 255, 255)' and h['round'] == '50%', h)
        await p.tap('[data-mdpt="side"]'); await p.wait_for_timeout(200)
        s = await p.evaluate("[...document.querySelectorAll('#mdBody .mdn')].reduce((a,x)=>a+ +x.textContent,0)")
        check('Sideboard shows its 15', s == 15, s)
        await p.tap('[data-mdpt="main"]'); await p.tap('[data-mdw="cols"]'); await p.wait_for_timeout(200)
        c = await p.evaluate("({cols:document.querySelectorAll('#mdBody .mdcol').length, lands:[...document.querySelectorAll('#mdBody .mdch')].some(x=>/Lands/.test(x.textContent)), sum:[...document.querySelectorAll('#mdBody .mdn')].reduce((a,x)=>a+ +x.textContent,0)})")
        check('Columns: mana-value columns and a Lands column, still 60', c['cols'] >= 3 and c['lands'] and c['sum'] == 60, c)
        await p.tap('[data-mdw="list"]'); await p.wait_for_timeout(200)
        l = await p.evaluate("({rows:document.querySelectorAll('#mdBody .mdli').length, sum:[...document.querySelectorAll('#mdBody .mdli b')].reduce((a,x)=>a+ +x.textContent,0), heads:[...document.querySelectorAll('#mdBody .mdlg h5')].map(x=>x.textContent), saved:localStorage.getItem('mt_mdview')})")
        check('List: grouped by type, still 60, and the view is remembered', l['sum'] == 60 and any('Lands' in x for x in l['heads']) and 'list' in (l['saved'] or ''), l)
        await p.tap('[data-mdw="pics"]'); await p.wait_for_timeout(200)
        fit = await p.evaluate("(()=>{ const r=[...document.querySelectorAll('#mDeck button, #mDeck .mdpic')].filter(x=>x.offsetParent && !x.closest('.mdbody') && !x.closest('.mdrows')).map(x=>x.getBoundingClientRect()); return r.every(b=>b.right<=845 && b.bottom<=391 && b.left>=-1); })()")
        check('every button outside the scrolling lists is on screen', fit)

        # filter
        await p.fill('#mdFilt', 'ragavan'); await p.wait_for_timeout(200)
        f = await p.evaluate("({rows:document.querySelectorAll('#mDeck .drow').length, want:DECKS.filter(d=>d.main.some(x=>/ragavan/i.test(x[0]))||/ragavan/i.test(d.arch)).length, focus:document.activeElement && document.activeElement.id})")
        check('the filter finds decks by a card in them, and keeps the keyboard', f['rows'] == f['want'] and 0 < f['rows'] < g['n'] and f['focus'] == 'mdFilt', f)
        await p.fill('#mdFilt', ''); await p.wait_for_timeout(150)

        # read a card
        await p.locator('#mdBody .mdpic').first.tap(); await p.wait_for_timeout(250)
        v = await p.evaluate("({vis:!document.querySelector('#mView').hidden, h:(document.querySelector('#mView h3')||{}).textContent, ed:!!document.querySelector('#mView .mded'), right:document.querySelector('#mView').getBoundingClientRect().right})")
        check('a tap reads the card (no − / + outside editing), the view uses the whole width', v['vis'] and v['h'] and not v['ed'] and v['right'] >= 843, v)
        await p.tap('#mView [data-mdv="x"]'); await p.wait_for_timeout(150)

        # edit a weekly deck
        await p.tap('[data-mde="edit"]'); await p.wait_for_timeout(200)
        n0 = await p.evaluate("JSON.parse(localStorage.getItem('mt_decks')||'[]').length")
        check('Edit alone saves nothing yet', n0 == 0, n0)
        first = await p.evaluate("document.querySelector('#mdBody .mdpic').dataset.mn")
        await p.locator('#mdBody .mdpic').first.tap(); await p.wait_for_timeout(200)
        await p.tap('#mView [data-mdv="main-"]'); await p.wait_for_timeout(250)
        e = await p.evaluate("""(()=>{ const sv=JSON.parse(localStorage.getItem('mt_decks')||'[]'), d=sv[0] && parseDeck(sv[0].text);
          return {n:sv.length, name:sv[0]&&sv[0].name, main:d?deckCount(d.main):0, seg:document.querySelector('[data-mds="saved"]').classList.contains('on'), sheet:(document.querySelector('#mView .mdrow b')||{}).textContent}; })()""")
        check('the first change makes "<name> (edited)" in My decks, 59 cards', e['n'] == 1 and e['name'] == h['want'] + ' (edited)' and e['main'] == 59 and e['seg'], e)
        check('the sheet stays open with the new count', e['sheet'] == '3', e)
        await p.tap('#mView [data-mdv="main+"]'); await p.tap('#mView [data-mdv="main+"]'); await p.wait_for_timeout(250)
        t = await p.evaluate("({main:deckCount(parseDeck(JSON.parse(localStorage.getItem('mt_decks'))[0].text).main), toast:document.querySelector('#toast').textContent})")
        check('a fifth copy is refused with a toast', t['main'] == 60 and '4 copies at most' in t['toast'], t)
        await p.tap('#mView [data-mdv="main-"]'); await p.tap('#mView [data-mdv="side+"]'); await p.wait_for_timeout(250)
        m = await p.evaluate("""(()=>{ const d=parseDeck(JSON.parse(localStorage.getItem('mt_decks'))[0].text); return {main:deckCount(d.main), side:deckCount(d.side), n:JSON.parse(localStorage.getItem('mt_decks')).length,
          warn:document.querySelector('.mdti .mdcnt').className, txt:document.querySelector('.mdti .mdcnt').textContent}; })()""")
        check('moving one to the sideboard: 59 + 16, the count warns, still one saved deck', m['main'] == 59 and m['side'] == 16 and 'bad' in m['warn'] and '15 at most' in m['txt'] and m['n'] == 1, m)
        await p.tap('#mView [data-mdv="x"]'); await p.tap('[data-mde="undo"]'); await p.tap('[data-mde="undo"]'); await p.wait_for_timeout(250)
        u = await p.evaluate("(()=>{ const d=parseDeck(JSON.parse(localStorage.getItem('mt_decks'))[0].text); return [deckCount(d.main), deckCount(d.side)]; })()")
        check('Undo takes changes back one at a time', u == [60, 15], u)
        await p.tap('#mdQ'); await p.type('#mdQ', 'Light'); await p.wait_for_timeout(900)
        sg = await p.evaluate("[...document.querySelectorAll('#mdSug button')].map(x=>x.textContent)")
        check('typing a name suggests cards', sg[:1] == ['Lightning Bolt'], sg)
        await p.tap('#mdSug button'); await p.wait_for_timeout(500)
        a = await p.evaluate("(()=>{ const d=parseDeck(JSON.parse(localStorage.getItem('mt_decks'))[0].text); return {bolt:(d.main.find(x=>x[0]==='Lightning Bolt')||[0,0])[1], main:deckCount(d.main), sheet:(document.querySelector('#mView h3')||{}).textContent}; })()")
        check('tapping a suggestion adds it to the main deck and opens its sheet', a['bolt'] >= 1 and a['main'] == 61 and a['sheet'] == 'Lightning Bolt', a)
        await p.tap('#mView [data-mdv="x"]'); await p.tap('[data-mde="done"]'); await p.wait_for_timeout(200)
        check('Done leaves editing (Play this deck back)', await p.evaluate("!!document.querySelector('#mdPlay') && !document.querySelector('#mdQ')"))

        # paste
        await p.tap('[data-mdp]'); await p.wait_for_timeout(200)
        await p.fill('#mdPN', 'Burn test')
        await p.fill('#mdPT', 'Creatures (4)\n4 Goblin Guide\n\nInstants (8)\n4 Lightnig Bolt\n4 Xyzzy Card\n\nSideboard (2)\n2 Lightning Helix\nhttps://www.moxfield.com/decks/x')
        await p.wait_for_timeout(200)
        pc = await p.evaluate("document.querySelector('#mdPC').textContent")
        check('the running count reads the list and names what it left out', '12 main · 2 sideboard' in pc and 'needs 60' in pc and 'left out 3 lines' in pc, pc)
        await p.evaluate("navigator.clipboard.writeText('4 Goblin Guide\\n4 Lightning Bolt’s Echo')")
        await p.tap('[data-mdpb="clip"]'); await p.wait_for_timeout(300)
        clip = await p.evaluate("document.querySelector('#mdPT').value")
        check('Paste from clipboard fills the box (or says to tap and hold)', 'Goblin Guide' in clip or 'clipboard' in await p.evaluate("document.querySelector('#toast').textContent"), clip)
        await p.fill('#mdPT', 'Creatures (4)\n4 Goblin Guide\n\nInstants (8)\n4 Lightnig Bolt\n4 Xyzzy Card\n\nSideboard (2)\n2 Lightning Helix\nhttps://www.moxfield.com/decks/x')
        await p.tap('[data-mdpb="add"]'); await p.wait_for_timeout(2500)
        pa = await p.evaluate("""(()=>{ const sv=JSON.parse(localStorage.getItem('mt_decks')); return {n:sv.length, name:sv[0].name, text:sv[0].text, title:document.querySelector('.mdti h3').textContent,
          note:(document.querySelector('.mdnote')||{}).textContent||'', on:(document.querySelector('#mDeck .drow.on b')||{}).textContent}; })()""")
        check('Add deck saves it at the top of My decks and opens it', pa['n'] == 2 and pa['name'] == 'Burn test' and pa['title'] == 'Burn test' and pa['on'] == 'Burn test', pa)
        check('a misspelling Scryfall recognizes is corrected in the saved list', 'Lightnig Bolt → Lightning Bolt' in pa['note'] and '4 Lightning Bolt' in pa['text'] and 'Lightnig' not in pa['text'], pa)
        check('an unknown card is named', 'Not found on Scryfall: Xyzzy Card' in pa['note'], pa['note'])

        # play the short pasted deck: the playtesting question, then the table
        await p.tap('#mdPlay'); await p.wait_for_timeout(400)
        q = await p.evaluate("(document.querySelector('#modal h3, #modal header')||{}).textContent||''")
        check("a short deck asks first: This deck isn't tournament legal", 'tournament legal' in q, q)
        await p.get_by_role('button', name="I'm playtesting").tap(); await p.wait_for_function('G.me && G.me.deck && !document.querySelector("#table").hidden', timeout=15000)
        check('… and sits down with it', await p.evaluate("G.me.deck") == 'Burn test')
        await p.evaluate("showDecks()"); await p.wait_for_timeout(400)
        check('coming back to the deck screen keeps My decks and the deck', await p.evaluate("document.querySelector('[data-mds=\"saved\"]').classList.contains('on') && document.querySelector('.mdti h3').textContent==='Burn test'"))
        await p.tap('[data-mde="del"]'); await p.wait_for_timeout(200)
        await p.get_by_role('button', name='Yes').tap(); await p.wait_for_timeout(300)
        dl = await p.evaluate("({n:JSON.parse(localStorage.getItem('mt_decks')).length, rows:document.querySelectorAll('#mDeck .drow').length, empty:!!document.querySelector('.mdempty')})")
        check('Delete removes it from My decks', dl['n'] == 1 and dl['rows'] == 1 and dl['empty'], dl)
        check('no page errors', not env.errors, env.errors[:3])
    finally:
        await env.stop()

if __name__=="__main__": asyncio.run(main())
if __name__=='__main__': print(('ALL PASS' if all(res) else 'SOME FAILED') + f' ({sum(res)}/{len(res)})')
