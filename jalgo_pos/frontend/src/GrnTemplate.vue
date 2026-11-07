<template>
<div class="scrim" style="z-index:18;padding:10px">
 <div class="mgwin gtwin" role="dialog" aria-modal="true">
  <div class="title"><i>S</i>Item Entry by Template<button class="x" style="margin-left:auto;width:40px;border:0;border-radius:8px;background:rgba(255,255,255,.12);color:#fff;height:28px" @click="$emit('close')" aria-label="Close">✕</button></div>
  <div class="gtbody" v-if="!result">
   <div class="gthead">
    <label>Business Location<select v-model="f.warehouse"><option v-for="l in locs" :key="l.name" :value="l.name">{{ l.label }}</option></select></label>
    <label>Supplier<select v-model="f.supplier"><option v-for="s in suppliers" :key="s" :value="s">{{ s }}</option></select></label>
    <label>Supplier Invoice No.<input v-model="f.inv" placeholder="e.g. PS/2611/0912"></label>
    <label>Supplier Invoice Date<input type="date" v-model="f.invDate"></label>
    <label>Category for New Item<select v-model="f.group"><option v-for="g in groups" :key="g">{{ g }}</option></select></label>
    <label>Specify Quantity By<div class="inl"><select v-model="f.attr" @change="rows.forEach(r=>r.q={})"><option v-for="(v,k) in attrs" :key="k">{{ k }}</option></select><button class="dots" title="Item fields" @click="fields=true">…</button></div></label>
    <label>Discount on bill %<input type="number" min="0" v-model.number="f.disc"></label>
    <div class="radio"><label><input type="radio" value="basic" v-model="f.basis"> Basic Price</label><label><input type="radio" value="incl" v-model="f.basis"> After Tax</label></div>
   </div>
   <div class="gtgrid"><table class="tbl2 rt mx"><thead><tr><th>#</th><th style="min-width:200px">Item Name</th><th v-for="v in values" :key="v" class="r">{{ v }}</th><th class="r">Total Qty</th><th class="r">Purchase ₹/unit</th><th class="r">Sales ₹</th><th class="r">MRP ₹</th><th class="r">GST %</th><th>HSN</th><th class="r">Amount</th><th></th></tr></thead>
    <tbody><tr v-for="(r,i) in rows" :key="i">
     <td>{{ i+1 }}</td><td><input class="cell wide" v-model="r.name" placeholder="Product name, e.g. Lay's Chips 50g"></td>
     <td v-for="v in values" :key="v" class="r"><input class="cell qcell" type="number" min="0" v-model.number="r.q[v]" :class="{has:r.q[v]>0}"></td>
     <td class="r num"><b>{{ rq(r) }}</b></td>
     <td class="r"><input class="cell" type="number" v-model.number="r.cost"></td><td class="r"><input class="cell" type="number" v-model.number="r.sale"></td><td class="r"><input class="cell" type="number" v-model.number="r.mrp"></td>
     <td class="r"><select class="cell" v-model.number="r.gst"><option v-for="g in [0,5,12,18,28,40]" :key="g" :value="g">{{ g }}</option></select></td>
     <td><input class="cell" style="width:90px;text-align:left" v-model="r.hsn" placeholder="auto"></td>
     <td class="r num">{{ fmt(rq(r) * (+r.cost || 0)) }}</td><td><button class="dots" @click="rows.splice(i,1)" aria-label="Remove row">✕</button></td></tr></tbody></table>
    <button class="btn" style="margin:8px" @click="addRow">+ Add item row</button>
    <p class="gtnote">Each filled cell becomes its own ERPNext item (a variant of the product), named like <b>{{ (rows.find(r=>r.name)||{name:'Product'}).name }} - {{ values[0] || 'Value' }}</b>, with barcode, price and MRP. Use one row per price: if 1 kg and 5 kg cost differently, put them on separate rows. HSN "auto" uses the code most common in the category.</p>
   </div>
   <div class="gtfoot">
    <div class="kvs"><span>Total Quantity</span><b class="num">{{ totQty }}</b><span>Manager PIN</span><input type="password" inputmode="numeric" v-model="pin" placeholder="if you are not a manager"></div>
    <div class="kvs"><span>Sub Total</span><b class="num">₹{{ fmt(sub) }}</b><span>Discount</span><b class="num">₹{{ fmt(sub * (+f.disc||0) / 100) }}</b><span>GST</span><b class="num">calculated by ERPNext</b></div>
    <div class="gtt"><span>Before tax (approx.)</span><b class="num">₹{{ fmt(sub * (1 - (+f.disc||0) / 100)) }}</b></div>
   </div>
   <p class="err" v-if="err">{{ err }}</p>
  </div>
  <div class="gtbody" v-else>
   <h3 style="margin:0">{{ result.name }} · {{ result.status }}</h3>
   <p>{{ result.qty }} units · Grand total ₹{{ fmt(result.grand_total) }} (GST ₹{{ fmt(result.taxes) }}) · into {{ result.warehouse }}</p>
   <table class="tbl2 rt"><thead><tr><th>Item</th><th>Code</th><th class="r">Qty</th><th class="r">Sale ₹</th></tr></thead>
    <tbody><tr v-for="x in result.items" :key="x.code"><td>{{ x.name }}</td><td class="num">{{ x.code }}</td><td class="r num">{{ x.qty }}</td><td class="r num">{{ x.sale }}</td></tr></tbody></table>
   <p class="erp">{{ result.status.startsWith('Held') ? 'Saved as a draft Purchase Receipt. Submit it in ERPNext when the goods are checked.' : 'Stock is added. The new items can be billed at the counter now.' }} <a :href="'/app/purchase-receipt/'+result.name" target="_blank" rel="noopener">Open in ERPNext ↗</a></p>
  </div>
  <div class="mgfoot">
   <span class="erp" v-if="!result">Creates: item template + variants ({{ f.attr }}) → Purchase Receipt into {{ (locs.find(l=>l.name===f.warehouse)||{}).label }}</span><span style="flex:1"></span>
   <template v-if="!result"><button class="gk" @click="rows=[];addRow()">Clear</button><button class="pk" :disabled="busy" @click="save(1)">Hold</button><button class="gbtn" :disabled="busy" @click="save(0)">{{ busy ? 'Saving…' : 'Save (F10)' }}</button></template>
   <button class="gk" @click="$emit('close', !!result)">{{ result ? 'Done' : 'Cancel' }}</button>
  </div>
 </div>
 <div class="scrim" v-if="fields" style="z-index:19" @click.self="fields=false">
  <div class="dlg" style="width:min(560px,100%)"><div class="title"><i>S</i>Item Fields<button class="x" @click="fields=false">✕</button></div>
   <div class="in">
    <p style="margin:0 0 8px;font-size:12.5px">These are ERPNext <b>Item Attributes</b>. Their values become the quantity columns.</p>
    <table class="tbl2 rt"><tbody><tr v-for="(v,k) in attrs" :key="k"><td><b>{{ k }}</b></td><td>{{ v.join(', ') }}</td></tr></tbody></table>
    <div class="rowd" style="grid-template-columns:1fr 2fr auto;margin-top:10px"><input id="af" class="cell wide" v-model="nf.name" placeholder="Field, e.g. Pack Size"><input id="av" class="cell wide" v-model="nf.values" placeholder="Values, comma separated: 500 g, 1 kg, 5 kg"><button class="gbtn" @click="saveField">Save</button></div>
    <p class="err" v-if="ferr">{{ ferr }}</p>
    <div class="dlgbtns"><button class="gbtn" @click="fields=false">Close</button></div>
   </div></div>
 </div>
