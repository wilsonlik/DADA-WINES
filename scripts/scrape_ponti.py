"""Ponti Wine Cellars (Shopline storefront) -> data/raw/ponti_all.json
Listing: /collections?page_num=N (16 cards per page).  Detail pages (tags + description with
Vintage/Country/Region/Size/Ratings) are cached in data/ponti_details.json for 30 days.
Row: [title, handle, price, compare, sold_out(1/0), image, tags('|'), description]"""
import json, re, sys, time, html, datetime
import requests
from bs4 import BeautifulSoup
from common import HEADERS, ROOT, save_if_sane, get_json

BASE = 'https://pontiwinecellars.com.sg'
DET = ROOT / 'data' / 'ponti_details.json'
MAX_DETAILS = 500          # new/expired detail pages per run
TTL_DAYS = 30


def money(s):
    m = re.search(r'([\d,]+(?:\.\d+)?)', s or '')
    return float(m.group(1).replace(',', '')) if m else None


def listing(s):
    rows = []
    for page in range(1, 200):
        r = get_json(s, f'{BASE}/collections?page_num={page}')
        if r is None:
            break
        soup = BeautifulSoup(r.text, 'html.parser')
        cards = soup.select('.product-card-wrapper')
        if not cards:
            break
        for c in cards:
            a = c.select_one('a[href*="/products/"]')
            if not a:
                continue
            handle = a['href'].split('/products/')[-1].split('?')[0].strip('/')
            title = (c.select_one('.visually-hidden') or c).get_text(' ', strip=True)
            img = c.select_one('img')
            img = (img.get('src') or '') if img else ''
            sale = c.select_one('.price-item--sale')
            reg = c.select_one('.price-item--regular')
            if sale and money(sale.get_text()):
                price = money(sale.get_text()); compare = money(reg.get_text()) if reg else None
            else:
                price = money(reg.get_text()) if reg else None; compare = None
            sold = 1 if re.search(r'sold\s*out', c.get_text(' ', strip=True), re.I) else 0
            rows.append([html.unescape(title), handle, price, compare, sold, img])
        print(f'ponti page {page}: {len(cards)} cards (total {len(rows)})')
        time.sleep(0.5)
    return rows


def details(s, handles):
    cache = json.load(open(DET)) if DET.exists() else {}
    now = datetime.datetime.utcnow()
    todo = [h for h in handles if h not in cache or
            (now - datetime.datetime.fromisoformat(cache[h].get('ts', '2000-01-01'))).days > TTL_DAYS]
    print(f'ponti details: {len(todo)} to fetch ({len(cache)} cached)')
    for i, h in enumerate(todo[:MAX_DETAILS]):
        r = get_json(s, f'{BASE}/products/{h}', tries=2)
        if r is None:
            continue
        t = r.text
        m = re.search(r'"tags"\s*:\s*(\[[^\]]*\])', t)
        tags = []
        if m:
            try:
                tags = json.loads(m.group(1))
            except Exception:
                tags = []
        desc = ''
        m = re.search(r'"@type"\s*:\s*"Product".*?"description"\s*:\s*"((?:[^"\\]|\\.)*)"', t, re.S)
        if m:
            try:
                desc = json.loads('"' + m.group(1) + '"')
            except Exception:
                desc = m.group(1)
        cache[h] = {'tags': tags, 'desc': html.unescape(desc).strip(), 'ts': now.isoformat(timespec='seconds')}
        if i % 50 == 0:
            json.dump(cache, open(DET, 'w'), ensure_ascii=False)
        time.sleep(0.4)
    json.dump(cache, open(DET, 'w'), ensure_ascii=False)
    return cache


def main():
    s = requests.Session(); s.headers.update(HEADERS)
    rows = listing(s)
    if not rows:
        raise SystemExit('ponti: no rows')
    cache = details(s, [r[1] for r in rows])
    out = []
    for r in rows:
        d = cache.get(r[1]) or {}
        out.append(r + ['|'.join(d.get('tags') or []), d.get('desc', '')])
    save_if_sane('ponti_all', out)


if __name__ == '__main__':
    main()
