#!/usr/bin/env python3
"""Crawl support for the fishermenpants.com migration.

Phase A (page fetching) lives in crawl_browser.mjs (Playwright Firefox — the
Shopify edge 403/429s plain HTTP clients). This module provides the job list,
Phase B (image downloads) and Phase C (parsing).

Usage:
  python3 tools/crawl2.py jobs            # write _crawl/jobs.json for the browser
  python3 tools/crawl2.py bc              # run phase B (images) + C (parse)
"""
import json, os, re, sys, time, hashlib, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://www.fishermenpants.com"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
HTML_DIR = os.path.join(ROOT, "_crawl", "html")
IMG_DIR = os.path.join(ROOT, "static", "img")

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

def all_jobs():
    jobs = [("/", "home")]
    jobs += [(f"/collections/{c}", f"collection-{c}") for c in COLLECTIONS]
    jobs += [(f"/products/{p}", f"product-{p}") for p in PRODUCTS]
    jobs += [(f"/pages/{p}", f"page-{p}") for p in PAGES]
    jobs += [("/policies/privacy-policy", "page-privacy-policy")]
    return jobs

def write_jobs():
    os.makedirs(HTML_DIR, exist_ok=True)
    json.dump(all_jobs(), open(os.path.join(ROOT, "_crawl", "jobs.json"), "w"), indent=1)
    log(f"wrote jobs.json ({len(all_jobs())} urls)")

def phase_b():
    """Download every CDN image referenced by the crawled HTML."""
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
    for u in todo:
        if not re.match(r'cdn/(shop|collections)/', u):
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

def phase_c():
    """Parse product/collection HTML into _crawl/parsed.json."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from crawl import parse_product, product_handles_from
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
    log("PHASE C done -> parsed.json")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "jobs"
    if cmd == "jobs":
        write_jobs()
    elif cmd == "bc":
        phase_b()
        phase_c()
    elif cmd == "b":
        phase_b()
    elif cmd == "c":
        phase_c()
    else:
        raise SystemExit("usage: crawl2.py [jobs|b|c|bc]")
