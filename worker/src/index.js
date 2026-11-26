/* Open tables (v5.43 / Draft v0.41): the list behind the front page's bands and the #looking-for-game posts.
   One Durable Object ("lobby") holds every listed table: {c code, n name, m mode, tok, ip, at, beat, msg}.
   A host opens a listing (POST /open), keeps it alive (POST /beat, every minute) and closes it (POST /close) when a friend
   joins, the event starts or they untick it. A listing with no beat for BEAT_MS, or older than MAX_MS, is dropped by the alarm.
   Each listing is posted to Discord through DISCORD_WEBHOOK_URL (a secret set by the deploy workflow, never in the repo) and the
   post is edited when it closes, so the channel doesn't fill up with dead codes. Free plan: every limit fails rather than bills. */

const ORIGINS = ['https://modern-table.github.io'];
const SITE = 'https://modern-table.github.io/';
const MODES = { playtest: 'Playtest', casual: 'Casual', match: 'Match', night: 'Modern Night', draft: 'Draft', sealed: 'Sealed', cube: 'Cube' };
const EVENT_PATH = { night: 'night/', draft: 'draft/', sealed: 'sealed/', cube: 'cube/' };
const BEAT_MS = 3 * 60 * 1000;      // no heartbeat for 3 minutes: the tab is gone
const MAX_MS = 30 * 60 * 1000;      // a listing lasts at most 30 minutes
const PER_IP = 3;                   // listings open at once from one address (friends sharing a house or a store wifi)
const OPENS_PER_HOUR = 12;
const MAX_LISTED = 60;

function cors(req) {
  const o = req.headers.get('Origin') || '';
  return {
    'Access-Control-Allow-Origin': ORIGINS.includes(o) ? o : ORIGINS[0],
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Max-Age': '86400',
    'Vary': 'Origin',
  };
}

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    const h = cors(req);
    if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: h });
    const ok = (req.method === 'GET' && url.pathname === '/list') ||
      (req.method === 'POST' && ['/open', '/beat', '/close'].includes(url.pathname));
    if (!ok) return new Response(url.pathname === '/' ? 'Modern Table open tables.' : 'Not found', { status: url.pathname === '/' ? 200 : 404, headers: h });
    let body = '';
    if (req.method === 'POST') {
      body = await req.text();
      if (body.length > 2000) return new Response('Too large', { status: 413, headers: h });
    }
    const stub = env.LOBBY.get(env.LOBBY.idFromName('lobby'));
    const r = await stub.fetch('https://lobby' + url.pathname, {
      method: req.method,
      body: req.method === 'POST' ? body : undefined,
      headers: { 'X-IP': req.headers.get('CF-Connecting-IP') || '' },
    });
    const out = new Response(r.body, r);
    for (const [k, v] of Object.entries(h)) out.headers.set(k, v);
    out.headers.set('Cache-Control', 'no-store');
    return out;
  },
};

const json = (o, status = 200) => new Response(JSON.stringify(o), { status, headers: { 'Content-Type': 'application/json' } });

