"""Crystal Wines (WooCommerce) -> data/raw/cw_all.json
Row: [name, id, permalink, price(minor units str), regular_price, sale_price, price_range,
      in_stock(1/0), type, categories('|'), bottle_size('|'), image, short_description,
      country, wine_colour, wine_type, region, vintage]"""
import re, time, requests
from common import HEADERS, save_if_sane, get_json

BASE = 'https://crystalwines.com'
TAX = ['country', 'wine_colour', 'wine_type', 'region', 'vintage']


def main():
    s = requests.Session(); s.headers.update(HEADERS)
    # 1) products from the Store API
    rows = {}
    for page in range(1, 80):
        r = get_json(s, f'{BASE}/wp-json/wc/store/v1/products?per_page=100&page={page}')
        if r is None:
            break
        prods = r.json()
        if not prods:
            break
        for x in prods:
            bs = next((a for a in (x.get('attributes') or []) if a.get('taxonomy') == 'pa_bottle-size'), None)
            pr = x.get('prices') or {}
            rng = pr.get('price_range')
            rows[x['id']] = [x['name'], x['id'], x['permalink'], pr.get('price'), pr.get('regular_price'), pr.get('sale_price'),
                             [rng.get('min_amount'), rng.get('max_amount')] if rng else None,
                             1 if x.get('is_in_stock') else 0, x.get('type', ''),
                             '|'.join(c['name'] for c in (x.get('categories') or [])),
                             '|'.join(t['name'] for t in bs['terms']) if bs else '',
                             ((x.get('images') or [{}])[0].get('src')) or None,
                             re.sub(r'<[^>]+>', '', x.get('short_description') or '')[:300]]
        print(f'crystal store page {page}: {len(prods)} (total {len(rows)})')
        if len(prods) < 100:
            break
        time.sleep(1)

    # 2) taxonomy term names
    terms = {}
    for t in TAX:
        terms[t] = {}
        for page in range(1, 30):
            r = get_json(s, f'{BASE}/wp-json/wp/v2/{t}?per_page=100&page={page}&_fields=id,name')
            if r is None:
                break
            j = r.json()
            if not isinstance(j, list) or not j:
                break
            for term in j:
                terms[t][term['id']] = term['name']
            if len(j) < 100:
                break

    # 3) per-product taxonomy ids
    tax_of = {}
    for page in range(1, 80):
        r = get_json(s, f'{BASE}/wp-json/wp/v2/product?per_page=100&page={page}&_fields=id,' + ','.join(TAX))
        if r is None:
            break
        j = r.json()
        if not isinstance(j, list) or not j:
            break
        for x in j:
            tax_of[x['id']] = ['|'.join(terms[t].get(i, '') for i in (x.get(t) or [])) for t in TAX]
        if len(j) < 100:
            break
        time.sleep(0.5)

    out = [row + (tax_of.get(pid) or ['', '', '', '', '']) for pid, row in rows.items()]
    save_if_sane('cw_all', out)


if __name__ == '__main__':
    main()
