#!/usr/bin/env bash
# Deploy to GitHub + GitHub Pages.
#   OWNER defaults to the authenticated gh account; REPO defaults to fishermenpants-com
#   BASE_URL can be overridden; defaults to https://<owner>.github.io/<repo>/
set -euo pipefail
cd "$(dirname "$0")/.."

OWNER="${OWNER:-$(gh api v1/user -q .login)}"
REPO="${REPO:-fishermenpants-com}"
FULL="${OWNER}/${REPO}"
BASE_URL="${BASE_URL:-https://${OWNER}.github.io/${REPO}/}"

# create the repo if missing
if ! gh repo view "$FULL" >/dev/null 2>&1; then
  echo "creating $FULL"
  gh repo create "$FULL" --public --description "Static Hugo clone of fishermenpants.com"
fi

# build for Pages
HUGO_BASEURL="$BASE_URL" ./build.sh

# push
git add -A
git commit -m "update site" --allow-empty || true
git remote add origin "https://github.com/${FULL}.git" 2>/dev/null || git remote set-url origin "https://github.com/${FULL}.git"
git push -u origin HEAD

# enable Pages on the / root of the default branch (serves public/)
BRANCH="$(git branch --show-current)"
existing="$(gh api "repos/${FULL}/pages" 2>/dev/null || true)"
if ! echo "$existing" | grep -q '"url"'; then
  gh api -X POST "repos/${FULL}/pages" -f source='{"branch":"'$BRANCH'","path":"/public"}' >/dev/null
fi
echo "Pages configured: $BASE_URL"
