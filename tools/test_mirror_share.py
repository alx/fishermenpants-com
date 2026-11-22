#!/usr/bin/env python3
"""Regression tests for the Mirror: consent copy + share buttons.

The Mirror captures a person's image, so two promises must stay true:
  1. The consent line appears BEFORE the camera is ever requested.
  2. Sharing shares the PAGE, never the photo (there is no upload).

Run after build.sh, against public/. Stdlib only, no network, no browser.

Checks
  1. consent copy is present on the setup step and precedes the start button
  2. share targets exist with the right hosts and an ABSOLUTE /mirror/ URL
  3. no share URL carries a data:/blob: image (the preview must never be shared)
  4. no third-party share SDK scripts (intent URLs only -> no extra cookie banner)
  5. share icons are resolvable: every fa-* class used exists in the CSS bundle,
     and the icon rule sets the brand font-family explicitly (the CSS bundle
     does not apply it via .fa-brands alone)
  6. privacy policy has the mirror section and the anchor the consent links to
Exit 0 on success, 1 on any failure.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC = os.path.join(ROOT, "public")
ok = True


def fail(msg):
    global ok
    ok = False
    print("FAIL:", msg)


def read(*parts):
    p = os.path.join(PUBLIC, *parts)
    if not os.path.exists(p):
        return None
    return open(p, errors="replace").read()


mirror = read("mirror", "index.html")
if mirror is None:
    fail("public/mirror/index.html missing - run build.sh first")
    print("MIRROR_SHARE FAILED")
    sys.exit(1)

policy = read("privacy-policy", "index.html")
css_brands = read("css", "fa-brands.min.css")
css_site = read("css", "style.css")
share_css = read("css", "style.css") or ""


# --------------------------------------------------------------------------
# 1. consent before the camera button
# --------------------------------------------------------------------------
print("checking consent copy precedes the camera start button...")
consent_at = mirror.find("mirror-consent")
start_at = mirror.find("mirror-start")
if consent_at < 0:
    fail("mirror: consent block (mirror-consent) not found on the page")
elif start_at < 0:
    fail("mirror: start button (mirror-start) not found")
elif consent_at > start_at:
    fail("mirror: consent copy appears AFTER the camera button - it must come first")
else:
    print(f"consent at char {consent_at}, start button at {start_at}: consent first")

# the promise must actually be stated, not just an empty container
if "never sent to us" not in mirror and "never sent" not in mirror:
    fail("mirror: consent copy does not state that the photo is not sent to us")

# camera must only be requested through the user's click (no autoplay capture)
js = read("js", "mirror.js") or ""
if re.search(r"^\s*(await\s+)?navigator\.mediaDevices\.getUserMedia", js, re.M):
    fail("mirror.js: getUserMedia appears to run at load, not on user action")
else:
    print("getUserMedia is only invoked from the start/again handlers")


# --------------------------------------------------------------------------
# 2. share targets present, absolute URL, correct hosts
# --------------------------------------------------------------------------
print("checking share targets...")
share_block = ""
i = mirror.find("mirror-share")
if i < 0:
    fail("mirror: share block (mirror-share) not found")
else:
    tag = mirror.rfind("<div", 0, i)
    end = mirror.find("</p>", mirror.find("mirror-share-status", i))
    share_block = mirror[tag:end + 4]

EXPECTED = {
    "WhatsApp": "wa.me",
    "Facebook": "facebook.com/sharer",
    "Pinterest": "pinterest.com/pin/create",
    "X": "x.com/intent",
}
hrefs = re.findall(r'href=["\']?([^"\'\s>]+)', share_block)
for name, host in EXPECTED.items():
    if name.lower() not in share_block.lower():
        fail(f"mirror: share target {name} missing")
        continue
    hit = [h for h in hrefs if host in h]
    if not hit:
        fail(f"mirror: share target {name} has no href containing {host}")
        continue
    print(f"  {name}: {hit[0][:70]}...")
    if "fishermenpants.com" not in hit[0]:
        fail(f"mirror: {name} share URL is not absolute (needs the live domain): {hit[0][:90]}")


# --------------------------------------------------------------------------
# 3. never share the image itself
# --------------------------------------------------------------------------
print("checking no share URL leaks the preview image...")
for h in hrefs:
    if h.startswith("data:") or h.startswith("blob:"):
        fail(f"mirror: share href carries a local image: {h[:60]}")
if not re.search(r"data:|blob:", share_block):
    print("no data:/blob: references in the share block")


# --------------------------------------------------------------------------
# 4. intent URLs only, no third-party SDK
# --------------------------------------------------------------------------
print("checking no third-party share SDK scripts...")
BANNED = ("connect.facebook.net", "platform.twitter.com", "assets.pinterest.com",
          "platform.linkedin.com", "addthis.com", "sharethis.com")
for b in BANNED:
    if b in mirror:
        fail(f"mirror: third-party share SDK referenced ({b}) - use intent URLs only")
if not any(b in mirror for b in BANNED):
    print("no share SDK scripts present")


# --------------------------------------------------------------------------
# 5. icons resolve and the font-family is set explicitly
# --------------------------------------------------------------------------
print("checking share icons resolve in the CSS bundle...")
used = set(re.findall(r"fa-(?:brands|solid)\s+(fa-[a-z0-9-]+)", share_block))
used |= set(re.findall(r'class="[^"]*\b(fa-[a-z0-9-]+)\b', share_block))
used = {u for u in used if u not in ("fa-brands", "fa-solid")}
if not used:
    fail("mirror: no fa-* icon classes found in the share block")
for icon in sorted(used):
    if css_brands and f".{icon}" not in css_brands:
        fail(f"mirror: icon class '{icon}' is not defined in css/fa-brands.min.css "
             f"(the bundled font only contains brand glyphs)")
if css_site and "mirror-share-btn i" in css_site:
    seg = css_site[css_site.find("mirror-share-btn i"):]
    seg = seg[:seg.find("}")] if "}" in seg else seg
    if "Font Awesome 6 Brands" not in seg:
        fail("style.css: .mirror-share-btn i must set font-family 'Font Awesome 6 Brands' "
             "explicitly - the bundle does not apply it via .fa-brands alone")
    else:
        print("share icon font-family is set explicitly")
print(f"icons checked: {', '.join(sorted(used)) or '(none)'}")


# --------------------------------------------------------------------------
# 6. privacy policy section + anchor
# --------------------------------------------------------------------------
print("checking privacy policy covers the mirror...")
if policy is None:
    fail("public/privacy-policy/index.html missing")
else:
    if "the-mirror-and-your-photo" not in mirror:
        fail("mirror: consent link does not point at the privacy section anchor")
    if "The Mirror and your photo" not in policy:
        fail("privacy policy: missing the 'The Mirror and your photo' section")
    elif not re.search(r"never reaches us|not uploaded", policy):
        fail("privacy policy: mirror section does not state that the photo is not sent to us")
    else:
        print("privacy section present and states the photo is not sent")

print()
print("MIRROR_SHARE OK" if ok else "MIRROR_SHARE FAILED")
sys.exit(0 if ok else 1)
