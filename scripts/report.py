"""Daily change report: data/merged_prev.json (yesterday) vs data/merged.json (today)
-> reports/YYYY-MM-DD.md, reports/latest.md, reports/latest.json"""
import json, re, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / 'reports'
REPORTS.mkdir(exist_ok=True)
SGT = timezone(timedelta(hours=8))
now = datetime.now(SGT)
today = now.strftime('%Y-%m-%d')

new = json.load(open(ROOT / 'data' / 'merged.json'))
prev_path = ROOT / 'data' / 'merged_prev.json'
prev = json.load(open(prev_path)) if prev_path.exists() else []
status_path = ROOT / 'data' / 'raw' / 'status.json'
status = json.load(open(status_path)) if status_path.exists() else {}
manifest_path = ROOT / 'data' / 'img_manifest.json'
manifest = json.load(open(manifest_path)) if manifest_path.exists() else {}

ST = {2: '有货', 1: '限量/询价', 0: '售罄'}
SITE = {'pivene': 'Pivene', 'crystal': 'Crystal', 'cornerstone': 'Cornerstone'}
LIMIT = 40


def sgd(p):
    return f'S${p:,.0f}' if p is not None else '询价'


def label(x):
    v = x['vintage'] if x['vintage'] and x['vintage'] != 'NV' else 'NV'
    size = f"{x['size']/1000:g} L" if x['size'] >= 1000 else f"{x['size']} ml"
    extra = '' if x['size'] == 750 else f' · {size}'
    return f"{x['name']}{extra}"


# identity across runs: any shared source URL
prev_by_url = {}
for x in prev:
    for s in x['sources']:
        prev_by_url[s['url']] = x
matched_prev = set()
added, price_up, price_down, stock_changes, rating_added, src_changes = [], [], [], [], [], []
for x in new:
    p = next((prev_by_url[s['url']] for s in x['sources'] if s['url'] in prev_by_url), None)
    if p is None:
        added.append(x)
        continue
    matched_prev.add(id(p))
    if x['price'] != p['price'] and x['price'] is not None and p['price'] is not None:
        d = (x['price'] - p['price']) / p['price'] * 100
        (price_up if d > 0 else price_down).append((x, p['price'], x['price'], d))
    elif x['price'] != p['price']:
        src_changes.append((x, f"价格 {sgd(p['price'])} → {sgd(x['price'])}"))
    if x['stock'] != p['stock']:
        stock_changes.append((x, p['stock'], x['stock']))
    if x['rating'] and not p['rating']:
        rating_added.append(x)
    ns, ps = {s['site'] for s in x['sources']}, {s['site'] for s in p['sources']}
    if ns != ps:
        src_changes.append((x, f"来源 {'+'.join(SITE[s] for s in sorted(ps))} → {'+'.join(SITE[s] for s in sorted(ns))}"))
removed = [x for x in prev if id(x) not in matched_prev]

by_site_new = {k: sum(1 for x in new for s in x['sources'] if s['site'] == k) for k in SITE}
by_site_prev = {k: sum(1 for x in prev for s in x['sources'] if s['site'] == k) for k in SITE}
imgs_today = [v for v in manifest.values() if v.get('file')]
out_now = sum(1 for x in new if x['stock'] == 0)

L = []
L.append(f"# DADA WINES 每日更新报告 — {today}")
L.append(f"更新时间 {now.strftime('%Y-%m-%d %H:%M')} (新加坡时间)")
L.append('')
L.append('## 概览')
L.append(f"- 产品总数：{len(prev):,} → **{len(new):,}**（{len(new)-len(prev):+d}）" if prev else f"- 产品总数：**{len(new):,}**（首次报告，无对比）")
L.append(f"- 新上架 {len(added)}，下架 {len(removed)}，涨价 {len(price_up)}，降价 {len(price_down)}，库存变动 {len(stock_changes)}，新增评分 {len(rating_added)}")
L.append(f"- 目前售罄 {out_now}，限量/询价 {sum(1 for x in new if x['stock'] == 1)}，有货 {sum(1 for x in new if x['stock'] == 2)}")
L.append('')
L.append('## 来源站抓取状态')
for key, name in [('pivene_all', 'Pivene'), ('cw_all', 'Crystal Wines'), ('cs_all', 'Cornerstone')]:
    s = status.get(key)
    if not s:
        L.append(f"- {name}：无记录")
        continue
    fresh = s['ts'][:10] == datetime.now(timezone.utc).strftime('%Y-%m-%d')
    if s['ok'] and fresh:
        L.append(f"- {name}：✅ 成功，{s['rows']:,} 条（上次 {s['previous']:,}）")
    elif not fresh:
        L.append(f"- {name}：⚠️ 今天没有新抓取（沿用 {s['ts'][:10]} 的数据，{s['rows']:,} 条）")
    else:
        L.append(f"- {name}：❌ 抓取异常，只拿到 {s['rows']:,} 条（上次 {s['previous']:,}），已沿用旧数据")
