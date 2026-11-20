#!/usr/bin/env python3
"""Run every Modern Table test in this folder.

    python3 tests/run_all.py                 # test the current build (run python3 build.py first)
    python3 tests/run_all.py --rev HEAD~1    # the same tests against an older build: new tests should FAIL there
    python3 tests/run_all.py -k resume       # only tests whose file name contains "resume"

Each test opens a practice game in headless Chromium (Playwright) over a local http.server, with Scryfall mocked.
A test prints PASS/FAIL lines and ends with "ALL PASS (n/n)" or "SOME FAILED (k/n)". Exit code 1 if any test fails.
Needs: pip install playwright && python3 -m playwright install chromium
"""
import argparse, glob, os, re, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATIC = {'test_turnkeys.py'}   # reads the source, not a build: skipped with --rev

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rev', help='serve index.html from this git revision instead of the working tree')
    ap.add_argument('-k', default='', help='only test files whose name contains this')
    ap.add_argument('--timeout', type=int, default=300, help='seconds per test')
    a = ap.parse_args()
    env = dict(os.environ)
    if a.rev:
        d = tempfile.mkdtemp(prefix='mt-rev-')
        html = subprocess.run(['git', 'show', f'{a.rev}:index.html'], cwd=REPO, capture_output=True, check=True).stdout
        open(os.path.join(d, 'index.html'), 'wb').write(html)
        env['MT_ROOT'] = d
        print(f'Serving index.html from {a.rev}')
    tests = sorted(t for t in glob.glob(os.path.join(HERE, 'test_*.py')) if a.k in os.path.basename(t))
    if a.rev: tests = [t for t in tests if os.path.basename(t) not in STATIC]
    rows, bad = [], 0
    for t in tests:
        n = os.path.basename(t); t0 = time.time()
        try:
            out = subprocess.run([sys.executable, t], env=env, capture_output=True, text=True, timeout=a.timeout)
            text = out.stdout + out.stderr
        except subprocess.TimeoutExpired:
            text = 'TIMEOUT'
        m = re.search(r'(ALL PASS|SOME FAILED) \((\d+)/(\d+)\)', text)
        ok = bool(m and m.group(1) == 'ALL PASS')
        if not ok:
            bad += 1
            fails = [l for l in text.splitlines() if l.startswith('FAIL') or 'Error' in l or l == 'TIMEOUT']
            print(f'--- {n}'); print('\n'.join(fails[:12]) or text[-800:])
        rows.append((n, m.group(0) if m else 'NO RESULT', time.time() - t0))
    print()
    for n, r, s in rows: print(f'{n:22} {r:22} {s:5.0f}s')
    print(f'\n{len(rows) - bad}/{len(rows)} test files passed')
    sys.exit(1 if bad else 0)

if __name__ == '__main__':
    main()
