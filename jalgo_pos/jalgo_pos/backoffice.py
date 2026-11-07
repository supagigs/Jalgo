"""Set-Up back office: read-only lists, ERPNext reports, dashboard and per-user button order.
All reads go through frappe.get_list / report runner, so ERPNext permissions apply."""
import json

import frappe
from frappe import _
from frappe.utils import flt, cint, nowdate, add_days, get_first_day

from jalgo_pos.api import _require_cashier, profile

# module -> (doctype, fields, labels, filters, order)
MODULES = {
	"Items": ("Item", ["name", "item_name", "item_group", "stock_uom", "disabled"], ["Code", "Name", "Category", "Unit", "Disabled"], {"is_stock_item": 1}, "item_name asc"),
	"Customers": ("Customer", ["name", "customer_name", "mobile_no", "customer_group", "gst_category"], ["ID", "Name", "Mobile", "Group", "GST category"], {}, "modified desc"),
	"Suppliers": ("Supplier", ["name", "supplier_name", "supplier_group", "gstin"], ["ID", "Name", "Group", "GSTIN"], {}, "modified desc"),
	"Sales Invoices": ("Sales Invoice", ["name", "posting_date", "customer_name", "rounded_total", "outstanding_amount", "status"], ["Bill", "Date", "Customer", "Total", "Outstanding", "Status"], {"docstatus": 1}, "creation desc"),
	"Sales Returns": ("Sales Invoice", ["name", "posting_date", "customer_name", "return_against", "rounded_total"], ["Credit note", "Date", "Customer", "Against", "Amount"], {"docstatus": 1, "is_return": 1}, "creation desc"),
	"Receive Payments": ("Sales Invoice", ["name", "posting_date", "customer_name", "rounded_total", "outstanding_amount"], ["Bill", "Date", "Customer", "Total", "Still owed"], {"docstatus": 1, "outstanding_amount": [">", 0]}, "posting_date asc"),
	"GRN": ("Purchase Receipt", ["name", "posting_date", "supplier", "supplier_delivery_note", "grand_total", "status"], ["GRN", "Date", "Supplier", "Supplier invoice", "Total", "Status"], {}, "creation desc"),
	"Make Payments": ("Purchase Invoice", ["name", "posting_date", "supplier", "bill_no", "grand_total", "outstanding_amount"], ["Bill", "Date", "Supplier", "Supplier bill no.", "Total", "To pay"], {"docstatus": 1, "outstanding_amount": [">", 0]}, "due_date asc"),
	"Manage Stock": ("Stock Entry", ["name", "posting_date", "stock_entry_type", "from_warehouse", "to_warehouse", "total_amount"], ["Entry", "Date", "Type", "From", "To", "Value"], {"docstatus": 1}, "creation desc"),
	"Transfer Stock": ("Stock Entry", ["name", "posting_date", "from_warehouse", "to_warehouse", "total_amount"], ["Entry", "Date", "From", "To", "Value"], {"docstatus": 1, "stock_entry_type": "Material Transfer"}, "creation desc"),
	"Cash Registers": ("JALGO POS Shift", ["name", "cashier", "status", "opened_at", "closed_at", "sales_total", "difference"], ["Shift", "Cashier", "Status", "Opened", "Closed", "Sales", "Cash difference"], {}, "creation desc"),
	"Business Locations": ("Warehouse", ["name", "warehouse_type", "is_group"], ["Warehouse", "Type", "Group"], {"is_group": 0}, "name asc"),
	"Employees": ("User", ["name", "full_name", "enabled", "last_login"], ["User", "Name", "Enabled", "Last login"], {"user_type": "System User"}, "full_name asc"),
}
SEARCH_FIELD = {"Item": "item_name", "Customer": "customer_name", "Supplier": "supplier_name", "Sales Invoice": "customer_name",
	"Purchase Receipt": "supplier", "Purchase Invoice": "supplier", "Stock Entry": "name", "JALGO POS Shift": "cashier", "Warehouse": "name", "User": "full_name"}


