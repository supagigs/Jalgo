"""Stock-side workflows for the POS back office: GRN by Template (item variants), transfers,
wastage write-off and collecting udhaar. Every write is an ordinary ERPNext document."""
import re

import frappe
from frappe import _
from frappe.utils import flt, cint, nowdate

from jalgo_pos.api import _require_cashier, _require_pin, profile, _parse

DARK_STORE_HINT = "Dark Store"


def _require_manager(pin=None):
	"""Stock and money movements need the JALGO Manager role (or System Manager), or the manager PIN."""
	_require_cashier()
	roles = set(frappe.get_roles())
	if roles & {"JALGO Manager", "System Manager", "Stock Manager"}:
		return
	_require_pin(pin, _("do this"))


def _gst_template(rate):
	co_abbr = frappe.get_cached_value("Company", profile().company, "abbr")
	name = f"GST {cint(rate) if flt(rate) == cint(rate) else rate}% - {co_abbr}" if flt(rate) else f"Nil-Rated - {co_abbr}"
	if not frappe.db.exists("Item Tax Template", name):
		frappe.throw(_("No Item Tax Template {0}. Set it up in ERPNext first.").format(name))
	return name


@frappe.whitelist()
def locations():
	_require_cashier()
	p = profile()
	return [{"name": w.name, "label": w.warehouse_name} for w in frappe.get_all("Warehouse", filters={"company": p.company, "is_group": 0,
		"warehouse_name": ["not in", ["Goods In Transit", "Work In Progress", "Finished Goods", "Stores"]]}, fields=["name", "warehouse_name"])]


@frappe.whitelist()
def attributes():
	_require_cashier()
	out = {}
	for a in frappe.get_all("Item Attribute", filters={"numeric_values": 0}, pluck="name"):
		out[a] = frappe.get_all("Item Attribute Value", filters={"parent": a}, pluck="attribute_value", order_by="idx asc")
	return out


def _abbr(v):
	a = re.sub(r"[^A-Za-z0-9]", "", v).upper()[:8]
	return a or "V"


@frappe.whitelist(methods=["POST"])
def save_attribute(name, values, pin=None):
	_require_manager(pin)
	name, values = (name or "").strip(), [v.strip() for v in _parse(values) if str(v).strip()]
	if not name or not values:
		frappe.throw(_("Enter a field name and at least one value."))
	doc = frappe.get_doc("Item Attribute", name) if frappe.db.exists("Item Attribute", name) else frappe.new_doc("Item Attribute")
	doc.attribute_name = name
	have = {r.attribute_value for r in doc.item_attribute_values}
	used_abbr = {r.abbr for r in doc.item_attribute_values}
	for v in values:
		if v not in have:
			ab = _abbr(v)
			while ab in used_abbr:
				ab += "X"
			used_abbr.add(ab)
			doc.append("item_attribute_values", {"attribute_value": v, "abbr": ab})
	doc.save()
	return attributes()


def _default_hsn(group):
	r = frappe.db.sql("""select gst_hsn_code, count(*) c from tabItem where item_group=%s and ifnull(gst_hsn_code,'')!=''
		group by gst_hsn_code order by c desc limit 1""", group)
	return r[0][0] if r else None


def _template(name, group, attribute, gst, hsn=None):
	"""Find or create the template item (has_variants) for a product name."""
	existing = frappe.db.get_value("Item", {"item_name": name, "has_variants": 1}, "name")
	if existing:
		t = frappe.get_doc("Item", existing)
		if not any(a.attribute == attribute for a in t.attributes):
			frappe.throw(_("{0} already uses {1}. Pick that field for this product.").format(name, ", ".join(a.attribute for a in t.attributes)))
		return t
	code = "JLGT-" + re.sub(r"[^A-Z0-9]+", "-", name.upper()).strip("-")[:30]
	t = frappe.get_doc({"doctype": "Item", "item_code": code, "item_name": name, "item_group": group, "stock_uom": "Nos",
		"is_stock_item": 1, "has_variants": 1, "variant_based_on": "Item Attribute", "attributes": [{"attribute": attribute}],
		"taxes": [{"item_tax_template": _gst_template(gst)}], "description": name, "gst_hsn_code": hsn or _default_hsn(group)})
	if not t.gst_hsn_code:
		frappe.throw(_("Enter the HSN code for {0}.").format(name))
	t.insert()
	return t


