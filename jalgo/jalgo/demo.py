"""Synthetic JALGO data for STAGING ONLY. Deterministic (seed 42). Everything is fake.
Run: bench --site jalgo.staging execute jalgo.demo.setup_company
     bench --site jalgo.staging execute jalgo.demo.load
"""
import random
from datetime import datetime, timedelta, time

import frappe
from frappe.utils import flt

from jalgo import logic

ABBR = "JLG"
COMPANY = "JALGO Retail (Demo)"
JALGAON = (21.0077, 75.5626)

GROUPS = {"dairy": "Dairy & Eggs", "fresh": "Vegetables", "fruits": "Fruits", "staples": "Atta, Rice & Dal",
	"oil": "Oil, Sugar & Spices", "snacks": "Snacks & Biscuits", "drinks": "Beverages", "breakfast": "Breakfast & Bakery",
	"household": "Cleaning", "personal": "Personal Care"}
COMMISSION = {"Dairy & Eggs": 3, "Atta, Rice & Dal": 4, "Oil, Sugar & Spices": 4, "Vegetables": 6, "Fruits": 6,
	"Snacks & Biscuits": 7, "Beverages": 7, "Breakfast & Bakery": 7, "Cleaning": 7, "Personal Care": 7}

# Same catalogue as the website (sample prices, not verified MRPs)
CATALOGUE = [
	("Amul Taaza Toned Milk", "500 ml", 28, None, "dairy"), ("Amul Gold Full Cream Milk", "500 ml", 34, None, "dairy"),
	("Gokul Full Cream Milk", "500 ml", 35, None, "dairy"), ("Amul Masti Dahi", "400 g", 35, None, "dairy"),
	("Amul Malai Paneer", "200 g", 95, None, "dairy"), ("Amul Butter", "100 g", 58, None, "dairy"),
	("Amul Pure Ghee", "500 ml", 330, 350, "dairy"), ("Farm Fresh White Eggs", "6 pcs", 48, 54, "dairy"),
	("Tomato (Local)", "1 kg", 32, 40, "fresh"), ("Onion (Nashik)", "1 kg", 38, None, "fresh"), ("Potato", "1 kg", 30, None, "fresh"),
	("Green Chilli", "100 g", 10, None, "fresh"), ("Jalgaon Banana (Shrimant)", "1 dozen", 48, None, "fruits"),
	("Shimla Apple", "4 pcs", 120, 140, "fruits"), ("Aashirvaad Shudh Chakki Atta", "5 kg", 255, 289, "staples"),
	("Fortune Chakki Fresh Atta", "5 kg", 240, 270, "staples"), ("India Gate Basmati Rice Classic", "1 kg", 185, 210, "staples"),
	("Kolam Rice (Loose)", "5 kg", 340, None, "staples"), ("Tata Sampann Toor Dal", "1 kg", 175, 195, "staples"),
	("Tata Sampann Moong Dal", "1 kg", 160, 180, "staples"), ("Rajdhani Besan", "500 g", 65, None, "staples"),
	("Fortune Soya Health Refined Soyabean Oil", "1 L", 145, 160, "oil"), ("Saffola Gold Oil", "1 L", 195, 225, "oil"),
	("Tata Salt", "1 kg", 28, None, "oil"), ("Madhur Pure Sugar", "1 kg", 55, 60, "oil"),
	("Everest Tikhalal Chilli Powder", "100 g", 48, None, "oil"), ("Everest Turmeric Powder", "100 g", 32, None, "oil"),
	("MDH Garam Masala", "100 g", 85, None, "oil"), ("Parle-G Gold Biscuits", "1 kg", 140, None, "snacks"),
	("Britannia Good Day Cashew", "200 g", 40, None, "snacks"), ("Sunfeast Dark Fantasy Choco Fills", "75 g", 40, None, "snacks"),
	("Lay's India's Magic Masala", "48 g", 20, None, "snacks"), ("Haldiram's Aloo Bhujia", "400 g", 105, 115, "snacks"),
	("Kurkure Masala Munch", "75 g", 20, None, "snacks"), ("Tata Tea Gold", "500 g", 290, 315, "drinks"),
	("Bru Instant Coffee", "100 g", 190, None, "drinks"), ("Real Fruit Power Mixed Fruit Juice", "1 L", 120, 135, "drinks"),
	("Thums Up", "750 ml", 40, None, "drinks"), ("Kellogg's Corn Flakes Original", "475 g", 185, 210, "breakfast"),
	("Saffola Masala Oats Classic", "500 g", 165, 185, "breakfast"), ("Maggi 2-Minute Masala Noodles", "280 g (4 pack)", 56, None, "breakfast"),
	("Britannia 100% Whole Wheat Bread", "400 g", 55, None, "breakfast"),
	("Surf Excel Easy Wash Detergent Powder", "1 kg", 140, 155, "household"), ("Tide Plus Double Power Detergent", "1 kg", 115, None, "household"),
	("Vim Dishwash Liquid Lemon", "500 ml", 115, 125, "household"), ("Harpic Power Plus Toilet Cleaner", "500 ml", 105, None, "household"),
	("Lifebuoy Total 10 Soap", "4 × 100 g", 150, 168, "personal"), ("Dettol Original Soap", "4 × 75 g", 190, 210, "personal"),
	("Colgate Strong Teeth Toothpaste", "200 g", 115, None, "personal"), ("Clinic Plus Strong & Long Shampoo", "340 ml", 210, 240, "personal"),
]
FIRST = "Aarav Aditi Akash Ananya Anil Anjali Arjun Bhavna Chetan Deepa Gaurav Harsh Isha Jayesh Kavita Kiran Manish Meera Mohan Neha Nikhil Pooja Pranav Priya Rahul Rekha Rohan Sachin Sakshi Sanjay Shreya Sneha Sunil Swati Tejas Uday Vaishali Vijay Yash Yogita".split()
LAST = "Patil Chaudhari Mahajan Joshi Kulkarni Deshmukh Pawar Shinde Wagh Bhangale Mundade Sonawane Jain Agrawal Kale More".split()


