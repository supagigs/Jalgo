<template>
<div v-if="s">
 <div class="setrow"><label><input type="checkbox" v-model="s.accept_barcode_in_name" :true-value="1" :false-value="0"> Accept Barcode in Item Name</label><small>Scanning into the Item Name box adds the item, so the cashier never has to switch fields.</small></div>
 <div class="setrow"><label><input type="checkbox" v-model="s.warn_not_found" :true-value="1" :false-value="0"> Warn when item not found on POS Main</label><small>An unknown barcode shows a warning instead of being ignored.</small></div>
 <div class="setrow"><label><input type="checkbox" v-model="s.require_shift" :true-value="1" :false-value="0"> Cashier must open a shift before billing</label><small>Needed for the day-end cash count.</small></div>
 <div class="setrow"><label>Max discount a cashier can give <input class="cell" type="number" min="0" v-model.number="s.max_cashier_discount" style="width:70px"> %</label><small>Above this the manager PIN is asked.</small></div>
 <div class="setrow"><label>Max discount with manager PIN <input class="cell" type="number" min="0" v-model.number="s.max_manager_discount" style="width:70px"> %</label></div>
 <div class="srow" style="margin-top:10px"><label v-if="!s.manager">Manager PIN <input class="cell" type="password" inputmode="numeric" v-model="pin" style="width:100px"></label>
  <button class="gbtn" @click="save">Save settings</button><span class="err" v-if="err">{{ err }}</span><span class="erp" v-if="ok">{{ ok }}</span></div>
 <p class="erp">The manager PIN itself is changed in ERPNext → JALGO POS Settings. Settings apply to every counter after the screen is reloaded.</p>
</div>
<p class="erp" v-else>{{ err || 'Loading…' }}</p>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { call } from './api'
const emit = defineEmits(['saved'])
const s = ref(null), pin = ref(''), err = ref(''), ok = ref('')
async function save() {
  err.value = ''; ok.value = ''
  try { s.value = await call('save_settings', { values: s.value, pin: pin.value || null }, { post: true, ns: 'labels' }); ok.value = 'Saved'; emit('saved', s.value) } catch (e) { err.value = e.message }
}
onMounted(async () => { try { s.value = await call('get_settings', {}, { ns: 'labels' }) } catch (e) { err.value = e.message } })
</script>
