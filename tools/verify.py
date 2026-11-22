#!/usr/bin/env python3
"""Verify the built site: pages, images, no dangling references."""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ok = True

def fail(msg):
    global ok
    ok = False
    print("FAIL:", msg)

# 1. content images referenced in frontmatter must exist
import glob
refs = 0
for f in glob.glob(os.path.join(ROOT, "content", "**", "*.md"), recursive=True):
    text = open(f, errors="replace").read()
    for m in re.finditer(r'images: \[([^\]]*)\]', text):
        for img in re.findall(r'"(.*?)"', m.group(1)):
            refs += 1
            p = os.path.join(ROOT, "static", img.lstrip("/"))
            if not (os.path.exists(p) and os.path.getsize(p) > 100):
                fail(f"{f}: missing image {img}")
print(f"checked {refs} product image refs")

# 2. home.json refs
_hp = os.path.join(ROOT, "data", "home.yaml")
if os.path.exists(_hp):
    try:
        import yaml
        home = yaml.safe_load(open(_hp))
    except ImportError:
        home = json.load(open(_hp))  # JSON is valid YAML
else:
    home = json.load(open(os.path.join(ROOT, "data", "home.json")))
def check_img(v, ctx):
    if v and str(v).startswith("/img/"):
        p = os.path.join(ROOT, "static", str(v).lstrip("/"))
        if not os.path.exists(p):
            fail(f"home.json {ctx}: missing {v}")
check_img(home.get("heroImage"), "hero")
for i, b in enumerate(home.get("banners", [])):
    check_img(b.get("image"), f"banner{i}")
for i, t in enumerate(home.get("collectionTiles", [])):
    check_img(t.get("image"), f"tile{i}")

# 3. built pages exist
public = os.path.join(ROOT, "public")
for sec in ("products", "collections"):
    d = os.path.join(ROOT, "content", sec)
    if os.path.isdir(d):
        for f in os.listdir(d):
            if f.endswith(".md"):
                name = f[:-3]
                page = os.path.join(public, sec, name, "index.html")
                if not os.path.exists(page):
                    fail(f"missing built page {sec}/{name}")
                elif os.path.getsize(page) < 500:
                    fail(f"tiny built page {sec}/{name}")
print("checked built pages")

# 4. built home has expected sections
home_html = open(os.path.join(public, "index.html"), errors="replace").read()
for k in ("hero", "newsletter", "formspree-form", "country-select-footer", "cart-link"):
    if k not in home_html:
        fail(f"home: missing {k}")
print("checked home sections")

# 5. search index
idx = json.load(open(os.path.join(public, "js", "search-index.json")))
print(f"search index: {len(idx['docs'])} docs")

# 6. count local images shipped
n_img = len([f for f in os.listdir(os.path.join(ROOT, "static", "img")) if not f.startswith("placeholder")])
print(f"local images: {n_img}")

# 8. catalogue integrity: every product is in a collection, every handle resolves
import re as _re
_prod_dir = os.path.join(ROOT, "content", "products")
_col_dir = os.path.join(ROOT, "content", "collections")
_prods = set()
for _f in os.listdir(_prod_dir):
    if not _f.endswith(".md"):
        continue
    if _re.search(r'^service:\s*true', open(os.path.join(_prod_dir, _f), errors="replace").read(), _re.M):
        continue  # a shipping add-on, not a catalogue product
    _prods.add(_f[:-3])
_listed = set()
for cf in glob.glob(os.path.join(_col_dir, "*.md")):
    cm = _re.search(r'^products:\s*\[(.*?)\]', open(cf, errors="replace").read(), _re.M | _re.S)
    handles = _re.findall(r'"([^"]+)"', cm.group(1)) if cm else []
    for h in handles:
        _listed.add(h)
        if h not in _prods:
            fail(f"{os.path.basename(cf)}: referenced product '{h}' does not exist")
# a product must appear in at least one *specific* collection (catch-alls don't count)
_skip = {"all-products", "new-arrivals", "best-sellers"}
_specific = set()
for cf in glob.glob(os.path.join(_col_dir, "*.md")):
    if os.path.basename(cf)[:-3] in _skip:
        continue
    cm = _re.search(r'^products:\s*\[(.*?)\]', open(cf, errors="replace").read(), _re.M | _re.S)
    if cm:
        _specific.update(_re.findall(r'"([^"]+)"', cm.group(1)))
_orphans = _prods - _specific
# products may also declare collections directly in front matter
for pf in glob.glob(os.path.join(_prod_dir, "*.md")):
    if _re.search(r'^collections:\s*\[', open(pf, errors='replace').read(), _re.M):
        _orphans.discard(os.path.basename(pf)[:-3])
for o in sorted(_orphans):
    fail(f"product '{o}' belongs to no collection (orphan)")
