#!/usr/bin/env python3
"""Build static/js/search-index.json from Hugo content files (no backend)."""
import json, os, re, sys, html as H

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "static", "js", "search-index.json")

def parse_frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not m:
        return {}, text
    fm_raw, body = m.group(1), m.group(2)
    fm = {}
    for line in fm_raw.split("\n"):
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        v = v.strip()
        try:
            fm[k.strip()] = json.loads(v)
        except Exception:
            fm[k.strip()] = v.strip('"')
    return fm, body

def text_of(body):
    b = re.sub(r"<!--.*?-->", " ", body, flags=re.S)
    b = re.sub(r"<[^>]+>", " ", b)
    b = H.unescape(b)
    return re.sub(r"\s+", " ", b).strip()

docs = []
for sec, urlfmt in (("products", "/products/{n}/"), ("collections", "/collections/{n}/"),
                    ("pages", "/{n}/")):
    d = os.path.join(ROOT, "content", sec)
    if not os.path.isdir(d):
        continue
    for f in sorted(os.listdir(d)):
        if not f.endswith(".md"):
            continue
        n = f[:-3]
        text = open(os.path.join(d, f), errors="replace").read()
        fm, body = parse_frontmatter(text)
        # Skip explicitly noindex'd pages (e.g. the internal $1 debug product).
        if "noindex" in str(fm.get("robots", "")).lower():
            continue
        img = (fm.get("images") or [None])[0] if isinstance(fm.get("images"), list) else None
        docs.append({
            "title": fm.get("title", n),
            "url": urlfmt.format(n=n),
            "price": (fm.get("price") or fm.get("priceMin")) if sec == "products" else "",
            "image": img or "",
            "text": text_of(body)[:500],
        })
for f in ("cart/index.md", "search/index.md"):
    p = os.path.join(ROOT, "content", f)
    if os.path.exists(p):
        fm, _ = parse_frontmatter(open(p).read())
        docs.append({"title": fm.get("title", f), "url": "/" + f.split("/")[0] + "/",
                     "price": "", "image": "", "text": "cart search checkout shopping"})

os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump({"docs": docs}, open(OUT, "w"))
print(f"search-index.json: {len(docs)} docs")