def setup_company():
	"""Completes the ERPNext setup wizard for the demo company (staging only)."""
	if frappe.db.exists("Company", COMPANY):
		print("company exists"); return
	from frappe.desk.page.setup_wizard.setup_wizard import setup_complete
	setup_complete({"language": "English", "country": "India", "timezone": "Asia/Kolkata", "currency": "INR",
		"full_name": "JALGO Admin", "email": "admin@jalgo.example", "password": "admin",
		"company_name": COMPANY, "company_abbr": ABBR, "chart_of_accounts": "Standard",
		"fy_start_date": "2026-04-01", "fy_end_date": "2027-03-31", "setup_demo": 0})
	frappe.db.commit()
	print("company created")


def _ensure(doctype, name, values):
	if not frappe.db.exists(doctype, name):
		frappe.get_doc({"doctype": doctype, **values}).insert(ignore_permissions=True)


def masters():
	for g in GROUPS.values():
		_ensure("Item Group", g, {"item_group_name": g, "parent_item_group": "All Item Groups"})
	_ensure("Item Group", "JALGO Services", {"item_group_name": "JALGO Services", "parent_item_group": "All Item Groups"})
	_ensure("Customer Group", "JALGO Demo", {"customer_group_name": "JALGO Demo", "parent_customer_group": "All Customer Groups"})
	_ensure("Price List", "JALGO MRP", {"price_list_name": "JALGO MRP", "selling": 1, "currency": "INR"})
	for code, name in (("JLG-DELIVERY", "Delivery Fee"), ("JLG-HANDLING", "Handling Fee")):
		_ensure("Item", code, {"item_code": code, "item_name": name, "item_group": "JALGO Services", "stock_uom": "Nos",
			"is_stock_item": 0, "is_sales_item": 1})
	for i, (name, pack, price, mrp, cat) in enumerate(CATALOGUE, 1):
		code = f"JLG-{i:03d}"
		_ensure("Item", code, {"item_code": code, "item_name": name, "description": pack, "item_group": GROUPS[cat],
			"stock_uom": "Nos", "is_stock_item": 1, "is_sales_item": 1, "valuation_rate": round(price * 0.82, 2)})
		if not frappe.db.exists("Item Price", {"item_code": code, "price_list": "Standard Selling"}):
			frappe.get_doc({"doctype": "Item Price", "item_code": code, "price_list": "Standard Selling", "price_list_rate": price}).insert()
		if mrp and not frappe.db.exists("Item Price", {"item_code": code, "price_list": "JALGO MRP"}):
			frappe.get_doc({"doctype": "Item Price", "item_code": code, "price_list": "JALGO MRP", "price_list_rate": mrp}).insert()
	for g, pct in COMMISSION.items():
		_ensure("JALGO Commission Rule", g, {"item_group": g, "commission_percent": pct, "notes": "Pilot proposal, not a benchmark"})
	parent = f"All Warehouses - {ABBR}"
	for wh in ("Mundade Supermarket", "JALGO Dark Store Ring Road"):
		_ensure("Warehouse", f"{wh} - {ABBR}", {"warehouse_name": wh, "company": COMPANY, "parent_warehouse": parent})
	_ensure("Supplier", "Mundade Supermarket", {"supplier_name": "Mundade Supermarket", "supplier_group": "All Supplier Groups"})
	_ensure("JALGO Fulfilment Location", "Mundade Supermarket (Pilot)", {"location_name": "Mundade Supermarket (Pilot)",
		"location_type": "Partner Store", "warehouse": f"Mundade Supermarket - {ABBR}", "supplier": "Mundade Supermarket",
		"is_open": 1, "latitude": 21.0101, "longitude": 75.5652, "picking_capacity_per_hour": 20, "service_radius_km": 6})
	_ensure("JALGO Fulfilment Location", "JALGO Dark Store Ring Road (Future)", {"location_name": "JALGO Dark Store Ring Road (Future)",
		"location_type": "Dark Store", "warehouse": f"JALGO Dark Store Ring Road - {ABBR}", "is_open": 0,
		"latitude": 21.0205, "longitude": 75.5498, "picking_capacity_per_hour": 40, "service_radius_km": 4})
	s = frappe.get_doc("JALGO Settings")
	s.company, s.selling_price_list = COMPANY, "Standard Selling"
	s.delivery_item, s.handling_item = "JLG-DELIVERY", "JLG-HANDLING"
	s.min_order_value, s.quick_delivery_fee, s.quick_handling_fee, s.quick_max_km = 200, 50, 15, 3
	s.scheduled_fee_upto_400, s.scheduled_free_from, s.scheduled_mid_fee = 15, 500, None
	s.rider_base_payout, s.rider_quick_incentive, s.rider_per_km_beyond_5 = 20, 5, 7
	s.gateway_fee_percent, s.packaging_cost_per_order = 2, 6
	s.set("payout_bands", [])
	for a, b, inc in ((0, 1, 0), (1, 2, 3), (2, 3, 7), (3, 4, 13), (4, 5, 18)):
		s.append("payout_bands", {"from_km": a, "to_km": b, "incentive": inc})
	s.save()
	frappe.db.commit()
	print("masters ok")


