# Modern Table

A free-form, two-player Magic: The Gathering table that runs in the browser. Nothing is enforced; you play it like paper, and the table does the chores.

**Play:** https://modern-table.github.io/

One player opens a table and sends the six-letter code; the other joins with it. Card images and rules text come from Scryfall. Built-in decklists are recent Modern tournament results from MTGGoldfish, refreshed weekly.

## Draft Table

**Draft:** https://modern-table.github.io/draft/

Booster draft for up to eight players, with bots in the empty seats. Packs follow each set's real pack odds. After the draft you build a 40-card deck and the page pairs three rounds, opening each match on the Modern Table with your drafted deck. Pack odds come from [taw/magic-sealed-data](https://github.com/taw/magic-sealed-data).

## How this repository works

- `index.html` is the whole game in one file. It is generated; do not edit it by hand.
- `src/app.src.html` is the game's source.
- `src/decks.txt` is the built-in decklists.
- `src/peerjs.min.js` is the PeerJS library (MIT), inlined at build time for player-to-player connections.
- `src/draft.src.html` is the Draft Table's source; `draft/sets/` holds one pack-odds file per set.
- `python3 build.py` rebuilds `index.html` and `draft/index.html` from `src/`.

Version numbers look like v1.13. The second number goes up when features change. A decks-only refresh keeps the version.

Unofficial fan project. Magic: The Gathering is a trademark of Wizards of the Coast; this project is not affiliated with or endorsed by them.
