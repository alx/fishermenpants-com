#!/usr/bin/env python3
"""Parse the crawled (browser-rendered) HTML into _crawl/parsed.json.

Per product page we extract:
  - initData JSON (id, handle, title, type, vendor, variants with prices)
  - media-gallery images
  - description HTML (div.product__description)
  - regular/sale prices from the price markup
"""
import json, os, re, sys, html as H

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CR = os.path.join(ROOT, "_crawl")
HTML = os.path.join(CR, "html")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from crawl2 import PRODUCTS, COLLECTIONS, log

def parse_product(fp):
    h = open(fp, errors="replace").read()
    handle = os.path.basename(fp).replace("product-", "").replace(".html", "")
    out = {"handle": handle, "title": handle, "description": "",
           "price_min": None, "price_max": None, "compare_at_min": None,
           "variants": [], "images": [], "options": [], "type": "", "vendor": ""}

    # --- initData JSON ---
    i = h.find("initData: {")
    if i >= 0:
        seg = h[i + len("initData: "):]
        try:
            obj, _ = json.JSONDecoder().raw_decode(seg)
            prods = {p.get("handle"): p for p in obj.get("products", []) if p.get("handle")}
            p = prods.get(handle)
            if p:
                out["title"] = p.get("title", out["title"])
                out["type"] = p.get("type", "")
                out["vendor"] = p.get("vendor", "")
                prices = []
                for v in p.get("variants", []):
                    amt = (v.get("price") or {}).get("amount")
                    if amt is None:
                        continue
                    prices.append(amt)
                    out["variants"].append({
                        "id": v.get("id"), "title": v.get("title", "Default Title"),
                        "price": amt, "sku": v.get("sku", ""), "available": True})
                if prices:
                    out["price_min"] = min(prices)
                    out["price_max"] = max(prices)
        except Exception as e:
            log(f"  initData parse fail for {handle}: {e}")

    # The source store configures many products with filler numbered
    # "Patterns" variants (1..20, all the same price). Every product on this
    # store is effectively single-price, so collapse same-price variant sets
    # to Shopify's single-variant convention ("Default Title").
    vs = out["variants"]
    if len(vs) > 1 and len({v["price"] for v in vs}) == 1:
        # Title is empty on purpose: "Default Title" is a Shopify placeholder for
        # "this product has no options" and must never reach the page.
        out["variants"] = [{"id": vs[0]["id"], "title": "",
                            "price": vs[0]["price"], "sku": "", "available": True}]
        out["price_min"] = vs[0]["price"]
        out["price_max"] = vs[0]["price"]
    # A genuine single-variant product keeps whatever Shopify gave it, which is
    # usually the same placeholder - normalise those too.
    for v in out["variants"]:
        if (v.get("title") or "").strip() == "Default Title":
            v["title"] = ""

    # --- gallery ---
    g = h.find("<media-gallery")
    if g >= 0:
        seg = h[g:h.find("</media-gallery>", g)]
        for m in re.finditer(r'(?:data-src|data-full-size|src|data-srcset)="([^"]+?cdn/[^"]+?)(?:\?[^"]*)?"', seg):
            u = H.unescape(m.group(1)).split("?")[0]
            if u.startswith("//"):
                u = "https:" + u
            if u not in out["images"]:
                out["images"].append(u)

    # --- description ---
    m = re.search(r'class="product__description[^"]*"[^>]*>(.*?)</div>', h, re.S)
    if m:
        out["description"] = m.group(1).strip()

    # --- prices from markup ---
    reg = re.search(r'price-item--regular[^>]*>\s*(?:<[^>]+>\s*)*\$?([0-9,]+(?:\.[0-9]+)?)', h)
    sal = re.search(r'price-item--sale[^>]*>\s*(?:<[^>]+>\s*)*\$?([0-9,]+(?:\.[0-9]+)?)', h)
    def amt(x):
        return float(x.group(1).replace(",", ""))
    if reg and (out["price_min"] is None):
        out["price_min"] = amt(reg)
        out["price_max"] = amt(reg)
    if sal:
        s = amt(sal)
        if reg and out["price_min"] is not None and s < out["price_min"] - 0.005:
            out["compare_at_min"] = out["price_min"]
            out["price_min"] = s
            out["price_max"] = s
    return out

def main():
    prods = []
    for p in PRODUCTS:
        fp = os.path.join(HTML, f"product-{p}.html")
        if not os.path.exists(fp) or os.path.getsize(fp) < 2000:
            log(f"  ! missing product page {p}")
            continue
        prod = parse_product(fp)
        prods.append(prod)
        log(f"parsed {p}: {len(prod['variants'])} variants, {len(prod['images'])} images, "
            f"price={prod['price_min']} compare={prod['compare_at_min']}")
    cols = {}
    for c in COLLECTIONS:
        fp = os.path.join(HTML, f"collection-{c}.html")
        if not os.path.exists(fp) or os.path.getsize(fp) < 2000:
            continue
        ch = open(fp, errors="replace").read()
        cols[c] = {"handles": sorted(set(re.findall(r'href="/products/([a-z0-9\-]+)"', ch))),
                   "title": c}
    json.dump({"products": prods, "collections": cols},
              open(os.path.join(CR, "parsed.json"), "w"), indent=1)
    log("parsed.json written")

if __name__ == "__main__":
    main()
