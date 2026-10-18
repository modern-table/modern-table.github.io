"""Print the download link from Scryfall's bulk-data answer (used by .github/workflows/cards.yml).
The link has been called download_uri; any field holding a data.scryfall.io .json link is accepted, and the field names are shown if none is found."""
import json, sys
d = json.load(open(sys.argv[1]))
if isinstance(d, dict) and isinstance(d.get('data'), list):   # the list of all bulk files
    d = next((x for x in d['data'] if x.get('type') == 'oracle_cards'), d)
def links(o, path=''):
    if isinstance(o, dict):
        for k, v in o.items(): yield from links(v, path + '.' + k)
    elif isinstance(o, list):
        for i, v in enumerate(o): yield from links(v, f'{path}[{i}]')
    elif isinstance(o, str) and o.startswith('https://') and ('.json' in o or 'data.scryfall' in o):
        yield path, o
found = list(links(d))
best = d.get('download_uri') if isinstance(d, dict) else None
best = best or next((u for p, u in found if 'download' in p), None) or next((u for p, u in found if '.json' in u), None)
if not best:
    sys.exit('no download link; fields: ' + ', '.join(f'{k}={str(v)[:40]}' for k, v in (d.items() if isinstance(d, dict) else [])))
print(best)
