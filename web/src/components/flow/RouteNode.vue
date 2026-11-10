<script setup>
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import { ROUTE_TYPES } from '../../composables/store.js'

const props = defineProps({ data: { type: Object, required: true } })
const d = props.data
const i = d.index
const r = d.route
const types = computed(() => (r.match && r.match.types) || [])

function toggleType(v) {
  if (!r.match) r.match = { types: [], senders_include: [], senders_exclude: [] }
  const t = r.match.types
  const k = t.indexOf(v)
  if (k >= 0) t.splice(k, 1); else t.push(v)
}
function setTarget(e) { r.target = e.target.value; d.sync() }
function splitLst(v) { return String(v || '').split(',').map(s => s.trim()).filter(Boolean) }
function setInc(e) { if (!r.match) r.match = { types: [], senders_include: [], senders_exclude: [] }; r.match.senders_include = splitLst(e.target.value) }
function setExc(e) { if (!r.match) r.match = { types: [], senders_include: [], senders_exclude: [] }; r.match.senders_exclude = splitLst(e.target.value) }
</script>

<template>
  <div class="route-card">
    <div class="rc-head">
      <input :value="r.name" placeholder="路由名称" class="nodrag" @input="r.name = $event.target.value || ('route' + (i+1))">
      <span class="rc-btns">
        <button title="上移" class="nodrag" @click="d.move(i, -1)">↑</button>
        <button title="下移" class="nodrag" @click="d.move(i, 1)">↓</button>
        <button class="danger nodrag" title="删除" @click="d.del(i)">×</button>
      </span>
    </div>
    <div class="rc-row"><span>目标</span>
      <select :value="r.target" class="nodrag" @change="setTarget($event)">
        <option value="">选择目标…</option>
        <option v-for="t in d.targets" :key="t.id" :value="t.adapter + ':GroupMessage:' + t.group">
          {{ t.adapter }}:{{ t.group || '（未填群号）' }}
        </option>
      </select>
    </div>
    <div class="rc-row"><span>类型</span><div class="type-chips">
      <span v-for="[v, l] in ROUTE_TYPES" :key="v" class="tc nodrag" :class="{ on: types.includes(v) }" @click="toggleType(v)">{{ l }}</span>
    </div></div>
    <div class="rc-row"><span>发送者包含</span><input :value="(r.match && (r.match.senders_include || [])).join(',')" placeholder="逗号分隔 uid" class="nodrag" @input="setInc($event)"></div>
    <div class="rc-row"><span>发送者排除</span><input :value="(r.match && (r.match.senders_exclude || [])).join(',')" placeholder="逗号分隔 uid" class="nodrag" @input="setExc($event)"></div>
    <Handle type="target" :position="Position.Left" />
    <Handle type="source" :position="Position.Right" />
  </div>
</template>
