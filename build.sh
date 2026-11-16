#!/usr/bin/env bash
# Build the Hugo site. HUGO_BASEURL overrides baseURL (GitHub Pages project sites
# need e.g. https://<user>.github.io/fishermenpants-com/)
set -euo pipefail
cd "$(dirname "$0")"
BASE="${HUGO_BASEURL:-/}"

# rebuild client-side search index from content files
python3 tools/mksearchindex.py

hugo --baseURL "$BASE" --minify

echo "built -> public/  (base: $BASE)"
