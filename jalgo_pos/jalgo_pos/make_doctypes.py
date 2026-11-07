"""Developer helper: creates the JALGO POS DocTypes (run once in developer mode; JSON files are then committed)."""
import frappe

MOD = "JALGO POS"
PERM = [{"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
	{"role": "Sales User", "read": 1, "write": 1, "create": 1}]


def make(name, fields, **kw):
	if frappe.db.exists("DocType", name):
		return
	d = frappe.get_doc({"doctype": "DocType", "name": name, "module": MOD, "custom": 0, "fields": fields,
		"permissions": kw.pop("permissions", PERM), **kw})
	d.insert()


def add_field(doctype, field):
	d = frappe.get_doc("DocType", doctype)
	if not any(f.fieldname == field["fieldname"] for f in d.fields):
		d.append("fields", field)
		d.save()


def run():
	make("JALGO POS Settings", issingle=1, permissions=[{"role": "System Manager", "read": 1, "write": 1}], fields=[
		{"fieldname": "max_cashier_discount", "label": "Max discount a cashier can give (%)", "fieldtype": "Percent", "default": "5"},
		{"fieldname": "max_manager_discount", "label": "Max discount with manager PIN (%)", "fieldtype": "Percent", "default": "20"},
		{"fieldname": "manager_pin", "label": "Manager PIN", "fieldtype": "Password", "description": "4–6 digits. Needed for bigger discounts, returns and voids."},
		{"fieldname": "require_shift", "label": "Cashier must open a shift before billing", "fieldtype": "Check", "default": "1"},
		{"fieldname": "accept_barcode_in_name", "label": "Accept barcode in Item Name", "fieldtype": "Check", "default": "1"},
		{"fieldname": "warn_not_found", "label": "Warn when item not found", "fieldtype": "Check", "default": "1"},
		{"fieldname": "rate_card", "label": "Rate Card (JSON)", "fieldtype": "Long Text", "read_only": 1, "description": "Digit-to-letter codes for purchase prices on stickers. Edit from the POS Barcode Printing screen."},
	])
	add_field("JALGO POS Settings", {"fieldname": "rate_card", "label": "Rate Card (JSON)", "fieldtype": "Long Text", "read_only": 1,
		"description": "Digit-to-letter codes for purchase prices on stickers. Edit from the POS Barcode Printing screen."})
	make("JALGO Held Bill", autoname="hash", fields=[
		{"fieldname": "customer", "label": "Customer", "fieldtype": "Data", "in_list_view": 1},
		{"fieldname": "sales_executive", "label": "Sales Executive", "fieldtype": "Data"},
		{"fieldname": "total", "label": "Total", "fieldtype": "Currency", "in_list_view": 1},
		{"fieldname": "item_count", "label": "Items", "fieldtype": "Int", "in_list_view": 1},
		{"fieldname": "lines", "label": "Lines (JSON)", "fieldtype": "Long Text"},
	])
	make("JALGO POS Shift", autoname="format:SHIFT-{YY}-{#####}", fields=[
		{"fieldname": "cashier", "label": "Cashier", "fieldtype": "Link", "options": "User", "in_list_view": 1, "reqd": 1},
		{"fieldname": "pos_profile", "label": "POS Profile", "fieldtype": "Link", "options": "POS Profile"},
		{"fieldname": "status", "label": "Status", "fieldtype": "Select", "options": "Open\nClosed", "default": "Open", "in_list_view": 1},
		{"fieldname": "opened_at", "label": "Opened at", "fieldtype": "Datetime"},
		{"fieldname": "opening_cash", "label": "Opening cash", "fieldtype": "Currency"},
		{"fieldname": "cb1", "fieldtype": "Column Break"},
		{"fieldname": "closed_at", "label": "Closed at", "fieldtype": "Datetime"},
		{"fieldname": "bills", "label": "Bills", "fieldtype": "Int"},
		{"fieldname": "sales_total", "label": "Sales total", "fieldtype": "Currency", "in_list_view": 1},
		{"fieldname": "returns_total", "label": "Returns total", "fieldtype": "Currency"},
		{"fieldname": "sb", "fieldtype": "Section Break", "label": "Cash count"},
		{"fieldname": "cash_sales", "label": "Cash sales", "fieldtype": "Currency"},
		{"fieldname": "upi_sales", "label": "UPI sales", "fieldtype": "Currency"},
		{"fieldname": "card_sales", "label": "Card sales", "fieldtype": "Currency"},
		{"fieldname": "credit_sales", "label": "Credit (udhaar) sales", "fieldtype": "Currency"},
		{"fieldname": "cb2", "fieldtype": "Column Break"},
		{"fieldname": "expected_cash", "label": "Expected cash in drawer", "fieldtype": "Currency"},
		{"fieldname": "counted_cash", "label": "Counted cash", "fieldtype": "Currency"},
		{"fieldname": "difference", "label": "Difference", "fieldtype": "Currency"},
	])
	frappe.db.commit()
