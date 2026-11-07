<template>
<div>
 <div class="grnbar">
  <button class="gk" @click="showCard=!showCard">Rate Card Mapping</button>
  <button class="gk" @click="fill">Fill Field1 with Rate Card Text</button>
  <button class="pk" :disabled="!rows.length" @click="print">Print stickers</button>
  <label class="radio">Sheet <select class="cell" style="width:auto" v-model="sheet"><option v-for="(s,k) in SHEETS" :key="k" :value="k">{{ s.label }}</option></select></label>
 </div>

 <div class="sform" v-if="showCard">
  <div class="lbl2" style="margin:0">Rate Card: a letter code for each digit (two codes make the same price print differently)</div>
  <table class="tbl2 rt rc"><thead><tr><th>Digit</th><th v-for="d in DIGITS" :key="d" class="num">{{ d }}</th></tr></thead>
   <tbody><tr v-for="k in [0,1]" :key="k"><td>Code {{ k+1 }}</td><td v-for="d in DIGITS" :key="d"><input class="cell rcc" maxlength="1" v-model="card[d][k]" :aria-label="'Code '+(k+1)+' for '+d"></td></tr></tbody></table>
  <div class="srow"><button class="gbtn" @click="copy">Copy code 1 → code 2</button><button class="gbtn" @click="suggest">Auto Suggest</button>
   <label>Manager PIN <input class="cell" type="password" inputmode="numeric" v-model="pin" style="width:100px" placeholder="if needed"></label>
   <button class="gbtn" @click="saveCard">Save rate card</button><span class="err" v-if="err">{{ err }}</span><span class="erp" v-if="ok">{{ ok }}</span></div>
  <p class="erp">Example: with A=0, B=1 a purchase price of ₹100 prints as BAA. Only staff who know the card can read it.</p>
 </div>

 <div class="searchwrap" style="max-width:440px;margin:6px 0 10px"><input class="cell wide" v-model="q" placeholder="Add item: type name or scan barcode" @input="search" @keydown.enter.prevent="add(found[0])">
  <div class="sugg" v-if="q && found.length"><button v-for="m in found" :key="m.code" @mousedown.prevent="add(m)"><span class="num">{{ m.barcode }}</span><span>{{ m.name }}</span><b class="num">{{ m.rate.toFixed(2) }}</b></button></div></div>

 <table class="tbl2 rt" v-if="rows.length"><thead><tr><th>Item</th><th>Barcode</th><th class="r" v-if="manager">Purchase ₹</th><th class="r">Sales ₹</th><th class="r">MRP ₹</th><th>Field1 (Rate Card)</th><th class="r">Stickers</th><th></th></tr></thead>
  <tbody><tr v-for="(r,i) in rows" :key="r.code"><td>{{ r.name }}</td><td class="num">{{ r.barcode }}</td><td class="r num" v-if="manager">{{ r.cost?.toFixed(2) }}</td><td class="r num">{{ r.rate.toFixed(2) }}</td><td class="r num">{{ (r.mrp||r.rate).toFixed(2) }}</td>
   <td><input class="cell" style="width:90px;text-align:left;font-family:var(--mono);font-weight:700" v-model="r.f1"></td><td class="r"><input class="cell" type="number" min="1" max="500" style="width:70px" v-model.number="r.n"></td><td><button class="dots" @click="rows.splice(i,1)">✕</button></td></tr></tbody></table>
 <p class="erp" v-else>Add items to print their stickers.</p>

 <div class="lbl2" v-if="rows.length">Preview · {{ SHEETS[sheet].label }} · {{ total }} stickers</div>
 <div class="sheet" v-if="rows.length"><div class="sticker" v-for="(s,k) in preview" :key="k" v-html="stickerHtml(s)"></div></div>
</div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import JsBarcode from 'jsbarcode'
import { call } from './api'
const emit = defineEmits(['toast'])
const DIGITS = '0123456789.'.split('')
const SHEETS = {
  r38: { label: '38×25 mm roll, 2 across', w: 38, h: 25, cols: 2, page: '80mm auto' },
  r50: { label: '50×25 mm roll, 1 across', w: 50, h: 25, cols: 1, page: '50mm 25mm' },
  a4: { label: 'A4 sheet, 65 labels (38.1×21.2 mm)', w: 38.1, h: 21.2, cols: 5, page: 'A4' },
}
const L = { ns: 'labels' }
const card = ref(Object.fromEntries(DIGITS.map(d => [d, ['', '']]))), showCard = ref(false), pin = ref(''), err = ref(''), ok = ref('')
const rows = ref([]), q = ref(''), found = ref([]), sheet = ref('r38'), manager = ref(false)
const total = computed(() => rows.value.reduce((s, r) => s + (+r.n || 0), 0))
const preview = computed(() => rows.value.flatMap(r => Array(Math.min(+r.n || 0, 6)).fill(r)).slice(0, 18))
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]))

