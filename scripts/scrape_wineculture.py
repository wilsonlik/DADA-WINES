"""Wine Culture (WooCommerce, older Store API path) -> data/raw/wc_all.json
Row: [name, id, permalink, price(minor units str), regular_price, sale_price, in_stock(1/0), categories('|'), image, short_description(text)]"""
import re, time, requests
from common import HEADERS, save_if_sane, get_json

BASE = 'https://wineculture.com.sg'


def main():
    s = requests.Session(); s.headers.update(HEADERS)
    rows = []
    for page in range(1, 80):
        r = get_json(s, f'{BASE}/wp-json/wc/store/products?per_page=100&page={page}')
        if r is None:
            break
        prods = r.json()
        if not isinstance(prods, list) or not prods:
            break
        for x in prods:
            pr = x.get('prices') or {}
            sd = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', x.get('short_description') or '')).strip()[:300]
            rows.append([x['name'], x['id'], x['permalink'], pr.get('price'), pr.get('regular_price'), pr.get('sale_price'),
                         1 if x.get('is_in_stock') else 0, '|'.join(c['name'] for c in (x.get('categories') or [])),
                         ((x.get('images') or [{}])[0].get('src')) or '', sd])
        print(f'wineculture page {page}: {len(prods)} (total {len(rows)})')
        if len(prods) < 100:
            break
        time.sleep(0.5)
    save_if_sane('wc_all', rows)


if __name__ == '__main__':
    main()