</div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { call } from './api'
const emit = defineEmits(['close'])
const S = { ns: 'stock' }
const attrs = ref({}), locs = ref([]), suppliers = ref([]), groups = ref([])
const today = new Date().toISOString().slice(0, 10)
const f = ref({ warehouse: '', supplier: '', inv: '', invDate: today, group: 'Snacks & Biscuits', attr: 'Flavour', disc: 0, basis: 'basic' })
const rows = ref([]), pin = ref(''), err = ref(''), busy = ref(false), result = ref(null), fields = ref(false), nf = ref({ name: '', values: '' }), ferr = ref('')
const values = computed(() => attrs.value[f.value.attr] || [])
const rq = r => Object.values(r.q).reduce((s, x) => s + (+x || 0), 0)
const totQty = computed(() => rows.value.reduce((s, r) => s + rq(r), 0))
const sub = computed(() => rows.value.reduce((s, r) => s + rq(r) * (+r.cost || 0), 0))
const fmt = n => (+n || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
function addRow() { rows.value.push({ name: '', q: {}, cost: 0, sale: 0, mrp: 0, gst: 5, hsn: '' }) }

async function save(hold) {
  busy.value = true; err.value = ''
  try {
    result.value = await call('grn_by_template', { supplier: f.value.supplier, attribute: f.value.attr, warehouse: f.value.warehouse, supplier_invoice: f.value.inv,
      invoice_date: f.value.invDate, item_group: f.value.group, price_basis: f.value.basis, discount: f.value.disc, hold,
      rows: rows.value.filter(r => r.name && rq(r) > 0).map(r => ({ ...r, q: Object.fromEntries(Object.entries(r.q).filter(([, x]) => +x > 0)) })), pin: pin.value || null }, { post: true, ...S })
  } catch (e) { err.value = e.message } finally { busy.value = false }
}
async function saveField() {
  ferr.value = ''
  try { attrs.value = await call('save_attribute', { name: nf.value.name, values: nf.value.values.split(','), pin: pin.value || null }, { post: true, ...S }); f.value.attr = nf.value.name.trim(); nf.value = { name: '', values: '' } }
  catch (e) { ferr.value = e.message }
}
onMounted(async () => {
  try {
    const [a, l, s, g] = await Promise.all([call('attributes', {}, S), call('locations', {}, S), call('module_list', { module: 'Suppliers' }, { ns: 'backoffice' }), call('module_list', { module: 'Items' }, { ns: 'backoffice' })])
    attrs.value = a; locs.value = l; suppliers.value = s.rows.map(r => r[0]); groups.value = [...new Set(g.rows.map(r => r[2]))].sort()
    f.value.warehouse = (l.find(x => /Mundade|Shubhendra/.test(x.name)) || l[0] || {}).name; f.value.supplier = suppliers.value[0]
    if (!a.Flavour) f.value.attr = Object.keys(a)[0] || ''
    rows.value = [{ name: "Lay's Potato Chips 50g", q: { Classic: 48, Masala: 96 }, cost: 16.5, sale: 20, mrp: 20, gst: 5, hsn: '' }]
    if (!a.Flavour) rows.value[0].q = {}
  } catch (e) { err.value = e.message }
})
window.addEventListener('keydown', e => { if (e.key === 'F10' && !result.value && document.querySelector('.gtwin')) { e.preventDefault(); save(0) } })
</script>
