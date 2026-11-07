"""Creates JALGO DocTypes through the framework (developer_mode writes their JSON into the app).
Run: bench --site jalgo.staging execute jalgo.doctype_defs.run
"""
import frappe

MODULE = "Jalgo"


def F(fieldname, fieldtype, label=None, **kw):
	d = {"fieldname": fieldname, "fieldtype": fieldtype, "label": label or fieldname.replace("_", " ").title()}
	d.update(kw)
	return d


ROLES = ["System Manager", "JALGO Ops", "JALGO Store", "JALGO Finance"]


def perms(write_roles=("System Manager", "JALGO Ops"), read_roles=("JALGO Store", "JALGO Finance")):
	p = [{"role": r, "read": 1, "write": 1, "create": 1, "delete": 1 if r == "System Manager" else 0, "report": 1, "export": 1} for r in write_roles]
	p += [{"role": r, "read": 1, "report": 1} for r in read_roles]
	return p


DOCTYPES = [
	# ---- child tables ----
	dict(name="JALGO Payout Band", istable=1, fields=[
		F("from_km", "Float", in_list_view=1, reqd=1), F("to_km", "Float", in_list_view=1, reqd=1),
		F("incentive", "Currency", in_list_view=1, reqd=1)]),
	dict(name="JALGO Order Item", istable=1, fields=[
		F("item_code", "Link", options="Item", in_list_view=1, reqd=1), F("item_name", "Data", in_list_view=1),
		F("item_group", "Link", options="Item Group"), F("qty", "Float", in_list_view=1, reqd=1, default="1"),
		F("rate", "Currency", in_list_view=1), F("amount", "Currency", in_list_view=1, read_only=1),
		F("commission_percent", "Percent", read_only=1), F("commission_amount", "Currency", read_only=1)]),
	# ---- settings (single) ----
	dict(name="JALGO Settings", issingle=1, fields=[
		F("company", "Link", options="Company"), F("selling_price_list", "Link", options="Price List"),
		F("delivery_item", "Link", "Delivery Fee Item", options="Item"), F("handling_item", "Link", "Handling Fee Item", options="Item"),
		F("sec_c", "Section Break", "Customer Pricing (pilot values, configurable)"),
		F("min_order_value", "Currency", default="200"), F("quick_delivery_fee", "Currency", default="50"),
		F("quick_handling_fee", "Currency", default="15"), F("quick_max_km", "Float", "Quick Max Distance (km)", default="3"),
		F("col1", "Column Break"),
		F("scheduled_fee_upto_400", "Currency", "Scheduled Fee (orders up to ₹400)", default="15"),
		F("scheduled_free_from", "Currency", "Scheduled Free Delivery From", default="500"),
		F("scheduled_mid_fee", "Currency", "Scheduled Fee ₹401–₹499 (blank = undecided, checkout blocked)"),
		F("sec_r", "Section Break", "Rider Payouts (Option B)"),
		F("rider_base_payout", "Currency", default="20"), F("rider_quick_incentive", "Currency", default="5"),
		F("rider_per_km_beyond_5", "Currency", "Per km beyond 5 km", default="7"),
		F("payout_bands", "Table", options="JALGO Payout Band"),
		F("sec_cost", "Section Break", "Cost Assumptions for Contribution (demo estimates)"),
		F("gateway_fee_percent", "Percent", "Payment Gateway Fee %", default="2"),
		F("packaging_cost_per_order", "Currency", default="6"),
	], perms=[{"role": "System Manager", "read": 1, "write": 1}, {"role": "JALGO Ops", "read": 1, "write": 1}, {"role": "JALGO Finance", "read": 1}]),
	# ---- masters ----
	dict(name="JALGO Fulfilment Location", autoname="field:location_name", fields=[
		F("location_name", "Data", reqd=1, unique=1, in_list_view=1),
		F("location_type", "Select", options="Partner Store\nDark Store", reqd=1, in_list_view=1, default="Partner Store"),
		F("warehouse", "Link", options="Warehouse", reqd=1), F("supplier", "Link", "Partner (Supplier)", options="Supplier"),
		F("is_open", "Check", in_list_view=1, default="1"),
		F("latitude", "Float", precision="6"), F("longitude", "Float", precision="6"),
		F("picking_capacity_per_hour", "Int", default="20"), F("service_radius_km", "Float", default="6")]),
	dict(name="JALGO Commission Rule", autoname="field:item_group", fields=[
		F("item_group", "Link", options="Item Group", reqd=1, unique=1, in_list_view=1),
		F("commission_percent", "Percent", reqd=1, in_list_view=1), F("notes", "Small Text")]),
	dict(name="JALGO Rider", autoname="field:rider_name", fields=[
		F("rider_name", "Data", reqd=1, unique=1, in_list_view=1), F("phone", "Data", options="Phone", in_list_view=1),
		F("status", "Select", options="Active\nInactive", default="Active", in_list_view=1),
		F("is_available", "Check", default="1"), F("vehicle", "Select", options="Bike\nScooter\nCycle", default="Bike"),
		F("is_demo", "Check", read_only=1)]),
	# ---- transactions ----
	dict(name="JALGO Order", autoname="JORD-.#####", track_changes=1, fields=[
		F("customer", "Link", options="Customer", reqd=1, in_list_view=1), F("customer_phone", "Data"),
		F("order_datetime", "Datetime", reqd=1, default="now"),
		F("delivery_mode", "Select", options="Quick\nScheduled", reqd=1, in_list_view=1, in_standard_filter=1),
		F("slot", "Select", options="\nMorning\nAfternoon\nEvening"),
		F("status", "Select", options="Pending Payment\nConfirmed\nAllocated\nPicking\nOut for Delivery\nDelivered\nCancelled\nRefunded",
			default="Confirmed", in_list_view=1, in_standard_filter=1),
		F("col_a", "Column Break"),
		F("fulfilment_location", "Link", options="JALGO Fulfilment Location", in_standard_filter=1),
		F("distance_km", "Float", precision="2"), F("delivery_address", "Small Text"),
		F("latitude", "Float", precision="6"), F("longitude", "Float", precision="6"),
		F("sec_items", "Section Break", "Items"), F("items", "Table", options="JALGO Order Item", reqd=1),
		F("sec_bill", "Section Break", "Bill (computed on the server)"),
		F("subtotal", "Currency", read_only=1), F("delivery_fee", "Currency", read_only=1), F("handling_fee", "Currency", read_only=1),
		F("discount", "Currency", default="0"), F("tip", "Currency", default="0"), F("grand_total", "Currency", read_only=1, in_list_view=1),
		F("col_b", "Column Break"),
		F("payment_method", "Select", options="UPI\nCard\nCash on Delivery", default="UPI"),
		F("payment_status", "Select", options="Unpaid\nPaid\nRefunded", default="Unpaid"),
		F("commission_amount", "Currency", "JALGO Commission", read_only=1),
		F("sales_invoice", "Link", options="Sales Invoice", read_only=1), F("delivery_job", "Link", options="JALGO Delivery Job", read_only=1),
		F("cancel_reason", "Small Text"), F("is_demo", "Check", read_only=1)]),
	dict(name="JALGO Delivery Job", autoname="DJOB-.#####", fields=[
		F("jalgo_order", "Link", "Order", options="JALGO Order", reqd=1, in_list_view=1),
		F("rider", "Link", options="JALGO Rider", in_list_view=1, in_standard_filter=1),
		F("delivery_mode", "Data", read_only=1), F("distance_km", "Float", precision="2"),
		F("status", "Select", options="Assigned\nPicked Up\nDelivered\nCancelled", default="Assigned", in_list_view=1),
		F("assigned_at", "Datetime"), F("delivered_at", "Datetime"), F("active_minutes", "Int"),
		F("sec_p", "Section Break", "Payout"),
		F("base_payout", "Currency", read_only=1), F("distance_incentive", "Currency", read_only=1),
		F("quick_incentive", "Currency", read_only=1), F("tip", "Currency", read_only=1),
		F("total_payout", "Currency", read_only=1, in_list_view=1), F("is_demo", "Check", read_only=1)]),
]


