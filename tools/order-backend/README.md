# Order backend (Cloudflare Worker)

Receives PayPal IPN, stores orders in KV, emails the customer a confirmation
(via Brevo free tier). This is finding #1 from
`org/proposals/fishermenpants-revenue-proposal.md` (beads org-9dl3).

## Deploy (owner steps — ~10 min)

1. **Brevo** (free, 300 emails/day): create account at brevo.com, verify a
   sending domain/address (e.g. `orders@fishermenpants.com` or the gmail).
   Get the API key: Settings → API keys.
2. **Cloudflare**: `npm i -g wrangler` (or `npx wrangler`), `wrangler login`.
3. From this directory:
   ```bash
   wrangler kv namespace create fp_orders   # paste the id into wrangler.toml
   wrangler secret put BREVO_API_KEY
   wrangler secret put BREVO_FROM_EMAIL
   wrangler deploy
   ```
4. **PayPal**: Developer Tools → IPN → add the Worker URL as IPN address
   (or, per classic button: Manage buttons → Advanced → set IPN address) to
   `https://fp-orders.<you>.workers.dev/ipn`.
5. **Test**: `npx wrangler tail` in this directory, then place a real (or
   $1 test) order. Expected: IPN verified, order in KV, customer gets the
   confirmation email. Lookup: `https://fp-orders.<you>.workers.dev/o/FP-XXXXXXXX`.

## What the site already does (no changes needed)

- `static/js/checkout.js` notifies the seller via Formspree (kept as fallback)
  and fires `fp:order_placed`.
- `static/js/paypal.js` packs the customer (name/email/address) into PayPal's
  `custom` field as `c1|…` (≤255 chars) so the confirmation email needs no
  other source of truth.

## Limits / next steps

- Confirmation only; shipping/review-request emails (beads org-saej) extend
  `worker.js` with a manual "mark shipped" route.
- When beads org-wgho (PayPal JS SDK) lands, replace the IPN route with the
  JS-SDK order webhook — the KV schema and email template carry over.
