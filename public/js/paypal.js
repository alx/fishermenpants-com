/* Fishermen Pants — PayPal buttons (PayPal JS SDK, client-side).
   Configure params.paypal.clientId in hugo.toml to enable. */
(function () {
  const cfg = window.FP_CONFIG && window.FP_CONFIG.paypal;
  const clientId = cfg && cfg.clientId;
  const currency = (cfg && cfg.currency) || "USD";
  const enabled = !!clientId && clientId !== "sb" && !String(clientId).includes("your-");

  const api = {
    enabled,
    productLine: null,
    cartItems: null,
    refreshProduct() {
      const art = document.querySelector(".product");
      const select = document.getElementById("variant-select") ||
                     document.getElementById("variant-select-single");
      if (!art || !select) return;
      const opt = select.options[select.selectedIndex];
      const qty = Math.max(1, parseInt((document.getElementById("qty-input") || {}).value, 10) || 1);
      api.productLine = {
        name: art.dataset.title,
        description: opt ? opt.textContent : "",
        qty,
        unitPrice: Number((opt && opt.dataset.price) || 0),
        cartId: String(opt ? opt.value : "1")
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
  if (!enabled) return;

  let sdkLoading = null;
  function loadSdk() {
    return sdkLoading || (sdkLoading = new Promise((res, rej) => {
      const s = document.createElement("script");
      s.src = `https://www.paypal.com/sdk/js?client-id=${encodeURIComponent(clientId)}&currency=${currency}`;
      s.onload = res;
      s.onerror = () => rej(new Error("paypal sdk failed to load"));
      document.head.appendChild(s);
    }));
  }

  async function render() {
    const slots = [document.getElementById("paypal-buttons"),
                   document.getElementById("paypal-buttons-cart")];
    for (const slot of slots) {
      if (!slot) continue;
      slot.innerHTML = "";
      if (slot.id === "paypal-buttons") {
        // product page: pay for selected variant
        const line = api.productLine;
        if (!line || !line.unitPrice) { continue; }
        await renderButtons(slot, (t, d) => orderForLines([line], t, d), currency);
      } else {
        // cart page: pay for the whole cart
        const items = (api.cartItems || []).filter(i => i.qty > 0);
        if (!items.length) {
          slot.innerHTML = '<p class="pay-disabled">Your cart is empty.</p>';
          continue;
        }
        const lines = items.map(i => ({ name: i.name, description: i.title, qty: i.qty, unitPrice: i.price, cartId: i.vid }));
        await renderButtons(slot, (t, d) => orderForLines(lines, t, d), currency);
      }
    }
  }

  async function renderButtons(slot, createOrder, cur) {
    try {
      await loadSdk();
      window.paypal.Buttons({
        style: { layout: "row", color: "gold", shape: "rect", label: "paypal" },
        createOrder: (t, d) => createOrder(t, d),
        onApprove: async (d, actions) => {
          const detail = await actions.order.capture();
          window.fpToast(`Payment ${detail.id} captured — order placed!`);
          if (slot.id === "paypal-buttons-cart" && window.FPCart) {
            const empty = { items: [] };
            localStorage.setItem("fp_cart_v1", JSON.stringify(empty));
            document.dispatchEvent(new CustomEvent("fp:cart", { detail: empty }));
          }
        },
        onError: () => window.fpToast("PayPal error — please try again")
      }).render(slot);
    } catch (e) {
      slot.innerHTML = '<p class="pay-disabled">PayPal unavailable right now.</p>';
    }
  }

  function orderForLines(lines, t, d) {
    return t.orders.create({
      intent: "CAPTURE",
      purchase_units: lines.map(l => ({
        description: `${l.name} — ${l.description}`,
        amount: {
          currency_code: cur,
          value: (l.unitPrice * l.qty).toFixed(2)
        },
        items: [{
          name: l.name,
          description: l.description,
          quantity: String(l.qty),
          unit_amount: { currency_code: cur, value: l.unitPrice.toFixed(2) }
        }]
      }))
    });
  }

  // initial render on product page
  const art = document.querySelector(".product");
  const cartPage = document.getElementById("cart-items");
  if (art || cartPage) render();
})();
