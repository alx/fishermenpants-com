#!/usr/bin/env bash
# Build the Hugo site. HUGO_BASEURL overrides baseURL (GitHub Pages project sites
# need e.g. https://<user>.github.io/fishermenpants-com/)
set -euo pipefail
cd "$(dirname "$0")"
BASE="${HUGO_BASEURL:-/}"

# Keep local and CI Hugo in sync (see .github/workflows/pages.yml). A version
# mismatch already caused a failed deploy: _build: front matter was removed in
# Hugo 0.145, so 0.159 accepted it locally while 0.169 in CI did not.
HUGO_PINNED="0.169.0"
HUGO_ACTUAL="$(hugo version 2>/dev/null | sed -n 's/.*v\([0-9][0-9.]*\).*/\1/p' | head -1)"
if [ -z "$HUGO_ACTUAL" ]; then
  echo "error: hugo not found in PATH" >&2
  exit 1
fi
if [ "$HUGO_ACTUAL" != "$HUGO_PINNED" ]; then
  echo "error: Hugo $HUGO_ACTUAL found, but this project is pinned to $HUGO_PINNED." >&2
  echo "       CI installs exactly $HUGO_PINNED; a different local version will" >&2
  echo "       build fine here and fail there. Install it with:" >&2
  echo "         npm install -g hugo-extended@$HUGO_PINNED" >&2
  echo "       (set SKIP_HUGO_CHECK=1 to bypass at your own risk)" >&2
  [ "${SKIP_HUGO_CHECK:-0}" = "1" ] || exit 1
fi

# generate responsive image variants (static/img/_gen); incremental, so this is
# fast on repeat builds and a no-op when nothing changed
python3 tools/optimize_images.py

# rebuild client-side search index from content files
python3 tools/mksearchindex.py

hugo --baseURL "$BASE" --minify

echo "built -> public/  (base: $BASE)"
