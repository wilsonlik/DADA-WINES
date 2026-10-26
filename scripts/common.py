"""Shared helpers for the nightly scrapers."""
import json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / 'data' / 'raw'
RAW.mkdir(parents=True, exist_ok=True)

UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36')
HEADERS = {'User-Agent': UA, 'Accept': 'application/json, text/html;q=0.9, */*;q=0.8',
           'Accept-Language': 'en-SG,en;q=0.9'}


def save_if_sane(name, rows, min_ratio=0.6):
    """Write data/raw/<name>.json only if the new snapshot is not suspiciously small
    compared with the previous one, so a broken scrape never wipes good data."""
    path = RAW / f'{name}.json'
    old_n = 0
    if path.exists():
        try:
            old_n = len(json.load(open(path)))
        except Exception:
            old_n = 0
    if old_n and len(rows) < old_n * min_ratio:
        print(f'[{name}] REFUSING to save: got {len(rows)} rows, previous snapshot had {old_n}', file=sys.stderr)
        sys.exit(2)
    if not rows:
        print(f'[{name}] REFUSING to save: no rows', file=sys.stderr)
        sys.exit(2)
    json.dump(rows, open(path, 'w'), ensure_ascii=False)
    print(f'[{name}] saved {len(rows)} rows (previous {old_n})')


def get_json(session, url, tries=3, **kw):
    for i in range(tries):
        try:
            r = session.get(url, timeout=60, **kw)
            if r.status_code == 200:
                return r
            print(f'  {url} -> HTTP {r.status_code}', file=sys.stderr)
        except Exception as e:
            print(f'  {url} -> {e}', file=sys.stderr)
        time.sleep(3 * (i + 1))
    return None
