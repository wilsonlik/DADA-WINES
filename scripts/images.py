"""Download product images, remove circular critic-score badges, resize, and cache them in img/.

Writes data/img_manifest.json  {source_url: {"file": "img/<hash>.jpg", "badge": n_removed}}
Only URLs that are not in the manifest are fetched, so nightly runs touch new products only.
"""
import hashlib, io, json, math, sys, time
from pathlib import Path
import numpy as np
import cv2
import requests
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / 'img'
IMG.mkdir(exist_ok=True)
MANIFEST = ROOT / 'data' / 'img_manifest.json'
MAX_SIDE = 480
HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
           'Accept': 'image/avif,image/webp,image/*,*/*;q=0.8'}


def remove_badges(bgr):
    """Paint over circular critic-score badges (dark disc on the light background) with white.
    Detection: Hough circles, then the disc must be dark inside and surrounded by light background
    on (almost) every side, which a bottle never is. Returns (image, number_of_badges_removed)."""
    h, w = bgr.shape[:2]
    side = min(h, w)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    g = cv2.GaussianBlur(gray, (5, 5), 1.2)
    circles = cv2.HoughCircles(g, cv2.HOUGH_GRADIENT, dp=1.2, minDist=side * 0.15, param1=120, param2=35,
                               minRadius=int(0.05 * side), maxRadius=int(0.25 * side))
    removed = 0
    if circles is None:
        return bgr, 0
    for cx, cy, R in circles[0]:
        cx, cy, R = float(cx), float(cy), float(R)
        inner = np.zeros_like(gray, np.uint8)
        cv2.circle(inner, (int(cx), int(cy)), max(1, int(R * 0.85)), 1, -1)
        if (gray[inner > 0] < 90).mean() < 0.45:      # not a dark disc
            continue
        # the rim of a badge is dark all the way round (a bottle crossing a circle is not)
        rim = np.zeros_like(gray, np.uint8)
        cv2.circle(rim, (int(cx), int(cy)), max(1, int(R * 0.7)), 1, 2)
        if (gray[rim > 0] < 150).mean() < 0.6:
            continue
        # light background all around: check 12 angular sectors of a ring just outside the disc
        ok_sectors = 0
        rr = R + max(10, 0.025 * side)
        for k in range(12):
            a0 = 2 * math.pi * k / 12
            pts = [(int(cx + rr * math.cos(a0 + j * (math.pi / 6) / 8)), int(cy + rr * math.sin(a0 + j * (math.pi / 6) / 8))) for j in range(8)]
            vals = [gray[y, x] for x, y in pts if 0 <= x < w and 0 <= y < h]
            frac = np.mean(np.array(vals) > 195) if vals else 1.0   # off the image edge counts as background
            if frac < 0.6:
                ok_sectors = -99
                break
            if frac >= 0.9:
                ok_sectors += 1
        if ok_sectors < 11:
            continue
        cv2.circle(bgr, (int(round(cx)), int(round(cy))), int(R * 1.2) + 4, (255, 255, 255), -1)
        removed += 1
    return bgr, removed


def process(data, is_cornerstone):
    im = Image.open(io.BytesIO(data)).convert('RGB')
    arr = cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)
    badges = 0
    if is_cornerstone:
        arr, badges = remove_badges(arr)
    h, w = arr.shape[:2]
    scale = MAX_SIDE / max(h, w)
    if scale < 1:
        arr = cv2.resize(arr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode('.jpg', arr, [cv2.IMWRITE_JPEG_QUALITY, 84])
    return buf.tobytes(), badges


def main(limit=None):
    merged = json.load(open(ROOT / 'data' / 'merged.json'))
    manifest = json.load(open(MANIFEST)) if MANIFEST.exists() else {}
    urls = []
    for x in merged:
        for s in x['sources']:
            u = s.get('img') or ''
            if u and u not in manifest and u not in urls:
                urls.append(u)
            if u:
                break  # only the first (preferred) image per product is needed
    print(f'{len(urls)} images to fetch ({len(manifest)} cached)')
    sess = requests.Session(); sess.headers.update(HEADERS)
    done = 0
    for u in urls[:limit]:
        try:
            r = sess.get(u, timeout=60)
            if r.status_code != 200 or not r.content:
                manifest[u] = {'file': None, 'error': r.status_code}
                continue
            out, badges = process(r.content, 'cornerstonewines' in u)
            name = hashlib.md5(u.encode()).hexdigest()[:16] + '.jpg'
            (IMG / name).write_bytes(out)
            manifest[u] = {'file': f'img/{name}', 'badge': badges}
            done += 1
        except Exception as e:
            print(f'  {u}: {e}', file=sys.stderr)
            manifest[u] = {'file': None, 'error': str(e)[:80]}
        if done % 200 == 0 and done:
            json.dump(manifest, open(MANIFEST, 'w'))
            print(f'  {done} done')
        time.sleep(0.15)
    json.dump(manifest, open(MANIFEST, 'w'))
    print(f'fetched {done}; badges removed on {sum(1 for v in manifest.values() if v.get("badge"))} images')


if __name__ == '__main__':
    main(int(sys.argv[1]) if len(sys.argv) > 1 else None)
