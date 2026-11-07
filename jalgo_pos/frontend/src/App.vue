<template>
<div class="wrap" @keydown="onKey">
 <div class="win" v-if="boot">
  <div class="title"><i>S</i>Shubhendra POS · JALGO</div>

  <div class="hdr">
   <div class="shop">
    <div class="storeimg"><small>JALGO</small><b>SP</b><span style="font-size:10px">since 1998</span></div>
    <div><h1>{{ boot.shop.name }}</h1><p>{{ boot.shop.address }}</p>
     <div class="who"><span><b>Login :</b> {{ boot.user_name }}</span><span><b>Cash Register :</b> {{ boot.profile }}</span></div></div>
   </div>
   <div class="inv">
    <label>Invoice # :</label><span class="lnk num">{{ lastBill ? 'Next after ' + lastBill : 'New bill' }}</span><label>Date :</label><span class="lnk num">{{ today }}</span>
    <label for="bc">Barcode :</label><input id="bc" v-model="bc" class="num" style="grid-column:2/4" autocomplete="off" @keydown.enter.prevent="scan"><span class="hint">Alt+B</span>
    <label for="q">Item Name :</label>
    <div class="searchwrap"><input id="q" v-model="q" autocomplete="off" @input="search" @keydown.down.prevent="hi=Math.min(hi+1,matches.length-1)" @keydown.up.prevent="hi=Math.max(hi-1,0)" @keydown.enter.prevent="nameEnter">
     <div class="sugg" v-if="q && matches.length"><button v-for="(m,i) in matches" :key="m.code" :class="{on:i===hi}" @mousedown.prevent="add(m)"><img :src="imgFor(m.name)" alt=""><span class="num">{{ m.barcode }}</span><span>{{ m.name }} <small style="color:#888">· {{ m.stock }} in stock</small></span><b class="num">{{ m.rate.toFixed(2) }}</b></button></div></div>
    <span class="hint">Alt+I</span>
    <label>Shift :</label><span class="lnk num" style="grid-column:2/4">{{ boot.shift ? boot.shift.name + ' · opened ' + String(boot.shift.opened_at).slice(11,16) : 'Not open' }}</span><button class="dots" @click="openCloseShift">{{ boot.shift ? 'Close' : 'Open' }}</button>
   </div>
  </div>

  <div class="tools">
   <button class="tb" title="New bill" @click="askCancel">🧾</button><button class="tb" title="Sync items from ERPNext" @click="refreshLines">🔄</button>
   <span class="sep"></span><button class="tb" title="Sales return" @click="openReturn">↩️</button><button class="tb" title="Offers (F12)" @click="openOffers">🏷️</button><button class="tb" title="Held bills (F7)" @click="openHeld">🗂️</button><button class="tb" title="Close shift / cash count" @click="openCloseShift">💰</button>
   <span class="sep"></span><button class="tb" title="Reprint last bill" @click="last ? dlg='receipt' : toast('No bill printed yet')">🖨️</button>
   <span class="sep"></span><button class="tb" title="Set-Up / back office" @click="setup=true">⚙️</button><button class="tb" title="Keyboard shortcuts (F1)" @click="dlg='help'">⌨️</button>
   <span class="brandtag"><i>J</i>JALGO POS</span>
  </div>

  <div class="body">
   <div class="left">
    <div class="grid">
     <table>
      <thead><tr><th style="width:44px">S<br>No.</th><th>Image</th><th>Barcode</th><th>Item Name</th><th class="r">Qty /<br>Weight</th><th>Measuring<br>Unit</th><th class="r">MRP</th><th class="r">Unit Price<br>with Tax</th><th class="r">Disc<br>%</th><th class="r">Amount<br>with Tax</th></tr></thead>
      <tbody>
       <tr v-for="(l,i) in lines" :key="l.code" :class="{sel:i===sel}" @click="sel=i">
        <td>{{ i+1 }}</td><td class="img"><img :src="imgFor(l.name)" :alt="l.name"></td><td class="num">{{ l.barcode }}</td><td>{{ l.name }}</td>
        <td class="r"><input class="qty num" :id="'qty'+i" type="number" min="0" step="any" v-model.number="l.qty" @focus="sel=i"></td>
        <td>{{ l.uom }}</td><td class="r num">{{ l.mrp.toFixed(2) }}</td><td class="r num">{{ l.rate.toFixed(2) }}</td>
        <td class="r"><input class="qty num" style="width:48px" type="number" min="0" :max="boot.max_manager_discount" v-model.number="l.disc" @focus="sel=i"><div v-if="offerFor(l)&&offerFor(l).discount>(+l.disc||0)" class="offtag" :title="offerFor(l).title">offer {{ offerFor(l).discount }}%</div></td>
        <td class="r num"><b>{{ amt(l).toFixed(2) }}</b></td>
       </tr>
      </tbody>
     </table>
     <div class="emptyrow" v-if="!lines.length">Scan a barcode (Alt+B) or type an item name (Alt+I) to start the bill.</div>
    </div>
    <div class="status">
     <span>Warehouse: <b>{{ boot.warehouse }}</b></span>
     <span class="conn" :title="queue.length ? 'Bills waiting to sync' : ''"><i class="dot" :class="{off:!online||queue.length}"></i>{{ online ? (queue.length ? queue.length + ' offline bill(s) syncing…' : 'ERPNext connected') : 'Offline · ' + queue.length + ' bill(s) queued' }}</span>
    </div>
   </div>

   <div class="right">
    <div class="keys">
     <button class="key o" @click="focusQty">Change<br>Quantity<br>F2</button>
     <button class="key o" @click="removeLine">Remove<br>Item<br>F4</button>
     <button class="key o" @click="showStock">Show Stock</button>
     <button class="key v" @click="holdBill">Hold<br>Invoice<br>F6</button>
     <button class="key v" @click="openHeld">Pick Held<br>Invoice<br>F7</button>
     <button class="key v" @click="askCancel">Cancel<br>Invoice<br>F10</button>
     <button class="key p" @click="dlg='tax'">Show Tax<br>Details</button>
     <button class="key p" @click="openOffers">Show Offer<br>Details<br>F12</button>
     <button class="key p big" @click="setup=true">Set-Up</button>
    </div>
    <div class="tot">
     <label>Total :</label><div class="box total">{{ fmt(payable) }}</div>
     <label>Discount Included :</label><div class="box disc">{{ fmt(discount) }}</div>
     <label>Quantity Total :</label><div class="box qtyt">{{ totQty }}</div>
    </div>
    <div class="who2">
     <label for="cu">Customer :</label><input id="cu" class="yl" :value="custLabel" readonly placeholder="Walk-in Customer" @click="openCust" @keydown.enter.prevent="openCust"><button class="dots" title="Find customer (F9)" @click="openCust">…</button>
     <label for="se">Sales Executive :</label><input id="se" class="yl" v-model="exec"><span></span>
    </div>
    <div class="pay">
     <button class="key g express" :disabled="busy" @click="pay(true)"><span class="ico">🏃</span>Express<br>Pay<br>(F5)</button>
     <button class="key g" :disabled="busy" @click="pay(false)"><span class="ico">💵</span>Pay Now<br>(F8)</button>
     <div class="est"><button class="key g" @click="estimate(false)">Estimate<br>(F11)</button><button class="key g" @click="estimate(true)">Save &amp; Print<br>Estimate (Alt F11)</button></div>
    </div>
   </div>
  </div>
 </div>
 <div class="win" v-else style="padding:40px;text-align:center">{{ bootErr || 'Loading POS…' }}</div>

 <div class="scrim" v-if="dlg" @click.self="close">
  <div class="dlg" role="dialog" aria-modal="true" :style="['receipt','tax','help','held','cust','offers','return','estimate','shiftClose'].includes(dlg)?'width:min(560px,100%)':''">
   <div class="title"><i>S</i>{{ titles[dlg] }}<button class="x" @click="close" aria-label="Close">✕</button></div>
   <div class="in">
    <template v-if="dlg==='pay'">
     <fieldset><legend>Quick Details</legend>
      <div class="rowd"><label>Total Before roundoff :</label><div class="fieldv c1">{{ fmt(netTotal) }}</div><span></span></div>
      <div class="rowd"><label>Roundoff Amount :</label><div class="fieldv c2">{{ fmt(payable-netTotal) }}</div><span></span></div>
      <div class="rowd"><label>Final Total :</label><div class="fieldv c1">{{ fmt(payable) }}</div><span></span></div>
      <div class="rowd" style="grid-template-columns:150px 1fr"><label>Payment Mode :</label>
       <div style="display:flex;gap:4px;flex-wrap:wrap"><button v-for="m in boot.modes" :key="m" class="btn" :style="mode===m?'border-color:var(--accent);color:var(--accent);font-weight:700':''" @click="mode=m">{{ m }}</button></div></div>
      <div class="rowd hl"><label for="rcv">Received Amount :</label><input id="rcv" class="rcv num" type="number" v-model.number="received" :disabled="mode!=='Cash'" @keydown.enter.prevent="finish"><button class="purp" title="Exact amount (Ctrl+P)" @click="received=payable">⇦</button></div>
      <div class="rowd"><label>Returnable Balance :</label><div class="fieldv c3">{{ fmt(Math.max(0,received-payable)) }}</div><span></span></div>
      <p class="err" v-if="err">{{ err }}</p>
      <p v-if="mode==='Credit'" style="margin:4px 0 0;font-size:12px;text-align:center">₹{{ fmt(payable) }} is added to {{ customer ? customer.customer_name : 'the customer' }}'s udhaar account{{ customer && customer.outstanding ? ' (now owes ₹'+fmt(customer.outstanding)+')' : '' }}.</p>
      <div v-else-if="mode==='UPI' && boot.razorpay && online" class="qrbox">
       <img v-if="qr && qr.image_url" :src="qr.image_url" alt="UPI QR code">
       <p v-if="!qr" style="margin:0">Show a Razorpay UPI QR for ₹{{ fmt(payable) }}.</p>
       <p v-else style="margin:0;font-weight:700" :style="{color: qrPaid ? '#177245' : '#8A4B00'}">{{ qrPaid ? 'Payment received ✓' : 'Waiting for the customer to pay…' }}</p>
       <button class="btn" v-if="!qr" @click="makeQr">Show UPI QR</button>
      </div>
      <p v-else-if="mode!=='Cash'" style="margin:4px 0 0;font-size:12px;text-align:center">Confirm the {{ mode }} payment of ₹{{ fmt(payable) }} on the {{ mode === 'Card' ? 'card machine' : 'UPI app' }} before saving.{{ mode === 'UPI' && !boot.razorpay ? ' (Razorpay is not set up on this server yet.)' : '' }}</p>
     </fieldset>
     <div class="dlgbtns"><button class="gbtn" :disabled="busy" @click="finish">{{ busy ? 'Saving…' : 'OK (F8)' }}</button><button class="gbtn" @click="close">Cancel</button></div>
    </template>
    <template v-else-if="dlg==='receipt'">
     <div class="receipt">{{ receiptText }}</div>
     <p v-if="last.offline" style="font-size:12px;margin:8px 0 0;color:#8A4B00"><b>Saved on this counter (offline).</b> It will be posted to ERPNext automatically when the connection returns.</p>
     <p v-else style="font-size:12px;margin:8px 0 0">Saved in ERPNext as <b>{{ last.name }}</b> (submitted). {{ last.is_return ? 'Stock is back in ' + boot.warehouse + '.' : 'Stock has left ' + boot.warehouse + '.' }}</p>
     <div class="dlgbtns"><button class="gbtn" @click="close">New Bill (Enter)</button><button class="gbtn" @click="printText(receiptText)">Print receipt (P)</button></div>
    </template>
    <template v-else-if="dlg==='tax'">
     <table class="tbl2"><thead><tr><th>GST %</th><th class="r">Taxable</th><th class="r">CGST</th><th class="r">SGST</th><th class="r">Total</th></tr></thead>
      <tbody><tr v-for="t in taxRows" :key="t.rate"><td>{{ t.rate }}%</td><td class="r num">{{ t.taxable.toFixed(2) }}</td><td class="r num">{{ (t.tax/2).toFixed(2) }}</td><td class="r num">{{ (t.tax/2).toFixed(2) }}</td><td class="r num">{{ t.gross.toFixed(2) }}</td></tr></tbody></table>
     <p style="font-size:12px;margin:8px 0 0">Estimate on screen. ERPNext calculates the final tax when the bill is saved.</p>
     <div class="dlgbtns"><button class="gbtn" @click="close">OK</button></div>
    </template>
    <template v-else-if="dlg==='stock'">
     <p style="margin:0 0 6px"><b>{{ lines[sel] ? lines[sel].name : 'Select a line first' }}</b></p>
     <table class="tbl2" v-if="lines[sel]"><tbody><tr><td>{{ boot.warehouse }}</td><td class="r num"><b>{{ lines[sel].stock }}</b></td></tr></tbody></table>
     <p style="font-size:12px;margin:8px 0 0">Live from ERPNext.</p>
     <div class="dlgbtns"><button class="gbtn" @click="close">OK</button></div>
    </template>
    <template v-else-if="dlg==='cancel'">
     <p style="margin:0 0 8px">Clear this bill with {{ lines.length }} items? Nothing has been saved yet.</p>
     <div class="dlgbtns"><button class="gbtn" style="background:#C0392B;border-color:#C0392B" @click="clearBill();close()">Yes, clear</button><button class="gbtn" @click="close">No</button></div>
    </template>
    <template v-else-if="dlg==='help'">
     <table class="tbl2"><tbody><tr v-for="k in keysHelp" :key="k[0]"><td style="width:110px"><b>{{ k[0] }}</b></td><td>{{ k[1] }}</td></tr></tbody></table>
     <div class="dlgbtns"><button class="gbtn" @click="close">OK</button></div>
    </template>
    <template v-else-if="dlg==='shiftOpen'">
     <p style="margin:0 0 8px">Count the cash in the drawer and open your shift. Bills can be made only during an open shift.</p>
     <div class="rowd hl"><label for="oc">Opening cash ₹</label><input id="oc" class="rcv num" type="number" v-model.number="openingCash" @keydown.enter.prevent="doOpenShift"><span></span></div>
     <p class="err" v-if="err">{{ err }}</p>
     <div class="dlgbtns"><button class="gbtn" @click="doOpenShift">Open shift</button></div>
    </template>
    <template v-else-if="dlg==='shiftClose'">
     <table class="tbl2"><tbody>
      <tr><td>Opening cash</td><td class="r num">{{ fmt(shiftSum.opening_cash) }}</td></tr>
      <tr><td>Bills</td><td class="r num">{{ shiftSum.bills }}</td></tr><tr><td>Sales</td><td class="r num">{{ fmt(shiftSum.sales_total) }}</td></tr>
      <tr><td>Returns</td><td class="r num">{{ fmt(shiftSum.returns_total) }}</td></tr>
      <tr><td>Cash (net of change)</td><td class="r num">{{ fmt(shiftSum.cash_sales) }}</td></tr><tr><td>UPI</td><td class="r num">{{ fmt(shiftSum.upi_sales) }}</td></tr>
      <tr><td>Card</td><td class="r num">{{ fmt(shiftSum.card_sales) }}</td></tr><tr><td>Credit (udhaar)</td><td class="r num">{{ fmt(shiftSum.credit_sales) }}</td></tr>
      <tr><td><b>Expected cash in drawer</b></td><td class="r num"><b>{{ fmt(shiftSum.expected_cash) }}</b></td></tr></tbody></table>
     <div class="rowd hl"><label for="cc">Counted cash ₹</label><input id="cc" class="rcv num" type="number" v-model.number="countedCash"><span></span></div>
     <div class="rowd"><label>Difference</label><div class="fieldv" :class="countedCash-shiftSum.expected_cash<0?'c3':'c1'">{{ fmt(countedCash-shiftSum.expected_cash) }}</div><span></span></div>
     <p class="err" v-if="err">{{ err }}</p>
     <div class="dlgbtns"><button class="gbtn" @click="doCloseShift">Close shift</button><button class="gbtn" @click="close">Not now</button></div>
    </template>
    <template v-else-if="dlg==='cust'">
     <input id="cq" class="cell wide" style="width:100%;margin-bottom:8px" v-model="cq" placeholder="Search name or mobile" @input="searchCust" @keydown.enter.prevent="custRows[0]&&pickCust(custRows[0])">
     <table class="tbl2 rt"><thead><tr><th>Customer</th><th>Mobile</th><th class="r">Owes ₹</th><th></th></tr></thead>
      <tbody><tr v-for="c in custRows" :key="c.name"><td>{{ c.customer_name }}</td><td class="num">{{ c.mobile_no || '' }}</td><td class="r num">{{ fmt(c.outstanding) }}</td><td><button class="gbtn" style="padding:3px 10px" @click="pickCust(c)">Pick</button></td></tr>
       <tr v-if="!custRows.length"><td colspan="4" style="color:#888">No match. Add a new customer below.</td></tr></tbody></table>
     <div class="rowd" style="grid-template-columns:auto 1fr 1fr auto;margin-top:10px"><label>New</label><input id="nn" class="cell wide" v-model="newCust.name" placeholder="Name"><input id="nm" class="cell wide" v-model="newCust.mobile" placeholder="10-digit mobile" inputmode="numeric"><button class="gbtn" style="padding:4px 10px" @click="addCust">Add</button></div>
     <p class="err" v-if="err">{{ err }}</p>
     <div class="dlgbtns"><button class="gbtn" @click="customer=null;close()">Walk-in Customer</button><button class="gbtn" @click="close">Close</button></div>
    </template>
    <template v-else-if="dlg==='held'">
     <p v-if="!heldList.length" style="margin:0">No held invoices.</p>
     <table class="tbl2 rt" v-else><thead><tr><th>Customer</th><th class="r">Items</th><th class="r">Total</th><th>Held by</th><th></th></tr></thead>
      <tbody><tr v-for="h in heldList" :key="h.name"><td>{{ h.customer || 'Walk-in' }}</td><td class="r num">{{ h.item_count }}</td><td class="r num">{{ fmt(h.total) }}</td><td>{{ h.owner }} · {{ String(h.creation).slice(11,16) }}</td>
       <td><button class="gbtn" style="padding:3px 10px" @click="recall(h.name)">Pick</button> <button class="dots" title="Discard" @click="discardHeld(h.name)">✕</button></td></tr></tbody></table>
     <div class="dlgbtns"><button class="gbtn" @click="close">Close</button></div>
    </template>
    <template v-else-if="dlg==='offers'">
     <p v-if="!offerList.length" style="margin:0">No active offers. Add them in ERPNext → Pricing Rule (discount percentage on an item or item group).</p>
     <table class="tbl2 rt" v-else><thead><tr><th>Offer</th><th>Applies to</th><th class="r">Min qty</th><th class="r">Discount</th><th>In this bill</th></tr></thead>
      <tbody><tr v-for="o in offerList" :key="o.name"><td>{{ o.title }}</td><td>{{ o.on }}</td><td class="r num">{{ o.min_qty || 0 }}</td><td class="r num">{{ o.discount }}%</td><td>{{ o.in_cart && o.in_cart.length ? 'Yes' : '' }}</td></tr></tbody></table>
     <p style="font-size:12px;margin:8px 0 0">Offers apply automatically when the quantity is reached. The bigger of the offer and the cashier's discount is used, never both.</p>
     <div class="dlgbtns"><button class="gbtn" @click="close">OK</button></div>
    </template>
    <template v-else-if="dlg==='pin'">
     <p style="margin:0 0 8px">{{ pinWhy }}</p>
     <div class="rowd hl"><label for="pin">Manager PIN</label><input id="pin" class="rcv num" type="password" inputmode="numeric" maxlength="6" v-model="pinIn" @keydown.enter.prevent="pinOk"><span></span></div>
     <div class="dlgbtns"><button class="gbtn" @click="pinOk">OK</button><button class="gbtn" @click="close">Cancel</button></div>
    </template>
    <template v-else-if="dlg==='return'">
     <div class="rowd" style="grid-template-columns:auto 1fr auto"><label for="rn">Bill number</label><input id="rn" class="cell wide" v-model="retNo" placeholder="e.g. SINV-26-00003" @keydown.enter.prevent="findBill"><button class="gbtn" style="padding:4px 12px" @click="findBill">Find</button></div>
     <template v-if="retBill">
      <p style="margin:6px 0">{{ retBill.name }} · {{ retBill.date }} · {{ retBill.customer }} · ₹{{ fmt(retBill.total) }}</p>
      <table class="tbl2 rt"><thead><tr><th>Item</th><th class="r">Sold</th><th class="r">Can return</th><th class="r">Return qty</th></tr></thead>
       <tbody><tr v-for="i in retBill.items" :key="i.code"><td>{{ i.name }}</td><td class="r num">{{ i.sold }}</td><td class="r num">{{ i.can_return }}</td><td class="r"><input class="cell" type="number" min="0" :max="i.can_return" v-model.number="retQty[i.code]" style="width:70px"></td></tr></tbody></table>
      <div class="rowd hl"><label for="rp">Manager PIN</label><input id="rp" class="rcv num" type="password" inputmode="numeric" maxlength="6" v-model="pinIn"><span></span></div>
      <p style="font-size:12px;margin:0">Cash refund of about ₹{{ fmt(retEstimate) }} from the drawer. Stock goes back to {{ boot.warehouse }}.</p>
     </template>
     <p class="err" v-if="err">{{ err }}</p>
     <div class="dlgbtns"><button class="gbtn" :disabled="!retBill||busy" @click="doReturn">{{ busy ? 'Saving…' : 'Make return' }}</button><button class="gbtn" @click="close">Cancel</button></div>
    </template>
    <template v-else-if="dlg==='estimate'">
     <div class="receipt">{{ estimateText }}</div>
     <p style="font-size:12px;margin:8px 0 0">Saved in ERPNext as Quotation <b>{{ est.name }}</b>, valid till {{ est.valid_till }}. No stock has moved.</p>
     <div class="dlgbtns"><button class="gbtn" @click="close">OK</button><button class="gbtn" @click="printText(estimateText)">Print estimate</button></div>
    </template>
    <template v-else>
     <p style="margin:0">{{ info }}</p><div class="dlgbtns"><button class="gbtn" @click="close">OK</button></div>
    </template>
   </div>
  </div>
 </div>
 <SetUp v-if="setup && boot" :boot="boot" @settings="v=>Object.assign(boot,{barcode_in_name:v.accept_barcode_in_name,warn_not_found:v.warn_not_found,require_shift:v.require_shift,max_discount:v.max_cashier_discount,max_manager_discount:v.max_manager_discount})" @close="setup=false;focusBc()" @info="m=>{info=m;dlg='info'}" @toast="toast" />
 <div class="toast" v-if="toastMsg" role="status">{{ toastMsg }}</div>
