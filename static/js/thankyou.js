/* Fishermen Pants — renders the order confirmation page from localStorage.
   PayPal returns here via return_url; the order is stored before payment starts. */
(function () {
  if (!document.getElementById("ty-ref")) return; // only on the confirmation page
  const KEY = "fp_order_v1";
  let order = null;
  try { order = JSON.parse(localStorage.getItem(KEY)); } catch {}

  const refEl = document.getElementById("ty-ref");
  if (!order) {
    if (refEl) refEl.textContent = "No order found";
    const lede = document.getElementById("ty-lede");
    if (lede) lede.textContent =
      "We couldn’t find a recent order in this browser. If you have already paid, email us and we’ll find your order.";
    ["ty-items-card", "ty-ship-card"].forEach(id => { const e = document.getElementById(id); if (e) e.hidden = true; });
    return;
  }

  const money = n => "$" + Number(n).toFixed(2);
  if (refEl) refEl.textContent = order.ref;
  const ledeEl = document.getElementById("ty-lede");
  if (ledeEl) ledeEl.textContent =
    "Your details are with us. Keep your order reference — we’ll email you once the payment is confirmed.";

  const items = document.getElementById("ty-items");
  if (items) {
    items.innerHTML = "";
    (order.items || []).forEach(it => {
      const row = document.createElement("div");
      row.className = "ty-line";
      row.innerHTML = `<span>${it.qty} × ${it.name}${it.description ? `<em>${it.description}</em>` : ""}</span>
                       <span class="ty-line-price">${money(it.price * it.qty)}</span>`;
      items.appendChild(row);
    });
  }
  const totalEl = document.getElementById("ty-total");
  if (totalEl) totalEl.textContent = money(order.total) + " USD";

  const c = order.customer || {};
  const ship = document.getElementById("ty-ship");
  if (ship) {
    ship.innerHTML = [c.name, c.address1, c.address2, [c.city, c.state, c.zip].filter(Boolean).join(", "), c.country]
      .filter(Boolean).map(l => l.replace(/</g, "&lt;")).join("<br>");
  }
  const emailEl = document.getElementById("ty-email");
  if (emailEl) emailEl.textContent = c.email || "your address";
})();