function barcodeSvg(code) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
  const ean = /^\d{13}$/.test(code)
  try { JsBarcode(svg, code, { format: ean ? 'EAN13' : 'CODE128', displayValue: false, margin: 0, height: 40, width: 1.4 }) }
  catch (e) { JsBarcode(svg, code, { format: 'CODE128', displayValue: false, margin: 0, height: 40, width: 1.4 }) }  // EAN with a bad check digit
  svg.setAttribute('preserveAspectRatio', 'none'); svg.setAttribute('class', 'bars')
  return svg.outerHTML
}
function stickerHtml(s) {
  return `<b class="sname">${esc(s.name)}</b>${barcodeSvg(s.barcode)}<div class="snum">${esc(s.barcode)}</div>` +
    `<div class="sprice"><span>MRP <s>₹${(s.mrp || s.rate).toFixed(2)}</s></span><b>₹${s.rate.toFixed(2)}</b>${s.f1 ? `<em>${esc(s.f1)}</em>` : ''}</div>`
}
let t; function search() { clearTimeout(t); t = setTimeout(async () => { found.value = q.value ? await call('search_items', { txt: q.value }).catch(() => []) : [] }, 200) }
async function add(m) {
  if (!m || rows.value.find(r => r.code === m.code)) { q.value = ''; return }
  try { const [r] = await call('sticker_items', { codes: [m.code] }, L); rows.value.push({ ...r, f1: '', n: 2 }) } catch (e) { emit('toast', e.message) }
  q.value = ''; found.value = []
}
async function fill() {
  if (!rows.value.length) return
  try { const fresh = await call('sticker_items', { codes: rows.value.map(r => r.code) }, L); fresh.forEach(f => { const r = rows.value.find(x => x.code === f.code); if (r) r.f1 = f.field1 })
    emit('toast', fresh.some(f => !f.field1) ? 'Some items have no purchase price or the rate card is incomplete' : 'Field1 filled with rate card codes') } catch (e) { emit('toast', e.message) }
}
function copy() { DIGITS.forEach(d => card.value[d][1] = card.value[d][0]) }
async function suggest() { const s = await call('suggest_rate_card', {}, L); DIGITS.forEach(d => card.value[d] = [...s[d]]) }
async function saveCard() {
  err.value = ''; ok.value = ''
  try { const c = await call('save_rate_card', { card: card.value, pin: pin.value || null }, { post: true, ...L }); DIGITS.forEach(d => card.value[d] = [c[d][0] || '', c[d][1] || '']); ok.value = 'Rate card saved' } catch (e) { err.value = e.message }
}
function print() {
  const S = SHEETS[sheet.value], all = rows.value.flatMap(r => Array(Math.max(0, Math.min(+r.n || 0, 500))).fill(r))
  const w = window.open('', '_blank', 'width=900,height=700')
  if (!w) return emit('toast', 'Allow pop-ups to print stickers')
  w.document.write(`<!doctype html><html><head><meta charset="utf-8"><title>Stickers</title><style>
    @page{size:${S.page};margin:${sheet.value === 'a4' ? '10mm 5mm' : '0'}}
    body{margin:0;font-family:Arial,sans-serif;-webkit-print-color-adjust:exact;print-color-adjust:exact}
    .grid{display:grid;grid-template-columns:repeat(${S.cols},${S.w}mm);gap:${sheet.value === 'r38' ? '2mm' : '0'};justify-content:start}
    .sticker{width:${S.w}mm;height:${S.h}mm;box-sizing:border-box;padding:1.2mm 1.6mm;display:flex;flex-direction:column;justify-content:space-between;overflow:hidden;page-break-inside:avoid}
    .sname{font-size:7pt;line-height:1.1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .bars{width:100%;height:${S.h * 0.38}mm;display:block}.snum{font:6pt monospace;text-align:center;letter-spacing:.08em}
    .sprice{display:flex;justify-content:space-between;align-items:baseline;font-size:6pt}.sprice b{font-size:9pt}.sprice em{font-style:normal;font-weight:700;font-family:monospace;border:0.2mm solid #000;padding:0 0.6mm}
  </style></head><body><div class="grid">${all.map(s => `<div class="sticker">${stickerHtml(s)}</div>`).join('')}</div>
  <script>window.onload=()=>{window.print()}<\/script></body></html>`)
  w.document.close()
}
onMounted(async () => { try { const r = await call('get_rate_card', {}, L); manager.value = r.manager; DIGITS.forEach(d => card.value[d] = [r.card[d]?.[0] || '', r.card[d]?.[1] || '']) } catch (e) { err.value = e.message } })
</script>