@frappe.whitelist()
def module_list(module, txt="", start=0):
	_require_cashier()
	if module not in MODULES:
		frappe.throw(_("Unknown module {0}.").format(module))
	dt, fields, labels, filters, order = MODULES[module]
	or_filters = None
	if txt:
		or_filters = {"name": ["like", f"%{txt}%"], SEARCH_FIELD[dt]: ["like", f"%{txt}%"]}
	rows = frappe.get_list(dt, fields=fields, filters=filters, or_filters=or_filters, order_by=order,
		start=cint(start), limit=50)
	if module == "Items" and rows:
		p = profile()
		stock = {b.item_code: b.actual_qty for b in frappe.get_all("Bin", filters={"item_code": ["in", [r.name for r in rows]], "warehouse": p.warehouse}, fields=["item_code", "actual_qty"])}
		price = {x.item_code: x.price_list_rate for x in frappe.get_all("Item Price", filters={"item_code": ["in", [r.name for r in rows]], "price_list": p.selling_price_list}, fields=["item_code", "price_list_rate"])}
		labels = labels + ["Price", "Shop stock"]
		for r in rows:
			r["price"], r["stock"] = flt(price.get(r.name)), flt(stock.get(r.name))
	if module == "Business Locations" and rows:
		vals = {r.warehouse: r.v for r in frappe.db.sql("select warehouse, sum(stock_value) v from tabBin group by warehouse", as_dict=1)}
		labels = labels + ["Stock value"]
		for r in rows:
			r["value"] = flt(vals.get(r.name))
	keys = list(rows[0].keys()) if rows else fields
	return {"doctype": dt, "labels": labels, "keys": keys, "rows": [[r.get(k) for k in keys] for r in rows],
		"total": frappe.db.count(dt, filters) if frappe.has_permission(dt, "read") else len(rows)}


# ---------------------------------------------------------------- reports
def _f(**extra):
	p = profile()
	return {"company": p.company, "from_date": str(get_first_day(nowdate())), "to_date": nowdate(), **extra}


def REPORTS():
	p = profile()
	return {
		"Analytical": [
			("Fast Moving Items", "Sales Analytics", _f(tree_type="Item", doc_type="Sales Invoice", value_quantity="Quantity", range="Monthly")),
			("Sales by Category", "Sales Analytics", _f(tree_type="Item Group", doc_type="Sales Invoice", value_quantity="Value", range="Weekly")),
			("Margin by Item", "Gross Profit", _f(group_by="Item Code")),
		],
		"Sales": [
			("Sales Register", "Sales Register", _f()),
			("Item-wise Sales", "Item-wise Sales Register", _f()),
			("Credit (Udhaar) Outstanding", "Accounts Receivable", {"company": p.company, "report_date": nowdate(), "ageing_based_on": "Due Date", "range": "30, 60, 90, 120"}),
		],
		"Stock": [
			("Stock Balance (this shop)", "Stock Balance", _f(warehouse=p.warehouse)),
			("Stock Balance (all locations)", "Stock Balance", _f()),
			("Stock Ledger", "Stock Ledger", _f(warehouse=p.warehouse)),
			("Stock Ageing", "Stock Ageing", {"company": p.company, "to_date": nowdate(), "range": "30, 60, 90"}),
		],
		"Purchase": [
			("Purchase Register", "Purchase Register", _f()),
			("Supplier Payments Due", "Accounts Payable", {"company": p.company, "report_date": nowdate(), "ageing_based_on": "Due Date", "range": "30, 60, 90, 120"}),
		],
		"GST": [
			("HSN-wise Summary", "HSN-wise-summary of outward supplies", _f(company_gstin=frappe.db.get_value("Company", p.company, "gstin"))),
		],
		"Accounts": [
			("General Ledger", "General Ledger", _f(group_by="Group by Voucher (Consolidated)")),
			("Profit and Loss", "Profit and Loss Statement", {"company": p.company, "filter_based_on": "Date Range", "period_start_date": str(get_first_day(nowdate())), "period_end_date": nowdate(), "periodicity": "Monthly"}),
		],
	}


@frappe.whitelist()
def report_catalog():
	_require_cashier()
	out = {}
	for group, items in REPORTS().items():
		out[group] = [{"name": n, "erp": r, "allowed": bool(frappe.db.exists("Report", r)) and frappe.has_permission("Report", "read", r)} for n, r, _ in items]
	return out


