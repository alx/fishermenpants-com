#!/usr/bin/env python3
"""Paced crawler for fishermenpants.com (respects Retry-After on 429).

Phase A: fetch home, collections, products, static pages (from sitemap URL list).
Phase B: download every referenced CDN image locally (CDN is not throttled).
Phase C: parse into _crawl/parsed.json (see build_content.py for Hugo emit).
"""
import json, os, re, sys, time, html as H
import urllib.request, urllib.error
import email

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://www.fishermenpants.com"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
HTML_DIR = os.path.join(ROOT, "_crawl", "html")
IMG_DIR = os.path.join(ROOT, "static", "img")
PACE = 30          # seconds between page fetches
MAX_RETRY = 8      # retries per URL on 429

COLLECTIONS = ["all-products", "fisherman-pants", "island-shirts", "shop-for-her",
               "new-arrivals", "best-sellers", "scarves", "accessories-1",
               "bags", "sarongs", "jewelry"]
PAGES = ["contact", "payment-methods", "data-sharing-opt-out", "shipping-information"]

PRODUCTS = ["kimono-samui-slim-sleeves","dragon-wrap-pants","hemp-ethnic-pants",
            "cotton-linen-vintage-kimono-women","ancient-pattern-lines-pants",
            "kimono-thailand-organic-tie-dye","kimono-samui-wide-sleeves",
            "hill-tribe-bag","stonewash-fisherman-pants","pants-with-handmade-embroidery",
            "lines","zoo-dress","handmade-painted-indigo-pants","mudmee-old-silk-thai-pants",
            "hi-low","tai-chi-pants","fishermans-island-shirt","natural-bags-from-rubber-tree",
            "organic-tye-dye-fisherman-pants","yacht-collection-waffle-pants",
            "handmade-cotton-fishermen-pants-with-embroidery","indigo-print-pants",
            "open-shoulder","meditation-yoga-pants","fisherman-pants-jeans","samui-caftan",
            "unique-fisherman-pants","two-style-mix","traditional-blue-kaftan",
            "island-night-long-sleeve","ems-fast-shipping-7-days","cotton-beach-towel",
            "thai-towel-for-female","thai-pha-ka-matowel","kimono-samui-slim-sleeves-copy",
            "traveling-pants-copy","traveling-pants-copy-1","printed-wrap-pants-copy",
            "hemp-ethnic-pants-copy"]

def log(m): print(time.strftime("[%H:%M:%S] ") + m, flush=True)

