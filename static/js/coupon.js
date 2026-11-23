/* Fishermen Pants — coupon codes.
 *
 * Single source of truth for discounts, mirroring shipping.js. Cart, PayPal and
 * checkout all read from here so the numbers can never disagree.
 *
 * Active code: SAMESAME — 10% off, minimum $99 of goods.
 *
 * IMPORTANT — what this is and is not:
 *   This is a marketing coupon evaluated in the browser. The code is visible to
 *   anyone who reads this file; SAMESAME is a shareable promo code, not a secret.
 *   Redemption is not tracked (no single-use-per-customer) because there is no
 *   backend in the purchase path to enforce it — the static site hands straight
 *   off to PayPal. What IS controlled: the amount sent to PayPal is the
 *   discounted total, so a customer cannot pay less than what we charge them.
 *
 * Rules (owner-confirmed):
 *   - case-insensitive, whitespace-trimmed
 *   - minimum applies to the GOODS subtotal, before discount
 *   - discount applies to GOODS ONLY, never to shipping
 *   - rounds down to the cent so we never over-discount
 *   - can never exceed the subtotal
 *   - the free-shipping threshold is measured AFTER the discount
 */
(function () {
  "use strict";

  var CODES = {
    SAMESAME: { percent: 10, minSubtotal: 99 },
  };

  var STORE_KEY = "fp_coupon_v1";

  function norm(code) {
    return String(code == null ? "" : code).trim().toUpperCase();
  }

  function money(n) {
    return Number(n || 0).toFixed(2);
  }

  /** Floor to whole cents — never round up in the customer's favour beyond plan. */
  function floorCents(n) {
    return Math.floor((Number(n) || 0) * 100) / 100;
  }

  /**
   * Is this code usable at all (ignoring the cart)? Returns {ok, reason, rule}.
   */
  function lookup(code) {
    var c = norm(code);
    if (!c) return { ok: false, reason: "empty", code: "" };
    var rule = CODES[c];
    if (!rule) return { ok: false, reason: "unknown", code: c };
    return { ok: true, reason: "", code: c, rule: rule };
  }

  /**
   * Evaluate a code against a goods subtotal.
   * Returns { ok, reason, code, percent, minSubtotal, amount, shortfall }.
   */
  function evaluate(code, subtotal) {
    var sub = Number(subtotal) || 0;
    var hit = lookup(code);
    if (!hit.ok) {
      return { ok: false, reason: hit.reason, code: hit.code, amount: 0, shortfall: 0 };
    }
    var rule = hit.rule;
    if (sub < rule.minSubtotal) {
      return {
        ok: false,
        reason: "minimum",
        code: hit.code,
        percent: rule.percent,
        minSubtotal: rule.minSubtotal,
        amount: 0,
        shortfall: Math.round((rule.minSubtotal - sub) * 100) / 100,
      };
    }
    var amount = floorCents(sub * (rule.percent / 100));
    // Never discount more than the goods are worth.
    if (amount > sub) amount = sub;
    if (amount < 0) amount = 0;
    return {
      ok: true,
      reason: "",
      code: hit.code,
      percent: rule.percent,
      minSubtotal: rule.minSubtotal,
      amount: amount,
      shortfall: 0,
    };
  }

  /** Goods subtotal after discount (never below zero). */
  function netSubtotal(subtotal, discount) {
    var sub = Number(subtotal) || 0;
    var d = Number(discount) || 0;
    return Math.max(0, Math.round((sub - d) * 100) / 100);
  }

  // ---- persistence -------------------------------------------------------
  function readStored() {
    try {
      var v = JSON.parse(localStorage.getItem(STORE_KEY) || "null");
      return v && typeof v.code === "string" ? norm(v.code) : "";
    } catch (e) {
      return "";
    }
  }

  function store(code) {
    try {
      if (code) localStorage.setItem(STORE_KEY, JSON.stringify({ code: norm(code) }));
      else localStorage.removeItem(STORE_KEY);
    } catch (e) {
      /* storage may be unavailable (private mode) — coupon still works this page */
    }
  }

  window.FPcoupon = {
    CODES: CODES,
    normalize: norm,
    lookup: lookup,
    evaluate: evaluate,
    netSubtotal: netSubtotal,
    money: money,
    stored: readStored,
    store: store,
  };
})();
