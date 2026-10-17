"""Post new "What's new" lines to Discord when the Modern Table version changes.

Usage: announce.py OLD_SOURCE_FILE NEW_SOURCE_FILE
  OLD_SOURCE_FILE may be "-" (manual run: announce only the newest entry).
Reads the Discord webhook URL from the DISCORD_WEBHOOK environment variable.
Set DRY_RUN=1 to print the payload instead of posting it.
"""
import json
import os
import re
import sys
import urllib.request

PLAY = 'https://modern-table.github.io/'
COLOR = 0xC9A227  # brass/gold, like the table's highlights

VERSION_RE = re.compile(r"const VERSION\s*=\s*'(v[\d.]+)'")
ENTRY_RE = re.compile(
    r"\[\s*'(v[\d.]+)'\s*,\s*'([^']*)'\s*,\s*"
    r"(\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*')\s*\]"
)


def read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def version_of(src):
    m = VERSION_RE.search(src)
    return m.group(1) if m else None


def key(v):
    return tuple(int(p) for p in v.lstrip('v').split('.'))


def js_string(lit):
    body = lit[1:-1]
    if lit[0] == '"':
        try:
            return json.loads(lit)
        except ValueError:
            pass
    return re.sub(r"\\(.)", r"\1", body)


def news(src):
    start = src.find('const NEWS')
    if start < 0:
        return []
    end = src.find('];', start)
    block = src[start:end]
    return [(v, d, js_string(t)) for v, d, t in ENTRY_RE.findall(block)]


def main():
    old_path, new_path = sys.argv[1], sys.argv[2]
    new_src = read(new_path)
    new_v = version_of(new_src)
    entries = news(new_src)
    if not new_v or not entries:
        print('No version or NEWS found; nothing to announce.')
        return

    if old_path == '-':
        fresh = entries[:1]
    else:
        old_v = version_of(read(old_path))
        if old_v == new_v:
            print(f'Version unchanged ({new_v}); nothing to announce.')
            return
        old_k = key(old_v) if old_v else (0,)
        fresh = [e for e in entries if key(e[0]) > old_k and key(e[0]) <= key(new_v)]
        if not fresh:
            print(f'{old_v} -> {new_v} but no new NEWS lines; nothing to announce.')
            return

    fresh = list(reversed(fresh[:10]))  # oldest first, Discord allows 10 embeds
    embeds = [{
        'title': f'Modern Table {v} is live',
        'url': PLAY,
        'description': f'{text}\n\n▶ [Play]({PLAY})',
        'color': COLOR,
        'footer': {'text': date},
    } for v, date, text in fresh]
    payload = {'embeds': embeds, 'allowed_mentions': {'parse': []}}

    if os.environ.get('DRY_RUN'):
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    hook = os.environ.get('DISCORD_WEBHOOK')
    if not hook:
        sys.exit('DISCORD_WEBHOOK secret is not set.')
    req = urllib.request.Request(
        hook,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'User-Agent': 'DiscordBot (https://github.com/modern-table/modern-table.github.io, 1.0)',
        },
    )
    with urllib.request.urlopen(req) as r:
        print('Posted', ', '.join(e[0] for e in fresh), '- HTTP', r.status)


if __name__ == '__main__':
    main()
