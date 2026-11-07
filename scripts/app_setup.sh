#!/usr/bin/env bash
# Creates and installs the jalgo app on the jalgo.staging site (throwaway sandbox staging).
set -euo pipefail
export PATH="/opt/node24/bin:$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
cd ~/jalgo-bench
ls apps/ sites/ Procfile
step(){ echo "=== $(date +%T) $* ==="; }

step backup before changes
bench --site jalgo.staging backup --with-files

step new app
if [ ! -d apps/jalgo ]; then
  printf 'JALGO\nHyperlocal grocery commerce for Jalgaon on ERPNext\nJALGO\nadmin@jalgo.example\nmit\nN\nN\nN\n' | bench new-app jalgo
fi
SRC=/home/frappe/jalgo-src
cp $SRC/doctype_defs.py $SRC/logic.py $SRC/api.py $SRC/demo.py $SRC/reports.py $SRC/test_jalgo.py apps/jalgo/jalgo/
mkdir -p apps/jalgo/jalgo/public/shop
cp -r $SRC/shop/* apps/jalgo/jalgo/public/shop/
grep -q 'JALGO doc_events' apps/jalgo/jalgo/hooks.py || cat >> apps/jalgo/jalgo/hooks.py <<'EOF'

# JALGO doc_events
doc_events = {
	"JALGO Order": {
		"validate": "jalgo.logic.order_validate",
		"on_update": "jalgo.logic.order_on_update",
	}
}
required_apps = ["erpnext"]
website_redirects = [{"source": "/shop", "target": "/assets/jalgo/shop/index.html"}]
EOF
grep -q '^Jalgo$' apps/jalgo/jalgo/modules.txt || echo "Jalgo" >> apps/jalgo/jalgo/modules.txt

step install app
bench --site jalgo.staging list-apps | grep -q jalgo || bench --site jalgo.staging install-app jalgo
step doctypes
bench --site jalgo.staging execute jalgo.doctype_defs.run
bench --site jalgo.staging migrate
bench build --app jalgo
step company
bench --site jalgo.staging execute jalgo.demo.setup_company
step DONE
