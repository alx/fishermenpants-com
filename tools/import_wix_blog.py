#!/usr/bin/env python3
"""Import blog posts (text + images) from the old Wix site into content/blog/.

Wix serves the post body in the HTML, plus its photos under
static.wixstatic.com/media/4c286c_* (the site's own media folder). Recurring
small images are site chrome (author avatar 128px, logo 225px) and are skipped.

Images are downloaded into static/img/blog/<slug>/NN.jpg and appended to the
post body as markdown, so the site keeps its own copy (Wix could disappear).

Usage:
    tools/import_wix_blog.py            # fetch + write posts with images
    tools/import_wix_blog.py --dry-run  # show what would be written
"""

from __future__ import annotations

import argparse
import html as H
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "content" / "blog"
MEDIA = ROOT / "static" / "img" / "blog"
BASE = "https://shmargad.wixsite.com/kohsamuishop/post/"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"

SLUGS = [
    "anyway",
    "fishing-for-compliments-get-yourself-down-to-fishermen-pants-shop-in-lamai",
    "multiple-purpose-free-size-thai-pants",
    "pair-your-thai-fisherman-pants-with-right-outfits-to-get-the-chic-look",
    "pants-that-make-a-difference",
    "sawadee-krap-hi-aloha",
]

# Site chrome that appears on every post (author avatar, logo) — never content.
CHROME = {
    "4c286c_5dcfe1efd9574c38976970b8dcdb7406~mv2.png",
    "4c286c_7a44d24fa1514da89e4ecbab4b40fdbb~mv2.png",
}

NOISE = (
    "This website was built on Wix",
    "Get Started",
    "Refunds & Cancelations",
    "Privacy policy",
    "Terms of Service",
    "Log In",
    "All Posts",
    "Subscribe",
    "Use tab to navigate",
    "Pants Island shirt Beach wear Accessories BLOG",
)

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def fetch(url: str, binary: bool = False):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        data = r.read()
    return data if binary else data.decode("utf-8", errors="replace")


def extract_text(raw: str) -> tuple[str, list[str], str]:
    paras: list[str] = []
    for chunk in re.findall(r"<p[^>]*>(.*?)</p>", raw, flags=re.S):
        txt = H.unescape(re.sub(r"<[^>]+>", " ", chunk))
        txt = re.sub(r"\s+", " ", txt).strip()
        if len(txt) < 35:
            continue
        if any(n.lower() in txt.lower() for n in NOISE):
            continue
        paras.append(txt)

    title = ""
    m = re.search(r"<title>(.*?)</title>", raw, re.S | re.I)
    if m:
        title = H.unescape(re.sub(r"\s+", " ", m.group(1))).strip()
        title = re.sub(r"\s*[|\-–]\s*(BLOG|Fisherman Pants Shop).*$", "", title, flags=re.I).strip()

    date = "2020-03-15"
    dm = re.search(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{1,2}),\s*(\d{4})", raw)
    if dm:
        mi = MONTHS.index(dm.group(1)[:3]) + 1
        date = f"{dm.group(3)}-{mi:02d}-{int(dm.group(2)):02d}"

    if paras:
        first = paras[0]
        cut = first.find("min read")
        if cut != -1:
            paras[0] = first[cut + len("min read"):].strip()
        if len(paras[0]) < 35:
            paras.pop(0)
    return title, paras, date


def media_names(raw: str) -> list[str]:
    """Ordered, de-duplicated asset names of the post's own photos."""
    names: list[str] = []
    for m in re.finditer(r'static\.wixstatic\.com/media/(4c286c_[^"/\\ ,]+)', raw):
        n = m.group(1)
        if n in CHROME or n in names:
            continue
        names.append(n)
    return names


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    written = imgs_total = 0

    for slug in SLUGS:
        try:
            raw = fetch(BASE + slug)
        except Exception as e:
            print(f"  ! {slug}: {e}")
            continue
        title, paras, date = extract_text(raw)
        if not paras:
            print(f"  ! {slug}: no body extracted")
            continue
        title = title or slug.replace("-", " ").title()

        rel_paths: list[str] = []
        for i, name in enumerate(media_names(raw), 1):
            ext = ".png" if name.lower().endswith(".png") else ".jpg"
            rel = f"img/blog/{slug}/{i:02d}{ext}"
            if args.dry_run:
                rel_paths.append(rel)
                continue
            dest = ROOT / "static" / rel
            try:
                data = fetch(f"https://static.wixstatic.com/media/{name}", binary=True)
                if len(data) < 2000:
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
                rel_paths.append(rel)
            except Exception:
                pass

        body = "\n\n".join(paras)
        if rel_paths:
            body += "\n\n" + "\n\n".join(
                f"![{title} — photo {i}](/{p})" for i, p in enumerate(rel_paths, 1))
            imgs_total += len(rel_paths)

        cover = f"\nimages:\n  - /{rel_paths[0]}" if rel_paths else ""
        doc = (
            "---\n"
            f"title: {title!r}\n"
            f"date: {date}T09:00:00+07:00\n"
            f"author: \"Erez Shmargad\"\n"
            f"description: {paras[0][:155]!r}\n"
            f'source: "{BASE}{slug}"{cover}\n'
            "draft: false\n"
            "---\n\n"
            f"{body}\n"
        )
        if args.dry_run:
            print(f"--- {slug}.md  ({len(paras)} paras, {len(rel_paths)} images)\n{doc[:300]}\n")
        else:
            (OUT / f"{slug}.md").write_text(doc)
            written += 1
            print(f"  ✓ {slug}.md — {len(paras)} paragraphs, {len(rel_paths)} images")

    print(f"\n{written} posts, {imgs_total} images downloaded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
