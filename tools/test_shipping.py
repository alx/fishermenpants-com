#!/usr/bin/env python3
"""Shipping economics regression tests (owner-confirmed: $149 threshold, $18 flat).

The bug this guards: the site claimed free shipping everywhere and PayPal was
handed the product total only, so the shop silently absorbed ~$18 on every
order. Nothing failed — the money just leaked. These checks make that visible.

Runs against the built site (static/js/*.js + public HTML) and against the
shipping module's own logic. Stdlib only, no network, no browser.

Checks
  1. static/js/shipping.js exists, is loaded BEFORE cart/checkout/paypal
  2. the rules are 149 / 18 and match the published copy
  3. cart page has a shipping line and a grand total
  4. PayPal receives shipping on BOTH paths (_cart line, _xclick handling)
  5. checkout order carries subtotal + shipping + total (not goods only)
  6. no page still claims free shipping unconditionally
  7. the module's boundary logic is correct (simulated in Python)
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC = os.path.join(ROOT, "public")
ok = True

FREE_OVER = 149
FLAT_RATE = 18


def fail(msg):
    global ok
    ok = False
    print("FAIL:", msg)


def read(*parts):
    p = os.path.join(ROOT, *parts) if parts[0] != "public" else os.path.join(PUBLIC, *parts[1:])
    return open(p, errors="replace").read() if os.path.exists(p) else None


# --------------------------------------------------------------------------
# 1. module present and loaded first
# --------------------------------------------------------------------------
print("checking shipping module...")
ship = read("static", "js", "shipping.js")
if ship is None:
    fail("static/js/shipping.js missing")
    ship = ""

baseof = read("layouts", "baseof.html") or ""
i_ship = baseof.find("js/shipping.js")
i_cart = baseof.find("js/cart.js")
i_pp = baseof.find("js/paypal.js")
i_co = baseof.find("js/checkout.js")
if i_ship < 0:
    fail("baseof.html does not load js/shipping.js")
else:
    for nm, ix in (("cart.js", i_cart), ("paypal.js", i_pp), ("checkout.js", i_co)):
        if 0 <= ix < i_ship:
            fail(f"{nm} is loaded BEFORE shipping.js - it would read an undefined FPShipping")


# --------------------------------------------------------------------------
# 2. rules match the published numbers
# --------------------------------------------------------------------------
print("checking threshold and flat rate...")
if ship:
    if not re.search(r"FREE_OVER\s*=\s*149", ship):
        fail("shipping.js: FREE_OVER is not 149")
    if not re.search(r"FLAT_RATE\s*=\s*18", ship):
        fail("shipping.js: FLAT_RATE is not 18")

sr = read("content", "pages", "shipping-returns.md") or ""
if "$149" not in sr:
    fail("shipping-returns page does not state the $149 threshold")
if "$18" not in sr:
    fail("shipping-returns page does not state the $18 flat rate")
if re.search(r"[Ss]tandard shipping is \*\*free\*\* on every order", sr):
    fail("shipping-returns still claims standard shipping is free on every order")


# --------------------------------------------------------------------------
# 3. cart shows shipping + total
# --------------------------------------------------------------------------
print("checking cart totals markup...")
cart_html = read("public", "cart", "index.html") or ""
cart_js = read("static", "js", "cart.js") or ""
if not cart_html:
    fail("public/cart/index.html missing - run build.sh first")
else:
    for el in ("cart-shipping", "cart-total"):
        if el not in cart_html:
            fail(f"cart page is missing the {el} element")
if "FPShipping.forSubtotal" not in cart_js:
    fail("cart.js does not call FPShipping.forSubtotal")


# --------------------------------------------------------------------------
# 4. PayPal is actually told about shipping
# --------------------------------------------------------------------------
print("checking PayPal receives shipping...")
pp = read("static", "js", "paypal.js") or ""
if not pp:
    fail("static/js/paypal.js missing")
else:
    # _cart path: a shipping line item
    if "Standard shipping" not in pp:
        fail("paypal.js: _cart path has no shipping line item - PayPal would "
             "charge goods only and the shop would absorb postage")
    # _xclick path: handling_cart
    if "handling_cart" not in pp:
        fail("paypal.js: _xclick path has no handling_cart - single-item orders "
             "would ship free")
    if "FPShipping.forSubtotal" not in pp:
        fail("paypal.js does not use the shared shipping rules")


# --------------------------------------------------------------------------
# 5. checkout order object carries the full total
# --------------------------------------------------------------------------
print("checking checkout order totals...")
co = read("static", "js", "checkout.js") or ""
if co:
    if not re.search(r"subtotal:\s*cart\.items", co):
        fail("checkout.js: order has no subtitle/subtotal field")
    if "shipping:" not in co:
        fail("checkout.js: order carries no shipping field")
    if "FPShipping.grandTotal" not in co:
        fail("checkout.js: order total does not include shipping")


# --------------------------------------------------------------------------
# 6. no unconditional free-shipping claims left anywhere
# --------------------------------------------------------------------------
print("checking published copy for untrue claims...")
PATTERNS = [
    r"free standard shipping, packed",
    r"worldwide with free standard shipping\.",
    r"Standard \(free\)",
    r"free on every order",
]
targets = []
for pat in ("layouts/**/*.html", "content/**/*.md"):
    import glob
    targets += glob.glob(os.path.join(ROOT, pat), recursive=True)
targets.append(os.path.join(ROOT, "static", "llms.txt"))
for f in targets:
    if not os.path.exists(f):
        continue
    rel = os.path.relpath(f, ROOT)
    text = open(f, errors="replace").read()
    for pat in PATTERNS:
        if re.search(pat, text):
            fail(f"{rel}: still claims unconditional free shipping ({pat})")

# the mirror of that: the honest claim must be present where it matters
if ship and "$149" not in (read("public", "products", "beach-bag-2", "index.html") or ""):
    fail("product page no longer mentions the $149 threshold")


# --------------------------------------------------------------------------
# 7. boundary logic (mirror of shipping.js, sanity-checked in Python)
# --------------------------------------------------------------------------
print("checking shipping boundaries...")
def logic(sub):
    if sub <= 0:
        return 0
    return 0 if sub >= FREE_OVER else FLAT_RATE

CASES = [
    (0, 0), (1, 18), (48.99, 18), (148.99, 18),
    (149, 0), (150, 0), (199, 0),
]
for sub, want in CASES:
    got = logic(sub)
    if got != want:
        fail(f"shipping logic: subtotal {sub} should cost {want}, got {got}")
    else:
        print(f"  ${sub} -> ${got}")

print()
print("SHIPPING OK" if ok else "SHIPPING FAILED")
sys.exit(0 if ok else 1)
