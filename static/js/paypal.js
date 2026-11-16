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
        description: desc,
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
      opts.items.forEach((it, idx) => {
        const n = idx + 1;
        const desc = it.description && it.description !== "Default Title" ? it.description : "";
        const name = desc ? (it.name + " — " + desc) : it.name;
        form.appendChild(field("item_name_" + n, name));
        form.appendChild(field("quantity_" + n, String(it.qty)));
        form.appendChild(field("amount_" + n, money(it.unitPrice * it.qty)));
      });
    } else {
      form.appendChild(field("item_name", opts.name));
      form.appendChild(field("amount", money(opts.unitPrice * opts.qty)));
      form.appendChild(field("quantity", String(opts.qty)));
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
          name: l.description ? (l.name + " — " + l.description) : l.name,
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
        .map(i => ({ name: i.name, description: i.title, qty: i.qty, unitPrice: i.price }));
      if (!items.length) {
        cart.innerHTML = '<p class="pay-disabled">Your cart is empty.</p>';
        return;
      }
      buildForm(cart, {
        cmd: "_cart",
        items,
        buttonLabel: "Checkout"
      });
    }
  }

  const isProduct = !!document.querySelector(".product");
  const isCart = !!document.getElementById("cart-items");
  if (isProduct) api.refreshProduct();
  else if (isCart) api.refreshCart();
})();