def ensure_roles():
	for r in ROLES[1:]:
		if not frappe.db.exists("Role", r):
			frappe.get_doc({"doctype": "Role", "role_name": r, "desk_access": 1}).insert(ignore_permissions=True)


def run():
	ensure_roles()
	if not frappe.db.exists("Module Def", MODULE):
		frappe.get_doc({"doctype": "Module Def", "module_name": MODULE, "app_name": "jalgo"}).insert()
	for spec in DOCTYPES:
		spec = dict(spec)
		name = spec.pop("name")
		p = spec.pop("perms", None)
		if frappe.db.exists("DocType", name):
			print("exists", name)
			continue
		deferred = None
		if name == "JALGO Order":
			deferred = next(f for f in spec["fields"] if f["fieldname"] == "delivery_job")
			spec["fields"] = [f for f in spec["fields"] if f["fieldname"] != "delivery_job"]
		doc = frappe.get_doc({"doctype": "DocType", "name": name, "module": MODULE, "custom": 0, **spec,
			"permissions": [] if spec.get("istable") else (p or perms())})
		doc.insert()
		print("created", name)
	order = frappe.get_doc("DocType", "JALGO Order")
	if not any(f.fieldname == "delivery_job" for f in order.fields):
		order.append("fields", {"fieldname": "delivery_job", "fieldtype": "Link", "label": "Delivery Job",
			"options": "JALGO Delivery Job", "read_only": 1, "insert_after": "sales_invoice"})
		order.save()
		print("linked JALGO Order -> JALGO Delivery Job")
	frappe.db.commit()
