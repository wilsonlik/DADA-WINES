"""Fine Wines SG (Odoo eCommerce) -> data/raw/fw_all.json
Row: [category, name, url, price, list_price, stock_text, ribbon, image]"""
import re, sys, time, html
import requests
from bs4 import BeautifulSoup
from common import HEADERS, save_if_sane, get_json

BASE = 'https://finewines.com.sg'
CATS = ['wine-249', 'sake-269', 'spirits-270']


def money(s):
    m = re.search(r'([\d,]+(?:\.\d+)?)', s or '')
    return float(m.group(1).replace(',', '')) if m else None


def scrape_cat(s, cat, rows, seen):
    for page in range(1, 120):
        url = f'{BASE}/shop/category/{cat}' + (f'/page/{page}' if page > 1 else '')
        r = get_json(s, url)
        if r is None:
            break
        soup = BeautifulSoup(r.text, 'html.parser')
        cards = soup.select('.oe_product')
        if not cards:
            break
        n = 0
        for c in cards:
            a = c.select_one('h2 a[itemprop=name], .o_wsale_products_item_title a')
            if not a:
                continue
            href = a.get('href') or ''
            if href in seen:
                continue
            seen.add(href)
            name = html.unescape(a.get('content') or a.get_text(' ', strip=True))
            lab = c.select_one('.o_wsale_product_information_text a.text-muted')
            label = lab.get_text(' ', strip=True) if lab else ''
            pr = c.select_one('[itemprop=price]')
            price = money(pr.get_text()) if pr else None
            lp = c.select_one('.oe_default_price, del, s, .text-decoration-line-through')
            list_price = money(lp.get_text()) if lp else None
            st = ' '.join(x.get_text(' ', strip=True) for x in c.select('.rating_stock_detail')).strip()
            rb = c.select_one('.o_ribbons, .o_ribbon')
            ribbon = rb.get_text(' ', strip=True) if rb else ''
            img = c.select_one('img[itemprop=image], img')
            img = (img.get('data-original') or img.get('src') or '') if img else ''
            if img.startswith('/'):
                img = BASE + img
            rows.append([label, name, BASE + href if href.startswith('/') else href, price, list_price, st, ribbon, img])
            n += 1
        print(f'finewines {cat} page {page}: {n} new (total {len(rows)})')
        if n == 0 and page > 1:
            break
        time.sleep(0.5)


def main():
    s = requests.Session(); s.headers.update(HEADERS)
    rows, seen = [], set()
    for cat in CATS:
        try:
            scrape_cat(s, cat, rows, seen)
        except Exception as e:
            print(f'finewines {cat}: {e}', file=sys.stderr)
    save_if_sane('fw_all', rows)


if __name__ == '__main__':
    main()
