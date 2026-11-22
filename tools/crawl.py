#!/usr/bin/env python3
"""Crawl fishermenpants.com and emit a crawl bundle into _crawl/.

Phase A: fetch pages (home, collections, products, static pages) with 429 backoff.
Phase B: download all referenced CDN images locally.
Phase C: parse everything and emit:
  - content/products/<handle>.md
  - content/collections/<handle>.md
  - data/home.json  (homepage layout data: banners, featured products, tiles, testimonials, video)
  - static/img/...  (all images, local)
  - _crawl/manifest.json

Run: python3 tools/crawl.py [--force]
"""
import json, os, re, sys, time, html as htmllib
import urllib.request, urllib.error
import hashlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://www.fishermenpants.com"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
HTML_DIR = os.path.join(ROOT, "_crawl", "html")
IMG_DIR = os.path.join(ROOT, "static", "img")
COLLECTIONS = ["all", "new-arrivals", "shop-for-her", "fisherman-pants",
               "island-shirts", "sarongs", "scarves", "bags", "jewelry", "accessories-1"]
STATIC_PAGES = {"/payment-methods": "payment-methods",
                "/policies/privacy-policy": "privacy-policy"}
FORCE = "--force" in sys.argv

def log(msg):
    print(time.strftime("[%H:%M:%S] ") + msg, flush=True)

def get(url, binary=False):
    """GET with 429 backoff. Returns bytes or None after max attempts."""
    waits = [20, 45, 90, 180, 300, 300, 300, 600]
    for i, wait in enumerate([0] + waits):
        if wait:
            log(f"  waiting {wait}s for rate limit (attempt {i + 1})")
            time.sleep(wait)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA,
                                                       "Accept": "*/*",
                                                       "Accept-Language": "en-US,en;q=0.9"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            if data.startswith(b"local_rate_limited"):
                continue
            return data
        except urllib.error.HTTPError as e:
            if e.code == 429:
                try:
                    body = e.read()[:60]
                except Exception:
                    body = b""
                log(f"  HTTP 429: {body!r}")
                continue
            if e.code == 404:
                raise
            log(f"  HTTP {e.code} for {url}")
        except Exception as e:
            log(f"  error: {e}")
    raise RuntimeError(f"gave up on {url}")

def get_page(path):
    return get(BASE + path).decode("utf-8", "replace")

def fetch_pages():
    os.makedirs(HTML_DIR, exist_ok=True)
    targets = {"/": "home"}
    for c in COLLECTIONS:
        targets[f"/collections/{c}"] = f"collection-{c}"
    # discover products from /collections/all
    all_html_path = os.path.join(HTML_DIR, "collection-all.html")
    if FORCE or not os.path.exists(all_html_path) or os.path.getsize(all_html_path) < 1000:
        h = get_page("/collections/all")
        open(all_html_path, "w").write(h)
        time.sleep(3)
    else:
        h = open(all_html_path).read()
        log("skipped collection/all (cached)")
    handles = sorted(set(re.findall(r'href="/products/([a-z0-9\-]+)"', h)))
    log(f"found {len(handles)} products in collection/all")
    for pth, name in STATIC_PAGES.items():
        targets[pth] = f"page-{name}"
    targets.update({f"/products/{h}": f"product-{h}" for h in handles})
    # fetch remaining collection pages
    for c in COLLECTIONS:
        fp = os.path.join(HTML_DIR, f"collection-{c}.html")
        if c != "all" and (FORCE or not os.path.exists(fp) or os.path.getsize(fp) < 1000):
            time.sleep(2.5)
            open(fp, "w").write(get_page(f"/collections/{c}"))
            log(f"fetched collection {c}")
    for path, name in targets.items():
        fp = os.path.join(HTML_DIR, f"{name}.html")
        if os.path.exists(fp) and os.path.getsize(fp) > 1000 and not FORCE:
            continue
        time.sleep(2.5)
        h = get_page(path)
        open(fp, "w").write(h)
        log(f"fetched {path} -> {name}.html ({len(h)}b)")
    return handles

def product_handles_from(html):
    return sorted(set(re.findall(r'href="/products/([a-z0-9\-]+)"', html)))

def cdn_urls_from(html):
    urls = set()
    for m in re.findall(r'//www\.fishermenpants\.com/(cdn/[^"\')\s?]+\.(?:jpg|jpeg|png|webp|avif|mp4|webm))', html):
        urls.add(m)
    return sorted(urls)

