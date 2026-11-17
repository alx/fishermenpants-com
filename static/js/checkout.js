/* Fishermen Pants — checkout: customer details, order reference, handoff to PayPal.
   No backend: details are stored in localStorage and sent to PayPal with the order. */
(function () {
  const CUST_KEY = "fp_customer_v1";
  const ORDER_KEY = "fp_order_v1";
  const NOTIFY_KEY = "fp_notified_v1";

  const form = document.getElementById("checkout-form");
  if (!form) return;

  const cartBlock = document.getElementById("checkout-block");
  const payBlock = document.getElementById("payment-block");
  const errBox = document.getElementById("co-error");
  const refEl = document.getElementById("co-ref");
  const countrySel = document.getElementById("co-country");

  let customer = {};
  try { customer = JSON.parse(localStorage.getItem(CUST_KEY)) || {}; } catch {}

  // ---- countries (same list as the site-wide selector) ----
  function countryList() {
    const src = document.querySelector(".country-select");
    if (src && src.options.length > 1) {
      return Array.from(src.options).map(o => o.value).filter(Boolean);
    }
    return ["Thailand", "United States", "United Kingdom", "Germany", "France", "Australia",
            "Canada", "Japan", "Netherlands", "Spain", "Italy", "Sweden", "Singapore"];
  }
  function fillCountries() {
    if (!countrySel) return;
    countrySel.innerHTML = '<option value="">Select country…</option>' +
      countryList().map(c => `<option value="${c}">${c}</option>`).join("");
    if (customer.country) countrySel.value = customer.country;
  }
  fillCountries();
  // the shared country selector populates asynchronously; refill once it is ready
  document.addEventListener("fp:country", () => { if (!countrySel.options.length || countrySel.options.length < 3) fillCountries(); });
  setTimeout(() => { if (countrySel.options.length < 3) fillCountries(); }, 300);

  // ---- restore previously entered details ----
  Object.entries(customer).forEach(([k, v]) => {
    const el = form.elements[k];
    if (el && v) el.value = v;
  });

  function readForm() {
    const data = {};
    Array.from(form.elements).forEach(el => {
      if (el.name) data[el.name] = (el.value || "").trim();
    });
    return data;
  }

  function valid(d) {
    const missing = [];
    if (!d.name) missing.push("full name");
    if (!d.email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(d.email)) missing.push("a valid email");
    if (!d.country) missing.push("country");
    if (!d.address1) missing.push("address");
    if (!d.city) missing.push("city");
    if (!d.zip) missing.push("postal code");
    return missing;
  }

  // Human-readable order reference: FP-YYMMDD-XXXX
  function newRef() {
    const d = new Date();
    const p = n => String(n).padStart(2, "0");
    const stamp = String(d.getFullYear()).slice(2) + p(d.getMonth() + 1) + p(d.getDate());
    let rand = "";
    const abc = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
    for (let i = 0; i < 4; i++) rand += abc[Math.floor(Math.random() * abc.length)];
    return `FP-${stamp}-${rand}`;
  }

  function saveCustomer(d) {
    try { localStorage.setItem(CUST_KEY, JSON.stringify(d)); } catch {}
  }

  function endpoint() {
    const cfg = (window.FP_CONFIG && window.FP_CONFIG.formspree) || {};
    return cfg.endpoint || "";
  }

  // Email the seller a copy of the order, so an order exists even if the
  // payment provider notification never reaches us. Idempotent per order ref.
  function notify(order) {
    const url = endpoint();
    if (!url || url.includes("your-form-id")) return Promise.resolve(false);
    if (!order || !order.ref) return Promise.resolve(false);
    try {
      const sent = JSON.parse(localStorage.getItem(NOTIFY_KEY)) || {};
      if (sent[order.ref]) return Promise.resolve(true); // already sent
    } catch {}

    const c = order.customer || {};
    const lines = (order.items || [])
      .map(it => `${it.qty} x ${it.name}${it.description ? " (" + it.description + ")" : ""} — $${(it.price * it.qty).toFixed(2)}`)
      .join("\n");

    const fd = new FormData();
    fd.set("_subject", `New order ${order.ref} — fishermenpants.com`);
    fd.set("order_reference", order.ref);
    fd.set("customer_name", c.name || "");
    fd.set("email", c.email || "");
    fd.set("phone", c.phone || "");
    fd.set("ship_to", [c.address1, c.address2, c.city, c.state, c.zip, c.country].filter(Boolean).join(", "));
    fd.set("items", lines);
    fd.set("subtotal", "$" + Number(order.total).toFixed(2) + " USD");
    // Carry the click-id (fbclid/gclid/…) from meta-events.js for ad attribution.
    let notes = c.notes || "";
    try {
      const cid = window.fpClickId ? window.fpClickId() : "";
      if (cid) notes = (notes ? notes + " | " : "") + cid;
    } catch {}
    fd.set("notes", notes.slice(0, 255));
    fd.set("placed_at", order.createdAt || new Date().toISOString());
    fd.set("payment", order.payment || "paypal");

    return fetch(url, { method: "POST", body: fd, headers: { Accept: "application/json" } })
      .then(res => {
        if (res.ok) {
          try {
            const sent = JSON.parse(localStorage.getItem(NOTIFY_KEY)) || {};
            sent[order.ref] = new Date().toISOString();
            localStorage.setItem(NOTIFY_KEY, JSON.stringify(sent));
          } catch {}
          return true;
        }
        return false;
      })
      .catch(() => false);
  }

  function showPayment() {
    const d = readForm();
    const missing = valid(d);
    if (missing.length) {
      errBox.hidden = false;
      errBox.textContent = "Please fill in " + missing.join(", ") + ".";
      return;
    }
    errBox.hidden = true;
    saveCustomer(d);

    const cart = window.FPCart ? window.FPCart.load() : { items: [] };
    const order = {
      ref: newRef(),
      createdAt: new Date().toISOString(),
      customer: d,
      items: cart.items.map(i => ({
        name: i.name, description: i.description || "", sku: i.sku || i.handle, qty: i.qty, price: i.price
      })),
      total: cart.items.reduce((s, i) => s + i.qty * i.price, 0)
    };
    try { localStorage.setItem(ORDER_KEY, JSON.stringify(order)); } catch {}
    notify(order);
    document.dispatchEvent(new CustomEvent("fp:order_placed", {
      detail: { items: order.items.length, total: order.total }
    }));

    if (refEl) refEl.textContent = order.ref;
    document.dispatchEvent(new CustomEvent("fp:checkout_started", {
      detail: { items: order.items.length, total: order.total }
    }));
    payBlock.hidden = false;
    window.FPPaypal && window.FPPaypal.refreshCart();
    payBlock.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  document.getElementById("co-continue").addEventListener("click", showPayment);
  form.addEventListener("submit", e => { e.preventDefault(); showPayment(); });

  // ---- show / hide the checkout block with the cart ----
  function sync() {
    const cart = window.FPCart ? window.FPCart.load() : { items: [] };
    const has = cart.items.length > 0;
    cartBlock.hidden = !has;
    if (!has && payBlock) payBlock.hidden = true;
    if (has) window.FPPaypal && window.FPPaypal.refreshCart();
  }
  document.addEventListener("fp:cart", sync);
  sync();

  // Expose the current order for paypal.js
  window.FPCheckout = {
    order() {
      try { return JSON.parse(localStorage.getItem(ORDER_KEY)) || null; } catch { return null; }
    },
    notify(order) { return notify(order); },
    clear() {
      try { localStorage.removeItem(ORDER_KEY); } catch {}
    }
  };
})();
