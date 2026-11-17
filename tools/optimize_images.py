#!/usr/bin/env python3
"""Generate responsive WebP/JPEG variants for static/img.

Originals stay untouched in static/img/. Variants go to static/img/_gen/<name>-<w>.webp
so Hugo copies them as plain static files (no Hugo image processing needed) and the
image partial can emit a srcset.

Usage: python3 tools/optimize_images.py [--force] [--limit N]
"""
import json
import os
import sys
import glob

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "static", "img")
OUT = os.path.join(SRC, "_gen")

WIDTHS = (400, 800, 1200, 1600, 2000)  # 1600/2000 feed 2x DPR on wide viewports
EXT = (".png", ".jpg", ".jpeg")
WEBP_QUALITY = 78
JPEG_QUALITY = 80
FORCE = "--force" in sys.argv


def variants(widths, src_w):
    """Widths worth generating: never upscale."""
    return sorted({w for w in widths if w < src_w} | ({src_w} if src_w < max(widths) else set()))


def main():
    os.makedirs(OUT, exist_ok=True)
    files = []
    for ext in EXT:
        files += glob.glob(os.path.join(SRC, "*" + ext))
    files = [f for f in files if not os.path.basename(f).startswith("og-")]

    manifest = {}
    made = skipped = 0
    total_bytes = 0
    for path in sorted(files):
        name = os.path.splitext(os.path.basename(path))[0]
        try:
            im = Image.open(path)
        except Exception as e:  # unreadable file: skip, don't fail the build
            print(f"  skip (unreadable) {os.path.basename(path)}: {e}")
            skipped += 1
            continue

        src_w, src_h = im.size
        manifest[name] = {
            "w": src_w,
            "h": src_h,
            "widths": variants(WIDTHS, src_w),
        }
        has_alpha = im.mode in ("RGBA", "LA") or (
            im.mode == "P" and "transparency" in im.info
        )
        # WebP keeps alpha; convert non-alpha PNGs to RGB for a smaller file
        webp_im = im if has_alpha else im.convert("RGB")

        for w in variants(WIDTHS, src_w):
            dest = os.path.join(OUT, f"{name}-{w}.webp")
            if os.path.exists(dest) and not FORCE:
                if os.path.getmtime(dest) >= os.path.getmtime(path):
                    skipped += 1
                    continue
            h = max(1, round(src_h * w / src_w))
            resized = webp_im.resize((w, h), Image.LANCZOS)
            resized.save(dest, "WEBP", quality=WEBP_QUALITY, method=4)
            total_bytes += os.path.getsize(dest)
            made += 1

        # JPEG fallback for browsers without WebP (only when the source is not transparent)
        if not has_alpha:
            for w in variants(WIDTHS, src_w):
                dest = os.path.join(OUT, f"{name}-{w}.jpg")
                if os.path.exists(dest) and not FORCE:
                    if os.path.getmtime(dest) >= os.path.getmtime(path):
                        continue
                h = max(1, round(src_h * w / src_w))
                im.convert("RGB").resize((w, h), Image.LANCZOS).save(
                    dest, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True
                )
                made += 1

    with open(os.path.join(OUT, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, separators=(",", ":"))

    print(f"images: {made} variants generated, {skipped} up to date, {total_bytes/1e6:.1f} MB written")


if __name__ == "__main__":
    main()
