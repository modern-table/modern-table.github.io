#!/usr/bin/env python3
"""Turn a pasted cube list into a Draft Table cube.

Usage:  python3 tools/make_cube.py CODE "Cube name" draft/cubes/CODE.txt [pack size, default 15]
Writes: draft/sets/CODE.json  {"code", "name", "size", "cube": 1, "names": [...]}
        and adds or updates the entry in draft/sets/index.json under the group "Cubes".

The text file is the cleaned list, one card name per line (lines starting with # are ignored).
A cube is shuffled once per draft and dealt out in packs without repeats; cards are looked up
on Scryfall by name when the draft starts.
"""
import json, sys

def main(code, name, path, size=15):
    names = []
    for line in open(path, encoding='utf-8'):
        line = line.strip()
        if line and not line.startswith('#'): names.append(line)
    dup = {n for n in names if names.count(n) > 1}
    json.dump({'code': code, 'name': name, 'size': size, 'cube': 1, 'names': names},
              open(f'draft/sets/{code}.json', 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
    index = [e for e in json.load(open('draft/sets/index.json', encoding='utf-8')) if e['code'] != code]
    index.append({'code': code, 'name': name, 'size': size, 'group': 'Cubes'})
    json.dump(index, open('draft/sets/index.json', 'w', encoding='utf-8'), separators=(',', ':'), ensure_ascii=False)
    print(f'{name}: {len(names)} cards, packs of {size}, enough for {len(names)//(size*3)} players without repeats'
          + (f'; listed more than once: {", ".join(sorted(dup))}' if dup else ''))

if __name__ == '__main__':
    if len(sys.argv) not in (4, 5): sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) == 5 else 15)
