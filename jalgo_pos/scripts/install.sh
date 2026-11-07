#!/usr/bin/env bash
# Install jalgo_pos into an existing ERPNext 16 bench. Run as the bench user.
# Usage: SITE=site.name BENCH=~/frappe-bench ./scripts/install.sh
set -euo pipefail
: "${SITE:?set SITE}"; BENCH="${BENCH:-$HOME/frappe-bench}"
SRC="$(cd "$(dirname "$0")/.." && pwd)"
cd "$BENCH"
[ -d apps/erpnext ] || { echo "ERPNext not found in $BENCH/apps"; exit 1; }
[ -e apps/jalgo_pos ] && { echo "apps/jalgo_pos already exists. Use scripts/update.sh"; exit 1; }
bench --site "$SITE" backup
rsync -a --exclude node_modules --exclude .git "$SRC/" apps/jalgo_pos/
(cd apps/jalgo_pos && git init -q && git add -A && git -c user.name=jalgo -c user.email=jalgo@localhost commit -qm "jalgo_pos import")
# add to apps.txt (works with both GNU and macOS tools)
TMP=$(mktemp); { cat sites/apps.txt; echo; echo jalgo_pos; } | grep -v '^$' | awk '!seen[$0]++' > "$TMP" && mv "$TMP" sites/apps.txt
if [ -x ./env/bin/pip ]; then ./env/bin/pip install -q -e apps/jalgo_pos; else uv pip install -q -e apps/jalgo_pos --python ./env/bin/python; fi
bench --site "$SITE" install-app jalgo_pos
bench build --app jalgo_pos
bench --site "$SITE" clear-cache
echo "Installed. Open /jalgo-pos. Change the manager PIN in JALGO POS Settings (demo PIN 2468)."
