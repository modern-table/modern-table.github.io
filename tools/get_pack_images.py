#!/usr/bin/env python3
"""Pack wrapper images for the Draft Table's sealed mode.

Reads tools/pack_images.txt (one line per set: `<set code> <URL of Wizards' WPN product shots zip>`), downloads each zip,
and writes the Play Booster wrappers (every cover variant) and the Prerelease Pack box to draft/packs/<set>/ as small WebP
files, plus draft/packs/<set>/index.json ({"boosters": [...], "kit": "..."}) for the page and listing.txt (every file in
the zip) so a later session can see what else is there. Run by .github/workflows/pack_images.yml, because the sandbox
cannot reach media.wizards.com.

Usage: python3 tools/get_pack_images.py [tools/pack_images.txt]
"""
import io, json, os, re, sys, urllib.request, zipfile
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = 'ModernTable/1.0 (+https://modern-table.github.io/)'

def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=600) as r:
        return r.read()

def shrink(data, width):
    im = Image.open(io.BytesIO(data))
    im.load()
    if im.mode not in ('RGBA', 'RGB'):
        im = im.convert('RGBA')
    bbox = im.getbbox() if im.mode == 'RGBA' else None   # trim empty transparent margins
    if bbox:
        im = im.crop(bbox)
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    out = io.BytesIO()
    im.save(out, 'WEBP', quality=86, method=6)
    return out.getvalue(), im.size

# Play Booster wrappers: names like MTGFRA_EN_Play_Bstr_01_01.png (02, 03 … for the other covers), or MTGFIN_EN_Bstr_Play_01_01.png. Not displays or boxes.
BOOSTER = re.compile(r'play[_ -]?b(oo)?st(e)?r|b(oo)?st(e)?r[_ -]?play', re.I)
NOT_BOOSTER = re.compile(r'dsp|display|box|bx|cs[_ -]|case|crtn|carton|bndl|bundle|clctr|collector|draft', re.I)
KIT = re.compile(r'prrls|prerelease', re.I)
IMG = re.compile(r'\.(png|jpe?g|tiff?|webp)$', re.I)

def main(listfile):
    for line in open(listfile):
        line = line.split('#')[0].strip()
        if not line:
            continue
        code, url = line.split()
        print(f'{code}: downloading {url}')
        z = zipfile.ZipFile(io.BytesIO(fetch(url)))
        names = [n for n in z.namelist() if not n.endswith('/') and '__MACOSX' not in n]
        outdir = os.path.join(ROOT, 'draft', 'packs', code)
        os.makedirs(outdir, exist_ok=True)
        with open(os.path.join(outdir, 'listing.txt'), 'w') as f:
            f.write('\n'.join(sorted(names)) + '\n')
        english = lambda n: re.search(r'[_-]EN[_-]', os.path.basename(n)) or not re.search(r'[_-](DE|FR|IT|JP|JA|ES|PT|KO|CS|CT|RU|ZH)[_-]', os.path.basename(n))
        boosters = sorted(n for n in names if IMG.search(n) and BOOSTER.search(os.path.basename(n)) and not NOT_BOOSTER.search(os.path.basename(n)) and english(n))
        kits = sorted(n for n in names if IMG.search(n) and KIT.search(os.path.basename(n)) and english(n))
        # one image per cover: when a cover comes in several angles (_01_01, _01_02 …), keep the first
        seen, picked = set(), []
        for n in boosters:
            m = re.search(r'Bstr[_-](\d+)', os.path.basename(n), re.I)
            key = m.group(1) if m else os.path.basename(n)
            if key not in seen:
                seen.add(key)
                picked.append(n)
        idx = {'boosters': [], 'kit': ''}
        for i, n in enumerate(picked, 1):
            data, size = shrink(z.read(n), 320)
            fn = f'booster-{i}.webp'
            open(os.path.join(outdir, fn), 'wb').write(data)
            idx['boosters'].append(fn)
            print(f'  {fn} <- {n} {size}')
        if kits:
            data, size = shrink(z.read(kits[0]), 480)
            open(os.path.join(outdir, 'kit.webp'), 'wb').write(data)
            idx['kit'] = 'kit.webp'
            print(f'  kit.webp <- {kits[0]} {size}')
        json.dump(idx, open(os.path.join(outdir, 'index.json'), 'w'), indent=1)
        print(f'  {len(names)} files in the zip, {len(picked)} booster covers, kit: {bool(kits)}')

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'tools', 'pack_images.txt'))
