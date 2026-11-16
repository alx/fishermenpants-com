/* Fishermen Pants — Simple Analytics events for the purchase funnel.
   sa_event is defined as a placeholder in <head> (baseof.html) so calls are safe
   before the script loads or when an ad blocker drops it.
   Never pass personal data (email, name, address) as event metadata. */
(function () {
  const ev = (name, meta) => {
    try { (window.sa_event || function () {})(name, meta); } catch {}
  };

  // add_to_cart — fired by cart.js via a DOM event, so it also catches
  // programmatic adds in future code.
  document.addEventListener("fp:added", e => {
    const d = (e.detail || {});
    ev("add_to_cart", {
      product: d.handle || "",
      price: Number(d.price || 0),
      qty: Number(d.qty || 1)
    });
  });

  // checkout_started — customer details accepted, payment step shown
  document.addEventListener("fp:checkout_started", e => {
    const d = (e.detail || {});
    ev("checkout_started", { items: Number(d.items || 0), total: Number(d.total || 0) });
  });

  // order_placed — the reference exists and the seller has been notified.
  // The reference itself is NOT sent: it is unique per visitor.
  document.addEventListener("fp:order_placed", e => {
    const d = (e.detail || {});
    ev("order_placed", { items: Number(d.items || 0), total: Number(d.total || 0) });
  });

  // newsletter_submit
  document.addEventListener("fp:newsletter", () => ev("newsletter_submit"));

  // contact_cta — the big contact button on payment/contact pages
  document.addEventListener("click", e => {
    const a = e.target.closest && e.target.closest(".pay-cta");
    if (a) ev("contact_cta");
  });
})();
