#!/usr/bin/env python3
"""Does the table read every cost line of these cards?

  python3 tools/cost_check.py "Ghalta the Unstoppable" "Thalia, Guardian of Thraben"
  python3 tools/cost_check.py --file new_cards.txt     (one card name per line)
  python3 tools/cost_check.py --all                    (every card in src/cards.json)
  python3 tools/cost_check.py --draft                  (every card in draft/cards/*.json)

Card text comes from src/cards.json (and draft/cards/*.json), never from memory. The script builds nothing:
it serves the repo's current index.html on a local port, opens a practice game in headless Chromium,
and asks the game's own functions about each line, so it follows the code as it is.

Lines it looks at, and what counts as read:
  "This spell costs {N} less to cast for each <phrase>."   costCount(<phrase>) gives a number
  "This spell costs {X} less to cast, where X is <phrase>." xNum(<phrase>) gives a number
  "This spell costs {N} less to cast if it targets …"       targetDiscount() offers the cheaper cast
  "This spell costs {N} less to cast if <condition>."       condTrue(<condition>) can judge it (true or false)
  any other "This spell costs …" sentence                   not read
  "<kind> spells … cost {N} less/more to cast …"            spellMods() picks the permanent up
  "This ability costs {N} less to activate for each …"      abilLess() knows the phrase
  other "… cost(s) {N} less/more to activate" sentences     not read (nothing handles them)
  Affinity, Delve, Convoke, Improvise                        read; Emerge, Undaunted, Assist not read

Prints one line per cost line (OK / NOT READ / PHRASE NOT UNDERSTOOD) and a summary.
--json prints the results as JSON instead. Exit code 0 either way; 2 if the page could not be driven.
"""
import asyncio, glob, json, os, re, socket, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

COSTY = re.compile(r'\bcosts? \{[^}]+\} (?:less|more)\b|\bcosts? (?:up to )?\{[^}]+\} less\b|(?:^|\n)(?:Affinity for|Delve|Convoke|Improvise|Emerge|Undaunted|Assist)\b', re.I)


def norm(s):
    import unicodedata
    return ''.join(ch for ch in unicodedata.normalize('NFKD', s) if not unicodedata.combining(ch)).lower().strip()


def faces(c):
    """[(face name, type line, oracle text, mana cost)] for a Scryfall card."""
    if c.get('card_faces') and not c.get('oracle_text'):
        return [(f.get('name', c['name']), f.get('type_line', ''), f.get('oracle_text', ''), f.get('mana_cost', '')) for f in c['card_faces']]
    return [(c['name'], c.get('type_line', ''), c.get('oracle_text', '') or '', c.get('mana_cost', '') or '')]


def load_db(draft):
    db = {}
    for k, c in json.load(open(os.path.join(ROOT, 'src/cards.json'))).items():
        if k.startswith('id:'):
            continue
        db[norm(c['name'])] = c
        db.setdefault(norm(c['name'].split(' // ')[0]), c)
    if draft:
        for f in sorted(glob.glob(os.path.join(ROOT, 'draft/cards/*.json'))):
            for c in json.load(open(f)).get('cards', {}).values():
                db.setdefault(norm(c['name']), c)
                db.setdefault(norm(c['name'].split(' // ')[0]), c)
    return db


