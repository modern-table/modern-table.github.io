"""v5.35 / Draft v0.39: at Game Night the match tab's own voice comes first and the Discord table channels are the backup.
The room's table button reads "Table N on Discord (backup)", the room's round text points to the match tab's microphone,
the Game Night front page says voice is built into the match tab, and the match tab's waiting cover offers Discord only as a backup."""
import asyncio, os, subprocess, sys, time, socket
ROOT = os.environ.get('MT_ROOT') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
res = []
def check(n, c, e=''): res.append(bool(c)); print('PASS' if c else 'FAIL', n, '' if c else e)

def free_port():
    s = socket.socket(); s.bind(('127.0.0.1', 0)); p = s.getsockname()[1]; s.close(); return p

async def main():
    from playwright.async_api import async_playwright
    port = free_port()
    srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(port), '--bind', '127.0.0.1'], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    pw = await async_playwright().start(); b = await pw.chromium.launch()
    errors = []
    try:
        ctx = await b.new_context(viewport={'width': 1500, 'height': 900})
        await ctx.route(lambda u: not u.startswith('http://127.0.0.1'), lambda r: r.abort())
        p = await ctx.new_page(); p.on('pageerror', lambda e: errors.append(str(e)))
        await p.goto(f'http://127.0.0.1:{port}/night/'); await p.wait_for_timeout(1200)
        front = await p.evaluate("()=>document.body.innerText")
        check('Game Night front page: voice is built into the match tab, Discord is the backup', 'Voice is built into your match tab' in front and 'backup' in front, front[:400])
        btn = await p.evaluate("()=>{ VOICE[0]=VOICE[0]||'https://discord.com/channels/1/2'; return voiceBtn(0); }")
        check('the room\'s table button reads "Table 1 on Discord (backup)"', 'Table 1 on Discord (backup)' in btn and 'Join Table' not in btn, btn)
        src = open(os.path.join(ROOT, 'night', 'index.html'), encoding='utf-8').read()
        check("the room's round text points to the match tab's microphone first", 'Talk through the microphone in your match tab' in src and 'join the Table ${st.k+1} voice channel' not in src)
        p2 = await ctx.new_page(); p2.on('pageerror', lambda e: errors.append(str(e)))
        await p2.goto(f'http://127.0.0.1:{port}/?nobake'); await p2.wait_for_timeout(1500)
        txt = await p2.evaluate("""()=>{ NIGHT={ev:'e', code:'ABCDEF', title:'Modern Tuesday Night Magic', round:1, table:2, opp:'Bob', start:Date.now()+60000, end:Date.now()+3600000, voice:'https://discord.com/channels/1/2'};
          G.code='ABCDEF'; nightWait(); const el=document.querySelector('#nightWait'); return el ? el.innerText : ''; }""")
        check("the match tab's waiting cover says the table offers voice once the opponent is here", 'offers to open a voice line' in txt and 'Bob' in txt, txt)
        check('… with Discord as the backup link', 'Backup: Table 2 on Discord' in txt and 'Join the Table' not in txt, txt)
        check('no page errors', not errors, errors[:3])
    finally:
        await b.close(); await pw.stop(); srv.terminate()

asyncio.run(main())
print(('ALL PASS' if all(res) else 'SOME FAILED') + f' ({sum(res)}/{len(res)})')
