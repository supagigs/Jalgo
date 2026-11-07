#!/usr/bin/env bash
# Update jalgo_pos in place. Backs up the site and keeps the old code for rollback.
# Usage: SITE=site.name BENCH=~/frappe-bench ./scripts/update.sh
set -euo pipefail
: "${SITE:?set SITE}"; BENCH="${BENCH:-$HOME/frappe-bench}"
SRC="$(cd "$(dirname "$0")/.." && pwd)"
cd "$BENCH"
[ -d apps/jalgo_pos ] || { echo "jalgo_pos is not installed. Use scripts/install.sh"; exit 1; }
if [ -d apps/jalgo_pos/.git ] && [ -n "$(cd apps/jalgo_pos && git status --porcelain)" ]; then
  echo "apps/jalgo_pos has local changes. Commit or move them first."; exit 1
fi
bench --site "$SITE" backup --with-files
STAMP=$(date +%Y%m%d-%H%M%S)
cp -a apps/jalgo_pos "apps/jalgo_pos.bak-$STAMP"
rsync -a --delete --exclude node_modules --exclude .git "$SRC/" apps/jalgo_pos/
(cd apps/jalgo_pos && git add -A && git -c user.name=jalgo -c user.email=jalgo@localhost commit -qm "jalgo_pos update $STAMP" || true)
bench --site "$SITE" migrate
bench build --app jalgo_pos
bench --site "$SITE" clear-cache
curl -fsS -o /dev/null "$(bench --site "$SITE" execute frappe.utils.get_url | tr -d '"')/api/method/ping" && echo "Health check OK"
echo "Updated. Old code kept in apps/jalgo_pos.bak-$STAMP"
