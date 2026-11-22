# Fishermen Pants — GAYA boutique by the sea

Static Hugo storefront for **https://www.fishermenpants.com**, hosted on GitHub Pages
on the custom domain. No backend: the cart is client-side, payment goes through
PayPal's classic checkout, and order emails go through Formspree.

## Content and editing

Content lives in the repo and is editable in the browser at **/admin/** (Sveltia CMS,
Git-based — every save is a commit that the deploy workflow publishes).

- `content/products/` — one Markdown file per product (YAML front matter)
- `content/collections/` — shop categories; each lists product handles
- `content/pages/` — About, Contact, Shipping & Returns, Size Guide, Payment Methods, Privacy
- `data/home.yaml` — home page: hero slides, interstitials, tiles, testimonials, video
- `layouts/` — Hugo templates
- `static/` — CSS, JS, images (`static/img/`)

Product front matter: `title`, `price`, `compareAtMin`, `ptype`, `vendor`,
`images` (paths like `/img/foo.png`), `collections` (category handles), body Markdown.

### Editing in the CMS

Open `/admin/`, choose **Sign In Using Access Token**, and paste a fine-grained
personal access token with **Contents: Read and write** on this repo. The token is
kept in the browser, never in the repo.

## Build

```bash
./build.sh                                          # -> public/
HUGO_BASEURL="https://www.fishermenpants.com/" ./build.sh
```

`build.sh` runs `tools/optimize_images.py` (generates WebP variants into
`static/img/_gen/`, gitignored and cached in CI), then `tools/mksearchindex.py`,
then Hugo.

**Hugo version matters:** CI installs `hugo-extended` unpinned (currently 0.169).
Local builds must use the same version — `_build:` front matter was removed in
0.145 and fails on newer Hugo.

## Deploy

Pushing to `master` runs `.github/workflows/pages.yml`: installs Pillow and
Hugo, builds, and deploys through `actions/deploy-pages`. Pages source is
**GitHub Actions** (`build_type: workflow`); the custom domain is set on the repo
and also tracked as `static/CNAME`.

GitHub resets `https_enforced` to false whenever the domain or certificate
changes — re-enable it with `PUT /repos/{owner}/{repo}/`pages`.

## Checks

```bash
python3 tools/verify.py
```

The verify step is the safety net and runs on every build. It checks: every
front-matter image exists; private pages (`/cart/`, `/search/`, `/order/thank-you/`)
are out of the sitemap and carry `noindex`; structured data (JSON-LD) is valid with
absolute URLs; every product belongs to a collection; every handle referenced in
`data/home.yaml` or in a collection resolves.

## Analytics

Simple Analytics (privacy-first), hostname `fishermenpants.com`, with funnel
events: `add_to_cart`, `checkout_started`, `order_placed`, `newsletter_submit`.
Events never include personal data.

## Payment

- **PayPal** classic checkout, `business = thaifishpants@gmail.com`. Cart lines send
  the **unit price** (PayPal multiplies it by quantity) plus a description via `on0/os0`.
- **MetaMask / Solana**: wallet addresses and QR codes on `/payment-methods/`.
- Orders are collected on `/cart/` (name, email, address) and emailed to the seller
  through Formspree; a reference like `FP-261116-ABCD` is generated per order.

## Tooling

- `tools/crawl2.py` — paced crawler of the original live site
- `tools/build_content.py` — turns `_crawl/parsed.json` into Hugo content
- `tools/mksearchindex.py` — rebuilds the client-side search index
- `tools/optimize_images.py` — responsive WebP variants into `static/img/_gen/`
