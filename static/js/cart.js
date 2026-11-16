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
        title: opt.textContent.split("—")[0].trim(),
        price: Number(opt.dataset.price || opt.textContent.match(/[\d.]+/)?.[0] || 0),
        image: images[0] ? images[0].src : "",
        handle: art.dataset.handle,
        name: art.dataset.title
      };
    }
    if (addBtn) {
      addBtn.addEventListener("click", () => {
        const s = selected();
        const qty = Math.max(1, Math.min(99, parseInt(qtyInput.value, 10) || 1));
        if (optDisabled(s.vid)) return;
        window.FPCart.add({ ...s, qty });
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
      const sub = document.getElementById("cart-subtotal");
      if (sub) sub.textContent = money(window.FPCart.total(cart)) + " USD";
      window.FPPaypal && window.FPPaypal.refreshCart();
    }
    document.addEventListener("fp:cart", renderCart);
    renderCart();
  }

  renderBadge(load());
})();
