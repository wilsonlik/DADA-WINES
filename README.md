# DADA WINES

Wine & spirits catalogue (Singapore), rebuilt nightly from three merchant sites.

- `index.html` — the site (generated, do not edit by hand)
- `scripts/site_template.html` — page template; edit this to change design or CONFIG (brand, WhatsApp, free-delivery threshold)
- `scripts/scrape_*.py` — nightly scrapers (Pivene, Crystal Wines, Cornerstone)
- `scripts/merge.py` — normalise, de-duplicate (same wine + vintage + size + pack), keep the higher price
- `scripts/build.py` — template + data -> `index.html` and `data/products_review.csv`
- `.github/workflows/update.yml` — runs every day at 03:00 SGT and pushes the result; also runnable from the Actions tab

Local rebuild: `python scripts/merge.py && python scripts/build.py`
