import frappe
from frappe.tests import IntegrationTestCase

from jalgo_pos import backoffice as bo


class TestBackoffice(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def test_every_module_lists(self):
		for m in bo.MODULES:
			r = bo.module_list(m)
			self.assertEqual(len(r["rows"][0]) if r["rows"] else len(r["keys"]), len(r["keys"]), m)
		items = bo.module_list("Items", "atta")
		self.assertTrue(any("Atta" in str(row) for row in items["rows"]))
		self.assertIn("Shop stock", items["labels"])

	def test_every_report_runs(self):
		failed = {}
		for group, items in bo.report_catalog().items():
			for r in items:
				if not r["allowed"]:
					continue
				try:
					out = bo.run_report(r["name"])
					self.assertIsInstance(out["rows"], list)
				except Exception as e:
					failed[r["name"]] = str(e)[:120]
		self.assertEqual(failed, {})

	def test_dashboard_and_button_order(self):
		d = bo.dashboard()
		self.assertIn("sales", d)
		bo.save_button_order(["Reports", "Items"])
		self.assertEqual(bo.get_button_order(), ["Reports", "Items"])
		with self.assertRaises(frappe.ValidationError):
			bo.save_button_order("not a list")

	def test_guest_blocked(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			bo.module_list("Items")
