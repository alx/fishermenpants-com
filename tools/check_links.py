#!/usr/bin/env python3
"""Link integrity checks for the built site.

Guards against the class of bug that shipped twice: a page living at
/pages/mirror/ while people (and our own templates) linked to /mirror/, and CI
deploying it happily because nothing verified internal links.

Run after build.sh, against public/. Stdlib only, no network.

Sections
  1. every internal link resolves to something in public/
  2. no real page links to a retired /pages/<slug>/ path (aliases only)
  3. every content/pages/*.md declares an explicit url:
  4. every renamed page has an alias covering its old path
  5. canonical / og:url on each page point at that page itself
  6. retired-prefix strings in source code are accounted for
Exit 0 on success, 1 on any failure.
"""
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC = os.path.join(ROOT, "public")
ok = True

# Pages that have been moved off the /pages/ prefix, and where they live now.
# Keep in sync with content/pages/*.md when adding a rename.
RENAMED = {
    "about": "about",
    "contact": "contact",
    "payment-methods": "payment-methods",
    "privacy-policy": "privacy-policy",
    "shipping-returns": "shipping-returns",
    "size-guide": "size-guide",
    "visit": "visit",
    "mirror": "mirror",
}

# Non-HTML extensions that are legitimately served as files.
ASSET_EXT = (
    ".css", ".js", ".json", ".png", ".jpg", ".jpeg", ".webp", ".svg", ".ico",
    ".gif", ".xml", ".txt", ".woff", ".woff2", ".ttf", ".wasm", ".tflite",
    ".manifest", ".webmanifest", ".pdf", ".map",
)


def fail(msg):
    global ok
    ok = False
    print("FAIL:", msg)


def public_path(url_path):
    """Map a site-relative URL path to a filesystem path under public/."""
    p = url_path.lstrip("/")
    return os.path.join(PUBLIC, p) if p else PUBLIC


def resolves(url_path):
    """True if this site-relative URL is served by the build."""
    if url_path in ("", "/"):
        return os.path.exists(os.path.join(PUBLIC, "index.html"))
    fs = public_path(url_path)
    if os.path.isfile(fs):
        return True
    if os.path.isdir(fs):
        return os.path.exists(os.path.join(fs, "index.html"))
    # pretty URL without trailing slash: /about -> public/about/index.html
    if os.path.exists(os.path.join(fs, "index.html")):
        return True
    return False


def html_files():
    return sorted(glob.glob(os.path.join(PUBLIC, "**", "*.html"), recursive=True))


def is_alias_stub(text):
    """Hugo alias stubs are a tiny page with a meta refresh and no content."""
    return (
        "http-equiv=refresh" in text.replace('"', "")
        or 'http-equiv="refresh"' in text
    ) and len(text) < 1200


# --------------------------------------------------------------------------
# 1. every internal link resolves
# --------------------------------------------------------------------------
print("checking internal links resolve...")
checked = 0
broken = {}
for f in html_files():
    rel = os.path.relpath(f, PUBLIC)
    text = open(f, errors="replace").read()
    for m in re.finditer(r'(?:href|src)=["\']?(/[^"\'>\s]*)', text):
        url = m.group(1)
        if url.startswith("//"):  # protocol-relative, external
            continue
        url = url.split("#")[0].split("?")[0].rstrip()
        if not url:
            continue
        # ignore pure-extremal-looking and data URIs
        if url.startswith(("data:", "mailto:", "tel:", "javascript:")):
            continue
        checked += 1
        if not resolves(url):
            broken.setdefault(url, []).append(rel)
if len(broken) > 15:
    for url in sorted(broken)[:15]:
        fail(f"broken internal link {url}  ({len(broken[url])} page(s))")
    fail(f"...and {len(broken) - 15} more distinct broken URLs "
         f"({sum(len(v) for v in broken.values())} references total)")
else:
    for url, pages in sorted(broken.items()):
        shown = ", ".join(sorted(set(pages))[:3])
        more = f" (+{len(pages)-3} more)" if len(pages) > 3 else ""
        fail(f"broken internal link {url}  referenced by {shown}{more}")
print(f"checked {checked} internal link references across {len(html_files())} files")


# --------------------------------------------------------------------------
# 2. real pages must not link to retired /pages/<slug>/ paths
# --------------------------------------------------------------------------
print("checking no real page links to a retired /pages/ path...")
offenders = 0
retired_pages = {}
for f in html_files():
    text = open(f, errors="replace").read()
    if is_alias_stub(text):
        continue  # the stub itself is allowed to point at the new URL
    rel = os.path.relpath(f, PUBLIC)
    for m in re.finditer(r'(?:href|src)=["\']?(/pages/[^"\'>\s]*)', text):
        url = m.group(1).split("#")[0].split("?")[0].rstrip("/")
        slug = url[len("/pages/"):]
        if slug in RENAMED:
            retired_pages.setdefault(slug, set()).add(rel)
            offenders += 1
