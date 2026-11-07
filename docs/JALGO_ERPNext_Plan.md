# JALGO × ERPNext — Ten-Section Delivery Plan

**Status:** Draft for approval · **Stage:** Plan (no code, schema or data created yet)
**Date:** 7 November 2026 · **Source:** JALGO project brief + website prototype (v11)

---

## 0. Summary

JALGO is a hyperlocal grocery platform for Jalgaon with Quick (10–30 min where feasible) and Scheduled delivery, fulfilled first by one partner supermarket and later by more partners and JALGO dark stores.

**Core architecture decision (from the project brief):** ERPNext is the *back-office ERP* (accounting, procurement, suppliers, stock valuation, GST records). It is **not** the real-time consumer engine. JALGO's order, allocation, pricing, rider and payout logic lives in **custom Frappe apps** on the same bench, using ERPNext through supported APIs and hooks. No ERPNext core files are modified.

### Proposed custom apps

| App | Purpose | Depends on |
|---|---|---|
| `jalgo_core` | Shared config (fees, commissions, rider payout rules, service zones, slots), fulfilment locations, audit log, settings | frappe |
| `jalgo_commerce` | Customer, catalogue mapping, cart pricing, orders, order state machine, allocation engine, stock reservation, refunds/cancellations, website API | jalgo_core, erpnext |
| `jalgo_logistics` | Riders, availability, assignment, delivery OTP/proof, tracking pings, payout calculation and statements | jalgo_core, jalgo_commerce |
| `jalgo_partner` | Partner stores, KYC, commission rules, settlements (T+1/T+2), partner dashboard | jalgo_core, jalgo_commerce, erpnext |
| `jalgo_payments` | Razorpay orders, signature verification, webhooks, idempotency keys, reconciliation | jalgo_core, jalgo_commerce |
| `jalgo_demo` | Synthetic data generator + fixtures (never installed on production) | all above |

*Alternative considered:* one `jalgo` monolith app with modules. Simpler to ship; harder to keep the demo/data app off production and to grant teams separate ownership. **Recommendation:** start as **one app (`jalgo`) with the modules above + a separate `jalgo_demo` app**. This is the "modular monolith" the brief asks for. Decision needed (Q3).

### Data ownership (source of truth)

| Data | Owner | ERPNext link |
|---|---|---|
| Item master, UOM, HSN, GST templates | ERPNext `Item`, `Item Tax Template` | — |
| Per-location stock ledger | ERPNext `Warehouse` per fulfilment location + `Stock Ledger Entry` | one warehouse per store/dark store |
| Live sellable quantity + reservations | `jalgo` `Stock Reservation` (fast) reconciled to ERPNext Bin | never pooled across locations |
| Customer | ERPNext `Customer` + `Contact`/`Address` | created on first order |
| Customer order (cart → delivered) | `jalgo` `JALGO Order` (state machine) | on delivery → ERPNext `Sales Invoice` (+ `Payment Entry`) |
| Fees (delivery, handling) | `jalgo` `Fee Rule` with history | invoice lines/charges |
| Partner commission & settlement | `jalgo` `Commission Rule`, `Partner Settlement` | `Journal Entry` / `Purchase Invoice` |
| Rider payouts | `jalgo` `Rider Payout Rule`, `Delivery Job`, `Payout Statement` | `Journal Entry` (or Expense Claim) |
| Payments | `jalgo` `Payment Attempt` | ERPNext `Payment Entry` after verification |

