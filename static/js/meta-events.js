/* Fishermen Pants — Meta pixel events + click-id persistence.
   Safe to load whether or not the pixel is configured (hugo.toml params.meta.pixelId):
   - Always: captures fbclid/gclid/ttclid/msclkid into localStorage so the
     checkout order email can carry attribution (window.fpClickId()).
   - Only when fbq() exists: fires the standard funnel events.
   Never pass personal data (email, name, address) as event metadata. */
(function () {
  // ---- click-id persistence (always on) ----
  const IDS = ["fbclid", "gclid", "ttclid", "msclkid"];
  const KEY = "fp_clickid";
  let stored = null;
  try { stored = JSON.parse(localStorage.getItem(KEY)); } catch {}

  const q = new URLSearchParams(location.search);
  for (const k of IDS) {
    const v = q.get(k);
    if (v && v.length < 200) {
      stored = { id: v, source: k, ts: Date.now() };
      try { localStorage.setItem(KEY, JSON.stringify(stored)); } catch {}
      break;
    }
  }
  window.fpClickId = function () {
    if (!stored) return "";
    // drop ids older than 90 days
    if (stored.ts && Date.now() - stored.ts > 90 * 86400 * 1000) return "";
    return stored.source + "=" + stored.id;
  };

  // ---- pixel events (only when the loader injected fbq) ----
  const track = (name, data) => {
    try { if (typeof window.fbq === "function") window.fbq("track", name, data || {}); } catch {}
  };

  const isProduct = !!document.querySelector(".product");
  const isCart = !!document.getElementById("cart-items");

  if (isProduct) {
    const art = document.querySelector(".product");
    track("ViewContent", {
      content_category: "product",
      content_ids: art ? art.dataset.handle : ""
    });
  } else if (!isCart && location.pathname.replace(/\/$/, "") !== "") {
    track("ViewContent", { content_category: "page" });
  }
  if (isCart && localStorage.getItem("fp_cart_v1")) {
    // cart page with items (load() lives in cart.js; keep this dependency-free)
    track("ViewContent", { content_category: "cart" });
  }

  document.addEventListener("fp:added", e => {
    const d = e.detail || {};
    track("AddToCart", {
      content_category: "product",
      content_ids: d.handle || "",
      value: Number(d.price || 0),
      quantity: Number(d.qty || 1)
    });
  });
  document.addEventListener("fp:checkout_started", e => {
    const d = e.detail || {};
    track("InitiateCheckout", {
      value: Number(d.total || 0),
      num_items: Number(d.items || 0)
    });
  });
  document.addEventListener("fp:order_placed", e => {
    const d = e.detail || {};
    track("Purchase", {
      value: Number(d.total || 0),
      num_items: Number(d.items || 0),
      currency: "USD"
    });
  });
})();
