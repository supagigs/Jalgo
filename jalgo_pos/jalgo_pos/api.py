"""JALGO POS API. Every price, discount and total is decided here, never trusted from the browser."""
import json

import frappe
from frappe import _
from frappe.utils import flt, cint, nowdate, nowtime, now_datetime, getdate

from jalgo_pos.setup import PROFILE


# ---------------------------------------------------------------- helpers
def profile():
	return frappe.get_cached_doc("POS Profile", PROFILE)


def settings():
	return frappe.get_single("JALGO POS Settings")


POS_ROLES = {"JALGO Cashier", "JALGO Manager", "System Manager"}


def _require_cashier():
	if frappe.session.user == "Guest":
		frappe.throw(_("Please log in to use the POS."), frappe.PermissionError)
	if not (set(frappe.get_roles()) & POS_ROLES):
		frappe.throw(_("Your login is not set up for the POS. Ask the owner to give you the JALGO Cashier role."), frappe.PermissionError)
	if not frappe.has_permission("Sales Invoice", "create"):
		frappe.throw(_("You are not allowed to make bills."), frappe.PermissionError)


def _pin_ok(pin):
	real = settings().get_password("manager_pin", raise_exception=False)
	return bool(real) and str(pin or "") == str(real)


def _require_pin(pin, why):
	if not _pin_ok(pin):
		frappe.throw(_("Manager PIN is needed to {0}.").format(why), frappe.PermissionError, title=_("Manager PIN"))


def _gst_rate(item_code):
	"""Total GST % from the item's tax template name, e.g. 'GST 5% - JLG' -> 5. Nil/Exempt -> 0."""
	tpl = frappe.db.get_value("Item Tax", {"parent": item_code, "parenttype": "Item"}, "item_tax_template") or ""
	if "GST " not in tpl:
		return 0
	try:
		return flt(tpl.split("GST ")[1].split("%")[0])
	except Exception:
		return 0


def _rates(codes):
	p = profile()
	price = {r.item_code: r.price_list_rate for r in frappe.get_all("Item Price", filters={"item_code": ["in", codes], "price_list": p.selling_price_list}, fields=["item_code", "price_list_rate"])}
	mrp = {r.item_code: r.price_list_rate for r in frappe.get_all("Item Price", filters={"item_code": ["in", codes], "price_list": "JALGO MRP"}, fields=["item_code", "price_list_rate"])}
	stock = {r.item_code: r.actual_qty for r in frappe.get_all("Bin", filters={"item_code": ["in", codes], "warehouse": p.warehouse}, fields=["item_code", "actual_qty"])}
	return price, mrp, stock


def _item_rows(items):
	codes = [i.name for i in items]
	if not codes:
		return []
	price, mrp, stock = _rates(codes)
	bars = {}
	for b in frappe.get_all("Item Barcode", filters={"parent": ["in", codes]}, fields=["parent", "barcode"]):
		bars.setdefault(b.parent, b.barcode)
	return [{"code": i.name, "name": i.item_name, "uom": i.stock_uom, "group": i.item_group, "image": i.image,
		"barcode": bars.get(i.name, ""), "rate": flt(price.get(i.name)), "mrp": flt(mrp.get(i.name) or price.get(i.name)),
		"stock": flt(stock.get(i.name)), "gst": _gst_rate(i.name)} for i in items]


def _parse(x):
	return frappe.parse_json(x) if isinstance(x, str) else (x or [])


# ---------------------------------------------------------------- offers (ERPNext Pricing Rules, simple % rules)
def _active_offers():
	today = getdate(nowdate())
	rules = frappe.get_all("Pricing Rule", filters={"selling": 1, "disable": 0, "rate_or_discount": "Discount Percentage", "price_or_product_discount": "Price"},
		fields=["name", "title", "apply_on", "discount_percentage", "min_qty", "valid_from", "valid_upto", "priority"])
	out = []
	for r in rules:
		if (r.valid_from and getdate(r.valid_from) > today) or (r.valid_upto and getdate(r.valid_upto) < today):
			continue
		child = {"Item Code": ("Pricing Rule Item Code", "item_code"), "Item Group": ("Pricing Rule Item Group", "item_group")}.get(r.apply_on)
		if not child:
			continue
		r.targets = frappe.get_all(child[0], filters={"parent": r.name}, pluck=child[1])
		r.apply_on_field = child[1]
		out.append(r)
	return out


