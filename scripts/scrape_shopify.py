"""Generic Shopify products.json scraper.  usage: scrape_shopify.py <key> [<key> ...] | all
Writes data/raw/sh_<key>.json, one row per variant:
[title, handle, product_type, vendor, tags('|'), variant_title, option1, option2, price, compare, available(1/0), image]"""
import sys, time, requests
from common import HEADERS, save_if_sane, get_json

SITES = {
    '1855':      'https://www.1855thebottleshop.com',
    'straits':   'https://straitswine.com',
    'wineconn':  'https://www.wineconnection.com.sg',
    'wholesale': 'https://www.wineswholesales.com.sg',
    'winesonl':  'https://winesonline.com.sg',
    'angra':     'https://angra.com.sg',
}


def scrape(key, base):
    s = requests.Session(); s.headers.update(HEADERS)
    rows = []
    for page in range(1, 80):
        r = get_json(s, f'{base}/products.json?limit=250&page={page}')
        if r is None:
            break
        prods = r.json().get('products', [])
        if not prods:
            break
        for p in prods:
            img = (p.get('images') or [{}])[0].get('src') or ''
            tags = p.get('tags') or []
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(',')]
            for v in p.get('variants') or []:
                rows.append([p['title'], p['handle'], p.get('product_type', ''), p.get('vendor', ''), '|'.join(tags),
                             v.get('title', ''), v.get('option1') or '', v.get('option2') or '',
                             v.get('price'), v.get('compare_at_price'), 1 if v.get('available') else 0, img])
        print(f'{key} page {page}: {len(prods)} products (variants so far {len(rows)})')
        if len(prods) < 250:
            break
        time.sleep(0.8)
    save_if_sane(f'sh_{key}', rows)


def main(keys):
    if not keys or keys == ['all']:
        keys = list(SITES)
    failed = []
    for k in keys:
        try:
            scrape(k, SITES[k])
        except SystemExit as e:
            failed.append(k)
        except Exception as e:
            print(f'{k}: {e}', file=sys.stderr); failed.append(k)
    if failed:
        print('failed:', failed, file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    main(sys.argv[1:])
