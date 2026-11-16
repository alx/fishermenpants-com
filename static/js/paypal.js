/* Fishermen Pants — PayPal checkout.
   Uses the classic PayPal checkout form (POST to /cgi-bin/webscr), which only
   needs the business email (params.paypal.business) — no client id / backend.
   - Product page: cmd=_xclick (single selected variant x qty)
   - Cart page:    cmd=_cart  (one line per cart item)
   Opens PayPal in a new tab. */
(function () {
  const cfg = (window.FP_CONFIG && window.FP_CONFIG.paypal) || {};
  const business = cfg.business;
  const currency = cfg.currency || "USD";

  const api = {
    enabled: !!business,
    productLine: null,
    cartItems: null,
    refreshProduct() {
      const art = document.querySelector(".product");
      if (!art) return;
      const select = document.getElementById("variant-select") ||
                     document.getElementById("variant-select-single");
      const opt = select ? select.options[select.selectedIndex] : null;
      let desc = opt ? opt.textContent.split("—")[0].trim() : "";
      if (desc === "Default Title") desc = "";
      const qty = Math.max(1, parseInt((document.getElementById("qty-input") || {}).value, 10) || 1);
      api.productLine = {
        name: art.dataset.title,
        description: desc || art.dataset.description || "",
        sku: art.dataset.sku || art.dataset.handle || "",
        qty,
        unitPrice: Number((opt && opt.dataset.price) || 0)
      };
      render();
    },
    refreshCart() {
      const cart = window.FPCart.load();
      api.cartItems = cart.items;
      render();
    }
  };
  window.FPPaypal = api;
  if (!api.enabled) return;

  const PP_URL = "https://www.paypal.com/cgi-bin/webscr";
  const money = n => (Math.round(n * 100) / 100).toFixed(2);

  function field(name, value) {
    const i = document.createElement("input");
    i.type = "hidden";
    i.name = name;
    i.value = value;
    return i;
  }

  function payButton(label) {
    const b = document.createElement("button");
    b.type = "submit";
    b.className = "pp-pay-btn";
    b.innerHTML = '<span class="pp-logo">Pay<span>Pal</span></span> ' + label;
    return b;
  }

  // Build the classic checkout form and render a gold PayPal button.
  function buildForm(slot, opts) {
    const form = document.createElement("form");
    form.action = PP_URL;
    form.method = "post";
    form.target = "_blank";
    form.rel = "noopener";
    form.appendChild(field("cmd", opts.cmd));
    form.appendChild(field("business", business));
    form.appendChild(field("currency_code", currency));
    if (opts.cmd === "_cart") form.appendChild(field("upload", "1"));
    if (opts.items) {
      const clean = v => String(v == null ? "" : v).replace(/Default Title/g, "").replace(/\s+/g, " ").trim();
      opts.items.forEach((it, idx) => {
        const n = idx + 1;
        const desc = clean(it.description);
        // PayPal: amount_N is the UNIT price; the quantity multiplies it.
        form.appendChild(field("item_name_" + n, clean(it.name) || "Item " + n));
        if (desc) {
          form.appendChild(field("on" + (n - 1), "Description"));
          form.appendChild(field("os" + (n - 1), desc.slice(0, 127)));
        }
        if (it.sku) form.appendChild(field("item_number_" + n, clean(it.sku)));
        form.appendChild(field("quantity_" + n, String(it.qty)));
        form.appendChild(field("amount_" + n, money(it.unitPrice)));
      });
    } else {
      const clean = v => String(v == null ? "" : v).replace(/Default Title/g, "").replace(/\s+/g, " ").trim();
      form.appendChild(field("item_name", clean(opts.name) || "Item"));
      if (opts.description && clean(opts.description)) {
        form.appendChild(field("on0", "Description"));
        form.appendChild(field("os0", clean(opts.description).slice(0, 127)));
      }
      if (opts.sku) form.appendChild(field("item_number", clean(opts.sku)));
      form.appendChild(field("amount", money(opts.unitPrice)));
      form.appendChild(field("quantity", String(opts.qty)));
    }
    if (opts.order) {
      const c = opts.order.customer || {};
      const split = nm => {
        const parts = String(nm || "").trim().split(/\s+/);
        return [parts.shift() || "", parts.join(" ")];
      };
      const [first, last] = split(c.name);
      if (c.email) form.appendChild(field("email", c.email));
      if (first) form.appendChild(field("first_name", first));
      if (last) form.appendChild(field("last_name", last));
      if (c.address1) form.appendChild(field("address1", c.address1));
      if (c.address2) form.appendChild(field("address2", c.address2));
      if (c.city) form.appendChild(field("city", c.city));
      if (c.state) form.appendChild(field("state", c.state));
      if (c.zip) form.appendChild(field("zip", c.zip));
      if (c.country) form.appendChild(field("country", c.country));
      if (c.phone) form.appendChild(field("night_phone_b", c.phone));
      if (opts.order.ref) form.appendChild(field("invoice", opts.order.ref));
      if (c.notes) form.appendChild(field("custom", String(c.notes).slice(0, 255)));
      form.appendChild(field("no_shipping", "1")); // address already collected
      form.appendChild(field("no_note", "0"));
    }
    if (opts.returnUrl) {
      form.appendChild(field("return", opts.returnUrl));
      form.appendChild(field("rm", "1")); // GET, so the browser lands back on our page
      form.appendChild(field("cancel_return", opts.cancelUrl || opts.returnUrl));
    }
    form.appendChild(payButton(opts.buttonLabel));
    slot.innerHTML = "";
    slot.appendChild(form);
  }

  function render() {
    const prod = document.getElementById("paypal-buttons");
    if (prod) {
      prod.innerHTML = "";
      const l = api.productLine;
      if (l && l.unitPrice > 0) {
        buildForm(prod, {
          cmd: "_xclick",
          name: l.name,
          description: l.description,
          sku: l.sku,
          unitPrice: l.unitPrice,
          qty: l.qty,
          buttonLabel: "Pay for item"
        });
      } else {
        prod.innerHTML = '<p class="pay-disabled">Select a product to pay with PayPal.</p>';
      }
    }

    const cart = document.getElementById("paypal-buttons-cart");
    if (cart) {
      const items = (api.cartItems || [])
        .filter(i => i.qty > 0 && i.price > 0)
        .map(i => ({
          name: i.name,
          description: i.description || (i.title && i.title !== "Default Title" ? i.title : ""),
          sku: i.sku,
          qty: i.qty,
          unitPrice: i.price
        }));
      if (!items.length) {
        cart.innerHTML = '<p class="pay-disabled">Your cart is empty.</p>';
        return;
      }
      const order = (window.FPCheckout && window.FPCheckout.order()) || null;
      buildForm(cart, {
        cmd: "_cart",
        items,
        order,
        returnUrl: order ? new URL("order/thank-you/", window.FP_BASE || location.origin + "/").href : "",
        cancelUrl: new URL("cart/", window.FP_BASE || location.origin + "/").href,
        buttonLabel: order ? "Pay with PayPal" : "Checkout"
      });
    }
  }

  const isProduct = !!document.querySelector(".product");
  const isCart = !!document.getElementById("cart-items");
  if (isProduct) api.refreshProduct();
  else if (isCart) api.refreshCart();
})();
