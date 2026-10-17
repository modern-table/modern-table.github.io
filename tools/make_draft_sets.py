#!/usr/bin/env python3
"""Convert booster odds from taw/magic-sealed-data into the small per-set files the Draft Table reads.

Usage:  python3 tools/make_draft_sets.py /path/to/magic-sealed-data/sealed_basic_data.json
Writes: draft/sets/<set>.json for every set in SETS below, and draft/sets/index.json.

Per-set file format:
  ids      list of card ids, "set:number" or "set:number:foil"
  sheets   {name: {"c": [idIndex, weight, idIndex, weight, ...], "b": 1 if colour-balanced, "f": 1 if fixed}}
  boosters [[weight, {sheetName: count}], ...]
"""
import json, os, sys

# (booster code in the dataset, group shown in the set picker)
SETS = [
    ('fra-play', 'Recent'), ('hob-play', 'Recent'), ('msh-play', 'Recent'), ('sos-play', 'Recent'), ('tmt-play', 'Recent'),
    ('ecl-play', 'Recent'), ('tla-play', 'Recent'), ('spm-play', 'Recent'), ('eoe-play', 'Recent'), ('fin-play', 'Recent'),
    ('tdm-play', 'Favourites'), ('fdn-play', 'Favourites'), ('dsk-play', 'Favourites'), ('blb-play', 'Favourites'),
    ('mh3-play', 'Favourites'), ('mom-draft', 'Favourites'), ('neo-draft', 'Favourites'), ('mh2-draft', 'Favourites'),
    ('eld-draft', 'Favourites'), ('mh1-draft', 'Favourites'), ('war-draft', 'Favourites'), ('dom-draft', 'Favourites'),
    ('ktk-draft', 'Favourites'), ('isd-draft', 'Favourites'), ('roe-draft', 'Favourites'),
]

def main(path):
    data = {b['code']: b for b in json.load(open(path, encoding='utf-8'))}
    os.makedirs('draft/sets', exist_ok=True)
    index = []
    for code, group in SETS:
        b = data[code]
        ids, pos = [], {}
        def ix(cid):
            if cid not in pos:
                pos[cid] = len(ids); ids.append(cid)
            return pos[cid]
        sheets = {}
        for name, s in b['sheets'].items():
            flat = []
            for cid, w in s['cards'].items():
                flat += [ix(cid), w]
            o = {'c': flat}
            if s.get('balance_colors'): o['b'] = 1
            if s.get('fixed'): o['f'] = 1
            sheets[name] = o
        boosters = [[bo['weight'], bo['sheets']] for bo in b['boosters']]
        sizes = {sum(bo['sheets'].values()) for bo in b['boosters']}
        assert len(sizes) == 1, (code, sizes)
        out = {'code': b['set_code'], 'name': b['set_name'], 'size': sizes.pop(), 'ids': ids, 'sheets': sheets, 'boosters': boosters}
        fn = f"draft/sets/{b['set_code']}.json"
        json.dump(out, open(fn, 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
        uniq = len({i.replace(':foil', '') for i in ids})
        index.append({'code': b['set_code'], 'name': b['set_name'], 'size': out['size'], 'group': group})
        print(f"{b['set_code']:4} {b['set_name'][:30]:30} {out['size']} cards/pack  {len(boosters):3} layouts  {uniq} cards  {os.path.getsize(fn)//1024} KB")
    try: index += [e for e in json.load(open('draft/sets/index.json', encoding='utf-8')) if e.get('group') == 'Cubes']   # cubes come from tools/make_cube.py
    except FileNotFoundError: pass
    json.dump(index, open('draft/sets/index.json', 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
    print(f'{len(index)} sets written')

if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
