"""Pivene (Shopify) -> data/raw/pivene_all.json
Row: [title, handle, type, vendor, price, compare, variant_title, available(1/0),
      country, region, vintage, format, rating, image]"""
import requests, time
from common import HEADERS, save_if_sane, get_json

BASE = 'https://www.pivene.com'


def pick(tags, k):
    for t in tags:
        if t.lower().startswith(k + ':'):
            return t.split(':', 1)[1]
    return ''


def main():
    s = requests.Session(); s.headers.update(HEADERS)
    rows = []
    for page in range(1, 40):
        r = get_json(s, f'{BASE}/products.json?limit=250&page={page}')
        if r is None:
            break
        prods = r.json().get('products', [])
        if not prods:
            break
        for p in prods:
            v = (p.get('variants') or [{}])[0]
            img = (p.get('images') or [{}])[0].get('src')
            tags = p.get('tags') or []
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(',')]
            rows.append([p['title'], p['handle'], p.get('product_type', ''), p.get('vendor', ''),
                         v.get('price'), v.get('compare_at_price'), v.get('title', ''),
                         1 if v.get('available') else 0,
                         pick(tags, 'country'), pick(tags, 'region'), pick(tags, 'vintage'),
                         pick(tags, 'format'), pick(tags, 'rating'), img])
        print(f'pivene page {page}: {len(prods)} (total {len(rows)})')
        if len(prods) < 250:
            break
        time.sleep(1)
    save_if_sane('pivene_all', rows)


if __name__ == '__main__':
    main()