def _variant(template, attribute, value):
	from erpnext.controllers.item_variant import get_variant, create_variant
	found = get_variant(template.name, {attribute: value})
	if found:
		return frappe.get_doc("Item", found)
	v = create_variant(template.name, {attribute: value})
	v.item_name = f"{template.item_name} - {value}"
	v.insert()
	return v


def _set_price(code, price_list, rate):
	if not flt(rate):
		return
	name = frappe.db.get_value("Item Price", {"item_code": code, "price_list": price_list})
	if name:
		frappe.db.set_value("Item Price", name, "price_list_rate", flt(rate))
	else:
		frappe.get_doc({"doctype": "Item Price", "item_code": code, "price_list": price_list, "price_list_rate": flt(rate)}).insert(ignore_permissions=True)


@frappe.whitelist(methods=["POST"])
def grn_by_template(supplier, attribute, rows, warehouse=None, supplier_invoice=None, invoice_date=None, item_group=None,
		price_basis="basic", discount=0, hold=0, pin=None):
	"""rows: [{name, q: {value: qty}, cost, sale, mrp, gst}]. Each filled cell becomes an ERPNext variant of the
	product template; one Purchase Receipt receives them all into the chosen warehouse. hold=1 keeps it as a draft."""
	_require_manager(pin)
	rows = _parse(rows)
	p = profile()
	warehouse = warehouse or p.warehouse
	if not frappe.db.exists("Supplier", supplier):
		frappe.throw(_("Supplier {0} not found.").format(supplier))
	if not frappe.db.exists("Item Attribute", attribute):
		frappe.throw(_("Field {0} not found.").format(attribute))
	allowed = set(attributes().get(attribute, []))
	group = item_group or "Products"
	lines, made = [], []
	for r in rows:
		name = (r.get("name") or "").strip()
		cells = {k: flt(v) for k, v in (r.get("q") or {}).items() if flt(v) > 0}
		if not name or not cells:
			continue
		bad = [k for k in cells if k not in allowed]
		if bad:
			frappe.throw(_("{0} is not a value of {1}.").format(", ".join(bad), attribute))
		if flt(r.get("cost")) <= 0:
			frappe.throw(_("Enter the purchase price for {0}.").format(name))
		gst = flt(r.get("gst"))
		t = _template(name, group, attribute, gst, (r.get("hsn") or "").strip() or None)
		for value, qty in cells.items():
			v = _variant(t, attribute, value)
			_set_price(v.name, p.selling_price_list, r.get("sale"))
			_set_price(v.name, "JALGO MRP", r.get("mrp") or r.get("sale"))
			cost = flt(r["cost"]) / (1 + gst / 100) if price_basis == "incl" else flt(r["cost"])
			lines.append({"item_code": v.name, "qty": qty, "rate": round(cost, 4), "warehouse": warehouse})
			made.append({"code": v.name, "name": v.item_name, "qty": qty, "sale": flt(r.get("sale"))})
	if not lines:
		frappe.throw(_("Enter an item name and at least one quantity."))
	co_abbr = frappe.get_cached_value("Company", p.company, "abbr")
	pr = frappe.get_doc({"doctype": "Purchase Receipt", "supplier": supplier, "company": p.company, "posting_date": nowdate(),
		"set_warehouse": warehouse, "supplier_delivery_note": supplier_invoice, "items": lines, "apply_discount_on": "Net Total",
		"additional_discount_percentage": flt(discount),
		"taxes_and_charges": f"Input GST In-state - {co_abbr}" if frappe.db.get_value("Supplier", supplier, "gstin")
			and frappe.db.exists("Purchase Taxes and Charges Template", f"Input GST In-state - {co_abbr}") else None,
		"remarks": f"JALGO POS GRN by Template ({attribute}). Supplier invoice {supplier_invoice or '-'} dated {invoice_date or '-'}"})
	pr.set_missing_values()
	pr.insert()
	if not cint(hold):
		pr.submit()
	return {"name": pr.name, "status": "Held (draft)" if cint(hold) else "Submitted", "qty": sum(l["qty"] for l in lines),
		"grand_total": pr.rounded_total or pr.grand_total, "taxes": pr.total_taxes_and_charges, "items": made, "warehouse": warehouse}


