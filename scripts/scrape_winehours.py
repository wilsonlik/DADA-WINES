"""Winehours (OpenCart) -> data/raw/wh_all.json
Row: [name, url, price, old_price, out_of_stock(1/0), ratings('WA 100|JS 98'), image, enquire(1/0)]"""
import re, sys, time, html
import requests
from bs4 import BeautifulSoup
from common import HEADERS, save_if_sane, get_json

BASE = 'https://winehours.com'
LIST = BASE + '/products/wine-shop?page={}&limit=100'


def price_of(el):
    """<sup>S$</sup>217<sup>98</sup> -> 217.98"""
    if el is None:
        return None
    h = str(el)
    h = re.sub(r'<sup>\s*S?\$\s*</sup>', 'S$', h)
    h = re.sub(r'<sup>\s*(\d{1,2})\s*</sup>', r'.\1', h)
    txt = BeautifulSoup(h, 'html.parser').get_text(' ', strip=True)
    m = re.search(r'S\$\s*([\d,]+(?:\.\d+)?)', txt)
    return float(m.group(1).replace(',', '')) if m else None


def slug_name(href):
    slug = href.rstrip('/').split('/')[-1]
    return ' '.join(w.capitalize() for w in slug.split('-'))


def main():
    s = requests.Session(); s.headers.update(HEADERS)
    rows, seen = [], set()
    for page in range(1, 80):
        r = get_json(s, LIST.format(page))
        if r is None:
            break
        soup = BeautifulSoup(r.text, 'html.parser')
        cards = soup.select('.product-block')
        n = 0
        for c in cards:
            a = c.select_one('.product-name a')
            if not a:
                continue
            href = a.get('href') or ''
            if href in seen:
                continue
            seen.add(href)
            name = html.unescape(a.get_text(' ', strip=True))
            if name.endswith('..'):
                name = slug_name(href)
            oos = 1 if 'out-of-stock' in (c.get('class') or []) else 0
            enquire = 1 if c.select_one('.product-details button') and 'enquir' in c.select_one('.product-details').get_text().lower() else 0
            pn = c.select_one('.price-new') or c.select_one('.price')
            if pn is not None and pn.select_one('.price-new'):
                pn = pn.select_one('.price-new')
            price = None if enquire else price_of(pn)
            old = price_of(c.select_one('.price-old'))
            tags = []
            for t in c.select('.wine-tags .tag'):
                sp = [x.get_text(strip=True) for x in t.select('span')]
                if len(sp) >= 2 and sp[1]:
                    tags.append(f'{sp[0]} {sp[1]}')
            img = c.select_one('.product-image img')
            img = (img.get('src') or img.get('data-src') or '') if img else ''
            rows.append([name, href, price, old, oos, '|'.join(tags), img, enquire])
            n += 1
        print(f'winehours page {page}: {len(cards)} cards, {n} new (total {len(rows)})')
        if len(cards) == 0 or n == 0:
            break
        time.sleep(0.6)
    save_if_sane('wh_all', rows)


if __name__ == '__main__':
    main()
