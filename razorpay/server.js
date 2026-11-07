// JALGO – Razorpay payment server (Node.js + Express)
// Run: npm install express razorpay dotenv  →  node server.js
// Keys live ONLY in a .env file on the server, never in the website code.

require('dotenv').config();
const express = require('express');
const crypto = require('crypto');
const Razorpay = require('razorpay');

const app = express();
const rzp = new Razorpay({
  key_id: process.env.RAZORPAY_KEY_ID,        // rzp_test_... while testing
  key_secret: process.env.RAZORPAY_KEY_SECRET // never sent to the browser
});

// Pilot pricing from the JALGO plan. Keep in config/admin later.
const CFG = { minOrder: 200, quick: { delivery: 50, handling: 15 }, sched: { upto400: 15, freeFrom: 500, mid: null } };

// IMPORTANT: prices must come from YOUR database, never from the browser.
const PRICE_DB = { 1: 29, 6: 32, 12: 265 /* … load from your catalogue … */ };

function priceCart(items, mode) {
  let sub = 0;
  for (const { id, qty } of items) {
    if (!PRICE_DB[id] || !Number.isInteger(qty) || qty < 1) throw new Error('Invalid item');
    sub += PRICE_DB[id] * qty;
  }
  if (sub < CFG.minOrder) throw new Error(`Minimum order is ₹${CFG.minOrder}`);
  let delivery = 0, handling = 0;
  if (mode === 'quick') { delivery = CFG.quick.delivery; handling = CFG.quick.handling; }
  else if (sub <= 400) delivery = CFG.sched.upto400;
  else if (sub < CFG.sched.freeFrom) {
    if (CFG.sched.mid == null) throw new Error('Scheduled fee for ₹401–₹499 not configured');
    delivery = CFG.sched.mid;
  }
  return { sub, delivery, handling, total: sub + delivery + handling };
}

// 1) Website asks the server to create a Razorpay order
app.post('/api/orders', express.json(), async (req, res) => {
  try {
    const bill = priceCart(req.body.items, req.body.mode);
    const receipt = 'JLG' + Date.now();
    const order = await rzp.orders.create({
      amount: bill.total * 100, // paise
      currency: 'INR',
      receipt,
      notes: { mode: req.body.mode }
    });
    // TODO: save {receipt, order.id, bill, items, customer} as PENDING in your DB
    res.json({ orderId: order.id, amount: order.amount, keyId: process.env.RAZORPAY_KEY_ID, bill });
  } catch (e) {
    res.status(400).json({ error: e.message });
  }
});

// 2) After the Razorpay window succeeds, the website sends the result here to verify
app.post('/api/payments/verify', express.json(), (req, res) => {
  const { razorpay_order_id, razorpay_payment_id, razorpay_signature } = req.body;
  const expected = crypto.createHmac('sha256', process.env.RAZORPAY_KEY_SECRET)
    .update(`${razorpay_order_id}|${razorpay_payment_id}`).digest('hex');
  const ok = expected.length === (razorpay_signature || '').length &&
    crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(razorpay_signature));
  if (!ok) return res.status(400).json({ verified: false });
  // TODO: mark order PAID in your DB (idempotent: ignore if already PAID)
  res.json({ verified: true });
});

// 3) Webhook: Razorpay tells you directly, even if the customer closed the browser
app.post('/api/razorpay/webhook', express.raw({ type: 'application/json' }), (req, res) => {
  const sig = req.headers['x-razorpay-signature'];
  const expected = crypto.createHmac('sha256', process.env.RAZORPAY_WEBHOOK_SECRET).update(req.body).digest('hex');
  if (sig !== expected) return res.sendStatus(400);
  const event = JSON.parse(req.body.toString());
  // payment.captured → mark PAID; payment.failed → mark FAILED; refund.processed → record refund
  // Use event.payload.payment.entity.order_id to find your order. Process each event once.
  console.log('Razorpay event:', event.event);
  res.sendStatus(200);
});

app.use(express.static('public')); // put the JALGO website in ./public
app.listen(process.env.PORT || 3000, () => console.log('JALGO server running'));
