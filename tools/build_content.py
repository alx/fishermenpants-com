#!/usr/bin/env python3
"""Build Hugo content (content/) + data/home.yaml from _crawl/parsed.json.

Run after crawl + parse. Output:
  content/products/<handle>.md   (one per product)
  content/collections/<handle>.md
  data/home.yaml                 (hero, banners, sections, reviews)
"""
import json, os, re, html as H

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CR = os.path.join(ROOT, "_crawl")
CONTENT = os.path.join(ROOT, "content")
DATA = os.path.join(ROOT, "data")

parsed = json.load(open(os.path.join(CR, "parsed.json")))
manifest = {}
mf = os.path.join(CR, "manifest.json")
if os.path.exists(mf):
    manifest = json.load(open(mf))

def local_for(url):
    if not url:
        return None
    key = url.split("?")[0].replace("https://www.fishermenpants.com/", "").replace("//www.fishermenpants.com/", "")
    if key in manifest:
        return f"img/{manifest[key]}"
    m = re.match(r"cdn/(shop|collections)/(.+)$", key)
    if m:
        return f"img/{os.path.basename(key)}"
    return None

def gallery(prod):
    seen, out = set(), []
    for u in prod.get("images", []):
        lp = local_for(u)
        if lp and lp not in seen:
            seen.add(lp)
            out.append(lp)
    return out

def money(x):
    x = float(x)
    return f"${x:.2f}".replace(".00", "") if x != int(x) else f"${int(x)}"

# ---------- products ----------
os.makedirs(os.path.join(CONTENT, "products"), exist_ok=True)
count_p = 0
for p in parsed.get("products", []):
    h = p["handle"]
    variants = p.get("variants", []) or []
    fpath = os.path.join(CONTENT, "products", f"{h}.md")
    if not variants and os.path.getsize(fpath) > 500:
        continue  # already has content from a previous run
    desc = re.sub(r"<[^>]+>", " ", p.get("description") or "")
    desc = re.sub(r"\s+", " ", H.unescape(desc)).strip()[:400]
    fm = {
        "title": p.get("title", h),
        "priceMin": p.get("price_min") or 0,
        "priceMax": p.get("price_max") or 0,
        "compareAtMin": p.get("compare_at_min") or 0,
        "variants": variants,
        "images": gallery(p),
        "type": p.get("type", ""),
        "vendor": p.get("vendor", ""),
    }
    lines = ["---"]
    lines.append(f'title: "{H.unescape(fm["title"])}"')
    lines.append(f"priceMin: {fm['priceMin']}")
    lines.append(f"priceMax: {fm['priceMax']}")
    lines.append(f"compareAtMin: {fm['compareAtMin']}")
    lines.append(f"variants: {json.dumps(variants)}")
    lines.append(f"images: {json.dumps(fm['images'])}")
    lines.append(f"ptype: {json.dumps(fm['type'])}")
    lines.append(f"vendor: {json.dumps(fm['vendor'])}")
    lines.append("---")
    lines.append(f"<!-- product:{h} -->")
    if desc:
        lines.append(desc)
    open(fpath, "w").write("\n".join(lines) + "\n")
    count_p += 1
print(f"built: {count_p} products")

# ---------- collections ----------
COLL_META = {
    "fisherman-pants": "Fisherman Pants",
    "island-shirts": "Island Shirts",
    "shop-for-her": "Shop for Her",
    "new-arrivals": "What's New",
    "best-sellers": "Best Sellers",
    "scarves": "Scarves",
    "accessories-1": "Accessories",
    "bags": "Bags",
    "sarongs": "Sarongs",
    "jewelry": "Jewelry",
    "all-products": "All Products",
}
os.makedirs(os.path.join(CONTENT, "collections"), exist_ok=True)
prod_handles = {p["handle"] for p in parsed.get("products", [])}
count_c = 0
for h, meta in parsed.get("collections", {}).items():
    title = COLL_META.get(h, h.replace("-", " ").title())
    # keep original order, but drop handles we did not crawl (no product page)
    handles = [x for x in meta.get("handles", []) if x in prod_handles]
    lines = ["---", f'title: "{title}"', f"products: {json.dumps(handles)}", "---"]
    open(os.path.join(CONTENT, "collections", f"{h}.md"), "w").write("\n".join(lines) + "\n")
    print(f"  collection {h}: {len(handles)}/{len(meta.get('handles', []))} handles with pages")
    count_c += 1
