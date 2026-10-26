"""Cornerstone Wines SG -> data/raw/cs_all.json and data/raw/cs_types.json
The listing is rendered client-side, so a headless browser visits the category pages
exactly like a shopper would (24 items per page).
Row: [category, page, title, href, list_price, offer_price, off_badge, stock_text, buy|enquire, image]
Type row: [category/type, title, href]"""
import re, sys, time
from playwright.sync_api import sync_playwright
from common import UA, save_if_sane

BASE = 'https://shop.cornerstonewines.com/sg'
CATS = {'france': 'france/all-france', 'italy': 'italy/all-italian', 'spain': 'spain/all-spanish',
        'germany': 'germany/all-german', 'chile': 'chile/all-chilean', 'us': 'us/all-american',
        'australia': 'australia/all-australian', 'new-zealand': 'new-zealand/all-new-zealand',
        'spirits': 'spirits/all-spirits'}
TYPE_PAGES = {'france/white': 'france/white', 'france/sweet': 'france/dessert-sweet', 'france/champagne': 'france/champagne',
              'italy/white': 'italy/white', 'italy/sparkling': 'italy/sparkling', 'italy/sweet': 'italy/sweet',
              'spain/white': 'spain/white', 'spain/sparkling': 'spain/sparkling', 'spain/sweet': 'spain/sweet',
              'germany/white': 'germany/white', 'australia/white': 'australia/white',
              'new-zealand/white': 'new-zealand/white', 'new-zealand/sparkling': 'new-zealand/sparkling',
              'chile/white': 'chile/white'}

EXTRACT = """() => {
  const num = s => s ? parseFloat(s.replace(/[^\\d.]/g, '')) : null;
  const rows = [];
  for (const b of document.querySelectorAll('.listBox')) {
    const a = b.querySelector('a.listImg'), h = b.querySelector('h4');
    const pp = b.querySelector('.price_product'), op = b.querySelector('.offer_price');
    const off = b.querySelector('.offBox'), stock = b.querySelector('.offShowG'), btn = b.querySelector('.enqBtn');
    rows.push([h ? h.textContent.trim() : '', a ? a.getAttribute('href') : '', num(pp ? pp.textContent : ''),
               num(op ? op.textContent : ''), off ? off.textContent.trim() : '', stock ? stock.textContent.trim() : '',
               btn ? 'enquire' : 'buy', a && a.querySelector('img') ? a.querySelector('img').getAttribute('src') : '']);
  }
  const m = document.body.innerText.match(/Showing \\d+ to \\d+ of ([\\d,]+)/);
  return {rows, total: m ? parseInt(m[1].replace(/,/g, '')) : null};
}"""


def load_page(page, url):
    for attempt in range(3):
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=60000)
            try:
                page.wait_for_selector('.listBox', timeout=25000)
            except Exception:
                pass  # empty category or slow; extract whatever is there
            time.sleep(0.8)
            return page.evaluate(EXTRACT)
        except Exception as e:
            print(f'  retry {attempt+1} for {url}: {e}', file=sys.stderr)
            time.sleep(5)
    return {'rows': [], 'total': None}


def crawl(page, slug, label, rows_out, with_meta=True):
    first = load_page(page, f'{BASE}/{slug}')
    total = first['total'] or len(first['rows'])
    pages = max(1, -(-total // 24))
    print(f'{label}: {total} items, {pages} pages')
    def add(res, n):
        for r in res['rows']:
            rows_out.append([label, n] + r if with_meta else [label, r[0], r[1]])
    add(first, 1)
    for n in range(2, pages + 1):
        res = load_page(page, f'{BASE}/{slug}/page/{n}')
        if not res['rows']:
            print(f'  page {n} empty, stopping', file=sys.stderr)
            break
        add(res, n)
        time.sleep(0.5)


def main():
    rows, types = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(user_agent=UA, viewport={'width': 1280, 'height': 900})
        page = ctx.new_page()
        page.route(re.compile(r'\.(png|jpg|jpeg|gif|webp|woff2?|svg)(\?.*)?$'), lambda route: route.abort())
        for label, slug in CATS.items():
            crawl(page, slug, label, rows, with_meta=True)
        for label, slug in TYPE_PAGES.items():
            crawl(page, slug, label, types, with_meta=False)
        browser.close()
    save_if_sane('cs_all', rows)
    if types:
        save_if_sane('cs_types', types, min_ratio=0.3)


if __name__ == '__main__':
    main()