def fetch(path, timeout=60):
    """One GET. Returns (bytes_or_None, retry_after_seconds_or_None)."""
    req = urllib.request.Request(BASE + path, headers={
        "User-Agent": UA, "Accept": "text/html,application/xhtml+xml",

        "Accept-Language": "en-US,en;q=0.9"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read(), None
    except urllib.error.HTTPError as e:
        if e.code == 429:
            ra = e.headers.get("Retry-After")
            try:
                ra = int(ra)
            except Exception:
                ra = 60
            try:
                e.read()
            except Exception:
                pass
            return None, ra
        if e.code == 404:
            return b"404", None
        log(f"  HTTP {e.code} {path}")
        return None, 10
    except Exception as ex:
        log(f"  {path}: {ex}")
        return None, 10

def fetch_with_retry(path):
    for attempt in range(MAX_RETRY):
        data, ra = fetch(path)
        if data is not None:
            return data
        wait = (ra or 60) + 5
        log(f"  429 on {path}, retry-after {ra}s -> wait {wait}s (try {attempt + 1}/{MAX_RETRY})")
        time.sleep(wait)
    return None

def save(path, name, data):
    fp = os.path.join(HTML_DIR, f"{name}.html")
    open(fp, "wb").write(data)
    log(f"saved {name}.html ({len(data)}b)")

def main():
    os.makedirs(HTML_DIR, exist_ok=True)
    os.makedirs(IMG_DIR, exist_ok=True)
    os.system(f"touch {ROOT}/_crawl/crawl.done")
    open(os.path.join(ROOT, "_crawl", "crawl.log"), "a").close()
    jobs = [("/", "home")]
    jobs += [(f"/collections/{c}", f"collection-{c}") for c in COLLECTIONS]
    jobs += [(f"/products/{p}", f"product-{p}") for p in PRODUCTS]
    jobs += [(f"/pages/{p}", f"page-{p}") for p in PAGES]
    jobs += [("/policies/privacy-policy", "page-privacy-policy")]
    ok, failed = 0, []
    for i, (path, name) in enumerate(jobs):
        fp = os.path.join(HTML_DIR, f"{name}.html")
        if os.path.exists(fp) and os.path.getsize(fp) > 2000 and not os.path.exists(fp + ".force"):
            ok += 1
            continue
        if i > 0:
            time.sleep(PACE)
        data = fetch_with_retry(path)
        if data is None:
            failed.append(path)
            continue
        save(path, name, data)
        ok += 1
        log(f"progress {i + 1}/{len(jobs)} ok={ok} failed={len(failed)}")
    log(f"PHASE A done: ok={ok} failed={len(failed)}")
    if failed:
        log("FAILED: " + ", ".join(failed))

    # ---- Phase B: images ----
    manifest = {}
    mf = os.path.join(ROOT, "_crawl", "manifest.json")
    if os.path.exists(mf):
        manifest = json.load(open(mf))
    todo = []
    for f in sorted(os.listdir(HTML_DIR)):
        if not f.endswith(".html"):
            continue
        h = open(os.path.join(HTML_DIR, f), "r", errors="replace").read()
        for m in re.findall(r'//[a-z.]*fishermenpants\.com/(cdn/[A-Za-z0-9_\-./]+\.(?:jpg|jpeg|png|webp|avif|mp4|webm))(?:\?[^"\')\s]*)?', h):
            if m not in manifest:
                todo.append(m)
    log(f"PHASE B: {len(todo)} images to download")
    import hashlib
    for u in todo:
        m = re.match(r'cdn/(shop|collections)/(.+)$', u)
        if not m:
            continue
        name = os.path.basename(u.split("?")[0])
        ext = os.path.splitext(name)[1].lower() or ".jpg"
        hsh = hashlib.md5(u.encode()).hexdigest()[:6]
        local = f"{hsh}_{name}"
        dst = os.path.join(IMG_DIR, local)
        if os.path.exists(dst) and os.path.getsize(dst) > 100:
            manifest[u] = local
            continue
        src = f"{BASE}/{u}"
        if ext in (".jpg", ".jpeg", ".png", ".webp"):
            src += ("&" if "?" in src else "?") + "width=1600"
        req = urllib.request.Request(src, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            open(dst, "wb").write(data)
            manifest[u] = local
        except Exception as ex:
            log(f"  img fail {u}: {ex}")
        time.sleep(1.0)
    json.dump(manifest, open(mf, "w"), indent=1)
    log(f"PHASE B done: {len(manifest)} images mapped")

    # ---- Phase C: parse ----
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from crawl import parse_product, product_handles_from  # reuse parser
    prods = []
    for p in PRODUCTS:
        fp = os.path.join(HTML_DIR, f"product-{p}.html")
        if not os.path.exists(fp) or os.path.getsize(fp) < 2000:
            continue
        prod, _ = parse_product(fp)
        prods.append(prod)
        log(f"parsed {p}: {len(prod['variants'])} variants, {len(prod['images'])} images")
    cols = {}
    for c in COLLECTIONS:
        fp = os.path.join(HTML_DIR, f"collection-{c}.html")
        if not os.path.exists(fp) or os.path.getsize(fp) < 2000:
            continue
        ch = open(fp, errors="replace").read()
        cols[c] = {"handles": product_handles_from(ch), "title": c}
    json.dump({"products": prods, "collections": cols},
              open(os.path.join(ROOT, "_crawl", "parsed.json"), "w"), indent=1)
    log("DONE crawl -> parsed.json")
    os.remove(os.path.join(ROOT, "_crawl", "crawl.done"))

if __name__ == "__main__":
    main()