print(f"built: {count_c} collections")

# ---------- home.json ----------
home_html = open(os.path.join(CR, "html", "home.html"), errors="replace").read()

home = {"hero": [], "brand": "GAYA",
        "tagline": "Elegant and sustainable beachwear for the adventurous trendsetters.",
        "interstitials": [], "whatsNew": [], "islandsVibes": [],
        "collectionTiles": [], "testimonials": [], "video": None, "videoKind": None}

# hero slideshow (verified: 2-slide hero of the original)
home["hero"] = [
    {"image": local_for("//www.fishermenpants.com/cdn/shop/files/Wrap_pants.png"),
     "heading": "Explore nature"},
    {"image": local_for("//www.fishermenpants.com/cdn/shop/files/Samui_collection.png"),
     "heading": "Breath the air"},
]

# banners (verified from crawled DOM)
home["interstitials"] = [
    {"image": local_for("//www.fishermenpants.com/cdn/shop/files/Screenshot_2025-03-28_145605.png"),
     "heading": "Exercise heavy travel light",
     "text": "Versatile and unisex pants designed for yoga, the beach, and beyond.",
     "cta": "Shop pants", "href": "/collections/fisherman-pants/", "flip": False},
    {"image": local_for("//www.fishermenpants.com/cdn/shop/files/Screenshot_2025-03-12_105305.png"),
     "heading": "Great Traveling Pants",
     "text": "",
     "cta": "Shop pants", "href": "/collections/fisherman-pants/", "flip": True},
]

# what's new (verified slider order)
home["whatsNew"] = ["hemp-ethnic-pants-copy", "samui-caftan", "yacht-collection-waffle-pants", "unique-fisherman-pants"]

# islands vibes (verified: yacht waffle + unique fisherman pants)
home["islandsVibes"] = ["yacht-collection-waffle-pants", "unique-fisherman-pants"]

# collection tiles (verified: caption -> following image)
home["collectionTiles"] = [
    {"handle": "shop-for-her", "label": "Samui collection",
     "image": local_for("//www.fishermenpants.com/cdn/shop/collections/Screenshot_2025-03-28_145738.png")},
    {"handle": "fisherman-pants", "label": "Thai wrap pants",
     "image": local_for("//www.fishermenpants.com/cdn/shop/collections/acesessories_e8277ea4-cfc9-4f01-a3c6-a70aea26e1ac.jpg")},
    {"handle": "accessories-1", "label": "Accessories",
     "image": local_for("//www.fishermenpants.com/cdn/shop/files/Screenshot_2025-03-11_191924.png")},
]

# testimonials: name <h3> + the longest <p> that follows
i = home_html.find("What people say")
seg = home_html[i:i + 30000] if i >= 0 else ""
for m in re.finditer(r"<h3[^>]*>([^<]{2,40})</h3>(.*?)(?=<h3[^>]*>|$)", seg, re.S):
    name = H.unescape(m.group(1)).strip()
    paras = [re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", "", p))).strip()
             for p in re.findall(r"<p[^>]*>(.*?)</p>", m.group(2), re.S)]
    paras = [p for p in paras if len(p) > 60]
    if name and paras:
        home["testimonials"].append({"name": name, "text": paras[0][:600]})
    if len(home["testimonials"]) >= 3:
        break

# video section
video = re.search(r'(?:<video[^>]*src="([^"]+)"|youtube\.com/embed/([A-Za-z0-9_\-]+))', home_html)
if video:
    if video.group(1):
        home["video"], home["videoKind"] = video.group(1), "file"
    else:
        home["video"], home["videoKind"] = f"https://www.youtube.com/embed/{video.group(2)}?enablejsapi=1&autoplay=1", "youtube"

os.makedirs(DATA, exist_ok=True)
json.dump(home, open(os.path.join(DATA, "home.yaml"), "w"), indent=1)  # JSON is valid YAML; CMS singleton edits this file
print("home.json:", json.dumps(home, indent=1)[:1200])
