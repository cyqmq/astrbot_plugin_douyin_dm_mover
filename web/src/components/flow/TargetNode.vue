<script setup>
import { Handle, Position } from '@vue-flow/core'
import { store, SELECTS, umoSplit } from '../../composables/store.js'

const props = defineProps({ data: { type: Object, required: true } })
const t = props.data.target
function setAdapter(e) { props.data.apply(e.target.value, umoSplit(t).group) }
function setGroup(e) { props.data.apply(umoSplit(t).adapter, e.target.value) }
const count = () => store.routes.filter(r => r.target === t).length
</script>

<template>
  <div class="target-card">
    <div class="tc-head">目标群</div>
    <div class="rc-row"><span>适配器</span>
      <select :value="umoSplit(t).adapter" class="nodrag" @change="setAdapter($event)">
        <option v-for="[v, l] in SELECTS.qq_adapter_id" :key="v" :value="v">{{ l }}</option>
      </select>
    </div>
    <div class="rc-row"><span>群号</span><input :value="umoSplit(t).group" placeholder="群号" class="nodrag" @change="setGroup($event)"></div>
    <div class="tc-sub">{{ count() }} 条路由指向</div>
    <Handle type="target" :position="Position.Left" />
  </div>
</template>
