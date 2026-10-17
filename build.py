#!/usr/bin/env python3
"""Build index.html (the Modern Table, one file) and draft/index.html (the Draft Table) from src/. Run: python3 build.py"""
import json, re, collections, sys
decks=[]; cur=None; sec='main'
for line in open('src/decks.txt', encoding='utf-8'):
    line=line.rstrip('\n')
    if line.startswith('#'): continue
    if line.startswith('@@'):
        f=[x.strip() for x in line[2:].strip().split('|')]
        ev,date,tid,place,arch,pilot=f[:6]; did=f[6] if len(f)>6 else ''
        cur=dict(ev=ev,date=date,tid=tid,place=place,arch=arch,pilot=pilot,id=did,main=collections.OrderedDict(),side=collections.OrderedDict()); sec='main'; decks.append(cur)
    elif line.strip().lower()=='sideboard': sec='side'
    elif line.strip() and cur is not None:
        m=re.match(r'(\d+)\s+(.+)',line.strip())
        if m: cur[sec][m.group(2)]=cur[sec].get(m.group(2),0)+int(m.group(1))
def placenum(p):
    m=re.match(r'\d+',p); return int(m.group()) if m else 99
decks.sort(key=lambda d:(-int(d['date'].replace('-','')), -int(d['tid'] or 0), placenum(d['place'])))
out=[]; bad=0
for d in decks:
    m=sum(d['main'].values()); s=sum(d['side'].values())
    ok = m>=60 and s<=15
    print(f"{d['date']} {d['place']:4} {d['arch'][:28]:28} {d['pilot'][:18]:18} main={m} side={s}{'' if ok else '  <-- DROPPED'}")
    if not ok: bad+=1; continue
    d['main']=[[n,c] for n,c in d['main'].items()]; d['side']=[[n,c] for n,c in d['side'].items()]
    out.append(d)
if len(out)<10: sys.exit(f'Only {len(out)} valid decks; refusing to build.')
src=open('src/app.src.html', encoding='utf-8').read()
peer=re.sub(r'//# sourceMappingURL=.*','',open('src/peerjs.min.js', encoding='utf-8').read()).replace('</script','<\\/script')
assert '/*__DECKS__*/[]' in src and '/*__PEERJS__*/' in src
html=src.replace('/*__DECKS__*/[]',json.dumps(out,separators=(',',':'),ensure_ascii=False)).replace('/*__PEERJS__*/',peer)
open('index.html','w', encoding='utf-8').write(html)
ver=re.search(r"const VERSION = '([^']+)'", src).group(1)
print(f'built index.html: {len(html)//1024} KB, {len(out)} decks, {bad} dropped, version {ver}')

# Draft Table: small page that loads PeerJS from ../src and one odds file per set from draft/sets/ (see tools/make_draft_sets.py)
dsrc=open('src/draft.src.html', encoding='utf-8').read()
sets=json.load(open('draft/sets/index.json', encoding='utf-8'))
assert '/*__SETS__*/[]' in dsrc and sets
dhtml=dsrc.replace('/*__SETS__*/[]', json.dumps(sets,separators=(',',':'),ensure_ascii=False))
open('draft/index.html','w', encoding='utf-8').write(dhtml)
dver=re.search(r"const VERSION = '([^']+)'", dsrc).group(1)
print(f'built draft/index.html: {len(dhtml)//1024} KB, {len(sets)} sets, version {dver}')
