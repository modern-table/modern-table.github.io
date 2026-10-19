#!/usr/bin/env python3
"""Write src/cards.json: Scryfall's data for every card in the built-in decks, so the Modern Table
can show those decks without asking Scryfall's card-lookup service (limited to 2 requests a second).

Run: python3 tools/make_cards.py /path/to/oracle-cards.json
The input is Scryfall's "Oracle Cards" bulk file (a JSON list or JSON Lines) (https://scryfall.com/docs/api/bulk-data), which
.github/workflows/cards.yml downloads once a week and whenever src/decks.txt changes.

src/cards.json maps the decklist name (lower case, as the game's keyOf() makes it) to a trimmed
Scryfall card object with only the fields toDB() in src/app.src.html reads, and 'id:<scryfall id>'
of each token a deck card makes to that token (what tokenArt() asks for).
Images are not copied: the game still loads them from Scryfall's image site, which has no rate limit."""
import json, re, sys, unicodedata

SKIP = {'art_series', 'token', 'double_faced_token', 'emblem', 'vanguard', 'scheme', 'planar', 'reversible_card'}
FACE = ('name', 'mana_cost', 'type_line', 'oracle_text', 'power', 'toughness', 'loyalty', 'colors')

def plain(n):
    return ''.join(ch for ch in unicodedata.normalize('NFD', str(n or '')) if unicodedata.category(ch) != 'Mn').lower().strip()

def img(o):
    u = (o.get('image_uris') or {}).get('normal')
    return {'normal': u} if u else None

def trim(c):
    t = {k: c[k] for k in ('name', 'mana_cost', 'type_line', 'oracle_text', 'power', 'toughness', 'loyalty', 'layout', 'colors', 'id', 'set') if c.get(k) is not None}
    if img(c): t['image_uris'] = img(c)
    if c.get('card_faces'):
        t['card_faces'] = []
        for f in c['card_faces']:
            g = {k: f[k] for k in FACE if f.get(k) is not None}
            if img(f): g['image_uris'] = img(f)
            t['card_faces'].append(g)
    parts = [{'id': p['id'], 'name': p['name'], 'component': 'token'} for p in c.get('all_parts') or [] if p.get('component') == 'token']
    if parts: t['all_parts'] = parts
    return t

def deck_names(path='src/decks.txt'):
    names = set()
    for line in open(path, encoding='utf-8'):
        line = line.strip()
        if not line or line.startswith('#') or line.startswith('@@') or line.lower() == 'sideboard': continue
        m = re.match(r'(\d+)\s+(.+)', line)
        if m: names.add(m.group(2).strip())
    return sorted(names)

def load_bulk(path):
    """The bulk file is either one JSON list or JSON Lines (one card per line, Scryfall's format since 2026)."""
    with open(path, encoding='utf-8') as f:
        head = f.read(1024).lstrip(); f.seek(0)
        if head.startswith('['): return json.load(f)
        out = []
        for line in f:
            line = line.strip().rstrip(',')
            if line and line not in ('[', ']'): out.append(json.loads(line))
        return out

def aliases(path='src/aliases.txt'):
    """Decklist name -> Scryfall name, for cards a decklist calls by another name (src/aliases.txt)."""
    out = {}
    try:
        for line in open(path, encoding='utf-8'):
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                a, b = (x.strip() for x in line.split('=', 1)); out[plain(a)] = b
    except FileNotFoundError: pass
    return out

def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    bulk = load_bulk(sys.argv[1])
    if not bulk: sys.exit('No cards read from ' + sys.argv[1])
    by_name, tokens = {}, {}
    for c in bulk:
        lay = c.get('layout', '')
        if lay in ('token', 'double_faced_token'):
            tokens.setdefault(plain(c['name']), []).append(c); continue
        if lay in SKIP: continue
        for n in {c['name'], c['name'].split(' // ')[0]}:
            by_name.setdefault(plain(n), c)     # the bulk file has one object per card; the full name and the front face both find it
    out, missing = {}, []
    names = deck_names()
    try: names = sorted(set(names) | set(deck_names('src/extra.txt')))
    except FileNotFoundError: pass
    for n in names:
        al = aliases().get(plain(n))
        c = (al and by_name.get(plain(al))) or by_name.get(plain(n)) or by_name.get(plain(n.split(' // ')[0]))
        if not c: missing.append(n); continue
        out[n.strip().lower()] = trim(c)
        for p in c.get('all_parts') or []:
            if p.get('component') != 'token': continue
            cands = tokens.get(plain(p['name'])) or []
            # the same token name can come in several sizes and colours: prefer the one whose type line matches the part's
            best = next((t for t in cands if t.get('type_line') == p.get('type_line')), cands[0] if cands else None)
            if best: out['id:' + p['id']] = trim(best)
    json.dump(out, open('src/cards.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'), sort_keys=True)
    ncards = sum(1 for k in out if not k.startswith('id:'))
    print(f'src/cards.json: {ncards} cards, {len(out) - ncards} tokens, {len(missing)} not found')
    for n in missing: print('  not found:', n)

if __name__ == '__main__':
    main()