JS = r"""(items) => {
  const m = G.me, opp = G.opp, out = [];
  m.bf = []; m.gy = []; m.hand = []; m.cast = {n:1, is:1, nc:1}; m.drn = {t:G.turn.n, n:1}; if(opp){ opp.bf = []; opp.cast = {n:1, is:1, nc:1}; opp.drn = {t:G.turn.n, n:1}; }
  const card = f => mk(null, {cu:{n:f.n, t:f.t, o:f.o, mc:f.mc||'', pt:f.pt||''}});
  const anchored = fn => [...String(fn).matchAll(/\/\^((?:[^\/\\\n]|\\.)+)\$\//g)].map(x=>{ try{ return new RegExp('^'+x[1]+'$', 'i'); }catch(e){ return null; } }).filter(Boolean);
  const abilPhr = anchored(abilLess);
  // every regex literal in the page's script that mentions a cost change: a sentence one of them matches has a handler somewhere
  const src = [...document.scripts].map(x=>x.textContent).join('\n'), lits = [];
  for(const x of src.matchAll(/\/((?:\\.|\[(?:\\.|[^\]\n])*\]|[^\/\n\[\\])+)\/([gimsuy]*)/g)){ if(!/cost/i.test(x[1]) || !/less|more/.test(x[1])) continue;
    if(x[1].replace(/\\.|\[[^\]]*\]|\([^)]*\|[^)]*\)/g, '').replace(/[^a-z]/gi, '').length < 35) continue;   /* generic detectors ("costs {N} (less|more) to cast") are not handlers */
    try{ lits.push(new RegExp(x[1], x[2].replace(/g/g,'')||'i')); }catch(e){} }
  let LINE = '';   /* the whole printed line the sentence came from: some handlers read two sentences at once (Zirda) */
  const litHit = s => { const t = s.replace(/^[+−\-]?(?:\d+|X):\s*/, ''), L = LINE.replace(/^[+−\-]?(?:\d+|X):\s*/, ''); return lits.find(re => re.test(t) || re.test(t.toLowerCase()) || re.test(L)); };
  for(const it of items){
    const c = card(it); c.lvl = 9; const sents = it.o.replace(/\([^)]*\)/g, '').split('\n').flatMap(l=>l.split(/(?<=\.)\s+(?=[A-Z{+−])/).map(s=>({s:s.trim(), l:l.trim()}))).filter(x=>x.s);
    for(const {s:s0, l} of sents){ LINE = l;
      const s = s0.replace(/^(?!This\b)[A-Z][\w'’ -]{1,30} — (?=This spell|This ability)/, '');   // ability word: "Domain — This spell costs …"
      let r = null, q;
      const res = (ok, how) => { r = {card: it.card, face: it.n, line: s, ok, how}; };
      if((q = s.match(/^This spell costs \{(\d+)\} less to cast for each ([^.]+?)\.$/i))){ const n = costCount(q[2], G.myId, c.id); n==null ? res('phrase', `costCount doesn't know "${q[2]}"`) : res('ok', `costCount("${q[2]}") = ${n}`); }
      else if((q = s.match(/^This spell costs \{X\} less to cast, where X is ([^.]+?)\.$/i))){ const n = xNum(q[1], c); n==null ? res('phrase', `xNum doesn't know "${q[1]}"`) : res('ok', `xNum("${q[1]}") = ${n}`); }
      else if(/^This spell costs \{\d+\} less to cast if it targets an? [^.]+\.$/i.test(s)){ m.hand.push(c); const t = targetDiscount(c); m.hand = []; t ? res('ok', 'targetDiscount (cheaper cast in the hand menu)') : res('no', 'targetDiscount gives nothing'); }
      else if((q = s.match(/^This spell costs \{(\d+)\} less to cast if ([^.]+?)\.$/i))){ const v = condTrue(q[2], c); v==null ? res('phrase', `condTrue can't judge "${q[2]}"`) : res('ok', `condTrue("${q[2]}") = ${v}`); }
      else if(/^This spell costs\b/i.test(s)) res('no', 'costNow reads no "This spell costs" line worded like this');
      else if(/\bcosts? \{\d+\} (?:less|more) to cast\b/i.test(s) && /\bspells?\b/i.test(s)){
        const keep = spellMatches; let hit = false;
        try{ spellMatches = () => true;
          for(const side of [m, opp].filter(Boolean)){ const x = card(it); x.chosen = 'Elf'; x.lvl = 9; side.bf = [x]; const sp = card({n:'Test Spell', t:'Instant', o:'', mc:'{3}'}); m.gy = [sp];
            for(const pid of [G.myId, oppId()]) for(const act of [G.myId, oppId()]){ const ta = G.turn.active; G.turn.active = act; try{ if(spellMods(sp, pid).some(e=>e.name===cdata(x).n.split(',')[0])) hit = true; } finally { G.turn.active = ta; } }
            side.bf = []; m.gy = []; } }
        finally { spellMatches = keep; }
        const lh = !hit && litHit(s);
        hit ? res('ok', 'spellMods (cost change from a permanent)') : lh ? res('ok', 'a handler matches it: '+String(lh).slice(0,90)) : res('no', 'spellMods skips this sentence (target, unknown condition after the cost, or wording)');
      }
      else if(/costs \{\d+\} less to activate for each \+1\/\+1 counter on the creature it targets/i.test(s)) res('ok', 'abilLess (equip, counters on the target)');
      else if((q = s.match(/^This ability costs \{\d+\} less to activate for each (other )?([^.]+?)\.$/i))){ const d = q[2].toLowerCase(); const lh = litHit(s); abilPhr.some(re=>re.test(d)) ? res('ok', 'abilLess') : lh ? res('ok', 'a handler matches it: '+String(lh).slice(0,90)) : res('phrase', `abilLess doesn't know "${q[2]}"`); }
      else if(/\bcosts? (?:up to )?\{[^}]+\} (?:less|more) to activate\b/i.test(s)) litHit(s) ? res('ok', 'a handler matches it: '+String(litHit(s)).slice(0,90)) : res('no', 'nothing reads activation cost changes worded like this');
      else if(/^(?:Affinity for \w+|Delve|Convoke|Improvise)\b/i.test(s)){ const a = s.match(/^Affinity for (\w+)/i); if(a){ const n = costCount(a[1]+' you control', G.myId, c.id); n==null ? res('phrase', `costCount doesn't know "${a[1]} you control"`) : res('ok', 'Affinity (costNow)'); } else res('ok', s.split(/\s/)[0]+' (paid in the pay window)'); }
      else if(/^(?:Emerge|Undaunted|Assist)\b/i.test(s)) res('no', s.split(/\s/)[0]+' is not handled');
      else if(/\bcosts? (?:up to )?\{[^}]+\} (?:less|more)\b/i.test(s)) litHit(s) ? res('ok', 'a handler matches it: '+String(litHit(s)).slice(0,90)) : res('no', 'a cost change the table has no reader for');
      if(r) out.push(r);
    }
  }
  return out;
}"""


