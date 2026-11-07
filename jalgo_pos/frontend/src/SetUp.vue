<template>
<div class="scrim" style="padding:10px;z-index:15">
 <div class="mgwin" role="dialog" aria-modal="true">
  <div class="title"><i>S</i>{{ reo ? 'Setup Button Reorder Manager' : 'Manage ' + mod }}<button class="x" style="margin-left:auto;width:40px;border:0;border-radius:8px;background:rgba(255,255,255,.12);color:#fff;height:28px" @click="$emit('close')" aria-label="Close">✕</button></div>
  <div class="mgbody">
   <nav class="mods">
    <div class="modtop"><button class="mini" :class="{ron:reo}" title="Setup Button Reorder Manager" @click="startReorder">🔀</button></div>
    <div class="modgrid">
     <button v-for="(m,mi) in (reo ? reo.list : modules)" :key="m.n" :class="['mod',{on:!reo&&mod===m.n,drag:reo,over:reo&&reo.over===mi}]" :draggable="!!reo"
       @dragstart="e=>{reo.from=mi;e.dataTransfer.effectAllowed='move'}" @dragover.prevent="reo&&(reo.over=mi)" @dragleave="reo&&(reo.over=null)" @drop.prevent="e=>dropMod(e,mi)"
       @click="!reo && pick(m.n)"><span class="tile" :style="'background:'+m.c">{{ m.i }}</span><span>{{ m.n }}</span></button>
    </div>
   </nav>

   <section class="mgmain">
    <!-- reorder -->
    <div class="mgpanel" v-if="reo">
     <h3>Setup Button Reorder Manager</h3>
     <p>Drag a button on the left and drop it on another. Hold <kbd>Alt</kbd> to interchange or <kbd>Shift</kbd> to insert, or choose below. The order is saved for your login.</p>
     <div class="radio" style="margin:10px 0"><b style="margin-right:8px">Move action</b><label><input type="radio" value="swap" v-model="reo.mode"> Interchange (Alt)</label><label><input type="radio" value="insert" v-model="reo.mode"> Insert (Shift)</label></div>
     <ol class="reolist"><li v-for="m in reo.list" :key="m.n">{{ m.i }} {{ m.n }}</li></ol>
     <div class="dlgbtns" style="justify-content:flex-start"><button class="gbtn" @click="saveReorder">Save</button><button class="gbtn" @click="reo.list=[...DEFAULT]">Reset to default</button><button class="gbtn" @click="reo=null">Cancel</button></div>
    </div>

    <!-- dashboard -->
    <div class="mgpanel" v-else-if="mod==='DashBoard'">
     <h3>Today at {{ boot.shop.name }}</h3>
     <div v-if="dash" class="dashgrid">
      <div class="dcard"><span>Bills</span><b>{{ dash.bills }}</b></div><div class="dcard"><span>Sales</span><b>₹{{ fmt(dash.sales) }}</b></div>
      <div class="dcard"><span>Average bill</span><b>₹{{ fmt(dash.avg_bill) }}</b></div><div class="dcard"><span>Returns</span><b>₹{{ fmt(dash.returns) }}</b></div>
      <div class="dcard"><span>On credit (udhaar)</span><b>₹{{ fmt(dash.credit) }}</b></div>
     </div>
     <div class="dash2" v-if="dash">
      <div><div class="lbl2">Top items today</div><table class="tbl2 rt"><thead><tr><th>Item</th><th class="r">Qty</th><th class="r">Sales ₹</th></tr></thead><tbody><tr v-for="t in dash.top" :key="t.item_name"><td>{{ t.item_name }}</td><td class="r num">{{ t.qty }}</td><td class="r num">{{ fmt(t.amt) }}</td></tr><tr v-if="!dash.top.length"><td colspan="3">No sales yet today.</td></tr></tbody></table></div>
      <div><div class="lbl2">Lowest stock in this shop</div><table class="tbl2 rt"><thead><tr><th>Item</th><th class="r">Qty</th></tr></thead><tbody><tr v-for="l in dash.low" :key="l.item_code"><td>{{ l.item_name }}</td><td class="r num">{{ l.actual_qty }}</td></tr></tbody></table></div>
      <div><div class="lbl2">Last 7 days</div><div class="bars7"><div v-for="w in dash.week" :key="w.d" class="bar7" :title="w.d+': ₹'+fmt(w.t)"><i :style="{height: Math.max(4, w.t / maxWeek * 100) + '%'}"></i><small>{{ w.d.slice(8) }}</small></div></div></div>
     </div>
     <p class="erp" v-else>Loading…</p>
    </div>

    <!-- reports -->
    <div class="mgsplit" v-else-if="mod==='Reports'">
     <div class="tree"><div class="tlbl">Report groups</div>
      <button v-for="g in Object.keys(catalog)" :key="g" :class="['node',{on:group===g}]" @click="group=g;rep=null">📁 {{ g }}</button></div>
     <div class="rlist">
      <div class="opts"><div class="radio"><label>From <input class="cell" type="date" v-model="from"></label><label>To <input class="cell" type="date" v-model="to"></label></div>
       <div class="srch"><button class="btn" v-if="rep" @click="rep=null">← All reports</button></div></div>
      <div class="rgrid" v-if="!rep"><table class="tbl2 rt"><thead><tr><th>Name</th><th>Runs ERPNext report</th></tr></thead>
       <tbody><tr v-for="r in (catalog[group]||[])" :key="r.name" @dblclick="run(r)" @click="run(r)"><td><b>{{ r.name }}</b> <span v-if="!r.allowed" class="live held">no access</span></td><td class="erp">{{ r.erp }}</td></tr></tbody></table></div>
      <div class="rgrid" v-else>
       <p class="erp" style="margin:8px">{{ rep.title }} · ERPNext <b>{{ rep.report }}</b> · {{ rep.rows.length }} of {{ rep.total }} rows · <a :href="'/app/query-report/'+encodeURIComponent(rep.report)" target="_blank" rel="noopener">open in ERPNext ↗</a></p>
       <table class="tbl2 rt"><thead><tr><th v-for="(c,i) in rep.cols" :key="i" :class="{r:rep.num[i]}">{{ c }}</th></tr></thead>
        <tbody><tr v-for="(row,j) in rep.rows" :key="j"><td v-for="(v,i) in row" :key="i" :class="{r:rep.num[i],num:rep.num[i]}">{{ rep.num[i] && v !== '' ? fmt(v) : v }}</td></tr>
         <tr v-if="!rep.rows.length"><td :colspan="rep.cols.length">No data for these dates.</td></tr></tbody></table>
      </div>
      <div class="cnt">{{ busy ? 'Running report…' : err }}</div>
     </div>
    </div>

    <div class="mgpanel" v-else-if="mod==='Barcode Printing'"><h3>Print Barcode Stickers</h3><Labels @toast="m=>$emit('toast',m)" /></div>
    <div class="mgpanel" v-else-if="mod==='Settings'"><h3>Invoice Settings</h3><p class="erp">Operations on the billing screen for this shop.</p><Settings @saved="v=>$emit('settings',v)" /></div>
    <!-- module list -->
    <div class="mgpanel" v-else>
     <div class="mghead"><h3>{{ mod }}</h3>
      <div class="srch"><input id="ms" class="cell wide" style="width:220px" v-model="txt" placeholder="Search" @input="debounced"><button class="btn" v-if="list" @click="openDesk('new')">+ New in ERPNext</button></div></div>
     <p class="erp">{{ info[mod] || '' }}</p>
     <p v-if="soon[mod]" class="callout2">{{ soon[mod] }}</p>
     <div class="grnbar" v-if="mod==='GRN'"><button class="gk" @click="grn=true">GRN by Template</button><button class="gk" @click="openDeskUrl('/app/purchase-receipt/new')">Normal GRN in ERPNext</button></div>
     <StockForm v-if="mod==='Transfer Stock'" kind="transfer" :boot="boot" @done="load" />
     <StockForm v-if="mod==='Manage Stock'" kind="wastage" :boot="boot" @done="load" />
     <StockForm v-if="mod==='Receive Payments' && list" kind="collect" :boot="boot" :rows="list.rows" @done="load" />
     <table class="tbl2 rt" v-if="list"><thead><tr><th v-for="l in list.labels" :key="l">{{ l }}</th></tr></thead>
      <tbody><tr v-for="(r,j) in list.rows" :key="j" @click="openDesk(r[0])" title="Open in ERPNext"><td v-for="(v,i) in r" :key="i" :class="{num:typeof v==='number',r:typeof v==='number'}">{{ typeof v === 'number' && !Number.isInteger(v) ? fmt(v) : (v ?? '') }}</td></tr>
       <tr v-if="!list.rows.length"><td :colspan="list.labels.length">Nothing found.</td></tr></tbody></table>
     <p class="erp" v-if="list">Showing {{ list.rows.length }} of {{ list.total }}. Click a row to open it in ERPNext. Live data.</p>
     <p class="cnt" v-if="busy">Loading…</p><p class="err" v-if="err">{{ err }}</p>
    </div>
   </section>
  </div>
  <div class="mgfoot">
   <button class="back" @click="$emit('close')" title="Back to billing">⇦</button>
   <button class="pk" @click="$emit('info','Backups run on the server every night (bench backup) and can be downloaded from ERPNext → Backups by the owner.')">Backup<br>Database</button>
   <button class="pk" @click="$emit('info','Restoring a backup replaces all data. Only the owner can do it, on the server, with the backup file.')">Restore<br>Database</button>
   <span style="flex:1"></span>
   <button class="gk" @click="pick('DashBoard')">DashBoard</button>
   <button class="gk" @click="$emit('close')">Go Back To<br>Main Screen</button>
   <button class="gk" @click="$emit('info','JALGO POS for Shubhendra Provision, running on ERPNext 16.')">About Us</button>
   <button class="gk" @click="openDeskUrl('/app/jalgo-pos-settings')">POS Settings</button>
  </div>
 </div>
 <GrnTemplate v-if="grn" @close="done=>{grn=false; if(done) load()}" />
