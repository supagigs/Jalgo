# JALGO × ERPNext — Staging Demo (v0.1.0, not a release)

Throwaway staging build made in Claude's sandbox on 7 Nov 2026. **Not production-ready.** No production system was touched.

## Repository layout
| Path | Contents |
|---|---|
| `jalgo/` | Frappe custom app (install into a bench next to ERPNext v16) |
| `website/` | JALGO storefront (`index.html`); the same file ships inside the app at `jalgo/jalgo/public/shop/` |
| `razorpay/` | Server-side Razorpay integration draft (not yet wired or tested) |
| `scripts/` | Staging setup scripts used for the demo |
| `docs/` | Ten-section ERPNext delivery plan, sample dashboard output |
| `screenshots/` | Screenshots from the running staging system |

## Environment actually used
| Component | Version |
|---|---|
| ERPNext | **16.53.0** (tag `v16.53.0`, commit 9cd11b1) |
| Frappe | 16.55.2 (`version-16`, commit 3d1284c) |
| Python / Node | 3.14 / 24.22 |
| MariaDB / Redis | 10.11 / local |
| Site | `jalgo.staging`, served on `127.0.0.1:8000` (default site, single-site bench in an isolated sandbox) |
| App | `jalgo` — commit `8ad020d` |

## What the `jalgo` app contains
| DocType | Purpose |
|---|---|
| JALGO Settings (single) | Min order ₹200, Quick ₹50 + ₹15 (≤3 km), Scheduled ₹15 ≤₹400 / free ≥₹500, ₹401–₹499 fee **with an explicit "decided" switch (off = checkout blocked)**, rider payout bands, cost assumptions |
| JALGO Fulfilment Location | Partner store / dark store, each linked to its **own ERPNext Warehouse** (stock never pooled) |
| JALGO Commission Rule | % by ERPNext Item Group (3–7%, pilot proposals) |
| JALGO Rider | Riders, availability |
| JALGO Order (+ items) | Order state machine; bill always recomputed on the server |
| JALGO Delivery Job | Rider assignment and Option B payout (₹20 base + band + ₹5 Quick + tips 100%) |
| JALGO Payout Band (child) | 0–1 ₹0, 1–2 ₹3, 2–3 ₹7, 3–4 ₹13, 4–5 ₹18, +₹7/km after 5 km |

Logic: `jalgo/logic.py` (fees, payouts, single-location allocation, commission, ERPNext posting) · API: `jalgo/api.py` · Data: `jalgo/demo.py` · Economics: `jalgo/reports.py`.

**ERPNext integration:** when an order reaches *Delivered*, the app creates and submits a **Sales Invoice** (update stock from the store's warehouse, with delivery and handling as service lines) and a **Payment Entry**. No ERPNext core files were modified.

**Website:** served at `/assets/jalgo/shop/index.html`. When it can reach the API it switches to live mode (green bar): products and prices come from ERPNext and checkout calls `jalgo.api.place_order`.

## Synthetic data (fake, deterministic seed 42)
1 demo company (JALGO Retail (Demo), INR, FY 2026-27), 50 items (real brand names, **sample prices**), 1 open partner store + 1 closed future dark store, 2 stock receipts, 200 customers (phones 90000xxxxx, group "JALGO Demo"), 12 riders, **860 demo orders over 8 Oct–6 Nov 2026 (820 delivered, 40 cancelled)**, plus 4 test orders placed during testing (JORD-00861 to 00864). That makes 821 submitted Sales Invoices and 821 Payment Entries. Everything is flagged `is_demo` or grouped for removal.

## Tests actually run (staging only)
**Unit tests:** `bench --site jalgo.staging run-tests --app jalgo --module jalgo.test_jalgo` → **9/9 passed** (after one fix, below).

**HTTP checks against 127.0.0.1:8000:**
| Check | Result |
|---|---|
| Catalogue returns 50 items with ERPNext prices and MRP | Pass |
| Quote below ₹200 refused with amount needed | Pass |
| Quick quote 0.38 km → ₹50 + ₹15, allocated to pilot store | Pass |
| Address 32 km away → refused, with per-store reasons | Pass |
| Order placed as guest → JORD-00861 | Pass |
| Tampered `rate: 1` ignored, server price used | Pass |
| Tracking with wrong phone → "Order not found" | Pass |
| Staff `advance` as guest → PermissionError | Pass |
| Dashboard as guest → 403 | Pass |
| Admin advances order to Delivered → submitted, paid Sales Invoice with stock from the store warehouse | Pass |
| Browser: full shop → login (demo OTP) → checkout → order JORD-00864 in ERPNext | Pass |

**Bugs found and fixed during testing:**
1. A blank ₹401–₹499 fee was read as ₹0, which would have meant free delivery. Fixed with an explicit "decided" switch; test added.
2. Outside the artifact preview, hidden popups covered the page. Fixed with a `[hidden]` CSS rule.

**Not tested:** Razorpay (no keys; COD/UPI recorded without a real gateway), background workers and scheduler, multi-store allocation with two open stores, GST/India Compliance (not installed), load, backup restore, upgrade path, Postgres.

## Economics from the synthetic month (illustrative only)
Contribution = commission + delivery + handling − rider payout (excl. tips) − 2% gateway fee on prepaid − ₹6 packaging. It excludes rent, staff, support, refunds, wastage, tech and tax.

| | Quick | Scheduled |
|---|---|---|
| Delivered orders | 119 | 702 |
| Average basket | ₹337 | ₹1,165 ⚠ |
| Contribution per order | **₹41** | **₹5.5** |
| Orders with negative contribution | 0 | **317 (45%)** |

Findings:
- **Free Scheduled delivery at ₹500+ is the weak point.** JALGO earns only the 3–7% commission while still paying ₹20–₹38+ per trip.
- **Orders over 5 km lose money overall** (−₹717 across 123 orders).
- **Riders:** ₹90–₹107 per *active* hour, but 12 riders shared ~27 orders/day, which is only 2–3 deliveries per rider per day. Pilot volume supports far fewer riders. Idle time is not modelled.
- ⚠ The generator's Scheduled baskets are too large (avg ₹1,165). Real AOV will be lower, which makes Scheduled economics **worse**. Calibrate with the store's real bills.

## Re-running it
```
export DB_ROOT_PASSWORD=... ADMIN_PASSWORD=...
sudo -E scripts/install.sh         # system packages, MariaDB (Ubuntu 24.04, run as root)
sudo -u frappe -E scripts/bench.sh # bench, ERPNext v16.53.0, site
sudo -u frappe scripts/app_setup.sh   # expects app sources; or copy ./jalgo into apps/ and `bench --site jalgo.staging install-app jalgo`
bench --site jalgo.staging execute jalgo.demo.load
```
Scripts were run in this sandbox only (with a proxy setup removed from these copies). They are not hardened: no rollback, Ubuntu-only, and they assume a fresh machine. **Never run `jalgo.demo` on a real site.**

## Known limitations
Guest checkout identifies customers by phone only (production needs OTP-verified login). Straight-line distance, not route distance. Rider assignment is round-robin. No stock reservation hold yet (stock is checked at allocation; it is deducted at invoice). Partner settlement and payout statement documents are not built yet. GST via India Compliance is not set up.