def free_port():
    s = socket.socket(); s.bind(('127.0.0.1', 0)); p = s.getsockname()[1]; s.close(); return p


async def run(items):
    from playwright.async_api import async_playwright
    port = free_port()
    srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(port), '--bind', '127.0.0.1'], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(0.8)
        async with async_playwright() as pw:
            try:
                b = await pw.chromium.launch()
            except Exception:
                b = await pw.chromium.launch(executable_path='/usr/bin/google-chrome')
            ctx = await b.new_context(viewport={'width': 1500, 'height': 900})
            for h in ['**/cards.scryfall.io/**', '**/svgs.scryfall.io/**', '**/backs.scryfall.io/**', '**/fonts.googleapis.com/**', '**/fonts.gstatic.com/**']:
                await ctx.route(h, lambda r: r.abort())
            await ctx.route('**/api.scryfall.com/**', lambda r: r.fulfill(status=200, content_type='application/json', body='{"data":[]}'))
            p = await ctx.new_page(); errs = []
            p.on('pageerror', lambda e: errs.append(str(e)))
            await p.goto(f'http://127.0.0.1:{port}/'); await p.wait_for_timeout(600)
            await p.click('#soloBtn'); await p.wait_for_timeout(600)
            await p.locator('.drow').first.click(); await p.wait_for_timeout(400)
            await p.get_by_role('button', name='Play this deck').click(); await p.wait_for_timeout(1500)
            for name in ['No deck', 'Keep']:
                bt = p.get_by_role('button', name=name)
                if await bt.count():
                    try: await bt.first.click(timeout=800)
                    except Exception: pass
            await p.wait_for_function('typeof G!=="undefined" && G.me && Array.isArray(G.me.bf)', timeout=10000)
            res = await p.evaluate(JS, items)
            await b.close()
            return res, errs
    finally:
        srv.terminate()


def main():
    a = sys.argv[1:]
    as_json = '--json' in a; a = [x for x in a if x != '--json']
    draft = '--draft' in a
    db = load_db(draft or '--all' not in a)
    names = []
    if '--all' in a:
        names = sorted({c['name'] for k, c in json.load(open(os.path.join(ROOT, 'src/cards.json'))).items() if not k.startswith('id:')})
    elif draft:
        for f in sorted(glob.glob(os.path.join(ROOT, 'draft/cards/*.json'))):
            names += [c['name'] for c in json.load(open(f)).get('cards', {}).values()]
        names = sorted(set(names))
    else:
        if '--file' in a:
            i = a.index('--file'); names += [l.strip() for l in open(a[i + 1]) if l.strip() and not l.startswith('#')]; a = a[:i] + a[i + 2:]
        names += a
    if not names:
        print(__doc__); return 0
    items, missing = [], []
    for n in names:
        c = db.get(norm(n)) or db.get(norm(n.split(' // ')[0]))
        if not c:
            missing.append(n); continue
        for fn, tl, o, mc in faces(c):
            if COSTY.search(o):
                items.append({'card': c['name'], 'n': fn, 't': tl, 'o': o, 'mc': mc})
    res, errs = ([], [])
    if items:
        try:
            res, errs = asyncio.run(run(items))
        except Exception as e:
            print('Could not drive the page:', e); return 2
    if as_json:
        print(json.dumps({'results': res, 'missing': missing, 'page_errors': errs}, indent=1)); return 0
    lab = {'ok': 'OK', 'no': 'NOT READ', 'phrase': 'PHRASE NOT UNDERSTOOD'}
    for r in sorted(res, key=lambda r: (r['ok'] == 'ok', r['card'])):
        print(f"{lab[r['ok']]:22} {r['card']}: {r['line']}\n{'':22}   → {r['how']}")
    bad = sorted({r['card'] for r in res if r['ok'] != 'ok'})
    print(f"\n{len(names)} cards checked, {len({r['card'] for r in res})} with cost lines, {len(res)} lines: "
          f"{sum(r['ok'] == 'ok' for r in res)} read, {sum(r['ok'] != 'ok' for r in res)} not.")
    if bad: print('Needs work:', '; '.join(bad))
    if missing: print('Not in the card data:', '; '.join(missing))
    if errs: print('Page errors:', *errs[:5], sep='\n  ')
    return 0


if __name__ == '__main__':
    sys.exit(main())
