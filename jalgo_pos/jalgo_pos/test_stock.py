import uuid

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import flt

from jalgo_pos import api, stock


def bal(code, wh=None):
	return flt(frappe.db.get_value("Bin", {"item_code": code, "warehouse": wh or api.profile().warehouse}, "actual_qty"))


class TestStock(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		if not api.current_shift():
			api.open_shift(0)

	def test_grn_by_template_creates_variants_and_receipt(self):
		stock.save_attribute("Flavour", ["Classic", "Masala", "Mint"])
		tag = frappe.generate_hash(length=4).upper()
		sup = frappe.get_all("Supplier", pluck="name", limit=1)[0]
		r = stock.grn_by_template(sup, "Flavour", [
			{"name": f"Test Chips {tag}", "q": {"Classic": 10, "Masala": 5}, "cost": 16, "sale": 20, "mrp": 20, "gst": 5}],
			supplier_invoice="TST/1", item_group="Snacks & Biscuits")
		self.assertEqual(r["status"], "Submitted")
		self.assertEqual(r["qty"], 15)
		codes = [i["code"] for i in r["items"]]
		self.assertEqual(len(codes), 2)
		self.assertEqual(frappe.db.get_value("Item", codes[0], "variant_of"), frappe.db.get_value("Item", {"item_name": f"Test Chips {tag}", "has_variants": 1}))
		self.assertEqual(bal(codes[0]), 10)
		# new variants are sellable at the counter right away
		found = api.search_items(codes[1])
		self.assertEqual(found[0]["rate"], 20)
		self.assertEqual(found[0]["gst"], 5)
		# receiving the same product again reuses the variants
		r2 = stock.grn_by_template(sup, "Flavour", [{"name": f"Test Chips {tag}", "q": {"Classic": 4}, "cost": 16, "sale": 20, "gst": 5}], hold=1)
		self.assertEqual(r2["items"][0]["code"], codes[0])
		self.assertEqual(r2["status"], "Held (draft)")
		self.assertEqual(bal(codes[0]), 10)  # draft does not move stock

	def test_bad_value_rejected(self):
		stock.save_attribute("Flavour", ["Classic"])
		sup = frappe.get_all("Supplier", pluck="name", limit=1)[0]
		with self.assertRaises(frappe.ValidationError):
			stock.grn_by_template(sup, "Flavour", [{"name": "X", "q": {"Chocolate": 1}, "cost": 1, "gst": 5}])

	def test_transfer_moves_stock_between_ledgers(self):
		dark = next(l["name"] for l in stock.locations() if "Dark" in l["name"])
		a, b = bal("JLG-029"), bal("JLG-029", dark)
		stock.transfer(dark, [{"code": "JLG-029", "qty": 6}])
		self.assertEqual(bal("JLG-029"), a - 6)
		self.assertEqual(bal("JLG-029", dark), b + 6)

	def test_write_off_needs_reason(self):
		before = bal("JLG-009")
		with self.assertRaises(frappe.ValidationError):
			stock.write_off([{"code": "JLG-009", "qty": 1}], "")
		stock.write_off([{"code": "JLG-009", "qty": 2}], "spoiled tomatoes")
		self.assertEqual(bal("JLG-009"), before - 2)

	def test_collect_udhaar_fifo(self):
		mob = "97" + frappe.generate_hash(length=8)
		mob = "".join(c if c.isdigit() else str(ord(c) % 10) for c in mob)[:10]
		c = api.create_customer("Udhaar FIFO " + mob[-4:], mob)
		b1 = api.submit_invoice(str(uuid.uuid4()), [{"code": "JLG-001", "qty": 1}], [{"mode": "Credit"}], customer=c["name"])
		b2 = api.submit_invoice(str(uuid.uuid4()), [{"code": "JLG-001", "qty": 2}], [{"mode": "Credit"}], customer=c["name"])
		owed = b1["outstanding"] + b2["outstanding"]
		with self.assertRaises(frappe.ValidationError):
			stock.collect_payment(c["name"], owed + 100)
		r = stock.collect_payment(c["name"], b1["outstanding"] + 1)
		self.assertEqual(flt(frappe.db.get_value("Sales Invoice", b1["name"], "outstanding_amount")), 0)
		self.assertEqual(flt(frappe.db.get_value("Sales Invoice", b2["name"], "outstanding_amount")), b2["outstanding"] - 1)
		self.assertAlmostEqual(r["still_owed"], owed - b1["outstanding"] - 1, places=2)

	def test_cashier_without_role_needs_pin(self):
		u = "jalgo-test-cashier@example.com"
		if not frappe.db.exists("User", u):
			frappe.get_doc({"doctype": "User", "email": u, "first_name": "Test Cashier", "send_welcome_email": 0,
				"roles": [{"role": r} for r in ["JALGO Cashier", "Sales User", "Accounts User", "Stock User"]]}).insert(ignore_permissions=True)
		frappe.set_user(u)
		with self.assertRaises(frappe.PermissionError):
			stock.write_off([{"code": "JLG-009", "qty": 1}], "test damage")


class TestLabels(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def test_rate_card_round_trip_and_stickers(self):
		from jalgo_pos import labels
		card = {d: [c] for d, c in zip("0123456789.", "ABCDEFGHIJX")}
		labels.save_rate_card(card)
		self.assertEqual(labels.encode(100), "BAA")
		self.assertEqual(labels.encode(209.5), "CAJXF")
		s = labels.sticker_items(["JLG-015"])[0]
		decode = {v[0]: d for d, v in card.items()}
		self.assertEqual(int("".join(decode[c] for c in s["field1"])), round(s["cost"]))
		with self.assertRaises(frappe.ValidationError):
			labels.save_rate_card({**card, "1": ["A"]})  # A already means 0

	def test_settings_validation(self):
		from jalgo_pos import labels
		with self.assertRaises(frappe.ValidationError):
			labels.save_settings({"max_cashier_discount": 30, "max_manager_discount": 20})
		r = labels.save_settings({"accept_barcode_in_name": 1, "max_cashier_discount": 5, "max_manager_discount": 20})
		self.assertEqual(r["accept_barcode_in_name"], 1)


class TestRoles(IntegrationTestCase):
	def test_cashier_can_bill_but_not_manage(self):
		from jalgo_pos import setup, labels
		u = "jalgo-role-cashier@example.com"
		if not frappe.db.exists("User", u):
			frappe.get_doc({"doctype": "User", "email": u, "first_name": "Role Cashier", "send_welcome_email": 0}).insert(ignore_permissions=True)
		frappe.set_user("Administrator")
		setup.make_pos_user(u)
		frappe.set_user(u)
		if not api.current_shift():
			api.open_shift(0)
		r = api.submit_invoice(str(uuid.uuid4()), [{"code": "JLG-001", "qty": 1}], [{"mode": "Cash", "amount": 100}])
		self.assertEqual(frappe.db.get_value("Sales Invoice", r["name"], "owner"), u)
		with self.assertRaises(frappe.PermissionError):
			labels.save_settings({"warn_not_found": 0})
		with self.assertRaises(frappe.PermissionError):
			stock.transfer("x", [{"code": "JLG-001", "qty": 1}])
		self.assertTrue(labels.save_settings({"warn_not_found": 1}, pin="2468"))

	def test_user_without_pos_role_blocked(self):
		u = "jalgo-no-role@example.com"
		if not frappe.db.exists("User", u):
			frappe.get_doc({"doctype": "User", "email": u, "first_name": "No Role", "send_welcome_email": 0,
				"roles": [{"role": "Sales User"}, {"role": "Accounts User"}]}).insert(ignore_permissions=True)
		frappe.set_user(u)
		with self.assertRaises(frappe.PermissionError):
			api.search_items("atta")


class TestPaymentsAndOffline(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def test_webhook_signature_and_qr_flow(self):
		from jalgo_pos import payments
		import json as _j
		body = _j.dumps({"event": "qr_code.credited", "payload": {"qr_code": {"entity": {"id": "qr_TEST1", "payment_amount": 2800, "notes": {"bill_uuid": "u1"}}},
			"payment": {"entity": {"id": "pay_TEST1", "status": "captured", "amount": 2800}}}}).encode()
		import hashlib, hmac
		sig = hmac.new(b"whsec", body, hashlib.sha256).hexdigest()
		self.assertTrue(payments.verify_signature(body, sig, "whsec"))
		self.assertFalse(payments.verify_signature(body, sig, "wrong"))
		self.assertFalse(payments.verify_signature(body, "", "whsec"))
		payments.handle_event(_j.loads(body))
		self.assertEqual(payments.qr_status("qr_TEST1")["status"], "paid")
		# with Razorpay switched on, an unpaid UPI line is refused and a paid one passes
		frappe.conf.update({"razorpay_key_id": "k", "razorpay_key_secret": "s", "razorpay_webhook_secret": "whsec"})
		try:
			with self.assertRaises(frappe.ValidationError):
				payments.check_upi_payment([{"mode": "UPI", "amount": 28, "qr_id": "qr_NOPE"}], 28)
			pays = [{"mode": "UPI", "amount": 28, "qr_id": "qr_TEST1"}]
			payments.check_upi_payment(pays, 28)
			self.assertEqual(pays[0]["reference"], "pay_TEST1")
		finally:
			for k in ("razorpay_key_id", "razorpay_key_secret", "razorpay_webhook_secret"):
				frappe.conf.pop(k, None)

	def test_offline_bill_syncs_with_its_own_time_and_once(self):
		from frappe.utils import add_to_date, now_datetime
		at = str(add_to_date(now_datetime(), hours=-2))
		u = str(uuid.uuid4())
		a = api.submit_invoice(u, [{"code": "JLG-001", "qty": 1}], [{"mode": "Cash", "amount": 50}], offline_at=at)
		b = api.submit_invoice(u, [{"code": "JLG-001", "qty": 1}], [{"mode": "Cash", "amount": 50}], offline_at=at)
		self.assertEqual(a["name"], b["name"])
		self.assertEqual(str(frappe.db.get_value("Sales Invoice", a["name"], "posting_time"))[:5], at[11:16])
		with self.assertRaises(frappe.ValidationError):
			api.submit_invoice(str(uuid.uuid4()), [{"code": "JLG-001", "qty": 1}], [{"mode": "Cash", "amount": 50}], offline_at="2020-01-01 10:00:00")
		self.assertTrue(len(api.catalog()["items"]) > 10)
