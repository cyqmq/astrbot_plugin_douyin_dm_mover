<script setup>
import { store, POLICY_GROUPS, SETTINGS_GROUPS, POLICY_KEYS, SETTINGS_KEYS } from '../../composables/store.js'
import { saveConfig } from '../../composables/actions.js'
import ConfigField from '../ConfigField.vue'

const props = defineProps({ mode: { type: String, required: true } })
const groups = props.mode === 'policy' ? POLICY_GROUPS : SETTINGS_GROUPS
const keys = props.mode === 'policy' ? POLICY_KEYS : SETTINGS_KEYS
const title = props.mode === 'policy' ? '保存策略' : '保存设置'
async function save() { await saveConfig(pick()) }
function pick() {
  const out = {}
  keys.forEach(k => {
    if (Object.prototype.hasOwnProperty.call(store.cfg, k)) out[k] = store.cfg[k]
  })
  return out
}
</script>

<template>
  <section>
    <div class="card cfg">
      <div class="gcard" v-for="[gtitle, gkeys] in groups" :key="gtitle">
        <h2>{{ gtitle }}</h2>
        <ConfigField v-for="k in gkeys" :key="k" :field="k" />
      </div>
      <div v-if="!groups.length" class="empty">无配置项</div>
    </div>
    <div class="save-row"><button class="primary" @click="save">{{ title }}</button></div>
  </section>
</template>
