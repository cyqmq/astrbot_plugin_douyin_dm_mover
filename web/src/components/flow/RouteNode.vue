<script setup>
import { Handle, Position } from '@vue-flow/core'
import { store, ROUTE_TYPES, SELECTS, umoSplit } from '../../composables/store.js'

const props = defineProps({ data: { type: Object, required: true } })
const i = props.data.index
const r = store.routes[i] || props.data.route
const types = (r.match && r.match.types) || []

function toggleType(v) {
  const t = r.match.types
  const k = t.indexOf(v)
  if (k >= 0) t.splice(k, 1); else t.push(v)
}
function splitLst(v) { return String(v || '').split(',').map(s => s.trim()).filter(Boolean) }
function setInc(e) { r.match.senders_include = splitLst(e.target.value) }
function setExc(e) { r.match.senders_exclude = splitLst(e.target.value) }
function setAdapter(e) { r.target = e.target.value + ':GroupMessage:' + umoSplit(r.target).group }
function setGroup(e) { r.target = umoSplit(r.target).adapter + ':GroupMessage:' + e.target.value.trim() }
</script>

<template>
  <div class="route-card">
    <div class="rc-head">
      <input :value="r.name" placeholder="路由名称" class="nodrag" @input="r.name = $event.target.value || ('route' + (i+1))">
      <span class="rc-btns">
        <button title="上移" class="nodrag" @click="data.move(i, -1)">↑</button>
        <button title="下移" class="nodrag" @click="data.move(i, 1)">↓</button>
        <button class="danger nodrag" title="删除" @click="data.del(i)">×</button>
      </span>
    </div>
    <div class="rc-row"><span>目标</span><div class="umo-row">
      <select :value="umoSplit(r.target).adapter" class="nodrag" @change="setAdapter($event)">
        <option v-for="[v, l] in SELECTS.qq_adapter_id" :key="v" :value="v">{{ l }}</option>
      </select>
      <input :value="umoSplit(r.target).group" placeholder="群号" class="nodrag" @change="setGroup($event)">
    </div></div>
    <div class="rc-row"><span>类型</span><div class="type-chips">
      <span v-for="[v, l] in ROUTE_TYPES" :key="v" class="tc nodrag" :class="{ on: types.includes(v) }" @click="toggleType(v)">{{ l }}</span>
    </div></div>
    <div class="rc-row"><span>发送者包含</span><input :value="(r.match && (r.match.senders_include || [])).join(',')" placeholder="逗号分隔 uid" class="nodrag" @input="setInc($event)"></div>
    <div class="rc-row"><span>发送者排除</span><input :value="(r.match && (r.match.senders_exclude || [])).join(',')" placeholder="逗号分隔 uid" class="nodrag" @input="setExc($event)"></div>
    <Handle type="target" :position="Position.Left" />
    <Handle type="source" :position="Position.Right" />
  </div>
</template>
