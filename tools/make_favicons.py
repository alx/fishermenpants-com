#!/usr/bin/env python3
"""Generate the favicon / app-icon set from static/img/favicon.jpg.

The source is a 150x150 JPEG of the GAYA logo (yellow brush ring + white
wordmark on dark maroon). Browsers render favicons as small as 16px, where the
"boutique by the sea" line is unreadable, so this script also produces a
detail-reduced variant: the ring is kept and the strapline is dropped, which
stays legible at 16-32px.

Outputs (into static/img/):
  favicon-16.png  favicon-32.png  favicon-48.png     tab icons
  favicon-180.png                                    apple-touch-icon
  favicon-192.png favicon-512.png                    android / PWA manifest
  favicon.ico                                        16+32+48 multi-res
  logo.png                                            wide header wordmark (transparent bg)
  logo-*.webp                                         responsive header variants

Usage: python3 tools/make_favicons.py [--force]
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "static" / "img"
SRC = IMG / "favicon.jpg"

# The source is square with the wordmark roughly centred. Below this size the
# strapline turns to mush, so we crop to the ring + wordmark band only.
SMALL_ICONS = {16, 32, 48}
LARGE_ICONS = {180, 192, 512}

# Logo colours sampled from the source.
BG = (48, 26, 27)      # dark maroon surround


def load_source() -> Image.Image:
    im = Image.open(SRC).convert("RGB")
    if im.width != im.height:
        side = min(im.size)
        left = (im.width - side) // 2
        top = (im.height - side) // 2
        im = im.crop((left, top, left + side, top + side))
    return im


def crop_detail(im: Image.Image) -> Image.Image:
    """Keep the upper ~72% — the brush ring and 'gaya' wordmark, minus strapline."""
    h = im.height
    return im.crop((0, int(h * 0.06), im.width, int(h * 0.78)))


def square_pad(im: Image.Image, size: int, bg: tuple[int, int, int] = BG) -> Image.Image:
    """Fit im inside a size x size canvas, padding with the brand background."""
    scale = min(size / im.width, size / im.height)
    w, h = max(1, round(im.width * scale)), max(1, round(im.height * scale))
    canvas = Image.new("RGB", (size, size), bg)
    canvas.paste(im.resize((w, h), Image.LANCZOS), ((size - w) // 2, (size - h) // 2))
    return canvas


def make_logo(im: Image.Image) -> Image.Image:
    """Wide header wordmark on transparent background (mail/newsletter/preview use)."""
    crop = im.crop((int(im.width * 0.04), int(im.height * 0.22),
                    int(im.width * 0.96), int(im.height * 0.66)))
    return crop.resize((crop.width * 4, crop.height * 4), Image.LANCZOS)


def main() -> int:
    force = "--force" in sys.argv
    im = load_source()
    small_src = crop_detail(im)
    made = []

    for size in sorted(SMALL_ICONS | LARGE_ICONS):
        dest = IMG / f"favicon-{size}.png"
        if dest.exists() and not force:
            continue
        src = small_src if size in SMALL_ICONS else im
        square_pad(src, size).save(dest, "PNG", optimize=True)
        made.append(dest.name)

    # apple-touch-icon: iOS masks corners itself, so use the full logo, no rounding
    ico = IMG / "favicon.ico"
    if force or not ico.exists():
        ims = [square_pad(small_src, s) for s in (16, 32, 48)]
        ims[0].save(ico, format="ICO", sizes=[(16, 16), (32, 32), (48, 48)], append_images=ims[1:])
        made.append(ico.name)

    # header logo + responsive variants
    logo = make_logo(im)
    lp = IMG / "logo.png"
    if force or not lp.exists():
        logo.save(lp, "PNG", optimize=True)
        made.append(lp.name)
    gen = IMG / "_gen"
    gen.mkdir(exist_ok=True)
    for w in (200, 400, 800):
        if w > logo.width:
            continue
        h = round(logo.height * w / logo.width)
        dest = gen / f"logo-{w}.webp"
        if force or not dest.exists():
            logo.resize((w, h), Image.LANCZOS).save(dest, "WEBP", quality=90, method=6)
            made.append(dest.name)

    print(f"icons written: {len(made)} -> {', '.join(made) if made else 'nothing to do'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
