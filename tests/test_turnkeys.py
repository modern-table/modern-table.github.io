# Static guard: every player field set from the turn number must be cleared at a new game (PER_GAME_KEYS or gather()).
import os, re
s=open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),'src','app.src.html'),encoding='utf-8').read()
setr=re.compile(r"\b(?:m|G\.me)\.([a-zA-Z]+)\s*=\s*(?:\{[^}]*\b[tn]\s*:\s*G\.turn\.n\b|G\.turn\.n\b)")
fields=sorted(set(setr.findall(s)))
pg=re.search(r"const PER_GAME_KEYS=\[(.*?)\];", s, re.S).group(1); pg=set(re.findall(r"'(\w+)'", pg))
gb=s[s.index('function gather(){'):]; gb=gb[:gb.index('\n}\n')]
gd=set(re.findall(r"delete m\.(\w+)", gb))|set(re.findall(r"\bm\.(\w+)=", gb))
miss=[f for f in fields if f not in pg and f not in gd]
print('turn-keyed player fields:', len(fields)); print('PASS' if not miss else 'FAIL', 'all cleared at a new game', miss)
print('ALL PASS (1/1)' if not miss else 'SOME FAILED (0/1)')
