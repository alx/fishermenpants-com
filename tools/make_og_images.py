#!/usr/bin/env python3
"""Generate 1200x630 OpenGraph social cards for fishermenpants.com.

Social platforms crop previews to 1.91:1 (1200x630). Product photos here are
portrait or square (e.g. 476x473), so a hard crop either blurs (upscaling) or
slices the garment off. This script instead:

  1. Blurs + darkens a cover-scaled copy of the source as a full-bleed backdrop.
  2. Fits the *whole* source image inside the frame (contain, no cropping).
  3. Adds the brand wordmark and, optionally, a caption line.

That keeps the product intact at every source aspect ratio and never upscales
the garment past its native pixels.

Usage:
    tools/make_og_images.py                 # every product + collection + page
    tools/make_og_images.py --only samui-bag,fisherman-pants
    tools/make_og_images.py --force         # regenerate existing cards
    tools/make_og_images.py --page visit    # single non-product page

Output: static/img/og/<kind>--<name>.jpg (1200x630, quality 82, progressive)
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "static" / "img"
OUT = IMG / "og"
W, H = 1200, 630
QUALITY = 82

BRAND = "GAYA"
DOMAIN = "fishermenpants.com"

# DejaVu is a reliable serif stand-in for the brand's Cormorant Garamond.
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
FONT_BOLD_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    for path in (FONT_BOLD_CANDIDATES if bold else FONT_CANDIDATES):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def parse_frontmatter(text: str) -> dict:
    """Parse simple YAML front matter, joining multi-line flow lists.

    Product front matter uses flow lists spanning several lines:
        images: [
          "/img/a.png",
          "/img/b.png",
          ]
    so a line-by-line split would truncate them at the opening bracket.
    """
    m = re.match(r"^---\n(.*?)\n---\n?", text, re.S)
    if not m:
        return {}
    fm: dict = {}
    lines = m.group(1).split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if ":" not in line or line.startswith((" ", "-", "#")):
            i += 1
            continue
        key, val = line.split(":", 1)
        key, val = key.strip(), val.strip()
        # flow list opened but not closed on this line -> absorb following lines
        if val and val[0] in "[{" and val.count(val[0]) > val.count("]" if val[0] == "[" else "}"):
            closer = "]" if val[0] == "[" else "}"
            parts = [val]
            i += 1
            while i < len(lines) and closer not in parts[-1]:
                parts.append(lines[i].strip())
                i += 1
            val = " ".join(parts)
        fm[key] = val.strip('"')
        i += 1
    return fm


def first_image(fm: dict) -> str | None:
    """First path inside the YAML `images: [ ... ]` block."""
    m = re.search(r"^images:\s*\[(.*?)\]", "\n".join(f"{k}: {v}" for k, v in fm.items()), re.S | re.M)
    if not m:
        return None
    paths = re.findall(r'"([^"]+)"', m.group(1))
    return paths[0] if paths else None


def source_for(kind: str, name: str) -> tuple[Path | None, str]:
    """Return (source image path, caption) for a product/collection."""
    d = ROOT / "content" / kind
    f = d / f"{name}.md"
    if not f.exists():
        return None, name
    fm = parse_frontmatter(f.read_text(errors="replace"))
    title = re.sub(r"\s+", " ", fm.get("title", name)).strip()

    img = first_image(fm)
    if not img and fm.get("image"):
        img = fm["image"]

    # Collections often have no image of their own: use their first product's.
    if not img and fm.get("products"):
        for handle in re.findall(r'"([^"]+)"', str(fm.get("products"))):
            pf = ROOT / "content" / "products" / f"{handle}.md"
            if pf.exists():
                pfm = parse_frontmatter(pf.read_text(errors="replace"))
                img = first_image(pfm)
                if img:
                    break

    if not img:
        return None, title
    p = IMG / str(img).lstrip("/").removeprefix("img/")
    return (p if p.exists() else None), title


def backdrop(src: Image.Image) -> Image.Image:
    """Cover-scaled, blurred, darkened copy of the source filling the frame."""
    sw, sh = src.size
    scale = max(W / sw, H / sh)
    bd = src.convert("RGB").resize((max(W, round(sw * scale)), max(H, round(sh * scale))), Image.LANCZOS)
    left = (bd.width - W) // 2
    top = (bd.height - H) // 2
    bd = bd.crop((left, top, left + W, top + H))
    bd = bd.filter(ImageFilter.GaussianBlur(28))
    # darken so foreground text always has contrast
    overlay = Image.new("RGB", (W, H), (12, 18, 24))
    return Image.blend(bd, overlay, 0.55)


def build_card(src_path: Path, caption: str, kind: str) -> Image.Image:
    src = Image.open(src_path).convert("RGB")
    card = backdrop(src)

    # Contain the full product, inset from the edges.
    pad = 46
    max_w, max_h = W - pad * 2 - 40, H - pad * 2
    sw, sh = src.size
    scale = min(max_w / sw, max_h / sh)
    # Never upscale past native pixels by more than 1.15x (keeps it sharp).
    scale = min(scale, 1.15)
    fw, fh = round(sw * scale), round(sh * scale)
    fg = src.resize((fw, fh), Image.LANCZOS)

    # Subtle drop shadow so the panel separates from the blurred backdrop.
    shadow = Image.new("RGBA", (fw + 60, fh + 60), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        (30, 30, 30 + fw, 30 + fh), radius=18, fill=(0, 0, 0, 150))
    shadow = shadow.filter(ImageFilter.GaussianBlur(16))
    card = card.convert("RGBA")
    px, py = (W - fw) // 2, (H - fh) // 2
    card.alpha_composite(shadow, (px - 30, py - 30))
    card.paste(fg, (px, py))

    d = ImageDraw.Draw(card)

    # Brand wordmark, top-left.
    d.text((48, 34), BRAND, font=font(40, bold=True), fill=(255, 255, 255, 235))

    # Caption, bottom, with a soft scrim for legibility.
    scrim_h = 104
    scrim = Image.new("RGBA", (W, scrim_h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(scrim)
    for i in range(scrim_h):
        a = int(190 * (i / scrim_h) ** 0.7)
        sd.line([(0, i), (W, i)], fill=(10, 14, 18, a))
    card.alpha_composite(scrim, (0, H - scrim_h))

    d.text((48, H - scrim_h + 16), caption[:70], font=font(34), fill=(255, 255, 255, 245))
    d.text((48, H - scrim_h + 60), DOMAIN, font=font(22), fill=(255, 255, 255, 170))

    return card.convert("RGB")


def build_plain(src_paths: list[Path], title: str, subtitle: str = "") -> Image.Image:
    """Multi-image card for pages without a single hero product (about, visit...)."""
    base = backdrop(Image.open(src_paths[0]).convert("RGB")) if src_paths else Image.new("RGB", (W, H), (12, 18, 24))
    card = base.convert("RGBA")

    if len(src_paths) >= 2:
        # two-up strip of fitted images, centred
        box_w, box_h = 380, H - 200
        for i, p in enumerate(src_paths[:2]):
            im = Image.open(p).convert("RGB")
            s = min(box_w / im.width, box_h / im.height)
            im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
            x = W // 2 - box_w - 12 if i == 0 else W // 2 + 12
            card.alpha_composite(
                im.convert("RGBA"),
                (max(0, x + (box_w - im.width) // 2), 108 + (box_h - im.height) // 2),
            )

    d = ImageDraw.Draw(card)
    d.text((48, 40), BRAND, font=font(38, bold=True), fill=(255, 255, 255, 235))
    d.text((48, H - 150), title[:60], font=font(46, bold=True), fill=(255, 255, 255, 250))
    if subtitle:
        d.text((48, H - 92), subtitle[:85], font=font(24), fill=(255, 255, 255, 205))
    d.text((48, H - 52), DOMAIN, font=font(20), fill=(255, 255, 255, 160))
    return card.convert("RGB")


# Non-product pages: title, subtitle, candidate photos (first that exists wins).
PAGES = {
    "visit": ("Visit the shop", "Lamai Beach, Koh Samui — open daily 9:00–19:30",
              ["shop/gaya-shopfront-night.jpg", "shop/gaya-shop-interior.jpg"]),
    "about": ("GAYA — boutique by the sea", "Handmade Thai clothing, made with care",
              ["shop/gaya-shop-interior.jpg", "shop/gaya-shopfront-night.jpg"]),
    "contact": ("Contact & find us", "Had Lamai Road, Koh Samui — open every day",
                ["shop/gaya-shopfront-night.jpg"]),
    "shipping-returns": ("Shipping & returns", "Free worldwide shipping from Koh Samui",
                         ["shop/gaya-shop-interior.jpg"]),
    "size-guide": ("Size guide", "One size, generous cut — how to measure",
                   ["shop/gaya-shop-interior.jpg"]),
    "payment-methods": ("Payment methods", "PayPal and crypto — simple and secure",
                        ["shop/gaya-shopfront-night.jpg"]),
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", default="", help="comma-separated names/kind--name")
    ap.add_argument("--force", action="store_true", help="regenerate existing cards")
    ap.add_argument("--page", default="", help="only this non-product page")
    args = ap.parse_args()
    only = {n.strip() for n in args.only.split(",") if n.strip()}

    OUT.mkdir(parents=True, exist_ok=True)
    made = skipped = missing = 0

    for kind in ("products", "collections"):
        for f in sorted((ROOT / "content" / kind).glob("*.md")):
            name = f.stem
            kind_name = f"{kind[:-1]}--{name}"
            if only and name not in only and kind_name not in only:
                continue
            fm = parse_frontmatter(f.read_text(errors="replace"))
            if "noindex" in str(fm.get("robots", "")).lower():
                continue  # debug product stays out of social
            dest = OUT / f"{kind_name}.jpg"
            if dest.exists() and not args.force:
                skipped += 1
                continue
            src, caption = source_for(kind, name)
            if not src:
                print(f"  ! no usable image for {kind_name}")
                missing += 1
                continue
            build_card(src, caption, kind).save(dest, "JPEG", quality=QUALITY, optimize=True, progressive=True)
            made += 1

    for slug, (title, subtitle, candidates) in PAGES.items():
        if (only or args.page) and slug not in only and slug != args.page:
            continue
        dest = OUT / f"page--{slug}.jpg"
        if dest.exists() and not args.force:
            skipped += 1
            continue
        srcs = [IMG / c for c in candidates if (IMG / c).exists()]
        if not srcs:
            print(f"  ! no photo available for page--{slug}")
            missing += 1
            continue
        build_plain(srcs, title, subtitle).save(dest, "JPEG", quality=QUALITY, optimize=True, progressive=True)
        made += 1

    total = sum(f.stat().st_size for f in OUT.glob("*.jpg"))
    print(f"og cards: {made} written, {skipped} up to date, {missing} missing images")
    print(f"  {len(list(OUT.glob('*.jpg')))} cards, {total / 1e6:.1f} MB total, in {OUT.relative_to(ROOT)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
