"""JALGO business rules. Every number comes from JALGO Settings / rules, never from the browser."""
import math

import frappe
from frappe import _
from frappe.utils import flt, now_datetime, get_datetime, add_to_date


def settings():
	return frappe.get_cached_doc("JALGO Settings")


# ---------------- geo ----------------
def km_between(lat1, lng1, lat2, lng2):
	"""Straight-line distance. Route distance needs a maps provider (not configured in the demo)."""
	r = math.radians
	dlat, dlng = r(lat2 - lat1), r(lng2 - lng1)
	h = math.sin(dlat / 2) ** 2 + math.cos(r(lat1)) * math.cos(r(lat2)) * math.sin(dlng / 2) ** 2
	return 2 * 6371 * math.asin(math.sqrt(h))


# ---------------- customer pricing ----------------
def compute_fees(subtotal, mode, distance_km=None):
	s = settings()
	subtotal = flt(subtotal)
	if subtotal < flt(s.min_order_value):
		frappe.throw(_("Minimum order value is ₹{0}. Add ₹{1} more.").format(s.min_order_value, flt(s.min_order_value) - subtotal),
			title=_("Below minimum order"))
	if mode == "Quick":
		if distance_km is not None and flt(distance_km) > flt(s.quick_max_km):
			frappe.throw(_("Quick delivery is available within {0} km. Choose Scheduled delivery.").format(s.quick_max_km),
				title=_("Quick not available"))
		return {"delivery_fee": flt(s.quick_delivery_fee), "handling_fee": flt(s.quick_handling_fee)}
	if subtotal >= flt(s.scheduled_free_from):
		return {"delivery_fee": 0, "handling_fee": 0}
	if subtotal <= 400:
		return {"delivery_fee": flt(s.scheduled_fee_upto_400), "handling_fee": 0}
	if not s.scheduled_mid_fee_decided:  # a blank Currency field reads as 0, so an explicit switch is required
		frappe.throw(_("The Scheduled delivery fee for orders of ₹401–₹499 has not been set yet."), title=_("Fee not configured"))
	return {"delivery_fee": flt(s.scheduled_mid_fee), "handling_fee": 0}


# ---------------- rider payout (Option B) ----------------
def compute_payout(distance_km, mode, tip=0):
	s = settings()
	d = flt(distance_km)
	bands = sorted(s.payout_bands, key=lambda b: b.from_km)
	incentive = 0.0
	if d > 5:
		top = next((b for b in bands if flt(b.from_km) == 4), None)
		incentive = flt(top.incentive if top else 18) + math.ceil(d - 5) * flt(s.rider_per_km_beyond_5)
	else:
		for b in bands:  # exactly one band applies: no double counting
			if flt(b.from_km) <= d <= flt(b.to_km) and (d > flt(b.from_km) or flt(b.from_km) == 0):
				incentive = flt(b.incentive)
				break
	quick = flt(s.rider_quick_incentive) if mode == "Quick" else 0
	base = flt(s.rider_base_payout)
	return {"base_payout": base, "distance_incentive": incentive, "quick_incentive": quick, "tip": flt(tip),
		"total_payout": base + incentive + quick + flt(tip)}


# ---------------- fulfilment allocation (rule-based v1) ----------------
def stock_at(warehouse, item_code):
	return flt(frappe.db.get_value("Bin", {"warehouse": warehouse, "item_code": item_code}, "actual_qty"))


def allocate(items, lat, lng, mode):
	"""One location fulfils the whole order. Never splits, never substitutes.
	Rules: open → has every item in full → within radius → nearest. Returns (location, distance, reasons)."""
	reasons = []
	candidates = []
	for loc in frappe.get_all("JALGO Fulfilment Location",
			fields=["name", "warehouse", "is_open", "latitude", "longitude", "service_radius_km"]):
		if not loc.is_open:
			reasons.append(f"{loc.name}: closed"); continue
		dist = km_between(lat, lng, loc.latitude, loc.longitude)
		if dist > flt(loc.service_radius_km):
			reasons.append(f"{loc.name}: {dist:.1f} km is outside its {loc.service_radius_km} km radius"); continue
		missing = [i["item_code"] for i in items if stock_at(loc.warehouse, i["item_code"]) < flt(i["qty"])]
		if missing:
			reasons.append(f"{loc.name}: short on {', '.join(missing[:3])}"); continue
		candidates.append((dist, loc.name))
	if not candidates:
		return None, None, reasons
	candidates.sort()
	return candidates[0][1], round(candidates[0][0], 2), reasons