def _offer_for(code, group, qty, offers):
	best = None
	for r in offers:
		target = code if r.apply_on_field == "item_code" else group
		if target in r.targets and flt(qty) >= flt(r.min_qty or 0):
			if not best or flt(r.discount_percentage) > flt(best.discount_percentage):
				best = r
	return best


@frappe.whitelist()
def offers(codes=None):
	_require_cashier()
	codes = _parse(codes)
	groups = {i.name: i.item_group for i in frappe.get_all("Item", filters={"name": ["in", codes]}, fields=["name", "item_group"])} if codes else {}
	res = []
	for r in _active_offers():
		hits = [c for c in codes if (c if r.apply_on_field == "item_code" else groups.get(c)) in r.targets] if codes else []
		res.append({"name": r.name, "title": r.title or r.name, "discount": r.discount_percentage, "min_qty": r.min_qty,
			"on": f"{r.apply_on}: {', '.join(r.targets[:4])}", "in_cart": hits, "field": r.apply_on_field, "targets": r.targets})
	return res


# ---------------------------------------------------------------- boot / search / customers
@frappe.whitelist()
def bootstrap():
	_require_cashier()
	p, s = profile(), settings()
	return {"profile": p.name, "company": p.company, "warehouse": p.warehouse, "price_list": p.selling_price_list,
		"customer": p.customer, "user": frappe.session.user, "user_name": frappe.utils.get_fullname(frappe.session.user),
		"modes": [r.mode_of_payment for r in p.payments] + ["Credit"], "max_discount": flt(s.max_cashier_discount),
		"max_manager_discount": flt(s.max_manager_discount), "require_shift": cint(s.require_shift),
		"barcode_in_name": cint(s.accept_barcode_in_name), "warn_not_found": cint(s.warn_not_found), "shift": current_shift(),
		"razorpay": __import__("jalgo_pos.payments", fromlist=["enabled"]).enabled(),
		"shop": {"name": "Shubhendra Provision", "address": "Main Market, Jalgaon, Maharashtra 425001",
			"gstin": frappe.db.get_value("Company", p.company, "gstin") or ""}}


@frappe.whitelist()
def search_items(txt="", limit=10):
	"""Barcode (exact) first, then item code, then name match. Only sellable, enabled items."""
	_require_cashier()
	txt = (txt or "").strip()
	if not txt:
		return []
	fields = ["name", "item_name", "stock_uom", "item_group", "image"]
	base = {"disabled": 0, "is_sales_item": 1, "has_variants": 0}
	code = frappe.db.get_value("Item Barcode", {"barcode": txt}, "parent")
	if code:
		return _item_rows(frappe.get_all("Item", filters={**base, "name": code}, fields=fields))
	if frappe.db.exists("Item", {**base, "name": txt}):
		return _item_rows(frappe.get_all("Item", filters={**base, "name": txt}, fields=fields))
	return _item_rows(frappe.get_all("Item", filters=base, or_filters={"item_name": ["like", f"%{txt}%"], "name": ["like", f"%{txt}%"]},
		fields=fields, limit=cint(limit) or 10, order_by="item_name asc"))


@frappe.whitelist()
def customers(txt=""):
	_require_cashier()
	txt = (txt or "").strip()
	rows = frappe.get_all("Customer", filters={"disabled": 0}, or_filters={"customer_name": ["like", f"%{txt}%"], "mobile_no": ["like", f"%{txt}%"], "name": ["like", f"%{txt}%"]},
		fields=["name", "customer_name", "mobile_no", "gstin"], limit=15, order_by="modified desc")
	if rows:
		out = {r.customer: r.amt for r in frappe.db.sql("""select customer, sum(outstanding_amount) amt from `tabSales Invoice`
			where docstatus=1 and customer in %s group by customer""", ([r.name for r in rows],), as_dict=1)}
		for r in rows:
			r.outstanding = flt(out.get(r.name))
	return rows


