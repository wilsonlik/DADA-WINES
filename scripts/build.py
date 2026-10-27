"""data/merged.json + scripts/site_template.html -> index.html, data/products_review.csv"""
import json, re, csv, collections
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
m = json.load(open(ROOT / 'data' / 'merged.json'))

SGT = timezone(timedelta(hours=8))
today = datetime.now(SGT).strftime('%-d %b %Y')


MANIFEST = ROOT / 'data' / 'img_manifest.json'
manifest = json.load(open(MANIFEST)) if MANIFEST.exists() else {}


def pick_img(x):
    """Local processed copy when we have one; otherwise the source image."""
    for s in x['sources']:
        u = s.get('img') or ''
        if not u:
            continue
        loc = (manifest.get(u) or {}).get('file')
        if loc and (ROOT / loc).exists():
            return loc
        if 'cdn.shopify.com' in u:
            u = u.split('?')[0] + '?width=480'
        return u
    return ''


CRITICS = {'RP': 'Robert Parker', 'WA': 'Wine Advocate', 'JS': 'James Suckling', 'WS': 'Wine Spectator', 'JH': 'James Halliday',
           'AG': 'Antonio Galloni', 'JD': 'Jeb Dunnuck', 'D': 'Decanter', 'DEC': 'Decanter', 'WE': 'Wine Enthusiast', 'BH': 'Burghound',
           'NM': 'Neal Martin', 'TA': 'Tim Atkin', 'JR': 'Jancis Robinson', 'V': 'Vinous', 'VM': 'Vinous', 'LM': 'Luca Maroni',
           'GR': 'Gambero Rosso', 'F': 'Falstaff', 'JL': 'Jeannie Cho Lee', 'LPB': 'Le Point', 'RVF': 'RVF', 'CT': 'CellarTracker',
           'WW': 'Wine & Spirits', 'JG': 'John Gilman', 'WK': 'Wine Kritik', 'HALLIDAY': 'James Halliday', 'TWI': 'The Wine Independent',
           'TRR': 'The Real Review', 'BC': 'Bob Campbell', 'RH': 'Richard Hemming', 'YC': 'Yves Beck', 'YB': 'Yves Beck'}


def ratings_of(raw):
    """'RP97 / JS96', 'Robert Parker-93', 'JS 95-96' -> 'Robert Parker 97 · James Suckling 96'"""
    if not raw:
        return ''
    out = []
    for part in re.split(r'[/|,;]+', raw):
        m = re.match(r'\s*([A-Za-z&.\' ]+?)[\s\-:]*(\d{2,3}(?:\s*-\s*\d{2,3})?\+?)\s*(?:pts|points)?\s*$', part.strip(), re.I)
        if not m:
            continue
        critic, score = m.group(1).strip(' .-'), m.group(2).replace(' ', '')
        name = CRITICS.get(critic.upper().replace('.', ''), critic.title() if critic.isupper() and len(critic) > 4 else critic)
        out.append(f'{name} {score}')
    return ' · '.join(out)



pub = [{'i': x['id'], 'n': x['name'], 't': x['type'], 'c': x['country'], 'r': x['region'], 'v': x['vintage'],
        's': x['size'], 'k': x['pack'], 'p': x['price'], 'cp': x['compare'], 'st': x['stock'], 'rt': ratings_of(x['rating']),
        'im': pick_img(x)} for x in m]
data = json.dumps(pub, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')

tpl = open(ROOT / 'scripts' / 'site_template.html', encoding='utf-8').read()
assert '/*__DATA__*/' in tpl
page = tpl.replace('/*__DATA__*/', data)
page = re.sub(r'<span id="updated">[^<]*</span>', f'<span id="updated">{today}</span>', page)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
       '<meta name="description" content="DADA WINES — fine wine, sake and spirits in Singapore. Browse the full list, '
       'filter by region, vintage and price, and send us your enquiry.">\n'
       '<style>img{max-width:100%}[hidden]{display:none!important}</style>\n</head>\n<body>\n' + page + '\n</body>\n</html>\n')
open(ROOT / 'index.html', 'w', encoding='utf-8').write(doc)

ST = {2: 'in stock', 1: 'limited / enquire', 0: 'out of stock'}
with open(ROOT / 'data' / 'products_review.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['id', 'name', 'type', 'country', 'region', 'vintage', 'size_ml', 'pack', 'price_sgd', 'compare_price',
                'stock_status', 'rating', 'n_sources', 'pivene_price', 'pivene_stock', 'crystal_price', 'crystal_stock',
                'cornerstone_price', 'cornerstone_stock', 'pivene_url', 'crystal_url', 'cornerstone_url'])
    for x in m:
        sp = {s['site']: s for s in x['sources']}
        g = lambda k, f: (sp[k][f] if k in sp else '')
        gs = lambda k: (ST[sp[k]['stock']] if k in sp else '')
        w.writerow([x['id'], x['name'], x['type'], x['country'], x['region'], x['vintage'], x['size'], x['pack'],
                    x['price'] if x['price'] is not None else '', x['compare'] or '', ST[x['stock']], x['rating'],
                    len(x['sources']), g('pivene', 'price'), gs('pivene'), g('crystal', 'price'), gs('crystal'),
                    g('cornerstone', 'price'), gs('cornerstone'), g('pivene', 'url'), g('crystal', 'url'), g('cornerstone', 'url')])

print(f'built index.html: {len(pub)} products, updated {today};',
      collections.Counter(ST[p["st"]] for p in pub))
