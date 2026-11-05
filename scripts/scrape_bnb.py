"""Bottles & Bottles (OpenCart) -> data/raw/bnb_all.json
Listing pages give brand/title/price/image; each product page gives stock, country and region
(country/region cached in data/bnb_details.json, stock refreshed every run).
Row: [category, brand, title, url, price, old_price, image, stock_text, country, region]"""
import json, re, sys, time, html, datetime
import requests
from bs4 import BeautifulSoup
from common import HEADERS, ROOT, save_if_sane, get_json

BASE = 'https://www.bnb.com.sg'
CATS = [
    ('red',       '/index.php?route=product/category&path=498_506_1843'),
    ('white',     '/wine/wine-by-type/all-white-wine'),
    ('sweet',     '/wine/wine-by-type/sweet-wine'),
    ('rose',      '/wine/wine-by-type/all-rose-wine'),
    ('nonalc',    '/index.php?route=product/category&path=498_506_1934'),
    ('sparkling', '/champagne-and-sparkling'),
    ('spirits',   '/spirits-and-sake'),
    ('wine',      '/wine'),
]
DET = ROOT / 'data' / 'bnb_details.json'
TTL_DAYS = 30


def money(s):
    m = re.search(r'([\d,]+(?:\.\d+)?)', s or '')
    return float(m.group(1).replace(',', '')) if m else None


def listing(s):
    rows, seen = [], set()
    for cat, path in CATS:
        for page in range(1, 60):
            sep = '&' if '?' in path else '?'
            r = get_json(s, f'{BASE}{path}{sep}limit=100&page={page}')
            if r is None:
                break
            soup = BeautifulSoup(r.text, 'html.parser')
            cards = soup.select('.product-layout')
            n = 0
            for c in cards:
                a = c.select_one('.text-title a')
                if not a:
                    continue
                href = a.get('href') or ''
                if href in seen:
                    continue
                seen.add(href)
                title = html.unescape(a.get_text(' ', strip=True))
                b = c.select_one('.text-brand')
                brand = b.get_text(' ', strip=True) if b else ''
                new = c.select_one('.price-new')
                old = c.select_one('.price-old')
                price = money(new.get_text()) if new else money((c.select_one('.price') or c).get_text())
                img = c.select_one('img')
                img = (img.get('src') or '') if img else ''
                rows.append([cat, brand, title, href, price, money(old.get_text()) if old else None, img])
                n += 1
            print(f'bnb {cat} page {page}: {len(cards)} cards, {n} new (total {len(rows)})')
            if not cards or n == 0:
                break
            time.sleep(0.5)
    return rows


def detail(s, url):
    r = get_json(s, url, tries=2)
    if r is None:
        return None
    soup = BeautifulSoup(r.text, 'html.parser')
    txt = soup.get_text(' ', strip=True)
    m = re.search(r'(\d+\s+Left in Stock|Out of Stock|In Stock|Pre-?Order)', txt, re.I)
    stock = m.group(1) if m else ''
    # the nav menu also contains "Country France Italy ..." so keep only short values (the product attribute)
    ctys = [m.strip() for m in re.findall(r'\bCountry\s+([A-Za-z][A-Za-z ]+?)\s+(?:Region|Grape|Food|Alcohol|Tasting|Awards|You May)', txt) if len(m.split()) <= 3]
    regs = [m.strip() for m in re.findall(r'\bRegion\s+([A-Za-z][A-Za-z ,\'-]+?)\s+(?:Grape|Food|Alcohol|Tasting|Awards|You May)', txt) if len(m.split()) <= 8]
    return dict(stock=stock, country=ctys[0] if ctys else '', region=regs[0] if regs else '')


def main():
    s = requests.Session(); s.headers.update(HEADERS)
    rows = listing(s)
    if not rows:
        raise SystemExit('bnb: no rows')
    cache = json.load(open(DET)) if DET.exists() else {}
    now = datetime.datetime.utcnow()
    for i, r in enumerate(rows):
        url = r[3]
        d = detail(s, url)
        if d is not None:
            old = cache.get(url) or {}
            cache[url] = dict(stock=d['stock'], country=d['country'] or old.get('country', ''),
                              region=d['region'] or old.get('region', ''), ts=now.isoformat(timespec='seconds'))
        if i % 100 == 0:
            print(f'bnb details {i}/{len(rows)}')
            json.dump(cache, open(DET, 'w'), ensure_ascii=False)
        time.sleep(0.25)
    json.dump(cache, open(DET, 'w'), ensure_ascii=False)
    out = []
    for r in rows:
        d = cache.get(r[3]) or {}
        out.append(r + [d.get('stock', ''), d.get('country', ''), d.get('region', '')])
    save_if_sane('bnb_all', out)


if __name__ == '__main__':
    main()
