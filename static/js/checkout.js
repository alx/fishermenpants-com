/* Fishermen Pants — checkout: customer details, order reference, handoff to PayPal.
   No backend: details are stored in localStorage and sent to PayPal with the order. */
(function () {
  const CUST_KEY = "fp_customer_v1";
  const ORDER_KEY = "fp_order_v1";

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

    if (refEl) refEl.textContent = order.ref;
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
    clear() {
      try { localStorage.removeItem(ORDER_KEY); } catch {}
    }
  };
})();
