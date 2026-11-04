"""Grand Vin (Shopify, vintage is a variant option) -> data/raw/gv_all.json
Row: [title, handle, product_type, vendor, tags('|'), variant_title, price, compare, available(1/0), image]"""
import requests, time
from common import HEADERS, save_if_sane, get_json

BASE = 'https://www.grandvin.com.sg'


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
            img = (p.get('images') or [{}])[0].get('src')
            tags = p.get('tags') or []
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(',')]
            for v in p.get('variants') or []:
                rows.append([p['title'], p['handle'], p.get('product_type', ''), p.get('vendor', ''), '|'.join(tags),
                             v.get('title', ''), v.get('price'), v.get('compare_at_price'), 1 if v.get('available') else 0, img])
        print(f'grandvin page {page}: {len(prods)} products (total variants {len(rows)})')
        if len(prods) < 250:
            break
        time.sleep(1)
    save_if_sane('gv_all', rows)


if __name__ == '__main__':
    main()
