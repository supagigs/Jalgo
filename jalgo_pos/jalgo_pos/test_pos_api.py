import uuid

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import flt

from jalgo_pos import api


def bal(code):
	return flt(frappe.db.get_value("Bin", {"item_code": code, "warehouse": api.profile().warehouse}, "actual_qty"))


class TestPOSApi(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		if not api.current_shift():
			api.open_shift(500)

	def test_search_by_barcode_and_name(self):
		code = frappe.db.get_value("Item Barcode", {"parent": "JLG-029"}, "barcode")
		r = api.search_items(code)
		self.assertEqual([x["code"] for x in r], ["JLG-029"])
		self.assertTrue(any(x["code"] == "JLG-015" for x in api.search_items("aashirvaad")))

	def test_bill_is_gst_inclusive_and_reduces_stock(self):
		before = bal("JLG-029")
		price = api.search_items("JLG-029")[0]["rate"]
		r = api.submit_invoice(str(uuid.uuid4()), [{"code": "JLG-029", "qty": 2}], [{"mode": "Cash", "amount": 1000}])
		self.assertAlmostEqual(r["grand_total"], price * 2, places=2)  # shelf price already includes GST
		self.assertGreater(sum(r["taxes"].values()), 0)
		self.assertEqual(bal("JLG-029"), before - 2)
		self.assertEqual(frappe.db.get_value("Sales Invoice", r["name"], "docstatus"), 1)

	def test_same_bill_id_is_not_saved_twice(self):
		u = str(uuid.uuid4())
		a = api.submit_invoice(u, [{"code": "JLG-001", "qty": 1}], [{"mode": "Cash", "amount": 100}])
		b = api.submit_invoice(u, [{"code": "JLG-001", "qty": 1}], [{"mode": "Cash", "amount": 100}])
		self.assertEqual(a["name"], b["name"])
		self.assertEqual(frappe.db.count("Sales Invoice", {"jalgo_pos_uuid": u}), 1)

	def test_browser_price_is_ignored(self):
		price = api.search_items("JLG-035")[0]["rate"]
		r = api.submit_invoice(str(uuid.uuid4()), [{"code": "JLG-035", "qty": 1, "rate": 1}], [{"mode": "UPI", "amount": price}])
		self.assertAlmostEqual(r["items"][0]["rate"], price, places=2)

	def test_limits(self):
		with self.assertRaises(frappe.ValidationError):
			api.submit_invoice(str(uuid.uuid4()), [{"code": "JLG-001", "qty": 1, "disc": 30}], [{"mode": "Cash", "amount": 100}])
		with self.assertRaises(frappe.ValidationError):
			api.submit_invoice(str(uuid.uuid4()), [{"code": "JLG-015", "qty": 1}], [{"mode": "Cash", "amount": 10}])

	def test_guest_blocked(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			api.search_items("atta")


PIN = "2468"


class TestSection2(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		if not api.current_shift():
			api.open_shift(500)

	def test_big_discount_needs_pin(self):
		with self.assertRaises(frappe.PermissionError):
			api.submit_invoice(str(uuid.uuid4()), [{"code": "JLG-035", "qty": 1, "disc": 10}], [{"mode": "Cash", "amount": 500}])
		r = api.submit_invoice(str(uuid.uuid4()), [{"code": "JLG-035", "qty": 1, "disc": 10}], [{"mode": "Cash", "amount": 500}], manager_pin=PIN)
		self.assertEqual(r["items"][0]["disc"], 10)

	def test_offer_applies_at_min_qty(self):
		r2 = api.submit_invoice(str(uuid.uuid4()), [{"code": "JLG-029", "qty": 2}], [{"mode": "Cash", "amount": 1000}])
		r3 = api.submit_invoice(str(uuid.uuid4()), [{"code": "JLG-029", "qty": 3}], [{"mode": "Cash", "amount": 1000}])
		self.assertEqual(r2["items"][0]["disc"], 0)
		self.assertEqual(r3["items"][0]["disc"], 5)
		self.assertTrue(any(o["in_cart"] for o in api.offers(["JLG-029"])))

	def test_hold_recall_and_paid_bill_clears_hold(self):
		h = api.hold_bill([{"code": "JLG-001", "qty": 2}], customer="", total=56)
		rec = api.recall_bill(h)
		self.assertEqual(rec["lines"][0]["qty"], 2)
		api.submit_invoice(str(uuid.uuid4()), rec["lines"], [{"mode": "Cash", "amount": 100}], held_bill=h)
		self.assertFalse(frappe.db.exists("JALGO Held Bill", h))

	def test_estimate_creates_quotation(self):
		e = api.save_estimate([{"code": "JLG-015", "qty": 2}])
		self.assertEqual(frappe.db.get_value("Quotation", e["name"], "docstatus"), 1)

	def test_credit_needs_named_customer_and_stays_outstanding(self):
		with self.assertRaises(frappe.ValidationError):
			api.submit_invoice(str(uuid.uuid4()), [{"code": "JLG-001", "qty": 1}], [{"mode": "Credit", "amount": 0}])
		mob = str(9100000000 + frappe.utils.random_string(4).__hash__() % 89999999)[:10]
		c = api.create_customer("Test Udhaar " + mob[-4:], mob)
		r = api.submit_invoice(str(uuid.uuid4()), [{"code": "JLG-001", "qty": 2}], [{"mode": "Credit", "amount": 0}], customer=c["name"])
		self.assertTrue(r["credit"])
		self.assertGreater(r["outstanding"], 0)

	def test_return_needs_pin_restores_stock_and_limits_qty(self):
		r = api.submit_invoice(str(uuid.uuid4()), [{"code": "JLG-024", "qty": 2}], [{"mode": "Cash", "amount": 500}])
		before = bal("JLG-024")
		with self.assertRaises(frappe.PermissionError):
			api.submit_return(r["name"], [{"code": "JLG-024", "qty": 1}])
		ret = api.submit_return(r["name"], [{"code": "JLG-024", "qty": 1}], manager_pin=PIN, uuid=str(uuid.uuid4()))
		self.assertTrue(ret["is_return"])
		self.assertEqual(bal("JLG-024"), before + 1)
		with self.assertRaises(frappe.ValidationError):
			api.submit_return(r["name"], [{"code": "JLG-024", "qty": 2}], manager_pin=PIN)

	def test_shift_close_counts_cash(self):
		summ = api.shift_summary()
		self.assertIn("expected_cash", summ)
		closed = api.close_shift(summ["expected_cash"])
		self.assertEqual(closed["status"], "Closed")
		self.assertEqual(closed["difference"], 0)
		with self.assertRaises(frappe.ValidationError):
			api.submit_invoice(str(uuid.uuid4()), [{"code": "JLG-001", "qty": 1}], [{"mode": "Cash", "amount": 100}])
		api.open_shift(0)