@frappe.whitelist(methods=["POST"])
def transfer(to_warehouse, items, from_warehouse=None, pin=None):
	_require_manager(pin)
	p = profile()
	from_warehouse = from_warehouse or p.warehouse
	if from_warehouse == to_warehouse:
		frappe.throw(_("Choose two different locations."))
	items = [i for i in _parse(items) if flt(i.get("qty")) > 0]
	if not items:
		frappe.throw(_("Add at least one item with quantity."))
	se = frappe.get_doc({"doctype": "Stock Entry", "stock_entry_type": "Material Transfer", "company": p.company,
		"from_warehouse": from_warehouse, "to_warehouse": to_warehouse, "remarks": "JALGO POS stock transfer",
		"items": [{"item_code": i["code"], "qty": flt(i["qty"]), "s_warehouse": from_warehouse, "t_warehouse": to_warehouse} for i in items]})
	se.insert()
	se.submit()
	return {"name": se.name, "value": se.total_outgoing_value}


@frappe.whitelist(methods=["POST"])
def write_off(items, reason, pin=None):
	"""Wastage / damage: removes stock from this shop at valuation cost (Material Issue)."""
	_require_manager(pin)
	reason = (reason or "").strip()
	if len(reason) < 3:
		frappe.throw(_("Write the reason (for example: spoiled tomatoes)."))
	p = profile()
	items = [i for i in _parse(items) if flt(i.get("qty")) > 0]
	if not items:
		frappe.throw(_("Add at least one item with quantity."))
	se = frappe.get_doc({"doctype": "Stock Entry", "stock_entry_type": "Material Issue", "company": p.company, "from_warehouse": p.warehouse,
		"remarks": f"Wastage: {reason} (JALGO POS)", "items": [{"item_code": i["code"], "qty": flt(i["qty"]), "s_warehouse": p.warehouse} for i in items]})
	se.insert()
	se.submit()
	return {"name": se.name, "value": se.total_outgoing_value}


@frappe.whitelist(methods=["POST"])
def collect_payment(customer, amount, mode="Cash"):
	"""Collect udhaar: one Payment Entry, allocated to the customer's oldest unpaid bills first."""
	_require_cashier()
	amount = flt(amount)
	if amount <= 0:
		frappe.throw(_("Enter the amount received."))
	p = profile()
	bills = frappe.get_all("Sales Invoice", filters={"customer": customer, "docstatus": 1, "outstanding_amount": [">", 0], "company": p.company},
		fields=["name", "outstanding_amount", "grand_total", "posting_date"], order_by="posting_date asc, name asc")
	owed = sum(flt(b.outstanding_amount) for b in bills)
	if not bills:
		frappe.throw(_("{0} owes nothing.").format(customer))
	if amount > owed + 0.001:
		frappe.throw(_("{0} owes only ₹{1}.").format(customer, owed))
	from erpnext.accounts.doctype.sales_invoice.sales_invoice import get_bank_cash_account
	acc = get_bank_cash_account(mode, p.company).get("account")
	recv = frappe.get_cached_value("Company", p.company, "default_receivable_account")
	pe = frappe.get_doc({"doctype": "Payment Entry", "payment_type": "Receive", "company": p.company, "party_type": "Customer",
		"party": customer, "posting_date": nowdate(), "mode_of_payment": mode, "paid_from": recv, "paid_to": acc,
		"paid_amount": amount, "received_amount": amount, "reference_no": f"POS-{frappe.generate_hash(length=8)}", "reference_date": nowdate(),
		"remarks": "Udhaar collected at JALGO POS counter"})
	left = amount
	for b in bills:
		if left <= 0:
			break
		alloc = min(left, flt(b.outstanding_amount))
		pe.append("references", {"reference_doctype": "Sales Invoice", "reference_name": b.name, "allocated_amount": alloc,
			"total_amount": b.grand_total, "outstanding_amount": b.outstanding_amount})
		left -= alloc
	pe.setup_party_account_field()
	pe.set_missing_values()
	pe.insert()
	pe.submit()
	return {"name": pe.name, "amount": amount, "still_owed": round(owed - amount, 2), "bills": [r.reference_name for r in pe.references]}
