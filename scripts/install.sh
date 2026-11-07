#!/usr/bin/env bash
# Throwaway staging install of ERPNext v16.53.0 in this sandbox. Not for production.
set -euo pipefail
LOG=/home/claude/setup/install.log
exec > >(tee -a "$LOG") 2>&1
step(){ echo "=== $(date +%T) $* ==="; }

step apt packages
export DEBIAN_FRONTEND=noninteractive
apt-get install -y -qq mariadb-server mariadb-client libmariadb-dev pkg-config build-essential git cron xvfb libffi-dev libssl-dev >/dev/null

step mariadb config
cat >/etc/mysql/mariadb.conf.d/99-frappe.cnf <<'EOF'
[mysqld]
character-set-client-handshake = FALSE
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci
innodb_buffer_pool_size = 512M
[mysql]
default-character-set = utf8mb4
EOF
service mariadb restart || (mysqld_safe >/dev/null 2>&1 & sleep 8)
mysql -uroot -e "ALTER USER 'root'@'localhost' IDENTIFIED VIA mysql_native_password USING PASSWORD('"${DB_ROOT_PASSWORD:?set DB_ROOT_PASSWORD}"'); FLUSH PRIVILEGES;" || true
mysql -uroot -p"${DB_ROOT_PASSWORD:?set DB_ROOT_PASSWORD}" -e "select version();"

step python 3.14 via uv
pip install -q --break-system-packages uv
uv python install 3.14
PY314=$(uv python find 3.14)
echo "python: $PY314"

step node 24
npm i -g -s node@24 yarn
hash -r
node --version

step frappe-bench cli
uv tool install --python 3.14 frappe-bench
export PATH="$HOME/.local/bin:$PATH"
bench --version

step bench init
cd /home/claude
if [ ! -d jalgo-bench ]; then
  bench init jalgo-bench --frappe-branch version-16 --python "$PY314" --skip-redis-config-generation --no-backups
fi
cd jalgo-bench
bench set-config -g redis_cache redis://127.0.0.1:6379
bench set-config -g redis_queue redis://127.0.0.1:6379
bench set-config -g redis_socketio redis://127.0.0.1:6379
(redis-cli ping || redis-server --daemonize yes)

step get erpnext v16.53.0
[ -d apps/erpnext ] || bench get-app --branch v16.53.0 erpnext https://github.com/frappe/erpnext

step new site
bench new-site jalgo.staging --db-root-password "${DB_ROOT_PASSWORD:?set DB_ROOT_PASSWORD}" --admin-password "${ADMIN_PASSWORD:?set ADMIN_PASSWORD}" --install-app erpnext
bench --site jalgo.staging set-config developer_mode 1
bench use jalgo.staging
bench version
step DONE