L.append('')


def section(title, rows, fmt):
    L.append(f'## {title}（{len(rows)}）')
    if not rows:
        L.append('- 无')
    for r in rows[:LIMIT]:
        L.append('- ' + fmt(r))
    if len(rows) > LIMIT:
        L.append(f'- …另有 {len(rows)-LIMIT} 条，见 latest.json')
    L.append('')


section('新上架', sorted(added, key=lambda x: -(x['price'] or 0)),
        lambda x: f"{label(x)} — {sgd(x['price'])} · {ST[x['stock']]} · {'/'.join(SITE[s['site']] for s in x['sources'])}")
section('下架', sorted(removed, key=lambda x: -(x['price'] or 0)),
        lambda x: f"{label(x)} — 原价 {sgd(x['price'])} · {'/'.join(SITE[s['site']] for s in x['sources'])}")
section('涨价', sorted(price_up, key=lambda r: -abs(r[3])),
        lambda r: f"{label(r[0])}：{sgd(r[1])} → **{sgd(r[2])}**（{r[3]:+.0f}%）")
section('降价', sorted(price_down, key=lambda r: -abs(r[3])),
        lambda r: f"{label(r[0])}：{sgd(r[1])} → **{sgd(r[2])}**（{r[3]:+.0f}%）")
section('库存变动', sorted(stock_changes, key=lambda r: (r[2], -(r[0]['price'] or 0))),
        lambda r: f"{label(r[0])}：{ST[r[1]]} → **{ST[r[2]]}**")
section('新增评分', rating_added, lambda x: f"{label(x)}：{x['rating']}")
section('其他变动', src_changes, lambda r: f"{label(r[0])}：{r[1]}")

L.append('## 图片')
L.append(f"- 图库共 {len(imgs_today):,} 张，其中已去除评分标 {sum(1 for v in imgs_today if v.get('badge')):,} 张")
L.append('')
L.append('来源数量：' + '，'.join(f"{SITE[k]} {by_site_prev.get(k, 0):,}→{by_site_new[k]:,}" for k in SITE))

md = '\n'.join(L)
(REPORTS / f'{today}.md').write_text(md, encoding='utf-8')
(REPORTS / 'latest.md').write_text(md, encoding='utf-8')
json.dump({
    'date': today, 'total': len(new), 'total_prev': len(prev),
    'added': [dict(name=label(x), price=x['price'], stock=ST[x['stock']], sources=[s['site'] for s in x['sources']]) for x in added],
    'removed': [dict(name=label(x), price=x['price'], sources=[s['site'] for s in x['sources']]) for x in removed],
    'price_up': [dict(name=label(x), old=a, new=b, pct=round(d, 1)) for x, a, b, d in price_up],
    'price_down': [dict(name=label(x), old=a, new=b, pct=round(d, 1)) for x, a, b, d in price_down],
    'stock_changes': [dict(name=label(x), old=ST[a], new=ST[b]) for x, a, b in stock_changes],
    'rating_added': [dict(name=label(x), rating=x['rating']) for x in rating_added],
    'other': [dict(name=label(x), change=c) for x, c in src_changes],
    'status': status,
}, open(REPORTS / 'latest.json', 'w'), ensure_ascii=False, indent=1)
print(f'report: +{len(added)} -{len(removed)} price↑{len(price_up)} ↓{len(price_down)} stock {len(stock_changes)}')