@frappe.whitelist()
def run_report(name, from_date=None, to_date=None):
	_require_cashier()
	spec = next(((n, r, f) for items in REPORTS().values() for n, r, f in items if n == name), None)
	if not spec:
		frappe.throw(_("Unknown report {0}.").format(name))
	_, report, filters = spec
	filters = dict(filters)
	for k, v in (("from_date", from_date), ("to_date", to_date), ("period_start_date", from_date), ("period_end_date", to_date)):
		if v and k in filters:
			filters[k] = v
	from frappe.desk.query_report import run
	res = run(report, filters=filters, ignore_prepared_report=True)  # checks report permission itself
	cols = []
	for c in res.get("columns") or []:
		if isinstance(c, dict):
			cols.append({"k": c.get("fieldname"), "l": c.get("label") or c.get("fieldname"), "t": c.get("fieldtype")})
		else:
			p = str(c).split(":")
			cols.append({"k": p[0], "l": p[0], "t": p[1] if len(p) > 1 else "Data"})
	rows = []
	for row in (res.get("result") or [])[:300]:
		if isinstance(row, dict):
			rows.append([row.get(c["k"]) for c in cols])
		elif isinstance(row, (list, tuple)):
			rows.append(list(row)[:len(cols)])
	keep = [i for i, c in enumerate(cols) if any(r[i] not in (None, "", 0, 0.0) for r in rows if i < len(r))][:12] or list(range(min(len(cols), 12)))
	num = ("Currency", "Float", "Int", "Percent")
	return {"report": report, "filters": {k: v for k, v in filters.items() if "date" in k},
		"cols": [cols[i]["l"] for i in keep], "num": [cols[i]["t"] in num for i in keep],
		"rows": [[(round(r[i], 2) if isinstance(r[i], float) else ("" if r[i] is None else str(r[i]) if not isinstance(r[i], (int, float)) else r[i])) if i < len(r) else "" for i in keep] for r in rows],
		"total": len(res.get("result") or [])}


# ---------------------------------------------------------------- dashboard
@frappe.whitelist()
def dashboard():
	_require_cashier()
	p, today = profile(), nowdate()
	inv = frappe.get_list("Sales Invoice", filters={"docstatus": 1, "posting_date": today, "pos_profile": p.name}, fields=["name", "is_return", "rounded_total", "grand_total", "is_pos"])
	sales = sum(flt(i.rounded_total or i.grand_total) for i in inv if not i.is_return)
	top = frappe.db.sql("""select i.item_name, sum(i.qty) qty, sum(i.amount) amt from `tabSales Invoice Item` i join `tabSales Invoice` s on s.name=i.parent
		where s.docstatus=1 and s.is_return=0 and s.posting_date=%s and s.pos_profile=%s group by i.item_code order by amt desc limit 5""", (today, p.name), as_dict=1)
	low = frappe.db.sql("""select b.item_code, i.item_name, b.actual_qty from tabBin b join tabItem i on i.name=b.item_code
		where b.warehouse=%s order by b.actual_qty asc limit 5""", p.warehouse, as_dict=1)
	week = frappe.db.sql("""select posting_date d, sum(rounded_total) t from `tabSales Invoice` where docstatus=1 and is_return=0 and pos_profile=%s
		and posting_date>=%s group by posting_date order by posting_date""", (p.name, add_days(today, -6)), as_dict=1)
	return {"date": today, "bills": len([i for i in inv if not i.is_return]), "sales": sales,
		"returns": -sum(flt(i.rounded_total or i.grand_total) for i in inv if i.is_return),
		"credit": sum(flt(i.rounded_total or i.grand_total) for i in inv if not i.is_pos and not i.is_return),
		"avg_bill": sales / max(1, len([i for i in inv if not i.is_return])), "top": top, "low": low,
		"week": [{"d": str(w.d), "t": flt(w.t)} for w in week]}


# ---------------------------------------------------------------- button order (per user)
@frappe.whitelist()
def get_button_order():
	_require_cashier()
	v = frappe.defaults.get_user_default("jalgo_pos_setup_order")
	return json.loads(v) if v else None


@frappe.whitelist(methods=["POST"])
def save_button_order(order):
	_require_cashier()
	if isinstance(order, str):
		try:
			order = json.loads(order)
		except ValueError:
			order = None
	if not isinstance(order, list) or not all(isinstance(x, str) for x in order) or len(order) > 40:
		frappe.throw(_("Invalid button order."))
	frappe.defaults.set_user_default("jalgo_pos_setup_order", json.dumps(order))
	return order
