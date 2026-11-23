#!/usr/bin/env python3
"""Coupon regression tests (SAMESAME: 10% off, min $99 of goods).

Guards the failure modes that cost real money and are invisible in the browser:
  - discount not reaching PayPal (customer overcharged)
  - discount applied twice or on shipping (shop undercharged)
  - the $99 boundary drifting
  - coupon offered on the product page (owner said no)
  - the free-shipping threshold measured BEFORE the discount (owner said after)

Stdlib only, no network, no browser. Runs against public/ + static/js.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC = os.path.join(ROOT, "public")
ok = True

PERCENT = 10
MIN_SUBTOTAL = 99


def fail(msg):
    global ok
    ok = False
    print("FAIL:", msg)


def read(*parts):
    p = os.path.join(ROOT, *parts)
    return open(p, errors="replace").read() if os.path.exists(p) else None


coupon_js = read("static", "js", "coupon.js") or ""
cart_js = read("static", "js", "cart.js") or ""
pp_js = read("static", "js", "paypal.js") or ""
co_js = read("static", "js", "checkout.js") or ""
baseof = read("layouts", "baseof.html") or ""

# --------------------------------------------------------------------------
# 1. the rules live in exactly one place
# --------------------------------------------------------------------------
print("checking the coupon rules are defined once...")
if "SAMESAME" not in coupon_js:
    fail("coupon.js does not define the SAMESAME code")
if not re.search(r"percent:\s*10\b", coupon_js):
    fail("coupon.js: SAMESAME percent is not 10")
if not re.search(r"minSubtotal:\s*99\b", coupon_js):
    fail("coupon.js: SAMESAME minimum is not 99")

for name, src in (("cart.js", cart_js), ("paypal.js", pp_js), ("checkout.js", co_js)):
    if "SAMESAME" in src:
        fail(f"{name}: hardcodes the coupon code — it must come from coupon.js only")

# --------------------------------------------------------------------------
# 2. discount maths (mirror of coupon.js)
# --------------------------------------------------------------------------
print("checking discount maths and boundaries...")


def floor_cents(n):
    return int(n * 100) / 100.0


def discount_for(subtotal):
    if subtotal < MIN_SUBTOTAL:
        return None
    return min(floor_cents(subtotal * PERCENT / 100.0), subtotal)


CASES = [
    (98.99, None),          # just below the minimum
    (99, 9.90),             # exact boundary is accepted
    (100, 10.00),
    (128, 12.80),
    (149.99, 14.99),        # floor: 14.999 -> 14.99, never over-discount
    (0, None),
]
for sub, want in CASES:
    got = discount_for(sub)
    if want is None:
        if got is not None:
            fail(f"subtotal {sub}: expected no discount (below ${MIN_SUBTOTAL}), got {got}")
        else:
            print(f"  ${sub} -> no discount")
    elif got != want:
        fail(f"subtotal {sub}: expected {want}, got {got}")
    else:
        print(f"  ${sub} -> ${got}")

# discount must never exceed the subtotal
for sub in (99, 500, 1000):
    d = discount_for(sub)
    if d is not None and d > sub:
        fail(f"subtotal {sub}: discount {d} exceeds the subtotal")

# --------------------------------------------------------------------------
# 3. the money path really carries the discount
# --------------------------------------------------------------------------
print("checking PayPal receives a discount line...")
if '"-" + money' not in pp_js and "'-' + money" not in pp_js:
    fail("paypal.js: no NEGATIVE discount line — PayPal would charge the "
         "undiscounted total and the customer would be overcharged")
if "Standard shipping" not in pp_js:
    fail("paypal.js: shipping line disappeared")
if "opts.discount" not in pp_js:
    fail("paypal.js: buildForm never reads opts.discount")

print("checking checkout totals...")
if "discount:" not in co_js:
    fail("checkout.js: order carries no discount field")
if "FPcoupon" not in co_js:
    fail("checkout.js: order total ignores the coupon")
# the order email must surface what was given away
if 'fd.set("discount"' not in co_js:
    fail("checkout.js: order email does not report the discount")

# --------------------------------------------------------------------------
# 4. owner decisions: shipping measured AFTER discount; no coupon on product pages
# --------------------------------------------------------------------------
print("checking shipping is computed on the DISCOUNTED subtotal...")
if "forSubtotal(netGoods)" not in cart_js:
    fail("cart.js: shipping is not computed on netGoods (must be measured AFTER "
         "the discount, per the owner's decision)")
if "forSubtotal(_netGoods)" not in pp_js:
    fail("paypal.js: shipping is not computed on the discounted subtotal")

print("checking the coupon is NOT offered on product pages...")
prod = read("public", "products", "beach-bag-2", "index.html") or ""
if "coupon-input" in prod:
    fail("product page exposes a coupon field (owner: cart only)")

cart_html = read("public", "cart", "index.html") or ""
if not cart_html:
    fail("public/cart/index.html missing — run build.sh first")
else:
    for el in ("coupon-input", "coupon-apply", "cart-discount"):
        if el not in cart_html:
            fail(f"cart page is missing #{el}")

# --------------------------------------------------------------------------
# 5. load order
# --------------------------------------------------------------------------
print("checking script load order...")
i_coupon = baseof.find("js/coupon.js")
i_cart = baseof.find("js/cart.js")
i_pp = baseof.find("js/paypal.js")
i_co = baseof.find("js/checkout.js")
if i_coupon < 0:
    fail("baseof.html does not load js/coupon.js")
else:
    for nm, ix in (("cart.js", i_cart), ("paypal.js", i_pp), ("checkout.js", i_co)):
        if 0 <= ix < i_coupon:
            fail(f"{nm} loads before coupon.js — FPcoupon would be undefined")

# --------------------------------------------------------------------------
# 6. coupon handlers must bind exactly once, outside the render loop
# --------------------------------------------------------------------------
print("checking coupon handlers bind only once...")
if "__fpCouponWired" not in cart_js:
    fail("cart.js: initCoupon has no re-entry guard — it lives inside renderCart(), "
         "so it re-attaches a click listener on every render")

# the guard must actually be consulted before addEventListener
guard_at = cart_js.find("__fpCouponWired")
listen_at = cart_js.find('addEventListener("click", apply)')
if guard_at == -1 or listen_at == -1:
    fail("cart.js: could not locate the coupon guard / apply listener")
elif guard_at > listen_at:
    fail("cart.js: the __fpCouponWired guard is set AFTER the click listener is "
         "attached — stacked handlers are still possible")

# remove handler must clear storage AND leave the UI consistent
if 'store("")' not in cart_js:
    fail("cart.js: the remove handler never clears the stored coupon")

print()
print("COUPON OK" if ok else "COUPON FAILED")
sys.exit(0 if ok else 1)
