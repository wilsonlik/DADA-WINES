"""Vinum Fine Wines Singapore -> data/raw/vinum_all.json
Their SG price list is a public Google Sheet linked from vinumfinewines.sg ("Price List XLS").
Row: [category, vintage, wine, format, qty, unit_price_incl_gst]"""
import csv, io, re, time, requests
from common import HEADERS, save_if_sane, get_json

SHEET = 'https://docs.google.com/spreadsheets/d/1gFUTC4wsKGWOpvnUusp5XHwf7MN3gLOb/export?format=csv'


def parse(text):
    rows = list(csv.reader(io.StringIO(text)))
    starts = [i for i, r in enumerate(rows) if r and r[0].strip() == 'Vintage']
    if not starts:
        return []
    out, cat = [], ''
    for r in rows[starts[0] + 1:]:
        r = [c.strip() for c in r] + [''] * 6
        if not r[1]:
            continue
        if not r[0] and not r[2] and not r[4]:
            cat = r[1]
            continue
        price = re.sub(r'[^\d.]', '', r[5]) or re.sub(r'[^\d.]', '', r[4])
        out.append([cat, r[0], r[1], r[2], r[3], float(price) if price else None])
    return out


UK_STORE = 'https://vinumfinewines.com/wp-json/wc/store/v1/products?per_page=100&_fields=name,images&page={}'
UK_CDN = 'https://vinumfinewinescom-21644.kxcdn.com/wp-content/uploads/'


def uk_images(s):
    """[name_without_format, image_path] from the UK shop, used only for bottle photos."""
    out, seen = [], set()
    for page in range(1, 60):
        r = get_json(s, UK_STORE.format(page), tries=2)
        if r is None:
            break
        j = r.json()
        if not isinstance(j, list) or not j:
            break
        for x in j:
            img = (x.get('images') or [{}])[0].get('src') or ''
            name = re.sub(r'\s+\d+x\d+cl$', '', x.get('name', ''))
            if img and name not in seen:
                seen.add(name)
                out.append([name, img.replace(UK_CDN, '')])
        if len(j) < 100:
            break
        time.sleep(0.3)
    return out


def main():
    s = requests.Session(); s.headers.update(HEADERS)
    r = get_json(s, SHEET, allow_redirects=True)
    if r is None:
        raise SystemExit('vinum: could not download price list')
    rows = parse(r.content.decode('utf-8-sig', errors='replace'))
    print(f'vinum: {len(rows)} rows')
    save_if_sane('vinum_all', rows)
    try:
        imgs = uk_images(s)
        print(f'vinum uk images: {len(imgs)}')
        if imgs:
            save_if_sane('vinum_uk_images', imgs, min_ratio=0.5)
    except SystemExit:
        raise
    except Exception as e:
        print('vinum uk images failed:', e)


if __name__ == '__main__':
    main()
