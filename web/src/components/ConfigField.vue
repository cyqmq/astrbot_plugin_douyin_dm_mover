<script setup>
import { computed, onMounted, ref } from 'vue'
import { store, SELECTS, UMO_KEYS, JSON_KEYS, lbl, umoSplit, apiGet } from '../composables/store.js'
import { toast } from '../composables/store.js'

const props = defineProps({ field: { type: String, required: true } })
const key = computed(() => props.field)
const schema = computed(() => store.schema[key.value] || {})
const hint = computed(() => schema.value.hint || '')

const fieldType = computed(() => {
  if (SELECTS[key.value]) return 'select'
  if (UMO_KEYS.includes(key.value)) return 'umo'
  if (JSON_KEYS.includes(key.value)) return 'json'
  if (schema.value.type === 'bool') return 'bool'
  if (schema.value.type === 'int') return 'int'
  return 'text'
})

// 通用 v-model 读写（写回 store.cfg）
const val = computed({
  get: () => store.cfg[key.value],
  set: v => { store.cfg[key.value] = v }
})

// UMO 会话下拉：走 bridge SDK 调插件端点 /umos（后端进程内调 AstrBot
// SessionManagementService，免 Dashboard token、无 CORS；认证失败/异常静默）。
const umos = ref([])
async function loadUmOs() {
  try {
    const d = await apiGet('umos')
    umos.value = (d && d.umos) || []
  } catch { umos.value = [] }  // 服务异常静默：下拉空，手输兜底
}
function pickUmo(e) {
  const v = e.target.value
  if (v) store.cfg[key.value] = v
}
onMounted(() => { if (fieldType.value === 'umo') loadUmOs() })

// sender list
const items = computed(() => String(val.value || '').split(',').map(s => s.trim()).filter(Boolean))
const addInput = ref('')
function addItem() {
  const v = addInput.value.trim()
  if (!v) return
  if (items.value.includes(v)) { toast('已在名单中'); return }
  store.cfg[key.value] = items.value.concat(v).join(',')
  addInput.value = ''
}
function delItem(v) { store.cfg[key.value] = items.value.filter(x => x !== v).join(',') }

// json textarea
const jsonText = ref()
if (fieldType.value === 'json') {
  jsonText.value = typeof val.value === 'string' ? val.value : JSON.stringify(val.value ?? '', null, 0)
}
function commitJson() {
  try { store.cfg[key.value] = JSON.parse(jsonText.value || 'null') } catch { store.cfg[key.value] = jsonText.value }
}

const umo = computed(() => umoSplit(val.value))
function setAdapter(v) {
  const g = umo.value.group
  store.cfg[key.value] = g ? (v + ':GroupMessage:' + g) : ''
}
function setGroup(e) {
  const g = e.target.value.trim()
  store.cfg[key.value] = g ? (umo.value.adapter + ':GroupMessage:' + g) : ''
}
</script>

<template>
  <label class="f">
    <span>{{ lbl(key) }}</span>
    <template v-if="fieldType === 'select'">
      <select v-model="val">
        <option v-for="[v, l] in SELECTS[key]" :key="v" :value="v">{{ l }}</option>
      </select>
    </template>
    <template v-else-if="fieldType === 'bool'">
      <input type="checkbox" v-model="val">
    </template>
    <template v-else-if="fieldType === 'int'">
      <input type="number" v-model="val" style="width:130px">
    </template>
    <template v-else-if="fieldType === 'umo'">
      <select v-if="umos.length" :value="val" @change="pickUmo($event)">
        <option value="">— 选择已记录会话 —</option>
        <option v-for="u in umos" :key="u.umo" :value="u.umo">{{ u.display_name || u.umo }}</option>
      </select>
      <div class="umo-row">
        <select :value="umo.adapter" @change="setAdapter($event.target.value)">
          <option v-for="[v, l] in SELECTS.qq_adapter_id" :key="v" :value="v">{{ l }}</option>
        </select>
        <input :value="umo.group" placeholder="群号（手输兜底，未记录会话）" @input="setGroup($event)">
      </div>
    </template>
    <template v-else-if="fieldType === 'json'">
      <textarea :value="jsonText" @input="jsonText = $event.target.value" @change="commitJson" rows="3"></textarea>
    </template>
    <template v-else>
      <input type="text" v-model="val">
    </template>
    <span v-if="hint" class="hint">{{ hint }}</span>
  </label>
</template>
