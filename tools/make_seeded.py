#!/usr/bin/env python3
"""Seeded prerelease boosters for the Draft Table's prerelease kits (Draft v0.36).

Usage:  python3 tools/make_seeded.py /path/to/magic-sealed-data/sealed_basic_data.json
Writes: draft/sets/<set>-seeded.json for every set in SEEDED below.

Khans of Tarkir's prerelease (September 2014): each player chose a clan and got five Khans boosters plus a seeded
booster of that clan's colours with a foil prerelease promo inside. The seeded booster's make-up comes from the same
open dataset as the pack odds (https://github.com/taw/magic-sealed-data, boosters ktk-prerelease-<clan>): 11 commons
and 4 uncommons from the clan's sheets and 1 foil promo, each clan rare twice as likely as its khan (mythic).
The dataset lists the promos as the stamped printings (pktk:12s); they are written here as the plain Khans printing
in foil (ktk:12:foil), as the Reality Fracture promo is, so the built-in card data has their pictures.

File format: {set, packs (regular boosters in the kit), clans: [{k, n, c, ids, sheets, boosters, promo}]}
(ids / sheets / boosters as in draft/sets/<set>.json; promo is the name of the promo sheet).
"""
import json, os, re, sys

SEEDED = {
    'ktk': {'packs': 5, 'clans': [('abzan', 'Abzan', 'WBG'), ('jeskai', 'Jeskai', 'WUR'), ('sultai', 'Sultai', 'UBG'),
                                   ('mardu', 'Mardu', 'WBR'), ('temur', 'Temur', 'URG')]},
}

def plain(cid):
    # pktk:12s:foil -> ktk:12:foil
    m = re.match(r'^p(\w+):(\d+)s(:foil)?$', cid)
    return f'{m.group(1)}:{m.group(2)}{m.group(3) or ""}' if m else cid

def main(path):
    data = {b['code']: b for b in json.load(open(path, encoding='utf-8'))}
    for code, spec in SEEDED.items():
        clans = []
        for k, n, c in spec['clans']:
            b = data[f'{code}-prerelease-{k}']
            ids, pos = [], {}
            def ix(cid):
                cid = plain(cid)
                if cid not in pos:
                    pos[cid] = len(ids); ids.append(cid)
                return pos[cid]
            sheets = {}
            for name, s in b['sheets'].items():
                flat = []
                for cid, w in s['cards'].items():
                    flat += [ix(cid), w]
                sheets[name] = {'c': flat}
            lay = [x for x in b['boosters']]
            assert len(lay) == 1, f'{k}: expected one layout'
            counts = dict(lay[0]['sheets'])
            promo = next(nm for nm in counts if 'promo' in nm)
            assert counts.pop(promo) == 1
            clans.append({'k': k, 'n': n, 'c': c, 'ids': ids, 'sheets': sheets, 'boosters': [[1, counts]], 'promo': promo})
            print(f'{code} {n}: {counts}, {len(sheets[promo]["c"])//2} promos')
        out = {'set': code, 'packs': spec['packs'], 'clans': clans}
        with open(f'draft/sets/{code}-seeded.json', 'w', encoding='utf-8') as f:
            json.dump(out, f, separators=(',', ':'))
        print(f'wrote draft/sets/{code}-seeded.json')

if __name__ == '__main__':
    main(sys.argv[1])
