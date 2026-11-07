# JALGO POS (`jalgo_pos`)

Counter billing app for **Shubhendra Provision**, built as a Frappe app on **ERPNext 16** with a **Vue 3** screen at `/jalgo-pos`.
Every bill, return, estimate, goods receipt and payment is an ordinary ERPNext document, so stock, GST and accounts stay in one place.

Tested on: Frappe 16.55.2 · ERPNext 16.53.0 · India Compliance 16.11.0 · Python 3.14 · Node 24 · MariaDB 10.11.

## What it does

| Area | Features | ERPNext documents |
|---|---|---|
| Billing | Barcode or name search (barcode also works in Item Name), F-key billing, GST-inclusive prices, Express Pay / Pay Now, change to return, 80 mm receipt printing | Sales Invoice (POS, updates stock) |
| | Hold / pick held bills, estimate, customer search and quick add, credit (udhaar), manager PIN for big discounts, returns, offers | JALGO Held Bill, Quotation, Customer, Sales Invoice (return), Pricing Rule |
| | Shift open with cash count, shift close with expected vs counted cash | JALGO POS Shift |
| Back office | Live lists (items, customers, suppliers, bills, returns, udhaar, GRNs, supplier bills, stock entries, shifts, locations, users), 15 ERPNext reports, today dashboard, Set-Up button reorder per user | read-only views |
| Stock | GRN by Template (size/flavour grid → item variants), item fields, transfers shop ↔ dark store, wastage write-off, collect udhaar | Item Attribute, Item (variants), Item Price, Purchase Receipt, Stock Entry, Payment Entry |
| Labels | Barcode stickers (EAN-13 / Code128) with the Rate Card coded purchase price; 38×25 roll, 50×25 roll, A4 65-up; counter settings | JALGO POS Settings |
| Safety | JALGO Cashier / JALGO Manager roles, offline billing queue with automatic sync, Razorpay UPI QR (when keys are set) | — |

## Install on an existing ERPNext 16 bench

```bash
# from a checkout of github.com/supagigs/jalgo, as the bench user
SITE=your.site.name BENCH=~/frappe-bench ./jalgo_pos/scripts/install.sh
```
Setup creates: the POS Profile "Shubhendra Provision Counter", payment modes Cash / UPI / Card, a GST-inclusive sales tax
template, JALGO POS Settings (demo PIN **2468**), a sample offer, and the roles **JALGO Cashier** and **JALGO Manager**.

Then:
1. **Change the manager PIN** in ERPNext → JALGO POS Settings.
2. **Give people access** (as Administrator):
   `bench --site $SITE execute jalgo_pos.setup.make_pos_user --kwargs "{'user': 'cashier@shop.in'}"` — add `'manager': 1` for managers.
3. Check the POS Profile warehouse (rename the shop warehouse in ERPNext if needed).
4. Open `https://your.site/jalgo-pos`.

## Update and rollback

```bash
SITE=your.site.name BENCH=~/frappe-bench ./jalgo_pos/scripts/update.sh
```
It refuses to run if `apps/jalgo_pos` has local changes, backs up the site with files, keeps the old code in
`apps/jalgo_pos.bak-<date>`, migrates, builds, clears cache and pings the site.
**Rollback:** move the `.bak` folder back to `apps/jalgo_pos`, then `bench --site $SITE restore <backup>` if the database changed.

## Razorpay UPI (optional)

```bash
bench --site $SITE set-config razorpay_key_id rzp_live_xxx
bench --site $SITE set-config razorpay_key_secret xxxx
bench --site $SITE set-config razorpay_webhook_secret xxxx
```
In the Razorpay dashboard add a webhook for **qr_code.credited** to
`https://your.site/api/method/jalgo_pos.payments.razorpay_webhook`. Keys stay on the server.
Without keys, the cashier confirms UPI and card payments. **Not tested against Razorpay itself** (no keys in staging);
the webhook signature check and the paid-QR check are covered by tests.

## Develop

```bash
cd apps/jalgo_pos/frontend && npm install && npm run dev     # Vite on :8080, proxies to bench on :8000
npm run build                                               # writes jalgo_pos/public/frontend and www/jalgo-pos.html
bench --site $SITE run-tests --app jalgo_pos               # 29 integration tests
```

## Known limitations
- Offline billing works after the screen has loaded once online (it caches the catalogue). Credit bills, PIN discounts and held bills need the connection.
- Offers: percentage discount on an item or item group from a minimum quantity.
- Returns refund cash; a return against a credit bill reduces what the customer owes.
- Back-office lists show 50 rows and reports the first 300 rows; use "open in ERPNext" for the rest.
- HSN codes and GST rates in the demo data are samples: confirm them with your CA.

## License
MIT
