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

print("VERIFY OK" if ok else "VERIFY FAILED")
sys.exit(0 if ok else 1)
