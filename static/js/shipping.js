/* Fishermen Pants — shipping rules.
 *
 * Single source of truth for the shipping line, so the cart, the checkout
 * summary, the PayPal form and the crypto instructions can never disagree.
 *
 * Confirmed by the owner (Nov 2026):
 *   - A 1-item parcel to Europe costs ~600 THB (~$18 USD).
 *   - Free standard shipping on orders of $149 or more.
 *   - Flat $18 below $149.
 *
 * Before this existed there was NO shipping line anywhere: PayPal received the
 * product total only and the shop silently absorbed ~$18 on every order.
 */
(function () {
  "use strict";

  var FREE_OVER = 149;   // USD
  var FLAT_RATE = 18;    // USD, one-standard-parcel rate

  function money(n) {
    return Number(n || 0).toFixed(2);
  }

  /**
   * Shipping for a given subtotal.
   * Returns { amount, free, label } where amount is in USD.
   * An empty cart costs nothing to ship.
   */
  function forSubtotal(subtotal) {
    var sub = Number(subtotal) || 0;
    if (sub <= 0) {
      return { amount: 0, free: true, label: "—" };
    }
    if (sub >= FREE_OVER) {
      return { amount: 0, free: true, label: "Free" };
    }
    return { amount: FLAT_RATE, free: false, label: "$" + money(FLAT_RATE) };
  }

  /** Grand total for a subtotal, including shipping. */
  function grandTotal(subtotal) {
    return (Number(subtotal) || 0) + forSubtotal(subtotal).amount;
  }

  /** How much more to spend to reach free shipping (0 when already there). */
  function toFreeShipping(subtotal) {
    var sub = Number(subtotal) || 0;
    if (sub <= 0 || sub >= FREE_OVER) return 0;
    return Math.round((FREE_OVER - sub) * 100) / 100;
  }

  window.FPShipping = {
    FREE_OVER: FREE_OVER,
    FLAT_RATE: FLAT_RATE,
    forSubtotal: forSubtotal,
    grandTotal: grandTotal,
    toFreeShipping: toFreeShipping,
    money: money,
  };
})();
