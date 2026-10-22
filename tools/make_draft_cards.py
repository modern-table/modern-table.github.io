#!/usr/bin/env python3
"""Write draft/cards/<code>.json: the Oracle text of every card in a Draft Table set or cube, so the cards can be checked
against the table's rules engine without asking Scryfall while playing (and, later, loaded by the Draft Table itself).

Run: python3 tools/make_draft_cards.py /path/to/oracle-cards.json
Which sets and cubes: draft/cards/targets.txt, one code per line (the file names in draft/sets/).
For a booster set, the cards are 'set:collector_number' ids; their names come from Scryfall's search
(/cards/search?q=e:<set> unique:prints include:extras, 0.2 s between pages, as Scryfall asks) and their text from the
Oracle bulk file. For a cube, the names are in the set file already.

Output: {"code", "name", "ids": {"fra:10": "card name", ...} (sets only), "cards": {"card name in lower case": trimmed card}, "missing": [...]}"""
import json, os, re, sys, time, urllib.request, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_cards import load_bulk, trim, plain, odd, SKIP

UA = 'ModernTable/1.0 (+https://modern-table.github.io/)'

def get(url):
    for i in range(5):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=60) as r: return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404: return None
            time.sleep(2 + 10 * i)
        except Exception:
            time.sleep(2 + 10 * i)
    raise SystemExit('Scryfall did not answer: ' + url)

def prints(setcode):
    """collector number -> oracle name for every printing in a set"""
    out, url = {}, 'https://api.scryfall.com/cards/search?' + urllib.parse.urlencode({'q': f'e:{setcode} unique:prints include:extras include:variations', 'order': 'set'})
    while url:
        time.sleep(0.2); page = get(url)
        if not page: break
        for c in page.get('data', []):
            out[str(c['collector_number']).lower()] = c['name']
        url = page.get('next_page') if page.get('has_more') else None
    return out

def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    targets = [l.strip() for l in open('draft/cards/targets.txt', encoding='utf-8') if l.strip() and not l.startswith('#')]
    bulk = load_bulk(sys.argv[1]); by_name = {}
    for c in bulk:
        if c.get('layout') in SKIP: continue
        for n in {c['name'], c['name'].split(' // ')[0]}:
            k = plain(n)
            if k not in by_name or odd(by_name[k]) > odd(c): by_name[k] = c
    cache = {}
    for code in targets:
        d = json.load(open(f'draft/sets/{code}.json', encoding='utf-8')); out = {'code': code, 'name': d.get('name', code), 'cards': {}, 'missing': []}
        if d.get('cube'): names = d['names']
        else:
            ids = sorted({re.sub(r':foil$', '', i) for i in d.get('ids', [])}); out['ids'] = {}
            for i in ids:
                s, n = i.split(':', 1)
                if s not in cache: cache[s] = prints(s)
                nm = cache[s].get(n.lower()) or cache[s].get(re.sub(r'[a-z★]+$', '', n.lower()))
                if nm: out['ids'][i] = nm
                else: out['missing'].append(i)
            names = sorted(set(out['ids'].values()))
        for n in names:
            c = by_name.get(plain(n)) or by_name.get(plain(n.split(' // ')[0]))
            if c: out['cards'][n.lower()] = trim(c)
            else: out['missing'].append(n)
        os.makedirs('draft/cards', exist_ok=True)
        with open(f'draft/cards/{code}.json', 'w', encoding='utf-8') as f: json.dump(out, f, ensure_ascii=False, separators=(',', ':'), sort_keys=True)
        print(f'{code}: {len(out["cards"])} cards, {len(out["missing"])} not found {out["missing"][:8]}')

if __name__ == '__main__': main()