</div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { call } from './api'
import { imgFor } from './img'
import SetUp from './SetUp.vue'

const r2 = n => Math.round(n * 100) / 100
const boot = ref(null), bootErr = ref('')
const lines = ref([]), sel = ref(0), bc = ref(''), q = ref(''), matches = ref([]), hi = ref(0)
const customer = ref(null), exec = ref(''), dlg = ref(null), info = ref(''), err = ref(''), busy = ref(false)
const mode = ref('Cash'), received = ref(0), last = ref(null), lastBill = ref(''), toastMsg = ref('')
const heldName = ref(null), heldList = ref([]), offerList = ref([]), custRows = ref([]), cq = ref(''), newCust = ref({ name: '', mobile: '' })
const pinIn = ref(''), pin = ref(''), pinWhy = ref(''), pinNext = ref(null), est = ref(null)
const retNo = ref(''), retBill = ref(null), retQty = ref({}), openingCash = ref(0), countedCash = ref(0), shiftSum = ref({})
const setup = ref(false)
const queue = ref(loadLS('jalgo_pos_queue', [])), catalog = ref(loadLS('jalgo_pos_catalog', { items: [] }).items), qr = ref(null), qrPaid = ref(false)
function loadLS(k, d) { try { return JSON.parse(localStorage.getItem(k)) ?? d } catch (e) { return d } }
function saveLS(k, v) { try { localStorage.setItem(k, JSON.stringify(v)) } catch (e) {} }
function localSearch(t) {
  t = t.toLowerCase(); const exact = catalog.value.filter(i => i.barcode === t || i.code.toLowerCase() === t)
  return exact.length ? exact : catalog.value.filter(i => i.name.toLowerCase().includes(t)).slice(0, 10)
}
const online = ref(navigator.onLine), billId = ref(crypto.randomUUID())

