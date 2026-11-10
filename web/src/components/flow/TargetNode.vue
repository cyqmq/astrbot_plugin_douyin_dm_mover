<script setup>
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import { store, SELECTS } from '../../composables/store.js'

const props = defineProps({ data: { type: Object, required: true } })
const t = props.data.target
const count = computed(() => {
  const umo = t.adapter + ':GroupMessage:' + t.group
  return store.routes.filter(r => r.target === umo).length
})
function setAdapter(e) { props.data.apply(t, e.target.value, t.group) }
function setGroup(e) { props.data.apply(t, t.adapter, e.target.value) }
</script>

<template>
  <div class="target-card">
    <div class="tc-head">目标群
      <span class="rc-btns" style="float:right"><button class="danger nodrag" title="删除目标" @click="data.del(t)">×</button></span>
    </div>
    <div class="rc-row"><span>适配器</span>
      <select :value="t.adapter" class="nodrag" @change="setAdapter($event)">
        <option v-for="[v, l] in SELECTS.qq_adapter_id" :key="v" :value="v">{{ l }}</option>
      </select>
    </div>
    <div class="rc-row"><span>群号</span><input :value="t.group" placeholder="群号" class="nodrag" @change="setGroup($event)"></div>
    <div class="tc-sub">{{ count }} 条路由指向</div>
    <Handle type="target" :position="Position.Left" />
  </div>
</template>
