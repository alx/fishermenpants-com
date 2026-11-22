#!/usr/bin/env python3
"""Import blog posts from the old Wix site (kohsamuishop) into content/blog/.

Wix pages are JS-heavy but the post body is present in the served HTML as
`<p>` rich-text blocks. This strips the Wix chrome (nav, footer, "This website
was built on Wix", tag/meta lines) and writes one Hugo markdown file per post.

The 3 stock Wix template stubs are skipped by default.

Usage:
    tools/import_wix_blog.py            # fetch + write content/blog/*.md
    tools/import_wix_blog.py --dry-run  # print what would be written
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
BASE = "https://shmargad.wixsite.com/kohsamuishop/post/"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"

SLUGS = [
    "about-the-process",
    "amazing-talent",
    "anyway",
    "daimonds",
    "fishermen-pants-song",
    "fishing-for-compliments-get-yourself-down-to-fishermen-pants-shop-in-lamai",
    "multiple-purpose-free-size-thai-pants",
    "natural-dye-hand-woven-fabrics",
    "pair-your-thai-fisherman-pants-with-right-outfits-to-get-the-chic-look",
    "pants-that-make-a-difference",
    "sawadee-krap-hi-aloha",
    "thai-design-with-modern-flair",
    "change-to-relaxation-mode",
]

# Wix scaffolding that must never reach the article body.
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
)


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def extract(raw: str) -> tuple[str, list[str], str]:
    """Return (title, paragraphs, date_iso)."""
    paras: list[str] = []
    for p in re.findall(r"<p[^>]*>(.*?)</p>", raw, flags=re.S):
        txt = H.unescape(re.sub(r"<[^>]+>", " ", p))
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

    # Wix renders "Mar 15, 2020" inside the post header
    date = "2020-03-15"
    dm = re.search(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{1,2}),\s*(\d{4})", raw)
    if dm:
        months = {m: i for i, m in enumerate(
            ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}
        date = f"{dm.group(3)}-{months[dm.group(1)[:3]]:02d}-{int(dm.group(2)):02d}"

    # The first paragraph is usually the nav + title + "erez shmargad<date>N min read" blob.
    if paras:
        first = paras[0]
        cut = first.find("min read")
        if cut != -1:
            paras[0] = first[cut + len("min read"):].strip()
        if len(paras[0]) < 35:
            paras.pop(0)
    return title, paras, date


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    written = 0
    for slug in SLUGS:
        try:
            raw = fetch(BASE + slug)
        except Exception as e:  # network hiccup: report and continue
            print(f"  ! {slug}: {e}")
            continue
        title, paras, date = extract(raw)
        if not paras:
            print(f"  ! {slug}: no body extracted")
            continue
        title = title or slug.replace("-", " ").title()
        body = "\n\n".join(paras)
        doc = f"""---
title: {title!r}
date: {date}T09:00:00+07:00
author: "Erez Shmargad"
description: {paras[0][:155]!r}
source: "{BASE}{slug}"
draft: false
---

{body}
"""
        dest = OUT / f"{slug}.md"
        if args.dry_run:
            print(f"--- {dest.name}\n{doc[:400]}\n")
        else:
            dest.write_text(doc)
            written += 1
            print(f"  ✓ {dest.name} ({len(paras)} paragraphs, {len(body)} chars)")
    print(f"\n{written} posts written to {OUT.relative_to(ROOT)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