const today = new Date().toLocaleDateString('en-GB')
const titles = { shiftOpen: 'Open Shift', shiftClose: 'Close Shift', cust: 'Choose Customer', held: 'Pick Held Invoice', offers: 'Offer Details', pin: 'Manager Approval', return: 'Sales Return', estimate: 'Estimate', pay: 'Returnable Amount', receipt: 'Invoice Saved', tax: 'Tax Details', stock: 'Show Stock', cancel: 'Cancel Invoice', help: 'Keyboard Shortcuts', info: 'Information' }
const keysHelp = [['Alt+B', 'Barcode box'], ['Alt+I', 'Item name search (also accepts barcodes)'], ['F2', 'Change quantity'], ['F4', 'Remove item'], ['F5', 'Express Pay (cash, exact)'], ['F8', 'Pay Now / OK'], ['F9', 'Find / add customer'], ['F6', 'Hold invoice'], ['F7', 'Pick held invoice'], ['F10', 'Cancel invoice'], ['F11', 'Estimate (Quotation)'], ['Alt+F11', 'Save & print estimate'], ['F12', 'Offer details'], ['+ / −', 'Quantity of selected line'], ['↑ ↓', 'Move between lines'], ['Esc', 'Close dialog']]

const fmt = n => (+n || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
function offerFor(l) {
  let best = null
  for (const o of offerList.value) { const t = o.field === 'item_code' ? l.code : l.group; if (o.targets.includes(t) && (+l.qty || 0) >= (o.min_qty || 0) && (!best || o.discount > best.discount)) best = o }
  return best
}
const effDisc = l => Math.max(+l.disc || 0, offerFor(l)?.discount || 0)
const amt = l => r2(l.rate * (+l.qty || 0) * (1 - effDisc(l) / 100))
const custLabel = computed(() => customer.value ? customer.value.customer_name + (customer.value.outstanding ? ` (owes ₹${fmt(customer.value.outstanding)})` : '') : '')
const retEstimate = computed(() => retBill.value ? retBill.value.items.reduce((s, i) => s + (+retQty.value[i.code] || 0) * i.rate, 0) : 0)
const netTotal = computed(() => r2(lines.value.reduce((s, l) => s + amt(l), 0)))
const payable = computed(() => Math.round(netTotal.value))
const totQty = computed(() => r2(lines.value.reduce((s, l) => s + (+l.qty || 0), 0)))
const discount = computed(() => r2(lines.value.reduce((s, l) => s + l.mrp * (+l.qty || 0), 0) - netTotal.value))
const taxRows = computed(() => { const m = {}; lines.value.forEach(l => { const g = amt(l), t = g - g / (1 + l.gst / 100); (m[l.gst] ||= { rate: l.gst, taxable: 0, tax: 0, gross: 0 }); m[l.gst].taxable += g - t; m[l.gst].tax += t; m[l.gst].gross += g }); return Object.values(m).sort((a, b) => a.rate - b.rate) })

function toast(t) { toastMsg.value = t; clearTimeout(toast._t); toast._t = setTimeout(() => toastMsg.value = '', 2200) }
function later(n, what) { toast(`${what} arrives in section ${n}`) }
function focusBc() { nextTick(() => document.getElementById('bc')?.focus()) }
function close() { clearInterval(qrTimer); if (dlg.value === 'pay') { qr.value = null; qrPaid.value = false }
  if (dlg.value === 'shiftOpen' && boot.value?.require_shift && !boot.value.shift) return; dlg.value = null; err.value = ''; focusBc() }

function add(m) {
  if (!m) return
  const i = lines.value.findIndex(l => l.code === m.code)
  if (i >= 0) { lines.value[i].qty = r2(+lines.value[i].qty + 1); sel.value = i }
  else { lines.value.push({ ...m, qty: 1, disc: 0 }); sel.value = lines.value.length - 1 }
  if (m.stock <= 0) toast(`${m.name}: ERPNext shows no stock in this shop`)
  q.value = ''; matches.value = []; hi.value = 0; focusBc()
}
async function scan() {
  const code = bc.value.trim(); if (!code) return
  try { const r = online.value ? await call('search_items', { txt: code }).catch(e => { if (e.offline) { online.value = false; return localSearch(code) } throw e }) : localSearch(code); if (r.length === 1) add(r[0]); else if (boot.value.warn_not_found) { info.value = `No item with barcode ${code} in this store. Check the packet, or add the item through GRN.`; dlg.value = 'info' } else toast('Not found: ' + code) }
  catch (e) { toast(e.message) }
  bc.value = ''
}
let tSearch
function search() {
  clearTimeout(tSearch); const t = q.value.trim(); if (!t) { matches.value = []; return }
  tSearch = setTimeout(async () => { try { matches.value = online.value ? await call('search_items', { txt: t }) : localSearch(t); hi.value = 0 } catch (e) { if (e.offline) { online.value = false; matches.value = localSearch(t) } else toast(e.message) } }, 180)
}
async function nameEnter() {
  const t = q.value.trim()
  if (boot.value.barcode_in_name && /^\d{6,14}$/.test(t)) { bc.value = t; q.value = ''; return scan() }  // barcode scanned into Item Name
  if (matches.value.length) add(matches.value[hi.value])
}
async function refreshLines() {
  for (const l of lines.value) { try { const [m] = await call('search_items', { txt: l.code }); if (m) Object.assign(l, { rate: m.rate, mrp: m.mrp, stock: m.stock, gst: m.gst }) } catch (e) {} }
  toast('Prices and stock refreshed from ERPNext')
}
function focusQty() { if (lines.value.length) nextTick(() => { const e = document.getElementById('qty' + sel.value); e && (e.focus(), e.select()) }) }
function removeLine() { if (!lines.value.length) return; toast('Removed ' + lines.value[sel.value].name); lines.value.splice(sel.value, 1); sel.value = Math.max(0, sel.value - 1) }
function showStock() { dlg.value = 'stock' }
function askCancel() { if (lines.value.length) dlg.value = 'cancel' }
function clearBill() { lines.value = []; customer.value = null; sel.value = 0; heldName.value = null; pin.value = ''; billId.value = crypto.randomUUID() }

function pay(express) {
  if (!lines.value.length) return toast('Add items first')
  if (lines.value.some(l => !(+l.qty > 0))) return toast('Fix lines with zero quantity')
  if (boot.value.require_shift && !boot.value.shift) { dlg.value = 'shiftOpen'; return }
  if (lines.value.some(l => +l.disc > boot.value.max_manager_discount)) return toast(`Discount cannot be more than ${boot.value.max_manager_discount}%`)
  if (lines.value.some(l => +l.disc > boot.value.max_discount) && !pin.value) return askPin(`Discount above ${boot.value.max_discount}% needs the manager.`, () => pay(express))
  mode.value = 'Cash'; received.value = payable.value; err.value = ''
  if (express) return finish()
  dlg.value = 'pay'; nextTick(() => { const e = document.getElementById('rcv'); e && (e.focus(), e.select()) })
}
async function finish() {
  if (busy.value) return
  if (mode.value === 'Cash' && received.value < payable.value) { err.value = 'Received amount is less than the final total.'; return }
  if (mode.value === 'Credit' && !customer.value) { err.value = 'Choose a named customer for a credit (udhaar) bill (F9).'; return }
  const amount = mode.value === 'Cash' ? received.value : mode.value === 'Credit' ? 0 : payable.value
  if (mode.value === 'UPI' && boot.value.razorpay && online.value && !qrPaid.value) { err.value = qr.value ? 'Wait for the UPI payment to arrive.' : 'Press "Show UPI QR" first.'; return }
  if (!online.value) return queueBill(amount)
  busy.value = true; err.value = ''
  try {
    const r = await call('submit_invoice', { uuid: billId.value, items: lines.value.map(l => ({ code: l.code, qty: +l.qty, disc: +l.disc || 0 })), payments: [{ mode: mode.value, amount, qr_id: qr.value?.id }], customer: customer.value?.name || null, sales_executive: exec.value, manager_pin: pin.value || null, held_bill: heldName.value }, { post: true })
    last.value = r; lastBill.value = r.name; clearBill(); qr.value = null; qrPaid.value = false
    dlg.value = 'receipt'; nextTick(() => document.querySelector('.dlg .gbtn')?.focus())
  } catch (e) { if (e.offline) { online.value = false; busy.value = false; return queueBill(amount) } if (/PIN/i.test(e.message)) pin.value = ''; err.value = e.message; if (!dlg.value) { info.value = e.message; dlg.value = 'info' } }
  finally { busy.value = false }
}
const receiptText = computed(() => {
  const r = last.value; if (!r) return ''
  const w = 40, pad = (a, b) => a + ' '.repeat(Math.max(1, w - a.length - String(b).length)) + b, ln = '-'.repeat(w), s = boot.value.shop
  return [`         ${s.name.toUpperCase()}`, `  ${s.address}`, s.gstin ? `       GSTIN ${s.gstin}` : '', r.is_return ? '        CREDIT NOTE (RETURN)' : r.credit ? '      TAX INVOICE - CREDIT' : '             TAX INVOICE', ln, r.is_return ? 'Against: ' + r.return_against : '',
    pad('Bill: ' + r.name, r.posting_date), pad('Time: ' + r.posting_time, 'Customer: ' + r.customer), ln,
    ...r.items.map(i => pad(i.name.slice(0, 24) + ' ' + i.qty + 'x' + i.rate, i.amount.toFixed(2))), ln,
    pad('Taxable value', r.net_total.toFixed(2)), ...Object.entries(r.taxes).map(([k, v]) => pad(k.slice(0, 26), v.toFixed(2))),
    pad('Round off', (r.rounding_adjustment || 0).toFixed(2)), pad('TOTAL', 'Rs ' + r.rounded_total.toFixed(2)),
    ...(r.is_return ? [] : r.payments.map(p => pad('Paid (' + p.mode + ')', 'Rs ' + p.amount.toFixed(2)))), r.is_return ? pad('Refunded (Cash)', 'Rs ' + Math.abs(r.rounded_total).toFixed(2)) : r.credit ? pad('Udhaar outstanding', 'Rs ' + r.outstanding.toFixed(2)) : pad('Returned', 'Rs ' + (r.change || 0).toFixed(2)),
    r.saved > 0 ? pad('You saved', 'Rs ' + r.saved.toFixed(2)) : '', ln, '   Order online: JALGO - Everything. Just Go.'].filter(Boolean).join('\n')
})

function askPin(why, next) { pinWhy.value = why; pinIn.value = ''; pinNext.value = next; dlg.value = 'pin'; nextTick(() => document.getElementById('pin')?.focus()) }
function pinOk() { if (!pinIn.value) return; pin.value = pinIn.value; const n = pinNext.value; dlg.value = null; n && n() }

async function doOpenShift() {
  try { boot.value.shift = await call('open_shift', { opening_cash: +openingCash.value || 0 }, { post: true }); dlg.value = null; toast('Shift opened'); focusBc() } catch (e) { err.value = e.message }
}
async function openCloseShift() {
  if (!boot.value.shift) { err.value = ''; dlg.value = 'shiftOpen'; return }
  try { shiftSum.value = await call('shift_summary'); countedCash.value = shiftSum.value.expected_cash; err.value = ''; dlg.value = 'shiftClose' } catch (e) { toast(e.message) }
}
async function doCloseShift() {
  try { const s = await call('close_shift', { counted_cash: +countedCash.value || 0 }, { post: true }); boot.value.shift = null
    info.value = `Shift ${s.name} closed. Expected ₹${fmt(s.expected_cash)}, counted ₹${fmt(s.counted_cash)}, difference ₹${fmt(s.difference)}.`; dlg.value = 'info' } catch (e) { err.value = e.message }
}

let tCust
async function openCust() { cq.value = ''; err.value = ''; newCust.value = { name: '', mobile: '' }; dlg.value = 'cust'; await loadCust(); nextTick(() => document.getElementById('cq')?.focus()) }
async function loadCust() { try { custRows.value = await call('customers', { txt: cq.value }) } catch (e) { err.value = e.message } }
function searchCust() { clearTimeout(tCust); tCust = setTimeout(loadCust, 200) }
function pickCust(c) { customer.value = c; close() }
async function addCust() {
  try { const c = await call('create_customer', { customer_name: newCust.value.name, mobile_no: newCust.value.mobile }, { post: true }); pickCust(c); toast('Customer added in ERPNext') } catch (e) { err.value = e.message }
}

async function holdBill() {
  if (!lines.value.length) return toast('Nothing to hold')
  try { await call('hold_bill', { lines: lines.value.map(l => ({ code: l.code, qty: l.qty, disc: l.disc })), customer: customer.value?.name || '', sales_executive: exec.value, total: payable.value, name: heldName.value }, { post: true })
    clearBill(); toast('Invoice held. Press F7 to pick it up.') } catch (e) { toast(e.message) }
}
async function openHeld() { try { heldList.value = await call('held_bills'); dlg.value = 'held' } catch (e) { toast(e.message) } }
async function recall(name) {
  if (lines.value.length) return toast('Hold or finish the current invoice first')
  try { const r = await call('recall_bill', { name }); lines.value = r.lines; heldName.value = r.name; exec.value = r.sales_executive || ''
    customer.value = r.customer ? { name: r.customer, customer_name: r.customer } : null; sel.value = 0; close(); toast('Held invoice picked. Prices refreshed from ERPNext.') } catch (e) { toast(e.message) }
}
async function discardHeld(name) { try { await call('discard_held', { name }, { post: true }); heldList.value = heldList.value.filter(h => h.name !== name); if (heldName.value === name) heldName.value = null } catch (e) { toast(e.message) } }

async function openOffers() { try { offerList.value = await call('offers', { codes: lines.value.map(l => l.code) }); dlg.value = 'offers' } catch (e) { toast(e.message) } }

async function estimate(print) {
  if (!lines.value.length) return toast('Add items first')
  if (lines.value.some(l => +l.disc > boot.value.max_discount) && !pin.value) return askPin(`Discount above ${boot.value.max_discount}% needs the manager.`, () => estimate(print))
  try { est.value = await call('save_estimate', { items: lines.value.map(l => ({ code: l.code, qty: +l.qty, disc: +l.disc || 0 })), customer: customer.value?.name || null, manager_pin: pin.value || null }, { post: true })
    print ? dlg.value = 'estimate' : toast(`Estimate saved as Quotation ${est.value.name}`) } catch (e) { info.value = e.message; dlg.value = 'info' }
}
const estimateText = computed(() => {
  const r = est.value; if (!r) return ''
  const w = 40, pad = (a, b) => a + ' '.repeat(Math.max(1, w - a.length - String(b).length)) + b, ln = '-'.repeat(w)
  return [`         ${boot.value.shop.name.toUpperCase()}`, '        ESTIMATE (NOT A BILL)', ln, pad('Quotation: ' + r.name, 'Valid till ' + r.valid_till), 'Customer: ' + r.customer, ln,
    ...r.items.map(i => pad(i.name.slice(0, 24) + ' ' + i.qty + 'x' + i.rate, i.amount.toFixed(2))), ln, pad('Taxable value', r.net_total.toFixed(2)),
    ...Object.entries(r.taxes).map(([k, v]) => pad(k.slice(0, 26), (+v).toFixed(2))), pad('ESTIMATED TOTAL', 'Rs ' + r.rounded_total.toFixed(2)), ln, 'Prices may change after the validity date.'].join('\n')
})

function openReturn() { retNo.value = lastBill.value || ''; retBill.value = null; retQty.value = {}; pinIn.value = ''; err.value = ''; dlg.value = 'return'; nextTick(() => document.getElementById('rn')?.focus()) }
async function findBill() { err.value = ''; try { retBill.value = await call('find_bill', { name: retNo.value.trim() }); retQty.value = {} } catch (e) { retBill.value = null; err.value = e.message } }
async function doReturn() {
  if (busy.value) return; busy.value = true; err.value = ''
  try { const r = await call('submit_return', { name: retBill.value.name, items: Object.entries(retQty.value).map(([code, qty]) => ({ code, qty })), manager_pin: pinIn.value, uuid: crypto.randomUUID() }, { post: true })
    last.value = r; dlg.value = 'receipt' } catch (e) { err.value = e.message } finally { busy.value = false }
}

function queueBill(amount) {
  if (mode.value === 'Credit' || pin.value || heldName.value) { err.value = 'Offline: only plain Cash, UPI or Card bills can be saved. Credit, PIN discounts and held bills need the connection.'; return }
  const at = new Date(), stamp = at.getFullYear() + '-' + String(at.getMonth() + 1).padStart(2, '0') + '-' + String(at.getDate()).padStart(2, '0') + ' ' + at.toTimeString().slice(0, 8)
  const args = { uuid: billId.value, items: lines.value.map(l => ({ code: l.code, qty: +l.qty, disc: +l.disc || 0 })), payments: [{ mode: mode.value, amount }], customer: customer.value?.name || null, sales_executive: exec.value, offline_at: stamp }
  queue.value.push(args); saveLS('jalgo_pos_queue', queue.value)
  const items = lines.value.map(l => ({ name: l.name, qty: l.qty, rate: l.rate, amount: amt(l) }))
  last.value = { offline: true, name: 'OFFLINE-' + billId.value.slice(0, 8), posting_date: stamp.slice(0, 10), posting_time: stamp.slice(11, 16), customer: customer.value?.customer_name || 'Walk-in Customer', items,
    net_total: netTotal.value, taxes: {}, rounding_adjustment: payable.value - netTotal.value, rounded_total: payable.value, payments: [{ mode: mode.value, amount }], change: Math.max(0, amount - payable.value), saved: discount.value }
  clearBill(); dlg.value = 'receipt'
}
let syncing = false
async function syncQueue() {
  if (syncing || !queue.value.length) return; syncing = true
  try {
    for (const b of [...queue.value]) {
      try { await call('submit_invoice', b, { post: true }); queue.value = queue.value.filter(x => x.uuid !== b.uuid); online.value = true }
      catch (e) { if (e.offline) { online.value = false; break } b.error = e.message; toast('Offline bill could not sync: ' + e.message) }
      saveLS('jalgo_pos_queue', queue.value)
    }
  } finally { syncing = false }
}
let qrTimer
async function makeQr() {
  err.value = ''
  try { qr.value = await call('create_upi_qr', { amount: payable.value, bill_uuid: billId.value }, { post: true, ns: 'payments' }); qrPaid.value = false
    clearInterval(qrTimer); qrTimer = setInterval(async () => { const s = await call('qr_status', { qr_id: qr.value.id }, { ns: 'payments' }).catch(() => ({})); if (s.status === 'paid') { qrPaid.value = true; clearInterval(qrTimer); finish() } }, 2000)
  } catch (e) { err.value = e.message }
}

function printText(text) {
  const w = window.open('', '_blank', 'width=420,height=700'); if (!w) return toast('Allow pop-ups to print')
  const esc = s => s.replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]))
  w.document.write(`<!doctype html><html><head><meta charset="utf-8"><title>Receipt</title><style>@page{size:80mm auto;margin:3mm}body{margin:0}pre{font:11px/1.35 monospace;margin:0;white-space:pre}</style></head><body><pre>${esc(text)}</pre><script>window.onload=()=>{window.print();setTimeout(()=>window.close(),300)}<\/script></body></html>`)
  w.document.close()
}

