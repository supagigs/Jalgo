"""Razorpay UPI QR for the counter.

Turned on only when the site config has razorpay_key_id, razorpay_key_secret and razorpay_webhook_secret
(bench --site <site> set-config razorpay_key_id rzp_live_xxx ...). Keys never go to the browser.
Flow: POS asks for a single-use QR for the exact amount -> customer pays -> Razorpay calls our webhook
(signature checked) -> POS sees 'paid' and saves the bill with the Razorpay payment id."""
import hashlib
import hmac
import json
import time

import frappe
import requests
from frappe import _
from frappe.utils import flt, cint

from jalgo_pos.api import _require_cashier

API = "https://api.razorpay.com/v1"
TTL = 60 * 60


def conf():
	c = frappe.conf
	return {"key": c.get("razorpay_key_id"), "secret": c.get("razorpay_key_secret"), "hook": c.get("razorpay_webhook_secret")}


def enabled():
	c = conf()
	return bool(c["key"] and c["secret"] and c["hook"])


def _key(qr_id):
	return f"jalgo_pos:qr:{qr_id}"


@frappe.whitelist()
def razorpay_status():
	_require_cashier()
	return {"enabled": enabled()}


@frappe.whitelist(methods=["POST"])
def create_upi_qr(amount, bill_uuid):
	_require_cashier()
	if not enabled():
		frappe.throw(_("Razorpay is not set up on this server. Confirm UPI payments manually."))
	paise = int(round(flt(amount) * 100))
	if paise <= 0:
		frappe.throw(_("Amount must be more than 0."))
	c = conf()
	r = requests.post(f"{API}/payments/qr_codes", auth=(c["key"], c["secret"]), timeout=15, json={
		"type": "upi_qr", "name": "Shubhendra Provision", "usage": "single_use", "fixed_amount": True,
		"payment_amount": paise, "description": f"POS bill {bill_uuid[:8]}", "close_by": int(time.time()) + 15 * 60,
		"notes": {"bill_uuid": bill_uuid, "cashier": frappe.session.user}})
	if r.status_code >= 300:
		frappe.log_error(f"Razorpay QR {r.status_code}: {r.text[:500]}", "JALGO POS Razorpay")
		frappe.throw(_("Razorpay did not create the QR ({0}). Try again or take cash.").format(r.status_code))
	qr = r.json()
	frappe.cache.set_value(_key(qr["id"]), {"status": "waiting", "amount": paise, "bill_uuid": bill_uuid}, expires_in_sec=TTL)
	return {"id": qr["id"], "image_url": qr.get("image_url"), "amount": paise / 100}


@frappe.whitelist()
def qr_status(qr_id):
	_require_cashier()
	return frappe.cache.get_value(_key(qr_id)) or {"status": "unknown"}


def verify_signature(body: bytes, signature: str, secret: str) -> bool:
	expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
	return bool(signature) and hmac.compare_digest(expected, signature)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def razorpay_webhook():
	"""Point the Razorpay dashboard webhook (event qr_code.credited) at /api/method/jalgo_pos.payments.razorpay_webhook."""
	body = frappe.request.get_data() or b""
	if not enabled() or not verify_signature(body, frappe.get_request_header("X-Razorpay-Signature") or "", conf()["hook"]):
		frappe.local.response.http_status_code = 401
		return "invalid signature"
	return handle_event(json.loads(body))


def handle_event(event):
	if event.get("event") != "qr_code.credited":
		return "ignored"
	qr = event["payload"]["qr_code"]["entity"]
	pay = event["payload"]["payment"]["entity"]
	state = frappe.cache.get_value(_key(qr["id"])) or {"amount": qr.get("payment_amount"), "bill_uuid": (qr.get("notes") or {}).get("bill_uuid")}
	state.update({"status": "paid" if pay.get("status") == "captured" else pay.get("status"), "payment_id": pay["id"], "paid": cint(pay.get("amount"))})
	frappe.cache.set_value(_key(qr["id"]), state, expires_in_sec=TTL)
	return "ok"


def check_upi_payment(payments, due):
	"""Called from submit_invoice when Razorpay is on: every UPI line must carry a paid QR covering its amount."""
	if not enabled():
		return
	for p in payments:
		if p.get("mode") != "UPI" or flt(p.get("amount")) <= 0:
			continue
		st = frappe.cache.get_value(_key(p.get("qr_id") or "")) or {}
		if st.get("status") != "paid" or cint(st.get("paid")) < int(round(flt(p["amount"]) * 100)):
			frappe.throw(_("The UPI payment has not been received yet."), title=_("Waiting for UPI"))
		p["reference"] = st.get("payment_id")
