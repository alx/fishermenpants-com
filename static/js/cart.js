/* Fishermen Pants — client-side cart (localStorage), no backend. */
(function () {
  const KEY = "fp_cart_v1";

  function load() {
    try { return JSON.parse(localStorage.getItem(KEY)) || { items: [] }; }
    catch { return { items: [] }; }
  }
  function save(cart) {
    localStorage.setItem(KEY, JSON.stringify(cart));
    renderBadge(cart);
    document.dispatchEvent(new CustomEvent("fp:cart", { detail: cart }));
  }
  function money(n) { return "$" + Number(n).toFixed(2); }

  function renderBadge(cart) {
    const el = document.getElementById("cart-count");
    if (!el) return;
    const n = cart.items.reduce((s, i) => s + i.qty, 0);
    el.textContent = String(n);
    el.hidden = n === 0;
  }

  window.FPCart = {
    load,
    add(item) {
      const cart = load();
      const hit = cart.items.find(i => i.vid === item.vid);
      if (hit) hit.qty = Math.min(99, hit.qty + item.qty);
      else cart.items.push(item);
      save(cart);
      return cart;
    },
    setQty(vid, qty) {
      const cart = load();
      const hit = cart.items.find(i => i.vid === vid);
      if (hit) hit.qty = qty;
      if (qty <= 0) cart.items = cart.items.filter(i => i.vid !== vid);
      save(cart);
      return cart;
    },
    remove(vid) {
      const cart = load();
      cart.items = cart.items.filter(i => i.vid !== vid);
      save(cart);
      return cart;
    },
    total(cart) { return cart.items.reduce((s, i) => s + i.qty * i.price, 0); },
    money
  };

  window.fpToast = function (msg) {
    let t = document.getElementById("fp-toast");
    if (!t) { t = document.createElement("div"); t.id = "fp-toast"; document.body.appendChild(t); }
    t.textContent = msg;
    t.classList.add("show");
    clearTimeout(fpToast._t);
    fpToast._t = setTimeout(() => t.classList.remove("show"), 2600);
  };

  // ---- product page wiring ----
  const art = document.querySelector(".product");
  if (art && window.FP_PRODUCT) {
    const select = document.getElementById("variant-select") ||
                   document.getElementById("variant-select-single");
    const qtyInput = document.getElementById("qty-input");
    const addBtn = document.getElementById("add-to-cart");
    const images = Array.from(art.querySelectorAll(".p-img"));

    images.forEach((img, i) => img.addEventListener("click", () => {
      images.forEach(x => x.classList.remove("active"));
      img.classList.add("active");
    }));
    if (images[0]) images[0].classList.add("active");

    function selected() {
      const opt = select.options[select.selectedIndex];
      return {
        vid: String(opt.value),
        // Variant label: only when the product really has named options. For a
        // single-variant product the option text is just a price, which is not a label.
        title: (() => {
          const t = opt.textContent.split("—")[0].trim();
          if (!t || t === "Default Title" || /^\$?[\d.,]+\s*USD$/i.test(t)) return "";
          return t;
        })(),
        price: Number(opt.dataset.price || opt.textContent.match(/[\d.]+/)?.[0] || 0),
        image: images[0] ? images[0].src : "",
        handle: art.dataset.handle,
        name: art.dataset.title,
        description: art.dataset.description || "",
        sku: art.dataset.sku || art.dataset.handle || ""
      };
    }
    if (addBtn) {
      addBtn.addEventListener("click", () => {
        const s = selected();
        const qty = Math.max(1, Math.min(99, parseInt(qtyInput.value, 10) || 1));
        if (optDisabled(s.vid)) return;
        window.FPCart.add({ ...s, qty });
        document.dispatchEvent(new CustomEvent("fp:added", {
          detail: { handle: s.handle, price: s.price, qty }
        }));
        window.fpToast(`Added "${s.name}" to cart`);
        window.FPPaypal && window.FPPaypal.refreshProduct();
      });
      // sync PayPal button price with selection
      select && select.addEventListener("change", () => window.FPPaypal && window.FPPaypal.refreshProduct());
      qtyInput && qtyInput.addEventListener("change", () => window.FPPaypal && window.FPPaypal.refreshProduct());
    }
    function optDisabled(vid) {
      const opt = select && Array.from(select.options).find(o => String(o.value) === String(vid));
      return opt ? opt.disabled : false;
    }
  }

  // ---- cart page rendering ----
  const cartItems = document.getElementById("cart-items");
  if (cartItems) {
    function renderCart() {
      const cart = load();
      cartItems.innerHTML = "";
      document.getElementById("cart-empty").hidden = cart.items.length > 0;
      for (const it of cart.items) {
        const row = document.createElement("div");
        row.className = "cart-line";
        row.innerHTML = `
          <img src="${it.image || ""}" alt="">
          <div>
            <div class="cl-title">${it.name}</div>
            <div class="cl-variant">${it.title || ""}</div>
          </div>
          <div class="cl-qty">
            <button data-act="dec" aria-label="Decrease">−</button>
            <span>${it.qty}</span>
            <button data-act="inc" aria-label="Increase">+</button>
          </div>
          <div class="cl-price">${money(it.price * it.qty)}</div>
          <button class="cl-remove" data-act="rm">Remove</button>`;
        row.addEventListener("click", e => {
          const b = e.target.closest("[data-act]");
          if (!b) return;
          const a = b.dataset.act;
          if (a === "inc") window.FPCart.setQty(it.vid, it.qty + 1);
          if (a === "dec") window.FPCart.setQty(it.vid, it.qty - 1);
          if (a === "rm") window.FPCart.remove(it.vid);
        });
        cartItems.appendChild(row);
      }
      const subtotal = window.FPCart.total(cart);
      const sub = document.getElementById("cart-subtotal");
      if (sub) sub.textContent = money(subtotal) + " USD";

      // ---- discount -------------------------------------------------------
      // Owner-confirmed: the free-shipping threshold is measured AFTER the
      // discount, i.e. on what the customer actually pays for the goods.
      const coupon = window.FPcoupon;
      const code = coupon ? coupon.stored() : "";
      const disc = coupon && code ? coupon.evaluate(code, subtotal) : null;
      const netGoods = disc && disc.ok ? coupon.netSubtotal(subtotal, disc.amount) : subtotal;

      const discRow = document.getElementById("cart-discount-row");
      const discEl = document.getElementById("cart-discount");
      const discLabel = document.getElementById("cart-discount-label");
      const statusEl = document.getElementById("coupon-status");
      const inputEl = document.getElementById("coupon-input");
      const removeEl = document.getElementById("coupon-remove");
      const applyEl = document.getElementById("coupon-apply");

      function setStatus(msg, kind) {
        if (!statusEl) return;
        statusEl.textContent = msg || "";
        statusEl.className = "cart-coupon-status" + (kind ? " is-" + kind : "");
      }

      if (disc && disc.ok) {
        if (discRow) discRow.hidden = false;
        if (discEl) discEl.textContent = "−$" + coupon.money(disc.amount) + " USD";
        if (discLabel) discLabel.textContent = "Discount (" + disc.code + " −" + disc.percent + "%)";
        if (removeEl) removeEl.hidden = false;
        if (applyEl) applyEl.hidden = true;
        if (inputEl) { inputEl.hidden = true; }
        setStatus("", "");
      } else {
        if (discRow) discRow.hidden = true;
        if (removeEl) removeEl.hidden = true;
        if (applyEl) applyEl.hidden = false;
        if (inputEl) { inputEl.hidden = false; }
        if (disc && disc.reason === "minimum") {
          // Code is real but the cart is too small: say exactly how much more.
          setStatus("Spend $" + coupon.money(disc.shortfall) + " more to use " +
                    disc.code + " (−" + disc.percent + "%).", "warn");
        } else if (disc && disc.reason === "unknown") {
          setStatus("That code isn't valid.", "error");
          if (coupon) coupon.store("");   // drop a stale/typo code so it can't linger
          if (inputEl) inputEl.hidden = false;
        } else {
          setStatus("", "");
        }
        if (inputEl && coupon && code && disc && disc.reason === "minimum") {
          inputEl.value = code;
        }
      }

      // Shipping line + grand total. Without this the shop silently absorbed
      // ~$18 on every order: PayPal was being handed the product total only.
      if (window.FPShipping) {
        const ship = window.FPShipping.forSubtotal(netGoods);
        const shipEl = document.getElementById("cart-shipping");
        if (shipEl) {
          shipEl.textContent = ship.free ? "Free" : "$" + window.FPShipping.money(ship.amount) + " USD";
          shipEl.classList.toggle("is-free", ship.free);
        }
        const totEl = document.getElementById("cart-total");
        if (totEl) totEl.textContent = "$" + window.FPShipping.money(window.FPShipping.grandTotal(netGoods)) + " USD";

        const nudge = document.getElementById("cart-ship-nudge");
        if (nudge) {
          const away = window.FPShipping.toFreeShipping(netGoods);
          if (away > 0) {
            nudge.hidden = false;
            nudge.textContent = "Add $" + window.FPShipping.money(away) +
              " more for free shipping.";
          } else if (netGoods > 0) {
            nudge.hidden = false;
            nudge.textContent = "You've got free standard shipping.";
          } else {
            nudge.hidden = true;
          }
        }
      }

      // Bundle nudge: show only while the cart holds exactly one piece.
      const totalQty = cart.items.reduce((s, i) => s + i.qty, 0);
      const banner = document.getElementById("bundle-banner");
      if (banner) banner.hidden = !(cart.items.length > 0 && totalQty === 1);

      // WhatsApp handoff: one tap sends the cart contents to the shop.
      const wa = document.getElementById("wa-cart");
      if (wa) {
        wa.hidden = cart.items.length === 0;
        if (!wa.hidden) {
          const cfg = (window.FP_CONFIG && window.FP_CONFIG.business) || {};
          const lines = cart.items.map(i =>
            `${i.qty} x ${i.name}${i.title ? " (" + i.title + ")" : ""} — $${(i.price * i.qty).toFixed(2)}`);
          const _sub = window.FPCart.total(cart);
          const _ship = window.FPShipping ? window.FPShipping.forSubtotal(_sub) : null;
          const _grand = window.FPShipping ? window.FPShipping.grandTotal(_sub) : _sub;
          const text = "Hi GAYA, I'd like to order:\n" + lines.join("\n") +
            "\nSubtotal: $" + _sub.toFixed(2) +
            (_ship ? "\nShipping: " + (_ship.free ? "free" : "$" + _ship.amount.toFixed(2)) : "") +
            "\nTotal: $" + _grand.toFixed(2);
          wa.href = "https://wa.me/" + String(cfg.phone || "").replace(/[^0-9]/g, "") +
            "?text=" + encodeURIComponent(text);
        }
      }

      window.FPPaypal && window.FPPaypal.refreshCart();
    }
    // ---- coupon: apply / remove / Enter --------------------------------
    (function initCoupon() {
      const inputEl = document.getElementById("coupon-input");
      const applyEl = document.getElementById("coupon-apply");
      const removeEl = document.getElementById("coupon-remove");
      if (!inputEl || !window.FPcoupon) return;

      function apply() {
        const raw = inputEl.value;
        const cart = load();
        const subtotal = window.FPCart.total(cart);
        const res = window.FPcoupon.evaluate(raw, subtotal);
        if (res.ok) {
          window.FPcoupon.store(res.code);
        } else if (res.reason === "unknown") {
          window.FPcoupon.store("");
        } else if (res.reason === "minimum") {
          // Keep it so the status can explain the shortfall, but don't apply.
          window.FPcoupon.store(res.code);
        }
        document.dispatchEvent(new CustomEvent("fp:cart"));
      }

      applyEl && applyEl.addEventListener("click", apply);
      inputEl.addEventListener("keydown", (e) => {
        if (e.key === "Enter") { e.preventDefault(); apply(); }
      });
      removeEl && removeEl.addEventListener("click", () => {
        window.FPcoupon.store("");
        if (inputEl) { inputEl.value = ""; }
        document.dispatchEvent(new CustomEvent("fp:cart"));
      });
    })();

    document.addEventListener("fp:cart", renderCart);
    renderCart();
  }

  renderBadge(load());
})();