def stock(posting_date, qty):
	se = frappe.new_doc("Stock Entry")
	se.update({"stock_entry_type": "Material Receipt", "company": COMPANY, "set_posting_time": 1, "posting_date": posting_date,
		"posting_time": "06:00:00", "to_warehouse": f"Mundade Supermarket - {ABBR}", "remarks": "JALGO demo stock"})
	for i, (name, pack, price, mrp, cat) in enumerate(CATALOGUE, 1):
		se.append("items", {"item_code": f"JLG-{i:03d}", "qty": qty, "basic_rate": round(price * 0.82, 2),
			"t_warehouse": f"Mundade Supermarket - {ABBR}"})
	se.insert(); se.submit()


def load(days=30, end="2026-11-06"):
	rnd = random.Random(42)
	frappe.flags.mute_emails = True
	masters()
	if frappe.db.count("JALGO Order", {"is_demo": 1}):
		print("demo orders already loaded"); return
	end_d = datetime.strptime(end, "%Y-%m-%d").date()
	start_d = end_d - timedelta(days=days - 1)
	stock(start_d - timedelta(days=1), 700)
	stock(start_d + timedelta(days=14), 500)
	# riders
	riders = []
	for i in range(12):
		n = f"{rnd.choice(FIRST)} {rnd.choice(LAST)} (R{i+1:02d})"
		_ensure("JALGO Rider", n, {"rider_name": n, "phone": f"70000{i:05d}", "status": "Active", "is_available": 1, "is_demo": 1})
		riders.append(n)
	# customers (fake numbers in the 90000xxxxx range)
	customers = []
	for i in range(200):
		nm = f"{rnd.choice(FIRST)} {rnd.choice(LAST)}"
		ph = f"90000{i:05d}"
		c = frappe.db.get_value("Customer", {"mobile_no": ph}, "name")
		if not c:
			doc = frappe.get_doc({"doctype": "Customer", "customer_name": nm, "customer_type": "Individual",
				"customer_group": "JALGO Demo", "territory": "India", "mobile_no": ph})
			doc.insert(ignore_permissions=True); c = doc.name
		lat = JALGAON[0] + rnd.uniform(-0.045, 0.045); lng = JALGAON[1] + rnd.uniform(-0.045, 0.045)
		customers.append((c, ph, lat, lng))
	frappe.db.commit()
	codes = [f"JLG-{i:03d}" for i in range(1, len(CATALOGUE) + 1)]
	staples = [c for c, row in zip(codes, CATALOGUE) if row[4] in ("staples", "oil", "household", "personal")]
	daily = [f"JLG-{i:03d}" for i in (1, 2, 4, 9, 10, 11, 13, 32, 42)]
	total = 0
	for d in range(days):
		day = start_d + timedelta(days=d)
		n = int(10 + d * 1.4 + rnd.randint(-3, 3))
		for _ in range(max(n, 5)):
			cust, ph, lat, lng = rnd.choice(customers)
			dist = logic.km_between(lat, lng, 21.0101, 75.5652)
			if dist > 6:
				continue
			mode = "Quick" if dist <= 3 and rnd.random() < 0.45 else "Scheduled"
			if mode == "Quick":
				basket = rnd.sample(daily, rnd.randint(2, 5)) + rnd.sample(codes, rnd.randint(0, 2))
			else:
				basket = rnd.sample(staples, rnd.randint(2, 5)) + rnd.sample(codes, rnd.randint(2, 6))
			items = {}
			for code in basket:
				items[code] = items.get(code, 0) + rnd.choice((1, 1, 1, 2))
			sub = sum(logic.item_price(c) * q for c, q in items.items())
			while sub < 200 or (mode == "Scheduled" and 400 < sub < 500):  # undecided ₹401–499 band: customer tops up
				c = rnd.choice(codes); items[c] = items.get(c, 0) + 1; sub += logic.item_price(c)
			hour = rnd.choice((8, 9, 10, 12, 13, 17, 18, 19, 20, 21)) if mode == "Quick" else rnd.choice((7, 8, 13, 14, 17, 18))
			odt = datetime.combine(day, time(hour, rnd.randint(0, 59)))
			slot = None if mode == "Quick" else ("Morning" if hour < 12 else "Afternoon" if hour < 16 else "Evening")
			cancelled = rnd.random() < 0.04
			tip = rnd.choice((10, 20)) if rnd.random() < 0.15 else 0
			pm = rnd.choices(("UPI", "Card", "Cash on Delivery"), (55, 10, 35))[0]
			order = frappe.get_doc({"doctype": "JALGO Order", "customer": cust, "customer_phone": ph, "order_datetime": odt,
				"delivery_mode": mode, "slot": slot, "status": "Cancelled" if cancelled else "Out for Delivery",
				"fulfilment_location": "Mundade Supermarket (Pilot)", "distance_km": round(dist, 2), "latitude": lat, "longitude": lng,
				"delivery_address": f"Demo address, Jalgaon", "payment_method": pm,
				"payment_status": "Unpaid" if pm == "Cash on Delivery" else "Paid", "tip": tip, "is_demo": 1,
				"cancel_reason": "Customer cancelled before pickup" if cancelled else None,
				"items": [{"item_code": c, "qty": q} for c, q in items.items()]})
			order.insert(ignore_permissions=True)
			if cancelled:
				continue
			pay = logic.compute_payout(dist, mode, tip)
			mins = rnd.randint(22, 40) if mode == "Quick" else rnd.randint(14, 28)  # scheduled orders are batched
			job = frappe.get_doc({"doctype": "JALGO Delivery Job", "jalgo_order": order.name, "rider": rnd.choice(riders),
				"delivery_mode": mode, "distance_km": round(dist, 2), "status": "Delivered", "assigned_at": odt,
				"delivered_at": odt + timedelta(minutes=mins), "active_minutes": mins, "is_demo": 1, **pay})
			job.insert(ignore_permissions=True)
			order.db_set("delivery_job", job.name, update_modified=False)
			order.status = "Delivered"
			order.save(ignore_permissions=True)  # posts Sales Invoice (+ Payment Entry) in ERPNext
			total += 1
		frappe.db.commit()
		print(day, "orders so far", total)
	print("DONE", total)


def remove():
	"""Deletes demo orders and jobs (invoices must be cancelled first in ERPNext). Staging only."""
	for dt in ("JALGO Delivery Job", "JALGO Order"):
		for n in frappe.get_all(dt, {"is_demo": 1}, pluck="name"):
			frappe.delete_doc(dt, n, force=1, ignore_permissions=True)
	frappe.db.commit()
