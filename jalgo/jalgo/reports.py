"""Per-order economics. Revenue is not profit: contribution subtracts rider payouts, gateway fees and packaging."""
import frappe
from frappe.utils import flt


def summary():
	s = frappe.get_cached_doc("JALGO Settings")
	gw = flt(s.gateway_fee_percent) / 100
	pack = flt(s.packaging_cost_per_order)
	rows = frappe.db.sql("""
		select o.name, date(o.order_datetime) d, o.delivery_mode mode, o.subtotal, o.delivery_fee, o.handling_fee,
			o.tip, o.grand_total, o.commission_amount, o.payment_method, o.distance_km,
			j.total_payout, j.tip job_tip, j.active_minutes, j.rider
		from `tabJALGO Order` o left join `tabJALGO Delivery Job` j on j.name = o.delivery_job
		where o.status = 'Delivered'""", as_dict=True)
	cancelled = frappe.db.count("JALGO Order", {"status": "Cancelled"})
	out = {"orders": len(rows), "cancelled": cancelled, "by_mode": {}, "by_day": {}, "riders": {}, "distance_bands": {}}
	for r in rows:
		gateway = flt(r.grand_total) * gw if r.payment_method != "Cash on Delivery" else 0
		rider_cost = flt(r.total_payout) - flt(r.job_tip)  # tips pass through 100% to riders
		revenue = flt(r.commission_amount) + flt(r.delivery_fee) + flt(r.handling_fee)
		contrib = revenue - rider_cost - gateway - pack
		m = out["by_mode"].setdefault(r.mode, {"orders": 0, "gmv": 0, "commission": 0, "fees": 0, "rider_cost": 0,
			"gateway": 0, "packaging": 0, "contribution": 0, "negative_orders": 0})
		m["orders"] += 1; m["gmv"] += flt(r.subtotal); m["commission"] += flt(r.commission_amount)
		m["fees"] += flt(r.delivery_fee) + flt(r.handling_fee); m["rider_cost"] += rider_cost
		m["gateway"] += gateway; m["packaging"] += pack; m["contribution"] += contrib
		m["negative_orders"] += 1 if contrib < 0 else 0
		day = out["by_day"].setdefault(str(r.d), {"orders": 0, "gmv": 0, "contribution": 0})
		day["orders"] += 1; day["gmv"] += flt(r.subtotal); day["contribution"] += contrib
		band = f"{min(int(flt(r.distance_km)), 5)}-{min(int(flt(r.distance_km)), 5) + 1} km" if flt(r.distance_km) < 5 else "5+ km"
		b = out["distance_bands"].setdefault(band, {"orders": 0, "contribution": 0})
		b["orders"] += 1; b["contribution"] += contrib
		if r.rider:
			rd = out["riders"].setdefault(r.rider, {"deliveries": 0, "earnings": 0, "minutes": 0})
			rd["deliveries"] += 1; rd["earnings"] += flt(r.total_payout); rd["minutes"] += flt(r.active_minutes)
	for m in out["by_mode"].values():
		n = m["orders"] or 1
		m["aov"] = m["gmv"] / n; m["contribution_per_order"] = m["contribution"] / n
	for rd in out["riders"].values():
		rd["per_active_hour"] = rd["earnings"] / (rd["minutes"] / 60) if rd["minutes"] else 0
	out["invoices"] = frappe.db.count("Sales Invoice", {"docstatus": 1, "remarks": ["like", "JALGO order%"]})
	out["payments"] = frappe.db.count("Payment Entry", {"docstatus": 1, "reference_no": ["like", "JORD-%"]})
	out["assumptions"] = {"gateway_fee_percent": s.gateway_fee_percent, "packaging_cost_per_order": pack,
		"note": "Excludes rent, staff, support, refunds, wastage, tech and taxes. Rider active minutes are synthetic."}
	return out