function cleanName(s) {
  s = String(s || '').replace(/[\u0000-\u001f\u007f-\u009f\u200b-\u200f\u2028-\u202e\u2066-\u2069]/g, '').replace(/\s+/g, ' ').trim();
  return (s || 'Player').slice(0, 20);
}
/* Discord: names are shown as plain text (markdown characters escaped, @ broken), and allowed_mentions stops any ping. */
const md = s => s.replace(/([\\*_~`|>\[\]<])/g, '\\$1').replace(/@/g, '@\u200b');

function joinLink(e) {
  return EVENT_PATH[e.m] ? `${SITE}${EVENT_PATH[e.m]}?join=${e.c}` : `${SITE}?t=${e.c}&r=g`;
}
function postText(e) {
  return EVENT_PATH[e.m]
    ? `**${md(e.n)}** is hosting a **${MODES[e.m]}** at Game Night, with seats open. Code **${e.c}** · Join: <${joinLink(e)}>`
    : `**${md(e.n)}** opened a **${MODES[e.m]}** table. Code **${e.c}** · Join: <${joinLink(e)}>`;
}
const WHY = { filled: 'Table filled.', started: 'The event has started.', full: 'The event is full.', left: 'No longer open.', expired: 'No longer open.' };

export class Lobby {
  constructor(ctx, env) {
    this.ctx = ctx;
    this.env = env;
    this.t = {};
    this.rate = {};
    ctx.blockConcurrencyWhile(async () => { this.t = (await ctx.storage.get('t')) || {}; });
  }

  async save() {
    await this.ctx.storage.put('t', this.t);
    if (Object.keys(this.t).length && !(await this.ctx.storage.getAlarm())) await this.ctx.storage.setAlarm(Date.now() + 60 * 1000);
  }

  async hook(method, path, content) {
    const u = this.env.DISCORD_WEBHOOK_URL;
    if (!u) return null;
    try {
      const r = await fetch(u + path, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content, allowed_mentions: { parse: [] } }),
      });
      if (!r.ok) return null;
      return method === 'POST' ? (await r.json()).id : true;
    } catch (e) { return null; }
  }

  async drop(e, why) {
    delete this.t[e.c];
    if (e.msg) await this.hook('PATCH', '/messages/' + e.msg, `~~${postText(e).replace(/ · Join: <[^>]+>$/, '')}~~ · ${WHY[why] || WHY.left}`);
  }

  async sweep(now) {
    const gone = Object.values(this.t).filter(e => now - e.beat > BEAT_MS || now - e.at > MAX_MS);
    for (const e of gone) await this.drop(e, 'expired');
    return gone.length;
  }

  async alarm() {
    if (await this.sweep(Date.now())) await this.ctx.storage.put('t', this.t);
    if (Object.keys(this.t).length) await this.ctx.storage.setAlarm(Date.now() + 60 * 1000);
  }

  async fetch(req) {
    const now = Date.now();
    const path = new URL(req.url).pathname;
    const ip = req.headers.get('X-IP') || '';
    let changed = (await this.sweep(now)) > 0;

    if (path === '/list') {
      if (changed) await this.save();
      const tables = Object.values(this.t).sort((a, b) => a.at - b.at).map(e => ({ n: e.n, c: e.c, m: e.m }));
      return json({ tables });
    }

    let b;
    try { b = JSON.parse(await req.text()); } catch (e) { return json({ ok: false, why: 'bad request' }, 400); }
    const c = String(b.c || '').toUpperCase();
    if (!/^[A-Z]{6}$/.test(c)) return json({ ok: false, why: 'bad code' }, 400);
    const e = this.t[c];

    if (path === '/open') {
      const m = String(b.m || '');
      if (!MODES[m]) return json({ ok: false, why: 'bad mode' }, 400);
      if (e) return json({ ok: false, why: 'already listed' }, 409);
      const hr = Math.floor(now / 3600000);
      const k = ip + '|' + hr;
      for (const key of Object.keys(this.rate)) if (!key.endsWith('|' + hr)) delete this.rate[key];
      if ((this.rate[k] || 0) >= OPENS_PER_HOUR) return json({ ok: false, why: 'too many' }, 429);
      this.rate[k] = (this.rate[k] || 0) + 1;
      const mine = Object.values(this.t).filter(x => ip && x.ip === ip).sort((a, x) => a.at - x.at);
      while (mine.length >= PER_IP) await this.drop(mine.shift(), 'left');
      if (Object.keys(this.t).length >= MAX_LISTED) return json({ ok: false, why: 'list full' }, 503);
      const n = { c, n: cleanName(b.n), m, tok: crypto.randomUUID(), ip, at: now, beat: now, msg: null };
      this.t[c] = n;
      await this.save();
      n.msg = await this.hook('POST', '?wait=true', postText(n));
      if (this.t[c] === n) await this.save();
      return json({ ok: true, t: n.tok });
    }

    if (!e || e.tok !== String(b.t || '')) {
      if (changed) await this.save();
      return json({ ok: false, gone: true });
    }
    if (path === '/beat') {
      e.beat = now;
      await this.save();
      return json({ ok: true });
    }
    if (path === '/close') {
      await this.drop(e, String(b.why || 'left'));
      await this.save();
      return json({ ok: true });
    }
    return json({ ok: false }, 404);
  }
}
