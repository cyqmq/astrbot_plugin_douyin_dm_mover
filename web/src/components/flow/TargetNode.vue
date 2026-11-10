<script setup>
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import { store, SELECTS } from '../../composables/store.js'

const props = defineProps({ data: { type: Object, required: true } })
const t = props.data.target
const advanced = props.data.advanced
const count = computed(() => {
  const umo = advanced
    ? (t.adapter + ':GroupMessage:' + (t.group || ''))
    : (t.kind === 'private' ? 'aiocqhttp:PrivateMessage:' + (t.value || '') : 'aiocqhttp:GroupMessage:' + (t.value || ''))
  return store.routes.filter(r => r.target === umo).length
})
function setAdapter(e) { props.data.update(t, { adapter: e.target.value }) }
function setGroup(e) { props.data.update(t, { group: e.target.value }) }
function setKind(e) { props.data.update(t, { kind: e.target.value }) }
function setValue(e) { props.data.update(t, { value: e.target.value }) }
</script>

<template>
  <div class="target-card">
    <div class="tc-head">目标{{ advanced ? '（高级）' : '' }}
      <span class="rc-btns" style="float:right"><button class="danger nodrag" title="删除目标" @click="data.del(t)">×</button></span>
    </div>
    <template v-if="advanced">
      <div class="rc-row"><span>适配器</span>
        <select :value="t.adapter" class="nodrag" @change="setAdapter($event)">
          <option v-for="[v, l] in SELECTS.qq_adapter_id" :key="v" :value="v">{{ l }}</option>
        </select>
      </div>
      <div class="rc-row"><span>群号</span><input :value="t.group" placeholder="群号" class="nodrag" @change="setGroup($event)"></div>
    </template>
    <template v-else>
      <div class="rc-row"><span>类型</span>
        <select :value="t.kind" class="nodrag" @change="setKind($event)">
          <option value="qq_group">QQ群</option>
          <option value="private">私聊</option>
        </select>
      </div>
      <div class="rc-row"><span>{{ t.kind === 'private' ? '对方' : '群号' }}</span>
        <input :value="t.value" :placeholder="t.kind === 'private' ? 'uid/qq' : '群号'" class="nodrag" @change="setValue($event)">
      </div>
    </template>
    <div class="tc-sub">{{ count }} 条路由指向</div>
    <Handle type="target" :position="Position.Left" />
  </div>
</template>
