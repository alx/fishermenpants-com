#!/usr/bin/env python3
"""Mobile layout regression tests: no horizontal overflow on phone widths.

The bug this guards: the landing-page interstitials (.iwt) stretched the whole
document wider than the phone screen, so the h2 looked like it overflowed to the
right and the page could be swiped sideways.

Cause: .iwt-media had `aspect-ratio: 4/3` PLUS `min-height: 340px`, which forces
a MINIMUM WIDTH of 340 * 4/3 = 453px — wider than a 375px phone. Grid children
also default to min-width:auto, so the 1fr column refused to shrink below it.

This check is static (parses the CSS) so it stays fast and hermetic. The live
geometry was verified separately with Chromium device emulation:
  before: clientWidth=375 scrollWidth=457  (overflow found)
  after : clientWidth=375 scrollWidth=375  (clean at 320/360/375/390/414)
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ok = True


def fail(msg):
    global ok
    ok = False
    print("FAIL:", msg)


css_path = os.path.join(ROOT, "static", "css", "style.css")
css = open(css_path, errors="replace").read() if os.path.exists(css_path) else ""
if not css:
    print("FAIL: static/css/style.css missing")
    sys.exit(1)


def rule(selector):
    """Return the declaration block for an exact selector, or ''."""
    m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    return m.group(1) if m else ""


def media_blocks(max_px):
    """All bodies of @media (max-width: Npx), matched by nested braces.
    There can be several such blocks (nav, home, ...) — collect every one."""
    out = []
    for m in re.finditer(r"@media \(max-width:\s*" + str(max_px) + r"px\)\s*\{", css):
        i = m.end()
        depth = 1
        start = i
        while i < len(css) and depth > 0:
            if css[i] == "{":
                depth += 1
            elif css[i] == "}":
                depth -= 1
            i += 1
        out.append(css[start:i - 1])
    return "\n".join(out)


# --------------------------------------------------------------------------
# 1. grid children must be allowed to shrink
# --------------------------------------------------------------------------
print("checking .iwt grid children can shrink...")
if not re.search(r"\.iwt\s*>\s*\*\s*\{[^}]*min-width:\s*0", css):
    fail(".iwt > * has no min-width:0 — a 1fr grid column defaults to min-width:auto "
         "and will refuse to shrink below its content, pushing the page wider than "
         "a phone screen")


# --------------------------------------------------------------------------
# 2. no aspect-ratio + min-height combo that implies a minimum width
# --------------------------------------------------------------------------
print("checking mobile .iwt-media does not force a minimum width...")
mobile = media_blocks(860)
if not mobile:
    fail("no @media (max-width: 860px) block found")
else:
    # there are several .iwt-media rules (.iwt--flip .iwt-media{order:0} etc.),
    # so pick the one that actually declares sizing properties
    cands = re.findall(r"\n\s*\.iwt-media\s*\{([^}]*)\}", mobile)
    mm = None
    for body in cands:
        if "aspect-ratio" in body or "min-height" in body:
            mm = re.match(r"(.*)", body, re.S)
            break
    if mm is None and cands:
        mm = re.match(r"(.*)", cands[0], re.S)
    if not mm:
        fail("mobile block has no .iwt-media rule")
    else:
        body = mm.group(1)
        has_ratio = "aspect-ratio" in body
        mh = re.search(r"min-height:\s*(\d+)px", body)
        if has_ratio and mh and int(mh.group(1)) > 0:
            implied = int(mh.group(1)) * 4 / 3
            if implied > 320:
                fail(f"mobile .iwt-media has aspect-ratio 4/3 with min-height:{mh.group(1)}px "
                     f"= implied minimum width {implied:.0f}px, wider than a 320px phone")
        if not re.search(r"min-height:\s*0", body):
            fail("mobile .iwt-media should set min-height:0 so width drives height")


# --------------------------------------------------------------------------
# 3. long headings must be allowed to wrap
# --------------------------------------------------------------------------
print("checking headings can wrap on small screens...")
if not re.search(r"\.iwt-content h2\s*\{[^}]*overflow-wrap:\s*break-word", mobile):
    fail("mobile .iwt-content h2 has no overflow-wrap — a long unbroken word can "
         "overflow the column")


# --------------------------------------------------------------------------
# 4. paragraphs must not be pinned wider than the column
# --------------------------------------------------------------------------
print("checking paragraphs are width-fluid on mobile...")
if "max-width: 100%" not in mobile:
    fail("mobile block does not cap .iwt-content p at max-width:100%")


# --------------------------------------------------------------------------
# 5. the desktop 2-column layout must still exist
# --------------------------------------------------------------------------
print("checking desktop layout is intact...")
iwt = rule(".iwt")
if "1.12fr 1fr" not in iwt.replace(" ", " "):
    if "grid-template-columns" not in iwt:
        fail(".iwt lost its desktop grid-template-columns")


print()
print("MOBILE_LAYOUT OK" if ok else "MOBILE_LAYOUT FAILED")
sys.exit(0 if ok else 1)