</div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { call } from './api'
import GrnTemplate from './GrnTemplate.vue'
import StockForm from './StockForm.vue'
import Labels from './Labels.vue'
import Settings from './Settings.vue'

const props = defineProps({ boot: Object })
const emit = defineEmits(['close', 'info', 'toast', 'settings'])
const DEFAULT = [
  { n: 'Items', i: '🛒', c: 'linear-gradient(#FFD84D,#F2A100)' }, { n: 'GRN', i: '🚚', c: 'linear-gradient(#FFD84D,#F2A100)' },
  { n: 'Manage Stock', i: '📦', c: 'linear-gradient(#9FE3F2,#3FB7D6)' }, { n: 'Transfer Stock', i: '🔁', c: 'linear-gradient(#9FE3F2,#3FB7D6)' },
  { n: 'Cash Registers', i: '🧮', c: 'linear-gradient(#F5DDB8,#D9A866)' }, { n: 'Sales Invoices', i: '🧾', c: 'linear-gradient(#F5DDB8,#D9A866)' },
  { n: 'Customers', i: '👥', c: 'linear-gradient(#FFC4D6,#F07AA0)' }, { n: 'Receive Payments', i: '💰', c: 'linear-gradient(#C9C9C9,#8A8A8A)' },
  { n: 'Suppliers', i: '🏭', c: 'linear-gradient(#C9C9C9,#8A8A8A)' }, { n: 'Make Payments', i: '💸', c: 'linear-gradient(#C9C9C9,#8A8A8A)' },
  { n: 'Business Locations', i: '🏪', c: 'linear-gradient(#A9C8F5,#5B8FDB)' }, { n: 'Sales Returns', i: '↩️', c: 'linear-gradient(#A9C8F5,#5B8FDB)' },
  { n: 'Employees', i: '🧑', c: 'linear-gradient(#CFF28A,#7DC21E)' }, { n: 'Reports', i: '📜', c: 'linear-gradient(#F05050,#B3121E)' },
  { n: 'DashBoard', i: '📊', c: 'linear-gradient(#F05050,#B3121E)' }, { n: 'Barcode Printing', i: '🏷️', c: 'linear-gradient(#F05050,#B3121E)' },
  { n: 'Settings', i: '⚙️', c: 'linear-gradient(#C9C9C9,#7A7A7A)' },
]
const DOCTYPE_SLUG = { Item: 'item', Customer: 'customer', Supplier: 'supplier', 'Sales Invoice': 'sales-invoice', 'Purchase Receipt': 'purchase-receipt', 'Purchase Invoice': 'purchase-invoice', 'Stock Entry': 'stock-entry', 'JALGO POS Shift': 'jalgo-pos-shift', Warehouse: 'warehouse', User: 'user' }
const info = { Items: 'Products with price and stock in this shop.', GRN: 'Goods received from suppliers (Purchase Receipts).', 'Manage Stock': 'All stock movements: receipts, issues (wastage) and transfers.', 'Transfer Stock': 'Stock moved between the shop and the dark store.', 'Cash Registers': 'Cashier shifts with cash counts.', 'Receive Payments': 'Bills where money is still owed (udhaar).', 'Make Payments': 'Supplier bills still to be paid.', 'Business Locations': 'Warehouses and their stock value.', Employees: 'People who can log in.' }
const soon = {}

