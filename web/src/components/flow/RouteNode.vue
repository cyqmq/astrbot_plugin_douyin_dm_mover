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
  if (!r.match) r.match = { types: [], senders_include: [] }
  const t = r.match.types
  const k = t.indexOf(v)
  if (k >= 0) t.splice(k, 1); else t.push(v)
}
</script>

<template>
  <div class="route-card">
    <div class="rc-head">
      <input :value="r.name" placeholder="路由名称" class="nodrag" @input="r.name = $event.target.value || ('route' + (i+1))">
      <span class="rc-btns">
        <button title="上移" class="nodrag" @click="d.move(r, -1)">↑</button>
        <button title="下移" class="nodrag" @click="d.move(r, 1)">↓</button>
        <button class="danger nodrag" title="删除" @click="d.del(r)">×</button>
      </span>
    </div>
    <div class="rc-row"><span>类型</span><div class="type-chips">
      <span v-for="[v, l] in ROUTE_TYPES" :key="v" class="tc nodrag" :class="{ on: types.includes(v) }" @click="toggleType(v)">{{ l }}</span>
    </div></div>
    <div class="rc-sub">连接来源桩(左)与目标桩(右)</div>
    <Handle type="target" :position="Position.Left" title="接收来源连接（从来源卡右桩拖来）" />
    <Handle type="source" :position="Position.Right" title="拖到目标卡左侧连接桩（连向目标）" />
  </div>
</template>