if not offenders:
    print("no real page links to a retired /pages/ path")
else:
    for slug in sorted(retired_pages):
        where = sorted(retired_pages[slug])
        shown = ", ".join(where[:2]) + (f" (+{len(where)-2} more)" if len(where) > 2 else "")
        fail(f"{len(where)} page(s) link to retired /pages/{slug}/ -> should be "
             f"/{RENAMED[slug]}/  [{shown}]")


# --------------------------------------------------------------------------
# 3. every content/pages/*.md declares an explicit url:
# --------------------------------------------------------------------------
print("checking content/pages/*.md declare explicit url...")
page_files = sorted(glob.glob(os.path.join(ROOT, "content", "pages", "*.md")))
for f in page_files:
    name = os.path.basename(f)
    head = open(f, errors="replace").read().split("---")[1] if "---" in open(f, errors="replace").read() else ""
    if not re.search(r"^url:\s*['\"]?/", head, re.M):
        fail(f"content/pages/{name}: missing explicit 'url:' in front matter")
print(f"checked {len(page_files)} page front matters")


# --------------------------------------------------------------------------
# 4. renamed pages expose an alias for their old path
# --------------------------------------------------------------------------
print("checking renames have aliases for the old path...")
alias_dir = os.path.join(ROOT, "content", "pages")
for slug in RENAMED:
    cand = os.path.join(alias_dir, f"{slug}.md")
    if not os.path.exists(cand):
        continue
    text = open(cand, errors="replace").read()
    if re.search(r"^\s*-\s*['\"]?/pages/" + re.escape(slug) + r"/?['\"]?\s*$", text, re.M):
        continue
    # accept a quoted form without trailing slash too
    if "/pages/" + slug in text:
        continue
    fail(f"{slug}.md: no alias covering the old /pages/{slug}/ path")


# --------------------------------------------------------------------------
# 5. canonical and og:url point at the page itself
# --------------------------------------------------------------------------
print("checking canonical / og:url are self-referential...")
BASE = "https://www.fishermenpants.com"
mismatch = 0
for f in html_files():
    text = open(f, errors="replace").read()
    if is_alias_stub(text):
        continue
    rel = os.path.relpath(f, PUBLIC)
    if rel == "404.html":
        continue  # error page: not addressable at a canonical URL of its own
    expected = "/" + os.path.dirname(rel).replace(os.sep, "/")
    expected = expected.rstrip("/") + "/" if expected != "/." else "/"
    if expected == "/.":
        expected = "/"
    for attr, pat in (
        ("canonical", r'<link[^>]+rel=["\']?canonical["\']?[^>]+href=["\']?([^"\'>\s]+)'),
        ("og:url", r'<meta[^>]+property=["\']?og:url["\']?[^>]+content=["\']?([^"\'>\s]+)'),
    ):
        m = re.search(pat, text)
        if not m:
            continue
        got = m.group(1).replace(BASE, "")
        got = got.split("?")[0]
        a, b = got.rstrip("/"), expected.rstrip("/")
        if a != b and a != b + "/index.html":
            fail(f"{rel}: {attr} is {got!r}, expected {expected!r}")
            mismatch += 1
print(f"canonical/og:url checked, {mismatch} mismatch(es)")


# --------------------------------------------------------------------------
# 6. retired-prefix strings in source are accounted for
# --------------------------------------------------------------------------
print("checking source for stray /pages/ references...")
SOURCE_GLOBS = [
    "layouts/**/*.html",
    "content/**/*.md",
    "tools/*.py",
    "static/llms.txt",
    "static/admin/config.yml",
]
stray = 0
for pattern in SOURCE_GLOBS:
    for f in glob.glob(os.path.join(ROOT, pattern), recursive=True):
        rel = os.path.relpath(f, ROOT)
        if rel.startswith("content/pages/"):
            continue  # front matter aliases and cross-links handled elsewhere
        if rel == os.path.join("tools", "check_links.py"):
            continue  # this file names the retired paths on purpose
        text = open(f, errors="replace").read()
        for slug in RENAMED:
            # Form A: literal absolute link  "href=/pages/about/"
            # Form B: Hugo template func     {{ "pages/about/" | relURL }}
            # Form C: absolute URL in tools   "/pages/about/"
            pat = (
                r'["\'](?:/)?pages/' + re.escape(slug) + r'/?["\']'
                r'|["\']pages["\']\s*,\s*["\'][^"\']*pages/'
            )
            hit_lines = {
                text.count("\n", 0, m.start()) + 1 for m in re.finditer(pat, text)
            }
            if hit_lines:
                where = ", ".join(f"L{n}" for n in sorted(hit_lines)[:4])
                fail(f"{rel}: hardcoded retired path for '{slug}' at {where}")
                stray += 1
if not stray:
    print("no stray rendered /pages/ links in source")

print()
print("CHECK_LINKS OK" if ok else "CHECK_LINKS FAILED")
sys.exit(0 if ok else 1)
