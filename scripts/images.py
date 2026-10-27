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


ALGO_VERSION = 4


def _sectors(mask, cx, cy, rr, w, h):
    """Fraction of background pixels in each of 12 angular sectors of a ring of radius rr."""
    out = []
    for k in range(12):
        a0 = 2 * math.pi * k / 12
        vals = []
        for j in range(8):
            a = a0 + j * (math.pi / 6) / 8
            x, y = int(cx + rr * math.cos(a)), int(cy + rr * math.sin(a))
            vals.append(mask[y, x] if 0 <= x < w and 0 <= y < h else 1)
        out.append(float(np.mean(vals)))
    return out


def remove_badges(bgr):
    """Paint over circular critic-score badges (black discs) with white.
    Detection: Hough circles -> dark inside with a dark rim -> surrounded by light background on every
    side. At most 2 sectors may be merely light-ish, and up to 3 may instead touch another badge candidate, so a
    stack of badges is found as a group; a bottle never passes because its body occupies far more of the
    ring than that. Returns (image, number_of_badges_removed)."""
    h, w = bgr.shape[:2]
    side = min(h, w)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    g = cv2.GaussianBlur(gray, (5, 5), 1.2)
    circles = cv2.HoughCircles(g, cv2.HOUGH_GRADIENT, dp=1.2, minDist=side * 0.15, param1=120, param2=35,
                               minRadius=int(0.05 * side), maxRadius=int(0.25 * side))
    if circles is None:
        return bgr, 0
    sat = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)[:, :, 1]
    nonbg = ((gray < 170) | (sat > 80)).astype(np.uint8)
    light = (gray > 195).astype(np.uint8)
    removed = 0
    cands = []
    for cx, cy, R in circles[0]:
        cx, cy, R = float(cx), float(cy), float(R)
        if cx > 0.42 * w:          # this merchant always places badges and medals in the left margin
            continue
        inner = np.zeros_like(gray, np.uint8)
        cv2.circle(inner, (int(cx), int(cy)), max(1, int(R * 0.85)), 1, -1)
        dark = (gray[inner > 0] < 90).mean()
        if dark < 0.45:
            # coloured award medal: a solid non-white disc completely surrounded by background
            rim = np.zeros_like(gray, np.uint8)
            cv2.circle(rim, (int(cx), int(cy)), max(1, int(R * 0.7)), 1, 2)
            if nonbg[inner > 0].mean() >= 0.7 and nonbg[rim > 0].mean() >= 0.6 and R >= 0.07 * side:
                if min(_sectors(light, cx, cy, R + max(10, 0.025 * side), w, h)) >= 0.9:
                    cv2.circle(bgr, (int(round(cx)), int(round(cy))), int(R * 1.2) + 4, (255, 255, 255), -1)
                    removed += 1
            continue
        rim = np.zeros_like(gray, np.uint8)
        cv2.circle(rim, (int(cx), int(cy)), max(1, int(R * 0.7)), 1, 2)
        if (gray[rim > 0] < 150).mean() < 0.45:
            continue
        # a score badge carries big light digits in its centre; a dark bottle body does not
        core = np.zeros_like(gray, np.uint8)
        cv2.circle(core, (int(cx), int(cy)), max(1, int(R * 0.6)), 1, -1)
        bright = (gray[core > 0] > 150).mean()
        if not 0.15 <= bright <= 0.8:
            continue
        cands.append((cx, cy, R, dark))
    if not cands:
        return bgr, removed
    plain = [_sectors(light, cx, cy, R + max(10, 0.025 * side), w, h) for cx, cy, R, _ in cands]
    # a candidate may cover a neighbour's sectors (stacked badges) only if it is itself mostly surrounded by background
    strong = [i for i, s in enumerate(plain) if sum(1 for f in s if f >= 0.9) >= 8]
    for i, (cx, cy, R, dark) in enumerate(cands):
        rr = R + max(10, 0.025 * side)
        masked_bg = light.copy()
        for j in strong:
            if j != i:
                ox, oy, oR, _ = cands[j]
                cv2.circle(masked_bg, (int(ox), int(oy)), int(oR * 1.25) + 6, 1, -1)
        masked = _sectors(masked_bg, cx, cy, rr, w, h)
        if min(masked) < 0.6:
            continue
        good = sum(1 for f in plain[i] if f >= 0.9)
        rescued = sum(1 for a, b in zip(plain[i], masked) if a < 0.9 <= b)
        if good + rescued < 10 or rescued > 4:
            continue
        cv2.circle(bgr, (int(round(cx)), int(round(cy))), int(R * 1.2) + 4, (255, 255, 255), -1)
        removed += 1
    return bgr, removed


def process(data, is_cornerstone):
    im = Image.open(io.BytesIO(data)).convert('RGB')
    arr = cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)
    h, w = arr.shape[:2]
    scale = MAX_SIDE / max(h, w)
    if scale < 1:
        arr = cv2.resize(arr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    badges = 0
    if is_cornerstone:
        arr, badges = remove_badges(arr)   # detection always runs at the same scale as the stored image
    ok, buf = cv2.imencode('.jpg', arr, [cv2.IMWRITE_JPEG_QUALITY, 84])
    return buf.tobytes(), badges


def main(limit=None):
    merged = json.load(open(ROOT / 'data' / 'merged.json'))
    manifest = json.load(open(MANIFEST)) if MANIFEST.exists() else {}
    urls = []
    for x in merged:
        for s in x['sources']:
            u = s.get('img') or ''
            stale = u in manifest and 'cornerstonewines' in u and manifest[u].get('v') != ALGO_VERSION
            if u and (u not in manifest or stale) and u not in urls:
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
            manifest[u] = {'file': f'img/{name}', 'badge': badges, 'v': ALGO_VERSION}
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