function onKey(e) {
  const k = e.key
  if (dlg.value) {
    if (k === 'Escape') { e.preventDefault(); close() }
    else if ((k === 'p' || k === 'P') && dlg.value === 'receipt' && e.target.tagName !== 'INPUT') { e.preventDefault(); printText(receiptText.value) }
    else if (k === 'F8' && dlg.value === 'pay') { e.preventDefault(); finish() }
    else if (e.ctrlKey && k.toLowerCase() === 'p' && dlg.value === 'pay') { e.preventDefault(); received.value = payable.value }
    return
  }
  if (setup.value) { if (k === 'Escape') { e.preventDefault(); setup.value = false; focusBc() } return }
  if (e.altKey && k === 'F11') { e.preventDefault(); estimate(true); return }
  if (e.altKey && ['b', 'i'].includes(k.toLowerCase())) { e.preventDefault(); document.getElementById(k.toLowerCase() === 'b' ? 'bc' : 'q').focus(); return }
  const map = { F1: () => dlg.value = 'help', F2: focusQty, F4: removeLine, F5: () => pay(true), F8: () => pay(false), F9: openCust, F10: askCancel, F6: holdBill, F7: openHeld, F11: () => estimate(false), F12: openOffers }
  if (map[k]) { e.preventDefault(); map[k](); return }
  const inInput = e.target.tagName === 'INPUT' && !(e.target.id === 'bc' && !bc.value)
  if (!inInput && lines.value.length) {
    if (k === 'ArrowDown') { e.preventDefault(); sel.value = Math.min(sel.value + 1, lines.value.length - 1) }
    if (k === 'ArrowUp') { e.preventDefault(); sel.value = Math.max(sel.value - 1, 0) }
    if (k === '+' || k === '=') { e.preventDefault(); lines.value[sel.value].qty = r2(+lines.value[sel.value].qty + 1) }
    if (k === '-' && lines.value[sel.value].qty > 1) { e.preventDefault(); lines.value[sel.value].qty = r2(lines.value[sel.value].qty - 1) }
  }
}

onMounted(async () => {
  window.addEventListener('online', () => { online.value = true; syncQueue() }); window.addEventListener('offline', () => online.value = false)
  setInterval(() => { if (navigator.onLine) syncQueue() }, 20000)
  window.addEventListener('keydown', e => { if (!e.target.closest || !e.target.closest('.wrap')) onKey(e) })
  try { boot.value = await call('bootstrap'); focusBc()
    call('offers', { codes: [] }).then(o => offerList.value = o).catch(() => {})
    call('catalog').then(c => { catalog.value = c.items; saveLS('jalgo_pos_catalog', c) }).catch(() => {})
    syncQueue()
    if (boot.value.require_shift && !boot.value.shift) dlg.value = 'shiftOpen' }
  catch (e) { bootErr.value = e.status === 403 ? 'Please log in to ERPNext first.' : e.message }
})
</script>
