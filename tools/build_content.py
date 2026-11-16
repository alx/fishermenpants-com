#!/usr/bin/env python3
"""Build Hugo content from _crawl/parsed.json + manifest + home.html.

Emits: content/products/*.md, content/collections/*.md, data/home.json
"""
import json, os, re, sys, html as H

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CR = os.path.join(ROOT, "_crawl")

parsed = json.load(open(os.path.join(CR, "parsed.json")))
manifest = {}
mf = os.path.join(CR, "manifest.json")
if os.path.exists(mf):
    manifest = json.load(open(mf))
home_html = open(os.path.join(CR, "html", "home.html")).read()

def local_for(url):
    """Map a cdn url (//host/cdn/... or cdn/...) to /img/<name>, best effort."""
    if not url:
        return None
    key = url
    if key.startswith("//www.fishermenpants.com/"):
        key = key[len("//www.fishermenpants.com/"):]
    if key.startswith("https://www.fishermenpants.com/"):
        key = key[len("https://www.fishermenpants.com/"):]
    if not key.startswith("cdn/"):
        return None
    if key in manifest:
        return f"/img/{manifest[key]}"
    # try to match ignoring size params
    for k, v in manifest.items():
        if re.sub(r"\?.*$", "", k) == re.sub(r"\?.*$", "", key):
            return f"/img/{v}"
    return None

# ---- products ----
prod_by_handle = {}
for p in parsed["products"]:
    prod_by_handle[p["handle"]] = p

# collection membership: which collections contain which products
membership = {p["handle"]: [] for p in parsed["products"]}
col_meta = {}
for ch, c in parsed["collections"].items():
    col_meta[ch] = c
    for h in c["handles"]:
        if h not in membership:
            membership[h] = []
        if ch not in membership[h]:
            membership[h].append(ch)

os.makedirs(os.path.join(ROOT, "content", "products"), exist_ok=True)
for h, p in prod_by_handle.items():
    imgs = []
    for u in p.get("images", []):
        l = local_for(u)
        if l and l not in imgs:
            imgs.append(l)
    variants = []
    for v in p.get("variants", []):
        variants.append({
            "id": v.get("id") or 0,
            "title": v.get("title", ""),
            "price": v.get("price"),
            "sku": v.get("sku", ""),
            "available": v.get("available", True),
        })
    fm = {
        "title": p.get("title", h),
        "priceMin": p.get("price_min"),
        "priceMax": p.get("price_max"),
        "variants": variants,
        "images": imgs,
        "options": p.get("options", []),
        "collections": membership.get(h, []),
        "product": True,
    }
    desc = (p.get("description") or "").strip()
    open(os.path.join(ROOT, "content", "products", f"{h}.md"), "w").write(
        f"---\ntitle: \"{p.get('title', h)}\"\npriceMin: {p.get('price_min') or 0}\n"
        f"priceMax: {p.get('price_max') or 0}\nvariants: {json.dumps(variants)}\n"
        f"images: {json.dumps(imgs)}\noptions: {json.dumps(p.get('options', []))}\n"
        f"collections: {json.dumps(membership.get(h, []))}\nproduct: true\n---\n"
        f"<!--desc-start-->{desc}<!--desc-end-->\n")

# ---- collections ----
os.makedirs(os.path.join(ROOT, "content", "collections"), exist_ok=True)
COL_TITLES = {"all": "All Products", "new-arrivals": "New Arrivals",
              "shop-for-her": "Shop for Her", "fisherman-pants": "Fisherman Pants",
              "island-shirts": "Island Shirts", "sarongs": "Sarongs",
              "scarves": "Scarves", "bags": "Bags", "jewelry": "Jewelry",
              "accessories-1": "Accessories"}
for ch, c in col_meta.items():
    open(os.path.join(ROOT, "content", "collections", f"{ch}.md"), "w").write(
        f"---\ntitle: \"{COL_TITLES.get(ch, c.get('title', ch))}\"\ncollection: {ch}\n"
        f"products: {json.dumps(c.get('handles', []))}\n---\n")

