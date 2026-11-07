"""One-time setup for JALGO POS on an ERPNext site. Safe to run again (idempotent)."""
import frappe

PROFILE = "Shubhendra Provision Counter"


def default_company():
	return frappe.db.get_single_value("Global Defaults", "default_company") or frappe.get_all("Company", pluck="name", limit=1)[0]


def ensure_roles_only():
	ensure_roles()


def abbr(company):
	return frappe.get_cached_value("Company", company, "abbr")


def ensure_custom_fields():
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
	create_custom_fields({
		"Sales Invoice": [
			{"fieldname": "jalgo_pos_uuid", "label": "JALGO POS Bill ID", "fieldtype": "Data", "unique": 1, "read_only": 1,
				"no_copy": 1, "insert_after": "is_pos", "description": "Set by the JALGO POS so a bill is never saved twice."},
			{"fieldname": "jalgo_sales_executive", "label": "Sales Executive", "fieldtype": "Data", "insert_after": "jalgo_pos_uuid"},
		]
	}, update=True)


def ensure_account(company, name, parent_suffix, account_type):
	a = abbr(company)
	full = f"{name} - {a}"
	if not frappe.db.exists("Account", full):
		frappe.get_doc({"doctype": "Account", "account_name": name, "company": company,
			"parent_account": f"{parent_suffix} - {a}", "account_type": account_type, "is_group": 0}).insert(ignore_permissions=True)
	return full


def ensure_mode(mode, mtype, company, account):
	if not frappe.db.exists("Mode of Payment", mode):
		frappe.get_doc({"doctype": "Mode of Payment", "mode_of_payment": mode, "type": mtype}).insert(ignore_permissions=True)
	doc = frappe.get_doc("Mode of Payment", mode)
	if not any(r.company == company for r in doc.accounts):
		doc.append("accounts", {"company": company, "default_account": account})
		doc.save(ignore_permissions=True)


def ensure_inclusive_tax_template(company):
	"""Shelf prices (MRP) already include GST, so the POS uses a template with 'included in print rate'."""
	a = abbr(company)
	name = f"Output GST In-state (Incl) - {a}"
	if frappe.db.exists("Sales Taxes and Charges Template", name):
		return name
	src = frappe.get_doc("Sales Taxes and Charges Template", f"Output GST In-state - {a}")
	new = frappe.copy_doc(src)
	new.title = "Output GST In-state (Incl)"
	new.is_default = 0
	new.tax_category = None
	for t in new.taxes:
		t.included_in_print_rate = 1
	new.insert(ignore_permissions=True)
	return new.name


def ensure_profile(company, warehouse, tax_template):
	if frappe.db.exists("POS Profile", PROFILE):
		return PROFILE
	walkin = "Walk-in Customer"
	if not frappe.db.exists("Customer", walkin):
		frappe.get_doc({"doctype": "Customer", "customer_name": walkin, "customer_type": "Individual",
			"customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}, "name")}).insert(ignore_permissions=True)
	a = abbr(company)
	p = frappe.get_doc({"doctype": "POS Profile", "name": PROFILE, "company": company, "warehouse": warehouse,
		"customer": walkin, "currency": "INR", "selling_price_list": "Standard Selling", "update_stock": 1,
		"taxes_and_charges": tax_template, "write_off_account": f"Write Off - {a}", "write_off_cost_center": f"Main - {a}",
		"cost_center": f"Main - {a}", "payments": [{"mode_of_payment": "Cash", "default": 1}, {"mode_of_payment": "UPI"}, {"mode_of_payment": "Card"}]})
	p.insert(ignore_permissions=True)
	return p.name


def after_install():
	ensure_roles()
	if not frappe.get_all("Company", limit=1) or not frappe.db.exists("Sales Taxes and Charges Template", {"title": "Output GST In-state"}):
		print("JALGO POS: finish the ERPNext setup wizard and India Compliance first, then run:\n"
			"  bench --site <site> execute jalgo_pos.setup.after_install")
		return {"skipped": "company or GST templates missing"}
	company = default_company()
	ensure_custom_fields()
	gw = ensure_account(company, "Razorpay Clearing", "Bank Accounts", "Bank")
	ensure_mode("Cash", "Cash", company, f"Cash - {abbr(company)}")
	ensure_mode("UPI", "Bank", company, gw)
	ensure_mode("Card", "Bank", company, gw)
	tpl = ensure_inclusive_tax_template(company)
	wh = frappe.db.get_value("Warehouse", {"company": company, "warehouse_name": ["like", "%Shubhendra%"]}) \
		or frappe.db.get_value("Warehouse", {"company": company, "warehouse_name": ["like", "%Mundade%"]}) \
		or frappe.db.get_value("Warehouse", {"company": company, "is_group": 0})
	ensure_profile(company, wh, tpl)
	ensure_settings()
	ensure_demo_offer()
	ensure_roles()
	frappe.db.commit()
	return {"company": company, "warehouse": wh, "tax_template": tpl, "profile": PROFILE}


def ensure_settings():
	s = frappe.get_single("JALGO POS Settings")
	if not s.max_manager_discount:
		s.update({"max_cashier_discount": 5, "max_manager_discount": 20, "require_shift": 1, "accept_barcode_in_name": 1, "warn_not_found": 1})
	if not s.get_password("manager_pin", raise_exception=False):
		s.manager_pin = "2468"  # demo PIN: change it in JALGO POS Settings before real use
	s.save(ignore_permissions=True)


def ensure_demo_offer():
	"""Sample offer so the Offers button has something to show. Disable or edit it in ERPNext > Pricing Rule."""
	title = "JALGO demo: 5% off Parle-G on 3 or more"
	if frappe.db.exists("Pricing Rule", {"title": title}) or not frappe.db.exists("Item", "JLG-029"):
		return
	frappe.get_doc({"doctype": "Pricing Rule", "title": title, "apply_on": "Item Code", "items": [{"item_code": "JLG-029"}],
		"selling": 1, "price_or_product_discount": "Price", "rate_or_discount": "Discount Percentage", "discount_percentage": 5,
		"min_qty": 3, "company": default_company(), "currency": "INR"}).insert(ignore_permissions=True)


CASHIER_ROLES = ["JALGO Cashier", "Sales User", "Accounts User", "Stock User"]
MANAGER_ROLES = CASHIER_ROLES + ["JALGO Manager", "Stock Manager", "Item Manager", "Purchase User", "Sales Manager"]
OWN_DOCTYPES = {"JALGO Held Bill": ("JALGO Cashier", 1), "JALGO POS Shift": ("JALGO Cashier", 1)}


def ensure_roles():
	for r in ("JALGO Cashier", "JALGO Manager"):
		if not frappe.db.exists("Role", r):
			frappe.get_doc({"doctype": "Role", "role_name": r, "desk_access": 1}).insert(ignore_permissions=True)
	from frappe.permissions import add_permission, update_permission_property
	for dt in OWN_DOCTYPES:
		for role in ("JALGO Cashier", "JALGO Manager"):
			add_permission(dt, role, 0)
			for p in ("read", "write", "create", "delete"):
				update_permission_property(dt, role, 0, p, 1)


@frappe.whitelist()
def make_pos_user(user, manager=0):
	"""Give an existing user the roles a counter needs. Owner/System Manager only."""
	frappe.only_for("System Manager")
	doc = frappe.get_doc("User", user)
	doc.add_roles(*(MANAGER_ROLES if frappe.utils.cint(manager) else CASHIER_ROLES))
	return sorted(r.role for r in doc.roles)