def dl_image(url_path):
    """url_path like cdn/shop/files/foo.png -> local file; returns (local_name, url)."""
    m = re.match(r'cdn/(shop|collections)/(.+)$', url_path)
    sub = m.group(2)
    name = os.path.basename(url_path.split("?")[0])
    h = hashlib.md5(url_path.encode()).hexdigest()[:6]
    ext = os.path.splitext(name)[1].lower() or ".jpg"
    local = f"{h}_{name}"
    dst = os.path.join(IMG_DIR, local)
    if os.path.exists(dst) and os.path.getsize(dst) > 100:
        return local, dst
    src = f"{BASE}/{url_path}"
    if ext in (".jpg", ".jpeg", ".png", ".webp"):
        src += ("&" if "?" in url_path else "?") + "width=1600"
    time.sleep(1.2)
    try:
        data = get(src)
    except RuntimeError:
        log(f"  ! failed image {url_path}")
        return None, None
    open(dst, "wb").write(data)
    return local, dst

def parse_product(fp):
    h = open(fp).read()
    title = htmllib.unescape(re.search(r'<h1[^>]*itemprop="name"[^>]*>(.*?)</h1>', h, re.S).group(1)).strip() if re.search(r'<h1[^>]*itemprop="name"', h) else os.path.basename(fp)
    prod = {"handle": os.path.basename(fp).replace("product-", "").replace(".html", "")}
    # embedded product JSON (OS 2.0 theme)
    pj = None
    for m in re.finditer(r'<script[^>]*id="ProductJson[^"]*"[^>]*>(.*?)</script>', h, re.S):
        try:
            d = json.loads(m.group(1).strip())
            if isinstance(d, dict) and "variants" in d:
                pj = d
                break
        except Exception:
            pass
    if pj is None:
        # fallback: any application/json with variants
        for m in re.finditer(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', h, re.S):
            try:
                d = json.loads(m.group(1).strip())
            except Exception:
                continue
            if isinstance(d, dict) and "variants" in d:
                pj = d
                break
    desc = ""
    dm = re.search(r'class="[^"]*product-(?:single|main)__description[^"]*"[^>]*>(.*?)</div>', h, re.S)
    if dm:
        desc = dm.group(1).strip()
    price_min, price_max, compare_min, compare_max = None, None, None, None
    variants = []
    images = []
    options = []
    if pj:
        price_min = pj.get("price_min"); price_max = pj.get("price_max")
        options = pj.get("options", [])
        for v in pj.get("variants", []):
            variants.append({
                "id": v.get("id"), "title": v.get("title"),
                "price": v.get("price"), "sku": v.get("sku"),
                "available": v.get("available", True),
            })
        for im in pj.get("images", []):
            images.append(im.get("src"))
    else:
        prices = [x / 100.0 for x in re.findall(r'data-price="(\d+)"', h)]
        if prices:
            price_min, price_max = min(prices), max(prices)
        for im in re.findall(r'src="(//www\.fishermenpants\.com/cdn/[^"\s?]+\.(?:jpg|png|webp))', h):
            if im not in images:
                images.append("https:" + im)
        variants = [{"id": 0, "title": title, "price": price_min, "sku": "", "available": True}] if price_min else []
    prod.update({"title": title, "description": desc,
                 "price_min": price_min, "price_max": price_max,
                 "variants": variants, "images": images, "options": options,
                 "compare_at_min": None})
    cm = re.search(r'compare_at_price(?:_max)?["\']?\s*[:=]\s*"?([0-9]+(?:\.[0-9]+)?)', h)
    return prod, h

def main():
    handles = fetch_pages()
    # Phase B: images
    manifest = {}
    for f in sorted(os.listdir(HTML_DIR)):
        if not f.endswith(".html"):
            continue
        h = open(os.path.join(HTML_DIR, f)).read()
        for u in cdn_urls_from(h):
            if u in manifest:
                continue
            local, dst = dl_image(u)
            if dst:
                manifest[u] = local
    # Phase C: parse products
    prods = []
    for hnd in handles:
        fp = os.path.join(HTML_DIR, f"product-{hnd}.html")
        if not os.path.exists(fp):
            continue
        prod, ph = parse_product(fp)
        prods.append(prod)
        log(f"parsed {hnd}: {len(prod['variants'])} variants, {len(prod['images'])} images")
    # collection membership + meta
    cols = {}
    for c in COLLECTIONS:
        fp = os.path.join(HTML_DIR, f"collection-{c}.html")
        if not os.path.exists(fp):
            continue
        ch = open(fp).read()
        cols[c] = {
            "handles": product_handles_from(ch),
            "title": htmllib.unescape(re.search(r'<h1[^>]*>([^<]+)</h1>', ch).group(1)).strip() if re.search(r'<h1[^>]*>([^<]+)</h1>', ch) else c.replace("-", " ").title(),
        }
    json.dump({"products": prods, "collections": cols},
              open(os.path.join(ROOT, "_crawl", "parsed.json"), "w"), indent=1)
    log("DONE crawl -> _crawl/parsed.json")

if __name__ == "__main__":
    main()
