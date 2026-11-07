<template>
<div class="sform">
 <div class="lbl2">{{ kind === 'transfer' ? 'New stock transfer' : kind === 'wastage' ? 'Write off wastage / damage' : 'Collect udhaar (credit payment)' }}</div>
 <template v-if="kind !== 'collect'">
  <div class="srow">
   <label v-if="kind==='transfer'">To <select class="cell" style="width:auto" v-model="to"><option v-for="l in locs.filter(l=>l.name!==boot.warehouse)" :key="l.name" :value="l.name">{{ l.label }}</option></select></label>
   <label v-else>Reason <input class="cell wide" style="width:240px" v-model="reason" placeholder="e.g. spoiled tomatoes"></label>
   <div class="searchwrap" style="flex:1;min-width:220px"><input class="cell wide" v-model="q" placeholder="Add item: name or barcode" @input="search" @keydown.enter.prevent="addIt(found[0])">
    <div class="sugg" v-if="q&&found.length"><button v-for="m in found" :key="m.code" @mousedown.prevent="addIt(m)"><span class="num">{{ m.code }}</span><span>{{ m.name }}</span><b class="num">{{ m.stock }} here</b></button></div></div>
  </div>
  <table class="tbl2 rt" v-if="lines.length"><thead><tr><th>Item</th><th class="r">In this shop</th><th class="r">Qty</th><th></th></tr></thead>
   <tbody><tr v-for="(l,i) in lines" :key="l.code"><td>{{ l.name }}</td><td class="r num">{{ l.stock }}</td><td class="r"><input class="cell" type="number" min="0" v-model.number="l.qty" style="width:80px"></td><td><button class="dots" @click="lines.splice(i,1)">✕</button></td></tr></tbody></table>
 </template>
 <template v-else>
  <div class="srow">
   <label>Customer <select class="cell" style="width:auto" v-model="cust"><option v-for="c in debtors" :key="c.name" :value="c.name">{{ c.name }} · owes ₹{{ fmt(c.owed) }}</option></select></label>
   <label>Amount ₹ <input class="cell" type="number" v-model.number="amount" style="width:110px"></label>
   <label>Mode <select class="cell" style="width:auto" v-model="mode"><option>Cash</option><option>UPI</option><option>Card</option></select></label>
  </div>
  <p class="erp" v-if="!debtors.length">Nobody owes money right now.</p>
 </template>
 <div class="srow">
  <label v-if="kind!=='collect'">Manager PIN <input class="cell" type="password" inputmode="numeric" v-model="pin" style="width:100px" placeholder="if needed"></label>
  <button class="gbtn" :disabled="busy" @click="submit">{{ busy ? 'Saving…' : kind === 'transfer' ? 'Transfer stock' : kind === 'wastage' ? 'Write off' : 'Collect payment' }}</button>
  <span class="err" v-if="err">{{ err }}</span><span class="erp" v-if="ok">{{ ok }}</span>
 </div>
</div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { call } from './api'
const props = defineProps({ kind: String, boot: Object, rows: Array })
const emit = defineEmits(['done'])
const locs = ref([]), to = ref(''), reason = ref(''), q = ref(''), found = ref([]), lines = ref([]), pin = ref(''), err = ref(''), ok = ref(''), busy = ref(false)
const cust = ref(''), amount = ref(0), mode = ref('Cash')
const fmt = n => (+n || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const debtors = computed(() => { const m = {}; (props.rows || []).forEach(r => { m[r[2]] = (m[r[2]] || 0) + (+r[4] || 0) }); return Object.entries(m).map(([name, owed]) => ({ name: name, owed })) })
watch(debtors, d => { if (d.length && !cust.value) { cust.value = d[0].name; amount.value = d[0].owed } }, { immediate: true })
watch(cust, c => { const d = debtors.value.find(x => x.name === c); if (d) amount.value = d.owed })
let t; function search() { clearTimeout(t); t = setTimeout(async () => { found.value = q.value ? await call('search_items', { txt: q.value }).catch(() => []) : [] }, 200) }
function addIt(m) { if (!m) return; if (!lines.value.find(l => l.code === m.code)) lines.value.push({ ...m, qty: 1 }); q.value = ''; found.value = [] }
async function submit() {
  err.value = ''; ok.value = ''; busy.value = true
  try {
    let r
    const items = lines.value.map(l => ({ code: l.code, qty: +l.qty }))
    if (props.kind === 'transfer') r = await call('transfer', { to_warehouse: to.value, items, pin: pin.value || null }, { post: true, ns: 'stock' })
    else if (props.kind === 'wastage') r = await call('write_off', { items, reason: reason.value, pin: pin.value || null }, { post: true, ns: 'stock' })
    else {
      const name = (await call('customers', { txt: cust.value }))[0]?.name || cust.value
      r = await call('collect_payment', { customer: name, amount: amount.value, mode: mode.value }, { post: true, ns: 'stock' })
    }
    ok.value = props.kind === 'collect' ? `Saved ${r.name}. Still owed ₹${fmt(r.still_owed)}.` : `Saved ${r.name} (value ₹${fmt(r.value)}).`
    lines.value = []; reason.value = ''; emit('done')
  } catch (e) { err.value = e.message } finally { busy.value = false }
}
onMounted(async () => { if (props.kind === 'transfer') { locs.value = await call('locations', {}, { ns: 'stock' }); to.value = (locs.value.find(l => l.name !== props.boot.warehouse) || {}).name } })
</script>
