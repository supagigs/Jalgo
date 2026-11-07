"""JALGO website API v1. Prices, fees, stock and allocation are always decided here, on the server.
Endpoints: /api/method/jalgo.api.<name>
"""
import re

import frappe
from frappe import _
from frappe.utils import flt, cint, now_datetime

from jalgo import logic

PHONE = re.compile(r"^[6-9]\d{9}$")


@frappe.whitelist(allow_guest=True, methods=["GET"])
def catalogue():
	s = logic.settings()
	items = frappe.get_all("Item", filters={"disabled": 0, "is_sales_item": 1, "is_stock_item": 1},
		fields=["item_code", "item_name", "item_group", "stock_uom", "description", "image"], order_by="item_group, item_name")
	prices = {p.item_code: p.price_list_rate for p in frappe.get_all("Item Price",
		filters={"price_list": s.selling_price_list}, fields=["item_code", "price_list_rate"])}
	mrps = {p.item_code: p.price_list_rate for p in frappe.get_all("Item Price",
		filters={"price_list": "JALGO MRP"}, fields=["item_code", "price_list_rate"])} if frappe.db.exists("Price List", "JALGO MRP") else {}
	whs = [l.warehouse for l in frappe.get_all("JALGO Fulfilment Location", filters={"is_open": 1}, fields=["warehouse"])]
	stock = {}
	for b in frappe.get_all("Bin", filters={"warehouse": ["in", whs or [""]]}, fields=["item_code", "actual_qty"]):
		stock[b.item_code] = max(stock.get(b.item_code, 0), b.actual_qty)  # best single location, never pooled
	return [{"code": i.item_code, "name": i.item_name, "group": i.item_group, "pack": (i.description or "").strip(),
		"price": prices.get(i.item_code), "mrp": mrps.get(i.item_code), "in_stock": stock.get(i.item_code, 0) > 0}
		for i in items if prices.get(i.item_code)]


@frappe.whitelist(allow_guest=True, methods=["POST"])
def quote(items, mode, lat, lng):
	items = _clean_items(items)
	loc, dist, reasons = logic.allocate(items, flt(lat), flt(lng), mode)
	if not loc:
		return {"ok": False, "message": _("No single store can supply your whole basket right now. Remove or reduce the items shown."), "reasons": reasons}
	subtotal = sum(logic.item_price(i["item_code"]) * flt(i["qty"]) for i in items)
	try:
		fees = logic.compute_fees(subtotal, mode, dist if mode == "Quick" else None)
	except frappe.ValidationError as e:
		frappe.clear_messages()
		return {"ok": False, "message": str(e)}
	return {"ok": True, "location": loc, "distance_km": dist, "subtotal": subtotal, **fees,
		"total": subtotal + fees["delivery_fee"] + fees["handling_fee"]}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def place_order(items, mode, lat, lng, phone, name, address, payment_method="Cash on Delivery", slot=None):
	"""Demo checkout (guest, phone identifies the customer). Production must require OTP-verified login
	and Razorpay signature verification before payment_status = Paid."""
	if not PHONE.match(str(phone or "")):
		frappe.throw(_("Enter a valid 10-digit mobile number."))
	if len((address or "").strip()) < 8:
		frappe.throw(_("Enter your full delivery address."))
	if payment_method not in ("UPI", "Card", "Cash on Delivery"):
		frappe.throw(_("Choose a payment method."))
	items = _clean_items(items)
	loc, dist, reasons = logic.allocate(items, flt(lat), flt(lng), mode)
	if not loc:
		frappe.throw(_("No single store can supply your whole basket right now."), title=_("Cannot allocate"))
	customer = _customer(phone, name)
	order = frappe.get_doc({"doctype": "JALGO Order", "customer": customer, "customer_phone": phone,
		"order_datetime": now_datetime(), "delivery_mode": mode, "slot": slot if mode == "Scheduled" else None,
		"status": "Allocated", "fulfilment_location": loc, "distance_km": dist, "latitude": flt(lat), "longitude": flt(lng),
		"delivery_address": address.strip(), "payment_method": payment_method,
		"payment_status": "Unpaid", "items": [{"item_code": i["item_code"], "qty": i["qty"]} for i in items]})
	order.insert(ignore_permissions=True)
	_assign_rider(order)
	return {"order": order.name, "grand_total": order.grand_total, "location": loc, "distance_km": dist, "status": order.status}


@frappe.whitelist(allow_guest=True, methods=["GET"])
def track(order, phone):
	o = frappe.db.get_value("JALGO Order", order, ["name", "status", "customer_phone", "delivery_mode", "grand_total",
		"fulfilment_location", "delivery_job", "sales_invoice"], as_dict=True)
	if not o or o.customer_phone != phone:
		frappe.throw(_("Order not found."), frappe.DoesNotExistError)
	o.pop("customer_phone")
	o.rider = frappe.db.get_value("JALGO Delivery Job", o.delivery_job, "rider") if o.delivery_job else None
	return o


@frappe.whitelist(methods=["POST"])
def advance(order):
	"""Ops/staff action: move an order one step forward. Delivered posts the ERPNext invoice + payment."""
	frappe.only_for(("System Manager", "JALGO Ops", "JALGO Store"))
	flow = ["Allocated", "Picking", "Out for Delivery", "Delivered"]
	doc = frappe.get_doc("JALGO Order", order)
	if doc.status not in flow[:-1]:
		frappe.throw(_("This order can't move forward from {0}.").format(doc.status))
	doc.status = flow[flow.index(doc.status) + 1]
	doc.save()
	return {"status": doc.status, "sales_invoice": doc.sales_invoice}


@frappe.whitelist(methods=["GET"])
def dashboard():
	frappe.only_for(("System Manager", "JALGO Ops", "JALGO Finance"))
	from jalgo.reports import summary
	return summary()


# ---------------- helpers ----------------
def _clean_items(items):
	items = frappe.parse_json(items) if isinstance(items, str) else items
	out = {}
	for i in items or []:
		code, qty = i.get("item_code") or i.get("code"), cint(i.get("qty"))
		if not code or qty < 1 or qty > 50 or not frappe.db.exists("Item", code):
			frappe.throw(_("Your cart has an invalid item."))
		out[code] = out.get(code, 0) + qty
	if not out:
		frappe.throw(_("Your cart is empty."))
	return [{"item_code": k, "qty": v} for k, v in out.items()]


def _customer(phone, name):
	existing = frappe.db.get_value("Customer", {"mobile_no": phone}, "name")
	if existing:
		return existing
	c = frappe.get_doc({"doctype": "Customer", "customer_name": (name or "JALGO Customer").strip()[:80],
		"customer_type": "Individual", "customer_group": "Individual", "territory": "India", "mobile_no": phone})
	c.insert(ignore_permissions=True)
	return c.name


def _assign_rider(order):
	rider = frappe.db.get_value("JALGO Rider", {"status": "Active", "is_available": 1}, "name", order_by="modified asc")
	p = logic.compute_payout(order.distance_km, order.delivery_mode, order.tip)
	job = frappe.get_doc({"doctype": "JALGO Delivery Job", "jalgo_order": order.name, "rider": rider,
		"delivery_mode": order.delivery_mode, "distance_km": order.distance_km, "status": "Assigned",
		"assigned_at": now_datetime(), **p})
	job.insert(ignore_permissions=True)
	frappe.db.set_value("JALGO Order", order.name, "delivery_job", job.name, update_modified=False)
	if rider:
		frappe.db.set_value("JALGO Rider", rider, "modified", now_datetime(), update_modified=False)
	return job.name
