#!/usr/bin/env bash
# Deploy: source -> master, built site -> gh-pages branch (GitHub Pages).
#   OWNER defaults to the authenticated gh account; REPO defaults to fishermenpants-com
#   BASE_URL defaults to https://<owner>.github.io/<repo>/
set -euo pipefail
cd "$(dirname "$0")/.."

OWNER="${OWNER:-$(gh api v1/user -q .login)}"
REPO="${REPO:-fishermenpants-com}"
FULL="${OWNER}/${REPO}"
BASE_URL="${BASE_URL:-https://${OWNER}.github.io/${REPO}/}"
REPO_URL="https://github.com/${FULL}.git"

# 1. create the repo if missing
if ! gh repo view "$FULL" >/dev/null 2>&1; then
  echo "creating $FULL"
  gh repo create "$FULL" --public --description "Static Hugo clone of fishermenpants.com"
fi

# 2. build for Pages
HUGO_BASEURL="$BASE_URL" ./build.sh

# 3. push source (master)
git add -A
git commit -m "update site" --allow-empty || true
git remote add origin "$REPO_URL" 2>/dev/null || git remote set-url origin "$REPO_URL"
git push -u origin HEAD

# 4. push built site to gh-pages branch
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
rsync -a --delete public/ "$TMP/"
git -C "$TMP" init -q -b gh-pages
git -C "$TMP" add -A
git -C "$TMP" -c user.name="${GIT_AUTHOR_NAME:-deploy}" -c user.email="${GIT_AUTHOR_EMAIL:-deploy@local}" \
  commit -qm "pages build $(date -u +%Y-%m-%dT%H:%M:%SZ)"
git -C "$TMP" push -q --force "$REPO_URL" gh-pages
rm -rf "$TMP"; trap - EXIT

# 5. enable Pages on gh-pages /
existing="$(gh api "repos/${FULL}/pages" 2>/dev/null || true)"
if ! echo "$existing" | grep -q '"url"'; then
  gh api -X POST "repos/${FULL}/pages" -f source[branch]="gh-pages" -f source[path]="/" >/dev/null
fi
echo "Pages source: gh-pages branch -> $BASE_URL"
