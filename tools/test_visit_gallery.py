#!/usr/bin/env python3
"""Visit gallery regression tests: photo removal + PhotoSwipe lightbox.

Guards three failures that are all silent in the browser:
  - a removed photo creeping back into the gallery
  - a gallery link missing data-pswp-width/height (PhotoSwipe then refuses to
    open, with no error at all)
  - declared dimensions disagreeing with the real image file

Run after build.sh, against public/. Stdlib only, no network, no browser.

Checks
  1. the gaya-shop-interior photo is gone from every variant
  2. gallery link count matches data/shop.yaml
  3. every link has positive integer data-pswp-width and data-pswp-height
  4. every lightbox href resolves to a real file under public/
  5. declared dimensions match the ACTUAL image file dimensions
  6. PhotoSwipe assets are vendored and referenced from /visit/ only
  7. thumbnails are in the static HTML (works with JS disabled)
"""
import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC = os.path.join(ROOT, "public")
ok = True


def fail(msg):
    global ok
    ok = False
    print("FAIL:", msg)


def read(path):
    return open(path, errors="replace").read() if os.path.exists(path) else None


visit_path = os.path.join(PUBLIC, "visit", "index.html")
visit = read(visit_path)
if visit is None:
    fail("public/visit/index.html missing - run build.sh first")
    print("VISIT_GALLERY FAILED")
    sys.exit(1)


def webp_size(path):
    """Width/height from a WebP header (stdlib only)."""
    with open(path, "rb") as fh:
        d = fh.read(64)
    if d[:4] != b"RIFF" or d[8:12] != b"WEBP":
        return None
    fmt = d[12:16]
    if fmt == b"VP8X":
        return (1 + int.from_bytes(d[24:27], "little"),
                1 + int.from_bytes(d[27:30], "little"))
    if fmt == b"VP8 ":
        return (int.from_bytes(d[26:28], "little") & 0x3FFF,
                int.from_bytes(d[28:30], "little") & 0x3FFF)
    return None


def jpeg_size(path):
    with open(path, "rb") as fh:
        data = fh.read()
    i = 2
    while i < len(data) - 9:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return w, h
        if marker in (0xD8, 0xD9):
            i += 2
            continue
        seg = struct.unpack(">H", data[i + 2:i + 4])[0]
        i += 2 + seg
    return None


def png_size(path):
    with open(path, "rb") as fh:
        d = fh.read(26)
    if d[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", d[16:24])


def image_size(path):
    ext = os.path.splitext(path)[1].lower()
    return {"webp": webp_size, "jpg": jpeg_size, "jpeg": jpeg_size,
            "png": png_size}.get(ext.lstrip("."), lambda p: None)(path)


# --------------------------------------------------------------------------
# 1. removed photo must not reappear
# --------------------------------------------------------------------------
print("checking the removed photo is gone...")
if re.search(r"gaya-shop-interior", visit):
    fail("visit page still references gaya-shop-interior (photo should be removed)")
else:
    print("gaya-shop-interior absent from /visit/")


# --------------------------------------------------------------------------
# 2. gallery count matches the data file
# --------------------------------------------------------------------------
print("checking gallery count...")
yaml_path = os.path.join(ROOT, "data", "shop.yaml")
expected = None
if os.path.exists(yaml_path):
    text = open(yaml_path, errors="replace").read()
    m = re.search(r"^gallery:\s*$(.*?)(?=^\S|\Z)", text, re.M | re.S)
    if m:
        expected = len(re.findall(r"^\s*-\s*src:", m.group(1), re.M))
links = re.findall(r"<a[^>]+class=\"?visit-photo-link\"?[^>]*>", visit)
links = links or re.findall(r"<a[^>]+visit-photo-link[^>]*>", visit)
if expected is None:
    fail("could not parse data/shop.yaml gallery count")
elif len(links) != expected:
    fail(f"gallery: {len(links)} lightbox links in HTML, {expected} entries in data/shop.yaml")
else:
    print(f"gallery: {len(links)} links matches data/shop.yaml")


# --------------------------------------------------------------------------
# 3 + 4 + 5. dimensions present, href resolves, dimensions match the file
# --------------------------------------------------------------------------
print("checking lightbox links...")
for a in links:
    href = re.search(r'href=\"?([^\"\s>]+)', a)
    dw = re.search(r'data-pswp-width=\"?(\d+)', a)
    dh = re.search(r'data-pswp-height=\"?(\d+)', a)
    if not href:
        fail(f"gallery link without href: {a[:70]}")
        continue
    url = href.group(1)
    if not dw or not dh:
        fail(f"{url}: missing data-pswp-width/height - PhotoSwipe will silently "
             f"refuse to open this photo")
        continue
    if int(dw.group(1)) <= 0 or int(dh.group(1)) <= 0:
        fail(f"{url}: non-positive data-pswp dimensions")
        continue
    fs = os.path.join(PUBLIC, url.lstrip("/"))
    if not os.path.isfile(fs):
        fail(f"{url}: lightbox target does not exist in public/")
        continue
    actual = image_size(fs)
    if actual is None:
        fail(f"{url}: could not read image dimensions")
        continue
    declared = (int(dw.group(1)), int(dh.group(1)))
    if actual != declared:
        fail(f"{url}: declares {declared[0]}x{declared[1]} but the file is "
             f"{actual[0]}x{actual[1]}")
    else:
        print(f"  {os.path.basename(url):38s} {declared[0]}x{declared[1]} OK")


# --------------------------------------------------------------------------
# 6. PhotoSwipe vendored, and only on /visit/
# --------------------------------------------------------------------------
print("checking PhotoSwipe assets...")
for asset in ("photoswipe/photoswipe.css", "photoswipe/photoswipe.esm.min.js",
              "photoswipe/photoswipe-lightbox.esm.min.js", "photoswipe/LICENSE"):
    if not os.path.isfile(os.path.join(PUBLIC, asset.replace("photoswipe/", "photoswipe/"))):
        fail(f"vendored asset missing from build: /{asset}")
if "photoswipe" not in visit:
    fail("visit page does not reference PhotoSwipe")
# must not leak site-wide
other_pages = 0
for dirpath, _dirs, files in os.walk(PUBLIC):
    if os.path.abspath(dirpath).startswith(os.path.abspath(os.path.join(PUBLIC, "visit"))):
        continue
    for f in files:
        if not f.endswith(".html"):
            continue
        p = os.path.join(dirpath, f)
        if "photoswipe" in open(p, errors="replace").read():
            fail(f"PhotoSwipe leaks onto {os.path.relpath(p, PUBLIC)} (should be /visit/ only)")
            other_pages += 1
if other_pages == 0:
    print("PhotoSwipe assets present and scoped to /visit/")


# --------------------------------------------------------------------------
# 7. thumbnails are real HTML (no-JS)
# --------------------------------------------------------------------------
print("checking no-JS fallback...")
if len(re.findall(r"<img[^>]+visit|class=\"?visit-photo-link\"?[^>]*>\s*<picture", visit)) == 0:
    if "<picture" not in visit:
        fail("no <picture>/<img> thumbnails in the static HTML - gallery would be "
             "empty without JS")
    else:
        print("thumbnails present in static HTML")
else:
    print("thumbnails present in static HTML")

print()
print("VISIT_GALLERY OK" if ok else "VISIT_GALLERY FAILED")
sys.exit(0 if ok else 1)