@frappe.whitelist(methods=["POST"])
def create_customer(customer_name, mobile_no):
	_require_cashier()
	customer_name, mobile_no = (customer_name or "").strip(), (mobile_no or "").strip()
	if len(customer_name) < 2 or not mobile_no.isdigit() or len(mobile_no) != 10:
		frappe.throw(_("Enter a name and a 10-digit mobile number."))
	dup = frappe.db.get_value("Customer", {"mobile_no": mobile_no}, "name")
	if dup:
		frappe.throw(_("Mobile {0} already belongs to {1}.").format(mobile_no, dup))
	c = frappe.get_doc({"doctype": "Customer", "customer_name": customer_name, "customer_type": "Individual",
		"customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}, "name"), "mobile_no": mobile_no})
	c.insert()
	if not c.mobile_no:  # some versions only set mobile through the primary contact
		frappe.db.set_value("Customer", c.name, "mobile_no", mobile_no)
	return {"name": c.name, "customer_name": c.customer_name, "mobile_no": mobile_no, "outstanding": 0}


# ---------------------------------------------------------------- shifts
@frappe.whitelist()
def current_shift():
	if frappe.session.user == "Guest":
		return None
	return frappe.db.get_value("JALGO POS Shift", {"cashier": frappe.session.user, "status": "Open"},
		["name", "opened_at", "opening_cash"], as_dict=1)


@frappe.whitelist(methods=["POST"])
def open_shift(opening_cash=0):
	_require_cashier()
	if current_shift():
		frappe.throw(_("You already have an open shift."))
	s = frappe.get_doc({"doctype": "JALGO POS Shift", "cashier": frappe.session.user, "pos_profile": PROFILE,
		"status": "Open", "opened_at": now_datetime(), "opening_cash": flt(opening_cash)})
	s.insert(ignore_permissions=True)
	return current_shift()


def _shift_summary(shift):
	invs = frappe.get_all("Sales Invoice", filters={"docstatus": 1, "owner": shift.cashier, "pos_profile": PROFILE,
		"creation": [">=", shift.opened_at]}, fields=["name", "is_return", "rounded_total", "grand_total", "is_pos", "outstanding_amount"])
	modes = {"Cash": 0, "UPI": 0, "Card": 0}
	for p in frappe.get_all("Sales Invoice Payment", filters={"parent": ["in", [i.name for i in invs] or [""]]}, fields=["mode_of_payment", "amount", "parent"]):
		modes[p.mode_of_payment] = modes.get(p.mode_of_payment, 0) + flt(p.amount)
	change = sum(flt(x) for x in frappe.get_all("Sales Invoice", filters={"name": ["in", [i.name for i in invs] or [""]]}, pluck="change_amount"))
	sales = sum(flt(i.rounded_total or i.grand_total) for i in invs if not i.is_return)
	returns = -sum(flt(i.rounded_total or i.grand_total) for i in invs if i.is_return)
	credit = sum(flt(i.rounded_total or i.grand_total) for i in invs if not i.is_pos and not i.is_return)
	cash_net = modes["Cash"] - change
	return {"bills": len([i for i in invs if not i.is_return]), "sales_total": sales, "returns_total": returns,
		"cash_sales": cash_net, "upi_sales": modes["UPI"], "card_sales": modes["Card"], "credit_sales": credit,
		"expected_cash": flt(shift.opening_cash) + cash_net}


@frappe.whitelist()
def shift_summary():
	_require_cashier()
	cur = current_shift()
	if not cur:
		return None
	shift = frappe.get_doc("JALGO POS Shift", cur.name)
	return {**_shift_summary(shift), "name": shift.name, "opened_at": str(shift.opened_at), "opening_cash": shift.opening_cash}


@frappe.whitelist(methods=["POST"])
def close_shift(counted_cash):
	_require_cashier()
	cur = current_shift()
	if not cur:
		frappe.throw(_("No open shift."))
	shift = frappe.get_doc("JALGO POS Shift", cur.name)
	summ = _shift_summary(shift)
	shift.update(summ)
	shift.update({"status": "Closed", "closed_at": now_datetime(), "counted_cash": flt(counted_cash), "difference": flt(counted_cash) - summ["expected_cash"]})
	shift.save(ignore_permissions=True)
	return shift.as_dict()


def _require_shift():
	if cint(settings().require_shift) and not current_shift():
		frappe.throw(_("Open your shift before billing."), title=_("No open shift"))


# ---------------------------------------------------------------- building invoices
def _lines(items, pin, offers_list):
	"""Validate lines; return [(code, qty, disc, price, offer_title)] with server prices and allowed discounts."""
	s = settings()
	price, mrp, stock = _rates([i["code"] for i in items])
	groups = {i.name: i.item_group for i in frappe.get_all("Item", filters={"name": ["in", [x["code"] for x in items]]}, fields=["name", "item_group"])}
	out = []
	for it in items:
		code, qty, disc = it["code"], flt(it.get("qty")), flt(it.get("disc"))
		if qty <= 0:
			frappe.throw(_("Quantity must be more than 0 for {0}.").format(code))
		if code not in price:
			frappe.throw(_("{0} has no selling price. Set a price before billing.").format(code))
		if disc < 0 or disc > flt(s.max_manager_discount):
			frappe.throw(_("Discount on {0} cannot be more than {1}%.").format(code, s.max_manager_discount))
		if disc > flt(s.max_cashier_discount):
			_require_pin(pin, _("give more than {0}% discount").format(s.max_cashier_discount))
		offer = _offer_for(code, groups.get(code), qty, offers_list)
		title = None
		if offer and flt(offer.discount_percentage) > disc:  # best of manual and offer, never both
			disc, title = flt(offer.discount_percentage), offer.title or offer.name
		out.append((code, qty, disc, flt(price[code]), title))
	return out


def _fill(doc, lines, p):
	for code, qty, disc, price, title in lines:
		row = {"item_code": code, "qty": qty, "price_list_rate": price, "discount_percentage": disc,
			"rate": flt(price * (1 - disc / 100), 2), "ignore_pricing_rule": 1}
		if doc.doctype == "Sales Invoice":
			row["warehouse"] = p.warehouse
		doc.append("items", row)
	doc.set_missing_values()
	for d in doc.items:  # set_missing_values may refetch prices; enforce ours
		match = next(l for l in lines if l[0] == d.item_code)
		d.price_list_rate, d.discount_percentage, d.rate = match[3], match[2], flt(match[3] * (1 - match[2] / 100), 2)
	doc.set("taxes", [])
	doc.taxes_and_charges = p.taxes_and_charges
	doc.set_taxes()
	doc.calculate_taxes_and_totals()


def _customer(name):
	p = profile()
	if name and not frappe.db.exists("Customer", name):
		frappe.throw(_("Customer {0} not found.").format(name))
	return name or p.customer


@frappe.whitelist(methods=["POST"])
def submit_invoice(uuid, items, payments, customer=None, sales_executive=None, manager_pin=None, held_bill=None, offline_at=None):
	"""Create and submit a POS Sales Invoice (stock leaves the counter's warehouse).
	payments: [{mode, amount}] ; mode 'Credit' means udhaar (named customer, no money now).
	Repeating the same uuid returns the first bill."""
	_require_cashier()
	items, payments = _parse(items), _parse(payments)
	if not uuid:
		frappe.throw(_("Missing bill ID."))
	existing = frappe.db.get_value("Sales Invoice", {"jalgo_pos_uuid": uuid}, "name")
	if existing:
		return receipt(existing)
	when = None
	if offline_at:  # bill made while the counter was offline, synced now
		when = frappe.utils.get_datetime(offline_at)
		if when > now_datetime() or (now_datetime() - when).days > 3:
			frappe.throw(_("Offline bill time {0} is not valid.").format(offline_at))
	else:
		_require_shift()
	if not items:
		frappe.throw(_("The bill has no items."))
	p = profile()
	cust = _customer(customer)
	credit = any(x.get("mode") == "Credit" for x in payments)
	if credit and cust == p.customer:
		frappe.throw(_("Choose a named customer for a credit (udhaar) bill."))
	lines = _lines(items, manager_pin, _active_offers())
	si = frappe.new_doc("Sales Invoice")
	si.update({"is_pos": 0 if credit else 1, "pos_profile": p.name, "company": p.company, "customer": cust,
		"posting_date": when.date() if when else nowdate(), "posting_time": when.time() if when else nowtime(), "set_posting_time": 1, "update_stock": 1,
		"set_warehouse": p.warehouse, "selling_price_list": p.selling_price_list, "jalgo_pos_uuid": uuid,
		"jalgo_sales_executive": (sales_executive or "")[:140], "remarks": "JALGO POS counter bill" + (" (credit)" if credit else "")})
	_fill(si, lines, p)
	if not credit:
		due = flt(si.rounded_total or si.grand_total)
		paid = sum(flt(x.get("amount")) for x in payments)
		if paid + 0.001 < due:
			frappe.throw(_("Payment of ₹{0} is less than the bill total ₹{1}.").format(paid, due))
		if not offline_at:
			from jalgo_pos.payments import check_upi_payment
			check_upi_payment(payments, due)
			refs = [x.get("reference") for x in payments if x.get("reference")]
			if refs:
				si.remarks += " | Razorpay " + ", ".join(refs)
		if offline_at:
			si.remarks += f" | made offline at {offline_at}"
		si.set("payments", [])
		for x in payments:
			if flt(x.get("amount")) > 0:
				si.append("payments", {"mode_of_payment": x["mode"], "amount": flt(x["amount"])})
	si.insert()
	si.submit()
	if held_bill and frappe.db.exists("JALGO Held Bill", held_bill):
		frappe.delete_doc("JALGO Held Bill", held_bill, ignore_permissions=True)
	return receipt(si.name)


@frappe.whitelist()
def receipt(name):
	_require_cashier()
	si = frappe.get_doc("Sales Invoice", name)
	si.check_permission("read")
	mrp = {r.item_code: r.price_list_rate for r in frappe.get_all("Item Price", filters={"item_code": ["in", [i.item_code for i in si.items]], "price_list": "JALGO MRP"}, fields=["item_code", "price_list_rate"])}
	taxes = {}
	for t in si.taxes:
		taxes[t.description or t.account_head] = flt(t.tax_amount)
	saved = sum(max(0, flt(mrp.get(i.item_code, i.price_list_rate)) * abs(i.qty) - abs(i.amount)) for i in si.items)
	return {"name": si.name, "posting_date": str(si.posting_date), "posting_time": str(si.posting_time)[:5], "customer": si.customer_name,
		"is_return": si.is_return, "return_against": si.return_against, "credit": not si.is_pos and not si.is_return,
		"items": [{"code": i.item_code, "name": i.item_name, "qty": i.qty, "rate": i.rate, "amount": i.amount, "disc": i.discount_percentage} for i in si.items],
		"net_total": si.net_total, "taxes": taxes, "grand_total": si.grand_total, "rounding_adjustment": si.rounding_adjustment,
		"rounded_total": si.rounded_total or si.grand_total, "paid": si.paid_amount, "change": si.change_amount, "outstanding": si.outstanding_amount,
		"payments": [{"mode": p.mode_of_payment, "amount": p.amount} for p in si.payments], "saved": round(saved, 2), "status": si.status}


# ---------------------------------------------------------------- hold / recall
@frappe.whitelist(methods=["POST"])
def hold_bill(lines, customer=None, sales_executive=None, total=0, name=None):
	_require_cashier()
	lines = _parse(lines)
	if not lines:
		frappe.throw(_("Nothing to hold."))
	slim = [{"code": l["code"], "qty": flt(l.get("qty")), "disc": flt(l.get("disc"))} for l in lines]
	doc = frappe.get_doc("JALGO Held Bill", name) if name and frappe.db.exists("JALGO Held Bill", name) else frappe.new_doc("JALGO Held Bill")
	doc.update({"customer": customer or "", "sales_executive": sales_executive or "", "total": flt(total), "item_count": len(slim), "lines": json.dumps(slim)})
	doc.save(ignore_permissions=True)
	return doc.name


@frappe.whitelist()
def held_bills():
	_require_cashier()
	return frappe.get_all("JALGO Held Bill", fields=["name", "customer", "total", "item_count", "owner", "creation"], order_by="creation desc", limit=30)


@frappe.whitelist()
def recall_bill(name):
	"""Return the held lines with fresh prices and stock. The held copy stays until the bill is paid or discarded."""
	_require_cashier()
	h = frappe.get_doc("JALGO Held Bill", name)
	lines = json.loads(h.lines or "[]")
	fresh = {r["code"]: r for r in _item_rows(frappe.get_all("Item", filters={"name": ["in", [l["code"] for l in lines]]}, fields=["name", "item_name", "stock_uom", "item_group", "image"]))}
	return {"name": h.name, "customer": h.customer, "sales_executive": h.sales_executive,
		"lines": [{**fresh[l["code"]], "qty": l["qty"], "disc": l["disc"]} for l in lines if l["code"] in fresh]}


@frappe.whitelist(methods=["POST"])
def discard_held(name):
	_require_cashier()
	frappe.delete_doc("JALGO Held Bill", name, ignore_permissions=True)
	return True


# ---------------------------------------------------------------- estimate (Quotation)
@frappe.whitelist(methods=["POST"])
def save_estimate(items, customer=None, manager_pin=None):
	_require_cashier()
	p = profile()
	lines = _lines(_parse(items), manager_pin, _active_offers())
	q = frappe.new_doc("Quotation")
	q.update({"quotation_to": "Customer", "party_name": _customer(customer), "company": p.company, "transaction_date": nowdate(),
		"valid_till": frappe.utils.add_days(nowdate(), 7), "selling_price_list": p.selling_price_list, "order_type": "Sales"})
	_fill(q, lines, p)
	q.insert()
	q.submit()
	return {"name": q.name, "valid_till": str(q.valid_till), "customer": q.customer_name,
		"items": [{"name": i.item_name, "qty": i.qty, "rate": i.rate, "amount": i.amount} for i in q.items],
		"net_total": q.net_total, "taxes": {t.description or t.account_head: t.tax_amount for t in q.taxes},
		"rounded_total": q.rounded_total or q.grand_total}


# ---------------------------------------------------------------- returns
@frappe.whitelist()
def find_bill(name):
	"""Original bill plus how much of each line can still come back."""
	_require_cashier()
	si = frappe.get_doc("Sales Invoice", name)
	si.check_permission("read")
	if si.docstatus != 1 or si.is_return:
		frappe.throw(_("{0} is not a submitted sale.").format(name))
	returned = {}
	for r in frappe.db.sql("""select i.item_code, sum(-i.qty) q from `tabSales Invoice Item` i join `tabSales Invoice` s on s.name=i.parent
		where s.return_against=%s and s.docstatus=1 group by i.item_code""", name, as_dict=1):
		returned[r.item_code] = flt(r.q)
	return {"name": si.name, "customer": si.customer_name, "date": str(si.posting_date), "total": si.rounded_total or si.grand_total, "credit": not si.is_pos,
		"items": [{"code": i.item_code, "name": i.item_name, "sold": i.qty, "rate": i.rate, "can_return": i.qty - returned.get(i.item_code, 0)} for i in si.items]}


@frappe.whitelist(methods=["POST"])
def submit_return(name, items, manager_pin=None, uuid=None):
	"""Create a return (credit note) against a POS bill; stock goes back; cash refunded from the drawer."""
	_require_cashier()
	_require_pin(manager_pin, _("take a return"))
	if uuid:
		ex = frappe.db.get_value("Sales Invoice", {"jalgo_pos_uuid": uuid}, "name")
		if ex:
			return receipt(ex)
	_require_shift()
	want = {i["code"]: flt(i["qty"]) for i in _parse(items) if flt(i.get("qty")) > 0}
	if not want:
		frappe.throw(_("Choose at least one item to return."))
	orig = find_bill(name)
	can = {i["code"]: i["can_return"] for i in orig["items"]}
	for code, q in want.items():
		if q > flt(can.get(code)):
			frappe.throw(_("Only {0} of {1} can still be returned.").format(can.get(code, 0), code))
	from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return
	ret = make_sales_return(name)
	ret.items = [d for d in ret.items if d.item_code in want]
	for d in ret.items:
		d.qty = -want[d.item_code]
	ret.jalgo_pos_uuid = uuid
	ret.remarks = f"JALGO POS return against {name}"
	ret.calculate_taxes_and_totals()
	if ret.is_pos:
		ret.set("payments", [])
		ret.append("payments", {"mode_of_payment": "Cash", "amount": flt(ret.rounded_total or ret.grand_total)})
		ret.calculate_taxes_and_totals()
	ret.insert()
	ret.submit()
	return receipt(ret.name)


@frappe.whitelist()
def catalog():
	"""All sellable items with price, barcode and stock, for offline billing on this counter."""
	_require_cashier()
	items = frappe.get_all("Item", filters={"disabled": 0, "is_sales_item": 1, "has_variants": 0}, fields=["name", "item_name", "stock_uom", "item_group", "image"], limit=5000)
	return {"at": str(now_datetime()), "items": [r for r in _item_rows(items) if r["rate"] > 0]}
