/* Fishermen Pants — order backend (Cloudflare Worker + KV + Brevo).
 *
 * Routes:
 *   POST /ipn          PayPal IPN receiver (verified against paypal.com/mqcp)
 *   GET  /o/:ref       Order JSON (owner lookup; no auth — refs are unguessable)
 *   GET  /healthz      Liveness
 *
 * The checkout page encodes the customer (name, email, address) into PayPal's
 * `custom` field (pipe-delimited, <= 255 chars) so the confirmation email can
 * be built entirely from the IPN payload.
 *
 * Secrets: BREVO_API_KEY, BREVO_FROM_EMAIL (set via `wrangler secret put`).
 */

const PP_VERIFY = "https://www.paypal.com/mqcp";

export default {
  async fetch(req, env, ctx) {
    const url = new URL(req.url);
    if (req.method === "POST" && url.pathname === "/ipn") return handleIpn(req, env, ctx);
    if (req.method === "GET" && url.pathname === "/healthz") return json({ ok: true });
    const m = url.pathname.match(/^\/o\/([A-Z0-9-]+)$/i);
    if (req.method === "GET" && m) {
      const order = await env.ORDERS.get(decodeURIComponent(m[1]), "json");
      if (!order) return notFound();
      return json(order);
    }
    return notFound();
  },
};

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status: status,
    headers: { "content-type": "application/json" },
  });
}
function notFound() {
  return new Response("not found", { status: 404 });
}

async function handleIpn(req, env, ctx) {
  const raw = await req.text();

  // PayPal IPN verification: replay the exact body with cmd=_notify-validate.
  const verify = await postForm(
    PP_VERIFY,
    new URLSearchParams([["cmd", "_notify-validate"], ...new URLSearchParams(raw).entries()])
  );
  if (!verify.body.startsWith("VERIFIED")) {
    // Not from PayPal (or verification service unavailable) — accept nothing.
    return new Response("unverified", { status: 400 });
  }

  const f = Object.fromEntries(new URLSearchParams(raw).entries());
  if (f.business !== env.BUSINESS_EMAIL) return json({ ignored: "wrong business" });

  const ref = f.invoice || "";
  if (!ref) return json({ ignored: "no invoice ref" });

  const order = {
    ref,
    receivedAt: new Date().toISOString(),
    currency: f.mc_currency || "USD",
    gross: Number(f.mc_gross || 0),
    paymentStatus: f.payment_status || "",
    transactionId: f.transaction_id || "",
    // classic-button line items (up to 12)
    items: parseClassicItems(f),
    customer: decodeCustom(f.custom),
  };
  await env.ORDERS.put(ref, JSON.stringify(order));

  // Fire the customer confirmation. Email failure must not make PayPal retry forever.
  if (f.payment_status === "Completed") {
    const ok = await sendConfirmation(env, order);
    ctx.log(ok ? "email sent" : "email failed");
  }
  return new Response("OK");
}

// classic _cart IPN: item_name_N / quantity_N / (amount_N absent) — name only, qty from IPN.
function parseClassicItems(f) {
  const out = [];
  for (let n = 1; n <= 12; n++) {
    const name = f[`item_name_${n}`];
    if (!name) break;
    out.push({ name: decodeURIComponent(name), qty: Number(f[`quantity_${n}`] || 1) });
  }
  return out;
}

// custom = c1|name|email|addr1|addr2|city|state|zip|country
function decodeCustom(c) {
  if (!c || !c.startsWith("c1|")) return {};
  const p = decodeURIComponent(c).split("|").slice(1);
  const keys = ["name", "email", "addr1", "addr2", "city", "state", "zip", "country"];
  const o = {};
  keys.forEach((k, i) => (o[k] = (p[i] || "").slice(0, 120)));
  return o;
}

async function sendConfirmation(env, order) {
  const c = order.customer || {};
  if (!c.email) return false;
  const lines = (order.items || [])
    .map((it) => `<tr><td style="padding:2px 12px 2px 0;white-space:nowrap">${esc(it.name)} x${it.qty}</td></tr>`)
    .join("");
  const html = `
  <div style="font-family:Arial,Helvetica,sans-serif;max-width:560px;margin:0 auto;color:#1c2430">
    <h1 style="font-size:20px">Thanks — your order is in, ${esc(c.name || "friend")}</h1>
    <p>Your order reference is <strong>${esc(order.ref)}</strong>. Quote it whenever you contact us.</p>
    <table cellpadding="0" cellspacing="0">${lines || "<tr><td>No line items decoded</td></tr>"}</table>
    <p style="font-size:18px;padding:10px 0"><strong>Total: $${order.gross.toFixed(2)} ${esc(order.currency)}</strong></p>
    ${
      c.addr1
        ? `<p><strong>Shipping to</strong><br>${esc(c.addr1)}${c.addr2 ? "<br>" + esc(c.addr2) : ""}<br>${esc(c.city)} ${esc(c.state)} ${esc(c.zip)}<br>${esc(c.country)}</p>`
        : ""
    }
    <p>Your parcel leaves our shop in Lamai Beach, Koh Samui within a few days.
       Delivery typically takes 2–4 business days in Thailand, 2–4 weeks to Europe/USA.
       We'll email you when it ships.</p>
    <p style="color:#6b7280;font-size:13px">Questions? WhatsApp <a href="https://wa.me/66625508121">+66 62 550 8121</a>
       or email <a href="mailto:thaifishpants@gmail.com">thaifishpants@gmail.com</a>
       — or see our <a href="${env.SITE}/pages/shipping-returns/">shipping &amp; returns policy</a>.</p>
  </div>`;
  const body = {
    to: [{ email: c.email, name: c.name || "" }],
    sender: { email: env.BREVO_FROM_EMAIL, name: "Thai FishermenPants" },
    subject: `Your order ${order.ref} — Fishermen Pants (Koh Samui)`,
    htmlContent: html,
  };
  try {
    const res = await fetch("https://api.brevo.com/v3/smtp/email", {
      method: "POST",
      headers: {
        "api-key": env.BREVO_API_KEY,
        "content-type": "application/json",
        accept: "application/json",
      },
      body: JSON.stringify(body),
    });
    return res.ok;
  } catch {
    return false;
  }
}

async function postForm(url, params) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 8000);
  try {
    const res = await fetch(url, {
      method: "POST",
      body: params.toString(),
      headers: { "content-type": "application/x-www-form-urlencoded" },
      signal: ctrl.signal,
    });
    return { status: res.status, body: await res.text() };
  } catch (e) {
    return { status: 0, body: "error: " + e.message };
  } finally {
    clearTimeout(t);
  }
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
}
