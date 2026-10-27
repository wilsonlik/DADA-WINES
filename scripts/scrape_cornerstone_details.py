"""Cornerstone product detail pages -> data/cs_details.json
{href: {rating, country, region, type, vintage, appellation, alc, ts}}
Pages are server-rendered, so plain requests are enough. Entries are cached and refreshed every 30 days."""
import json, re, sys, time, html
from datetime import date
import requests
from common import HEADERS, RAW, ROOT, get_json

BASE = 'https://shop.cornerstonewines.com'
OUT = ROOT / 'data' / 'cs_details.json'
LABELS = ['Country', 'Region', 'Type', 'Alc. Volume', 'Vintage', 'Packaging', 'Appellation', 'Varietal', 'Producer']
STOP = '|'.join(re.escape(l) for l in LABELS) + r'|Tasting Notes|Ratings|CORPORATE INFORMATION|Features'


def parse(page_html):
    txt = re.sub(r'<script[\s\S]*?</script>|<style[\s\S]*?</style>', ' ', page_html)
    m = re.search(r'<h3>\s*Ratings\s*</h3>\s*<p[^>]*>(.*?)</p>', txt, re.S)
    rating = html.unescape(re.sub(r'<[^>]+>', ' ', m.group(1))).strip() if m else ''
    rating = re.sub(r'\s+', ' ', rating)
    text = html.unescape(re.sub(r'<[^>]+>', ' ', txt))
    text = re.sub(r'\s+', ' ', text)
    out = {'rating': rating}
    for lab in LABELS:
        m = re.search(re.escape(lab) + r'\s*:\s*(.+?)\s*(?=(?:' + STOP + r')\s*:?|$)', text)
        val = m.group(1).strip() if m else ''
        if len(val) > 80:
            val = ''
        out[lab.lower().replace('. ', '_').replace(' ', '_')] = val
    return out


def main():
    rows = json.load(open(RAW / 'cs_all.json'))
    hrefs = []
    for r in rows:
        if r[3] and r[3] not in hrefs:
            hrefs.append(r[3])
    cache = json.load(open(OUT)) if OUT.exists() else {}
    today = date.today()
    todo = [h for h in hrefs if h not in cache or (today - date.fromisoformat(cache[h].get('ts', '2000-01-01'))).days > 30]
    print(f'cornerstone details: {len(hrefs)} products, {len(todo)} to fetch')
    s = requests.Session(); s.headers.update(HEADERS)
    n = 0
    for h in todo:
        r = get_json(s, BASE + h, tries=2)
        if r is None:
            continue
        d = parse(r.text)
        d['ts'] = today.isoformat()
        cache[h] = d
        n += 1
        if n % 100 == 0:
            json.dump(cache, open(OUT, 'w'), ensure_ascii=False)
            print(f'  {n}/{len(todo)}')
        time.sleep(0.3)
    json.dump(cache, open(OUT, 'w'), ensure_ascii=False)
    with_rating = sum(1 for h in hrefs if cache.get(h, {}).get('rating'))
    print(f'done: {n} fetched, {with_rating} of {len(hrefs)} have ratings')


if __name__ == '__main__':
    main()