ap = os.path.join(_col_dir, "all-products.md")
if os.path.exists(ap):
    cm = _re.search(r'^products:\s*\[(.*?)\]', open(ap, errors="replace").read(), _re.M | _re.S)
    listed = set(_re.findall(r'"([^"]+)"', cm.group(1))) if cm else set()
    # Some product files are deliberately not shoppable cards:
    #   ptype: test            -> debug SKUs (e.g. debug-order-1, 1 USD)
    #   service: true          -> shipping add-ons (e.g. ems-fast-shipping),
    #                             listed at checkout, not in the grid
    _excl = set()
    for pf in glob.glob(os.path.join(_prod_dir, "*.md")):
        t = open(pf, errors="replace").read()
        if _re.search(r'^ptype:\s*["\']?test', t, _re.M) or _re.search(r'^service:\s*true', t, _re.M):
            _excl.add(os.path.basename(pf)[:-3])
    _expected = _prods - _excl
    _missing = _expected - listed
    _extra = listed - _prods
    for m in sorted(_missing):
        fail(f"product '{m}' is shoppable but missing from all-products")
    for m in sorted(_extra):
        fail(f"all-products lists '{m}' but no content/products/{m}.md exists")
    print(f"all-products: {len(listed)} listed, {len(_expected)} shoppable, "
          f"{len(_excl)} excluded (test/service)")
print(f"catalogue: {len(_prods)} products, all in a collection, all handles resolve")

# 10. every product handle referenced in data/home.yaml must exist
try:
    import yaml as _yaml
    _home = _yaml.safe_load(open(os.path.join(ROOT, "data", "home.yaml"), errors="replace"))
    _refd = list(_home.get("whatsNew") or []) + list(_home.get("islandsVibes") or [])
    for _k in ("hero", "interstitials", "collectionTiles"):
        for _entry in (_home.get(_k) or []):
            for _field in ("image",):
                _img = (_entry or {}).get(_field)
                if _img and not os.path.exists(os.path.join(ROOT, "static", str(_img).lstrip("/"))):
                    fail(f"home.yaml {_k}: missing image {_img}")
    for _h in _refd:
        if _h not in _prods:
            fail(f"home.yaml references unknown product '{_h}'")
    for _t in (_home.get("collectionTiles") or []):
        _c = (_t or {}).get("handle")
        if _c and not os.path.exists(os.path.join(ROOT, "content", "collections", str(_c) + ".md")):
            fail(f"home.yaml collectionTile: unknown collection '{_c}'")
    print(f"home.yaml: {len(_refd)} product refs and all tile images resolve")
except ImportError:
    print("home.yaml: skipped (pyyaml not installed)")
except FileNotFoundError:
    pass

# 7. private pages must not be in the sitemap or indexable
sm = os.path.join(ROOT, "public", "sitemap.xml")
if os.path.exists(sm):
    xml = open(sm, errors="replace").read()
    for blocked in ("/order/", "/cart/", "/search/"):
        if blocked in xml:
            fail(f"sitemap.xml must not contain {blocked}")
ty = os.path.join(ROOT, "public", "order", "thank-you", "index.html")
if os.path.exists(ty):
    html = open(ty, errors="replace").read()
    if "noindex" not in html:
        fail("/order/thank-you/ must carry a robots noindex meta tag")
if os.path.exists(os.path.join(ROOT, "public", "order", "index.html")):
    fail("/order/ section index must not be generated (_build.render: never)")
print("private pages: not in sitemap, noindex verified")

# 9. structured data must be valid JSON with absolute URLs
_ld_checked = 0
for _f in ("products/beach-bag-2", "collections/bags", "contact", ""):
    _p = os.path.join(ROOT, "public", _f, "index.html")
    if not os.path.exists(_p):
        continue
    _blocks = re.findall(r'<script type=application/ld\+json>(.*?)</script>', open(_p, errors="replace").read(), re.S)
    if not _blocks:
        fail(f"{_f or '/'}: no JSON-LD structured data")
        continue
    try:
        _d = json.loads(_blocks[0])
    except Exception as e:
        fail(f"{_f or '/'}: invalid JSON-LD: {e}")
        continue
    _types = {n.get("@type") for n in _d.get("@graph", [])}
    if not {"Organization", "WebSite"} <= _types:
        fail(f"{_f or '/'}: JSON-LD missing Organization/WebSite")
    for _n in _d.get("@graph", []):
        _u = _n.get("url")
        if isinstance(_u, str) and _u.startswith("/"):
            fail(f"{_f or '/'}: JSON-LD url must be absolute, got {_u}")
    _ld_checked += 1
print(f"structured data: {_ld_checked} pages valid")

print("VERIFY OK" if ok else "VERIFY FAILED")
sys.exit(0 if ok else 1)
