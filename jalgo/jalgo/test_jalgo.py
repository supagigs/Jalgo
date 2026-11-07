"""Run: bench --site jalgo.staging run-tests --app jalgo --module jalgo.test_jalgo"""
import unittest

import frappe

from jalgo import logic


class TestJalgoRules(unittest.TestCase):
	def test_min_order_blocks(self):
		with self.assertRaises(frappe.ValidationError):
			logic.compute_fees(199, "Scheduled")

	def test_quick_fees(self):
		self.assertEqual(logic.compute_fees(250, "Quick", 2.5), {"delivery_fee": 50, "handling_fee": 15})

	def test_quick_beyond_3km_refused(self):
		with self.assertRaises(frappe.ValidationError):
			logic.compute_fees(250, "Quick", 3.4)

	def test_scheduled_fees(self):
		self.assertEqual(logic.compute_fees(350, "Scheduled")["delivery_fee"], 15)
		self.assertEqual(logic.compute_fees(400, "Scheduled")["delivery_fee"], 15)
		self.assertEqual(logic.compute_fees(500, "Scheduled")["delivery_fee"], 0)

	def test_scheduled_mid_band_undecided_blocks(self):
		with self.assertRaises(frappe.ValidationError):
			logic.compute_fees(450, "Scheduled")

	def test_rider_payout_bands_no_double_count(self):
		cases = {0.5: 20, 1.5: 23, 2.5: 27, 3.5: 33, 4.5: 38, 1.0: 20, 2.0: 23}
		for km, total in cases.items():
			self.assertEqual(logic.compute_payout(km, "Scheduled")["total_payout"], total, km)

	def test_rider_quick_and_beyond_5(self):
		self.assertEqual(logic.compute_payout(2.5, "Quick")["total_payout"], 32)
		self.assertEqual(logic.compute_payout(6.2, "Scheduled")["total_payout"], 20 + 18 + 14)  # 2 extra km (ceil)

	def test_tip_passes_through(self):
		self.assertEqual(logic.compute_payout(0.5, "Scheduled", tip=20)["total_payout"], 40)

	def test_allocation_single_location_or_none(self):
		code = frappe.db.get_value("Item", {"item_code": ["like", "JLG-0%"]}, "name")
		loc, dist, _ = logic.allocate([{"item_code": code, "qty": 1}], 21.0077, 75.5626, "Quick")
		self.assertEqual(loc, "Mundade Supermarket (Pilot)")
		loc, _, reasons = logic.allocate([{"item_code": code, "qty": 999999}], 21.0077, 75.5626, "Quick")
		self.assertIsNone(loc)  # never splits or substitutes
		loc, _, _ = logic.allocate([{"item_code": code, "qty": 1}], 21.30, 75.90, "Quick")
		self.assertIsNone(loc)  # outside service radius
