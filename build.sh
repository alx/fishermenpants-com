#!/usr/bin/env bash
# Build the Hugo site. HUGO_BASEURL overrides baseURL (GitHub Pages project sites
# need e.g. https://<user>.github.io/fishermenpants-com/)
set -euo pipefail
cd "$(dirname "$0")"
BASE="${HUGO_BASEURL:-/}"

# generate responsive image variants (static/img/_gen); incremental, so this is
# fast on repeat builds and a no-op when nothing changed
python3 tools/optimize_images.py

# rebuild client-side search index from content files
python3 tools/mksearchindex.py

hugo --baseURL "$BASE" --minify

echo "built -> public/  (base: $BASE)"