# ---------------- commission ----------------
def commission_percent(item_group):
	return flt(frappe.db.get_value("JALGO Commission Rule", item_group, "commission_percent"))


# ---------------- order events (wired in hooks.py) ----------------
def order_validate(doc, method=None):
	subtotal = commission = 0
	for it in doc.items:
		item = frappe.get_cached_value("Item", it.item_code, ["item_name", "item_group"], as_dict=True)
		it.item_name, it.item_group = item.item_name, item.item_group
		if not it.rate:
			it.rate = item_price(it.item_code)
		it.amount = flt(it.rate) * flt(it.qty)
		it.commission_percent = commission_percent(it.item_group)
		it.commission_amount = flt(it.amount * it.commission_percent / 100, 2)
		subtotal += it.amount
		commission += it.commission_amount
	doc.subtotal = subtotal
	fees = compute_fees(subtotal, doc.delivery_mode, doc.distance_km if doc.delivery_mode == "Quick" else None)
	doc.delivery_fee, doc.handling_fee = fees["delivery_fee"], fees["handling_fee"]
	doc.grand_total = subtotal + doc.delivery_fee + doc.handling_fee - flt(doc.discount) + flt(doc.tip)
	ltype = frappe.db.get_value("JALGO Fulfilment Location", doc.fulfilment_location, "location_type") if doc.fulfilment_location else None
	doc.commission_amount = commission if ltype == "Partner Store" else 0
	if doc.delivery_mode == "Scheduled" and not doc.slot:
		frappe.throw(_("Choose a delivery slot for Scheduled orders."))


def order_on_update(doc, method=None):
	if doc.status == "Delivered" and not doc.sales_invoice:
		make_sales_invoice(doc)
	if doc.status == "Delivered" and doc.delivery_job:
		frappe.db.set_value("JALGO Delivery Job", doc.delivery_job, {"status": "Delivered", "delivered_at": doc.get("_delivered_at") or now_datetime()})


def item_price(item_code):
	pl = settings().selling_price_list or "Standard Selling"
	return flt(frappe.db.get_value("Item Price", {"item_code": item_code, "price_list": pl}, "price_list_rate"))


# ---------------- ERPNext posting ----------------
def make_sales_invoice(order, posting_dt=None):
	s = settings()
	wh = frappe.db.get_value("JALGO Fulfilment Location", order.fulfilment_location, "warehouse")
	posting_dt = get_datetime(posting_dt or order.order_datetime)
	si = frappe.new_doc("Sales Invoice")
	si.update({"customer": order.customer, "company": s.company, "set_posting_time": 1,
		"posting_date": posting_dt.date(), "posting_time": posting_dt.time(), "due_date": posting_dt.date(),
		"update_stock": 1, "set_warehouse": wh, "selling_price_list": s.selling_price_list,
		"remarks": f"JALGO order {order.name} ({order.delivery_mode})"})
	for it in order.items:
		si.append("items", {"item_code": it.item_code, "qty": it.qty, "rate": it.rate, "warehouse": wh})
	if flt(order.delivery_fee):
		si.append("items", {"item_code": s.delivery_item, "qty": 1, "rate": order.delivery_fee})
	if flt(order.handling_fee):
		si.append("items", {"item_code": s.handling_item, "qty": 1, "rate": order.handling_fee})
	si.flags.ignore_permissions = True
	si.insert()
	si.submit()
	if order.payment_status == "Paid" or order.payment_method == "Cash on Delivery":
		from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
		pe = get_payment_entry("Sales Invoice", si.name)
		pe.posting_date = posting_dt.date()
		pe.reference_no = order.name
		pe.reference_date = posting_dt.date()
		pe.flags.ignore_permissions = True
		pe.insert(); pe.submit()
	frappe.db.set_value("JALGO Order", order.name, {"sales_invoice": si.name, "payment_status": "Paid"}, update_modified=False)
	return si.name
