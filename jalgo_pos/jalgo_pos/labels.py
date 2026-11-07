"""Barcode stickers with an encoded purchase price (Rate Card), and counter settings.
The purchase price never leaves the server for cashiers: they only receive the encoded text."""
import json
import random
import string

import frappe
from frappe import _
from frappe.utils import flt, cint

from jalgo_pos.api import _require_cashier, _parse, profile, settings
from jalgo_pos.stock import _require_manager

DIGITS = list("0123456789.")
SETTING_FIELDS = ["max_cashier_discount", "max_manager_discount", "require_shift", "accept_barcode_in_name", "warn_not_found"]


def _is_manager():
	return bool(set(frappe.get_roles()) & {"JALGO Manager", "System Manager", "Stock Manager"})


def _card():
	raw = settings().get("rate_card")
	card = json.loads(raw) if raw else {}
	return {d: [c for c in (card.get(d) or [])][:2] for d in DIGITS}


def encode(price, card=None):
	"""Encode a price with the rate card. With two codes for a digit, one is picked at random each time."""
	card = card or _card()
	txt = f"{flt(price):.2f}".rstrip("0").rstrip(".") if flt(price) != int(flt(price)) else str(int(flt(price)))
	out = []
	for ch in txt:
		opts = [c for c in card.get(ch, []) if c]
		if not opts:
			frappe.throw(_("The rate card has no code for '{0}'. Fill it in first.").format(ch))
		out.append(random.choice(opts))
	return "".join(out)


@frappe.whitelist()
def get_rate_card():
	_require_cashier()
	return {"card": _card(), "manager": _is_manager()}


@frappe.whitelist(methods=["POST"])
def save_rate_card(card, pin=None):
	_require_manager(pin)
	card = _parse(card) if isinstance(card, str) else card
	clean = {}
	for d in DIGITS:
		codes = [str(c).strip().upper()[:1] for c in (card.get(d) or []) if str(c).strip()][:2]
		if not codes:
			frappe.throw(_("Give digit '{0}' at least one code.").format(d))
		clean[d] = codes
	# a code must decode to exactly one digit
	owner = {}
	for d, codes in clean.items():
		for c in codes:
			if owner.get(c, d) != d:
				frappe.throw(_("Code {0} is used for both {1} and {2}.").format(c, owner[c], d))
			owner[c] = d
	frappe.db.set_single_value("JALGO POS Settings", "rate_card", json.dumps(clean))
	return clean


@frappe.whitelist()
def suggest_rate_card():
	_require_cashier()
	letters = random.sample(string.ascii_uppercase, 22)
	return {d: [letters[i * 2], letters[i * 2 + 1]] for i, d in enumerate(DIGITS)}


@frappe.whitelist()
def sticker_items(codes):
	"""Name, barcode, price, MRP and Field1 (rate-card code of the purchase price) for each item."""
	_require_cashier()
	codes = _parse(codes)
	p = profile()
	card = _card()
	have_card = all(card[d] for d in DIGITS)
	out = []
	for code in codes:
		it = frappe.db.get_value("Item", code, ["name", "item_name", "valuation_rate", "last_purchase_rate"], as_dict=1)
		if not it:
			continue
		cost = flt(frappe.db.get_value("Bin", {"item_code": code, "warehouse": p.warehouse}, "valuation_rate")) or flt(it.valuation_rate) or flt(it.last_purchase_rate)
		row = {"code": code, "name": it.item_name,
			"barcode": frappe.db.get_value("Item Barcode", {"parent": code}, "barcode") or code,
			"rate": flt(frappe.db.get_value("Item Price", {"item_code": code, "price_list": p.selling_price_list}, "price_list_rate")),
			"mrp": flt(frappe.db.get_value("Item Price", {"item_code": code, "price_list": "JALGO MRP"}, "price_list_rate")),
			"field1": encode(round(cost), card) if have_card and cost else ""}
		if _is_manager():
			row["cost"] = round(cost, 2)
		out.append(row)
	return out


@frappe.whitelist()
def get_settings():
	_require_cashier()
	s = settings()
	return {f: s.get(f) for f in SETTING_FIELDS} | {"manager": _is_manager()}


@frappe.whitelist(methods=["POST"])
def save_settings(values, pin=None):
	_require_manager(pin)
	values = _parse(values) if isinstance(values, str) else values
	s = settings()
	for f in SETTING_FIELDS:
		if f in values:
			s.set(f, values[f])
	if flt(s.max_cashier_discount) > flt(s.max_manager_discount):
		frappe.throw(_("The cashier limit cannot be more than the manager limit."))
	s.save(ignore_permissions=True)
	return get_settings()