const grn = ref(false)
const modules = ref([...DEFAULT]), mod = ref('Reports'), list = ref(null), txt = ref(''), busy = ref(false), err = ref('')
const catalog = ref({}), group = ref('Sales'), rep = ref(null), dash = ref(null), reo = ref(null)
const today = new Date().toISOString().slice(0, 10)
const from = ref(today.slice(0, 8) + '01'), to = ref(today)
const fmt = n => (+n || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const maxWeek = computed(() => Math.max(1, ...(dash.value?.week || []).map(w => w.t)))

async function pick(n) {
  mod.value = n; list.value = null; err.value = ''; rep.value = null; txt.value = ''
  if (n === 'Reports') return
  if (n === 'DashBoard') { dash.value = null; try { dash.value = await call('dashboard', {}, { ns: 'backoffice' }) } catch (e) { err.value = e.message } return }
  if (n === 'Barcode Printing' || n === 'Settings') return
  load()
}
async function load() {
  busy.value = true; err.value = ''
  try { list.value = await call('module_list', { module: mod.value, txt: txt.value }, { ns: 'backoffice' }) } catch (e) { err.value = e.message; list.value = null }
  finally { busy.value = false }
}
let t; function debounced() { clearTimeout(t); t = setTimeout(load, 250) }
function openDeskUrl(u) { window.open(u, '_blank', 'noopener') }
function openDesk(name) { if (!list.value) return; const slug = DOCTYPE_SLUG[list.value.doctype]; openDeskUrl(`/app/${slug}/${encodeURIComponent(name)}`) }

async function run(r) {
  if (!r.allowed) { err.value = 'You do not have access to this report.'; return }
  busy.value = true; err.value = ''
  try { rep.value = { ...(await call('run_report', { name: r.name, from_date: from.value, to_date: to.value }, { ns: 'backoffice' })), title: r.name } }
  catch (e) { err.value = e.message } finally { busy.value = false }
}

function startReorder() { reo.value = { list: [...modules.value], from: null, over: null, mode: 'swap' } }
function dropMod(e, to) {
  const r = reo.value; if (!r || r.from == null) return
  const mode = e.altKey ? 'swap' : e.shiftKey ? 'insert' : r.mode, L = [...r.list]
  if (mode === 'swap') [L[r.from], L[to]] = [L[to], L[r.from]]; else { const [x] = L.splice(r.from, 1); L.splice(to, 0, x) }
  r.list = L; r.from = null; r.over = null
}
async function saveReorder() {
  try { await call('save_button_order', { order: reo.value.list.map(m => m.n) }, { post: true, ns: 'backoffice' }); modules.value = reo.value.list; reo.value = null; emit('toast', 'Set-Up button order saved for your login') }
  catch (e) { err.value = e.message }
}

onMounted(async () => {
  try {
    const [cat, order] = await Promise.all([call('report_catalog', {}, { ns: 'backoffice' }), call('get_button_order', {}, { ns: 'backoffice' })])
    catalog.value = cat
    if (order) { const by = Object.fromEntries(DEFAULT.map(m => [m.n, m])); modules.value = [...order.map(n => by[n]).filter(Boolean), ...DEFAULT.filter(m => !order.includes(m.n))] }
  } catch (e) { err.value = e.message }
})
</script>