# ---- static pages ----
static_map = {
    "page-payment-methods.html": ("pages", "payment-methods", "Payment Methods"),
    "page-privacy-policy.html": ("pages", "privacy-policy", "Privacy Policy"),
}
for f, (sec, name, title) in static_map.items():
    fp = os.path.join(CR, "html", f)
    if not os.path.exists(fp):
        continue
    h = open(fp).read()
    m = re.search(r'<main[^>]*>(.*?)</main>', h, re.S)
    body = ""
    if m:
        body = re.sub(r'\s+', ' ', m.group(1))
        body = re.sub(r'<script.*?</script>', '', body, flags=re.S)
    open(os.path.join(ROOT, "content", sec, f"{name}.md"), "w").write(
        f"---\ntitle: \"{title}\"\n---\n{body}\n")

# ---- home.json ----
def sec_segment(anchor_text):
    i = home_html.find(anchor_text)
    return home_html[i:i + 20000] if i >= 0 else ""

def banner_sections():
    """image-banner sections: heading + image"""
    out = []
    for m in re.finditer(r'section-image-banner[^"]*"(.*?)(?=section-|<footer)', home_html, re.S):
        seg = m.group(1)
        t = re.search(r'<h2[^>]*>([^<]+)</h2>', seg)
        img = re.search(r'src="([^"]+cdn/[^"]+)"', seg)
        if t or img:
            out.append({"heading": H.unescape(t.group(1)).strip() if t else "",
                        "image": local_for(img.group(1)) if img else None})
    return out

def products_near(anchor):
    seg = sec_segment(anchor)
    hs = []
    for m in re.finditer(r'href="/products/([a-z0-9\-]+)"', seg):
        if m.group(1) not in hs:
            hs.append(m.group(1))
    return hs

def collection_tiles():
    seg = sec_segment("Collections")
    out = []
    for m in re.finditer(r'<a[^>]*href="/collections/([a-z0-9\-]+)"[^>]*>(.*?)(?=<a |</section>)', seg, re.S):
        t = re.search(r'>([^<]{3,40})</a>', m.group(0))
        img = re.search(r'src="([^"]+cdn/[^"]+)"', m.group(2))
        if t or img:
            out.append({"handle": m.group(1),
                        "label": H.unescape(t.group(1)).strip() if t else m.group(1),
                        "image": local_for(img.group(1)) if img else None})
    return out

def testimonials():
    seg = sec_segment("What people say")
    out = []
    # names are in h3-like spans; text paragraphs follow
    blocks = re.findall(r'([A-Z][A-Za-z .]{2,25})</(?:h3|span|p)>\s*(?:<[^>]+>\s*)*<p[^>]*>(.*?)</p>', seg, re.S)
    for name, txt in blocks:
        t = H.unescape(re.sub(r'<[^>]+>', ' ', txt)).strip()
        t = re.sub(r'\s+', ' ', t)
        if t and name.strip() not in ("What people say",):
            out.append({"name": name.strip(), "text": t})
    if not out:
        # fallback: all substantial paragraphs after the heading
        txt = H.unescape(re.sub(r'<[^>]+>', '\n', seg))
        lines = [re.sub(r'\s+', ' ', l).strip() for l in txt.split('\n') if len(l.strip()) > 40]
        for i in range(0, len(lines) - 1, 2):
            out.append({"name": lines[i][:40], "text": lines[i + 1]})
    return out[:4]

video = None
mv = re.search(r'(https?://(?:www\.)?youtube\.com/(?:watch\?v=|embed/)[\w\-]+[^"\']*)', home_html)
if mv:
    video = mv.group(1)

home = {
    "heroImage": None,
    "brand": "GAYA",
    "tagline": "Elegant and sustainable beachwear for the adventurous trendsetters.",
    "banners": banner_sections(),
    "whatsNew": products_near("What's  new") or products_near("What’s new"),
    "islandsVibes": products_near("Islands vibes"),
    "collectionTiles": collection_tiles(),
    "testimonials": testimonials(),
    "video": video,
}
# hero = first image in the first image-banner section
hb = re.search(r'<section[^>]*image-banner[^>]*>(.*?)</section>', home_html, re.S)
if hb:
    img = re.search(r'src="([^"]+cdn/[^"]+)"', hb.group(1))
    if img:
        home["heroImage"] = local_for(img.group(1))

json.dump(home, open(os.path.join(ROOT, "data", "home.json"), "w"), indent=1)
print("built:", len(prod_by_handle), "products,", len(col_meta), "collections")
print("home.json:", json.dumps({k: v for k, v in home.items() if k != "testimonials"}, indent=1)[:1200])
