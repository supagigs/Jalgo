#!/usr/bin/env bash
set -euo pipefail
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
step(){ echo "=== $(date +%T) $* ==="; }
step user tools
pip install -q --user --break-system-packages uv 2>/dev/null || python3 -m pip install -q --user --break-system-packages uv
uv python install 3.14
PY314=$(uv python find 3.14); echo "$PY314"
uv tool install --python 3.14 frappe-bench >/dev/null
which node; node --version; yarn --version
cd ~
step bench init
[ -d jalgo-bench ] || bench init jalgo-bench --frappe-branch version-16 --python "$PY314" --skip-redis-config-generation --no-backups
cd jalgo-bench
bench set-config -g redis_cache redis://127.0.0.1:6379
bench set-config -g redis_queue redis://127.0.0.1:6379
bench set-config -g redis_socketio redis://127.0.0.1:6379
bench set-config -g developer_mode 1
step get erpnext v16.53.0
[ -d apps/erpnext ] || bench get-app --branch v16.53.0 erpnext https://github.com/frappe/erpnext
step new site
[ -d sites/jalgo.staging ] || bench new-site jalgo.staging --db-root-password "${DB_ROOT_PASSWORD:?set DB_ROOT_PASSWORD}" --admin-password "${ADMIN_PASSWORD:?set ADMIN_PASSWORD}" --install-app erpnext
bench use jalgo.staging
bench version
step DONE