> **Partner-store inventory caveat:** partners own their stock. Mirroring their stock into ERPNext warehouses works for the pilot (father's store), but large partners may not want ERPNext as their stock system. Decision needed (Q8).

---

## Section 1 — Discovery & technical audit

**Goals:** confirm the real environment before any build.
- Verify the exact Frappe/ERPNext version requested (**"16.53.0" must be checked** — use the actual tagged release available on the chosen branch; do not assume the number exists).
- Bench path, Python/Node/MariaDB/Redis versions, existing apps and customisations, sites, backups.
- Create an **isolated staging site** on its own port; confirm routing is not production.
- Inventory the father's store data: item list, barcodes, GST setup, billing system export format.

**Deliverables:** environment report, staging site, backup procedure, data-export samples.
**Done when:** staging site reachable on a documented port, backup + restore tested once, versions recorded.
**Risks:** the store's existing billing software may not export cleanly; version mismatch.

## Section 2 — Architecture & data model

**Goals:** DocTypes, links, state machines, API contract.
Key DocTypes: `Fulfilment Location`, `Service Zone` (polygon/radius), `Delivery Slot`, `Fee Rule` (+ versioned history), `Commission Rule`, `Rider`, `Rider Payout Rule`, `JALGO Order`, `JALGO Order Item`, `Stock Reservation`, `Allocation Log`, `Delivery Job`, `Delivery Ping`, `Payment Attempt`, `Partner Settlement`, `Payout Statement`, `Audit Event`.
- Order states: `Draft → Pending Payment → Paid/COD Confirmed → Allocated → Picking → Packed → Out for Delivery → Delivered`; branches `Cancelled`, `Refund Pending`, `Refunded`, `Failed`.
- REST API v1 (`/api/method/jalgo.api.v1.*`), versioned, used by the website.
**Done when:** ERD + state diagrams + API spec approved; no code yet beyond scaffolding.

## Section 3 — Design system & application shell

- Website already prototyped (navy/blue/coral, R1 mark). Convert to a production frontend (Frappe-served Vue 3 + frappe-ui, or a separate Next.js/Vue app calling the API — Q10).
- Desk workspaces for Operations, Store, Rider Ops, Finance, with consistent JALGO branding.
**Done when:** shell, login, navigation, light/dark tokens, empty/error/loading states built on staging.

## Section 4 — Core commerce (catalogue, cart pricing, orders)

- Catalogue API from ERPNext `Item` + price lists + per-location availability.
- Server-side cart pricing: ₹200 minimum; Quick ₹50 + ₹15 handling (≤3 km); Scheduled ₹15 up to ₹400, free ≥ ₹500; **₹401–₹499 stays configurable and unset** (blocks checkout until decided).
- Single-location allocation (rule-based): all items in stock → nearest open → capacity → rider availability; **no splitting, no silent substitution**.
- Stock reservation with expiry; idempotent order creation.
**Done when:** a test customer can place a COD order on staging end-to-end to `Allocated`, with correct fees and an audit trail.

## Section 5 — Store operations & reporting

- Store app/desk: accept order, pick list, out-of-stock handling (ask customer, never auto-substitute), pack, hand-over.
- Reports: daily orders, AOV, Quick/Scheduled mix, picking time, cancellation and refund rates.
**Done when:** store staff can process an order from `Allocated` to `Packed`; reports return correct figures on synthetic data.

## Section 6 — Delivery & rider logistics

- Rider onboarding docs, availability toggle, assignment (manual first, then nearest-free), accept/reject, pickup confirm, delivery OTP, proof photo.
- Payout engine: ₹20 base + distance bands (₹0/3/7/13/18, +₹7/km beyond 5 km), +₹5 Quick, configurable waiting/peak/weather/cancellation, 100% tips; route distance where reliable, else straight-line flagged.
- Weekly payout statements.
**Done when:** synthetic week produces statements whose totals reconcile to delivery jobs, including earnings-per-active-hour.

## Section 7 — Permissions, notifications, audit

- Roles: Customer, Store Manager, Store Staff, Rider, Ops Admin, Finance, Super Admin; record-level restrictions (store sees only its orders; rider sees only assigned jobs).
- SMS/WhatsApp/email/push hooks (provider TBD — Q13), order status notifications.
- `Audit Event` for fee/commission/payout changes and every order transition.
**Done when:** permission tests prove cross-store and cross-rider access is denied server-side.

## Section 8 — ERPNext & external integration

- Delivered order → `Sales Invoice` (GST) + `Payment Entry`; refunds → `Credit Note`.
- Partner settlements → `Journal Entry`/`Purchase Invoice`; rider payouts → `Journal Entry`.
- Razorpay: server-side order creation, signature verification, webhooks, idempotency, daily reconciliation report (code already drafted).
- Maps/geocoding provider for distance (Q12).
**Done when:** synthetic month posts to ERPNext with balanced ledgers and a clean Razorpay test-mode reconciliation.

## Section 9 — Security, QA, performance, deployment

- Secrets only in `site_config.json`/env, never in repo; rate limits on OTP and checkout; input validation; CSRF; least privilege.
- Load test: target peak orders/hour (Q15).
- Backups, monitoring, error reporting, staging → production promotion runbook.
**Done when:** security checklist passes, load test meets target, restore drill done on staging.

## Section 10 — End-to-end validation, packaging, handover

- Fresh install + upgrade test on disposable bench; full journey tests; screenshot evidence; install/update/rollback scripts (Mac/Linux); admin and store guides (Markdown).
**Done when:** 1.0.0 ZIP passes on a disposable environment with a written test report.

---

## Synthetic data (`jalgo_demo`)

Generated deterministically (fixed seed) on **staging only**:
- 1 company (JALGO, Maharashtra, GST-registered placeholder), 1 partner store (father's supermarket stand-in), 1 future dark store (disabled).
- ~50 items from the website catalogue with HSN/GST placeholders, ~300 total SKUs optional.
- 3 service zones in Jalgaon, 3 slots/day.
- 200 customers (fake names/phones in a reserved test range), 12 riders, 30 days of orders at a chosen volume (e.g., 25 → 100/day ramp), realistic cancellations/refunds, payouts and settlements.
- No real personal data; clearly flagged `is_demo = 1` and removable.

## Backup, staging, rollback

- Backup (DB + files + site_config) before every migrate; restore tested in Section 1.
- All work on a staging site with its own port; production untouched until Section 10 sign-off.
- Rollback: restore backup + uninstall app version via documented script; migrations written to be reversible where practical.

## Release scope

**First release (pilot):** Sections 1–8 for one partner store, COD + Razorpay, Quick + Scheduled, manual/simple rider assignment.
**Deferred:** dark-store procurement automation, smart allocation, multi-store splitting, memberships, sponsored listings, food/rides/pharmacy.

---

## Open questions (please answer what you can; unanswered items become stated assumptions)

1. **Where will this run?** Do you have a bench/server (Frappe Cloud, VPS, local Mac)? I can't build here — this workspace has no bench or MariaDB.
2. **Version:** "ERPNext 16.53.0" — is that what your server reports (`bench version`)? If unsure, I'll target the latest stable v16 tag verified in Section 1.
3. **App structure:** one `jalgo` app (modular) + `jalgo_demo`, or separate apps per area?
4. Is there an **existing ERPNext site** with real data, or a fresh install?
5. **Father's store billing system:** which software, and can it export items/stock/prices (CSV/Excel)?
6. Is JALGO **GST-registered** yet? Which entity invoices the customer — JALGO or the store?
7. **Who is the seller of record** for partner-store orders (marketplace vs. inventory model)? This drives invoicing and tax.
8. Should partner stock be **mirrored in ERPNext warehouses**, or only availability flags synced from the store?
9. **Payment methods at pilot:** Razorpay (UPI/cards) + COD? Any COD limit?
10. **Frontend:** keep the website as a Frappe-served app (Vue/frappe-ui), or a separate frontend calling the API?
11. **Mobile apps:** web-only for pilot, or Android apps (customer/rider/store) in this scope?
12. **Maps provider** for distance/geocoding (Google Maps, Ola Maps, OSM)? Budget?
13. **OTP/SMS/WhatsApp provider** (MSG91, Gupshup, Twilio)?
14. **Pilot service area:** store address and radius/zones?
15. **Expected pilot volume** (orders/day at launch and at 3 months)?
16. **Riders:** JALGO-contracted or store staff for the pilot? Payout frequency?
17. **₹401–₹499 Scheduled fee:** decided yet? (Checkout blocks until set.)
18. **Synthetic data volume:** 30 days at ~25–100 orders/day OK?
19. **Repository:** GitHub org/repo to use? Any CI?
20. **Acceptance:** who signs off each section?

---

**Next step:** answer the questions (partial is fine), then approve the plan or request changes. After approval I'll start **Section 1** only — and Section 1 needs access to a real staging bench.
