<script setup>
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import { store } from '../../composables/store.js'

const props = defineProps({ data: { type: Object, required: true } })
const t = props.data.target
const advanced = props.data.advanced
const ad = computed(() => t.adapter || 'aiocqhttp')
const kind = computed(() => (t.kind === 'private' ? 'private' : (t.kind === 'qq_group' ? 'group' : (t.kind || 'group'))))
const umo = computed(() => ad.value + ':' + (kind.value === 'private' ? 'PrivateMessage' : 'GroupMessage') + ':' + (t.value || ''))
const count = computed(() => store.routes.filter(r => r.target === umo.value).length)

function setAdapter(e) {
  const v = e.target.value
  if (v === 'qq_official' && kind.value === 'private') props.data.update(t, { adapter: v, kind: 'group' })
  else props.data.update(t, { adapter: v })
}
function setKind(e) { props.data.update(t, { kind: e.target.value }) }
function setValue(e) { props.data.update(t, { value: e.target.value }) }
function setGroup(e) { props.data.update(t, { group: e.target.value }) }
</script>

<template>
  <div class="target-card">
    <div class="tc-head">目标{{ advanced ? '（高级）' : '' }}
      <span class="rc-btns" style="float:right"><button class="danger nodrag" title="删除目标" @click="data.del(t)">×</button></span>
    </div>
    <template v-if="advanced">
      <div class="rc-row"><span>适配器</span>
        <select :value="ad" class="nodrag" @change="setAdapter($event)">
          <option value="aiocqhttp">OneBot</option>
          <option value="qq_official">官方机器人</option>
        </select>
      </div>
      <div class="rc-row"><span>群号</span><input :value="t.group" placeholder="群号" class="nodrag" @change="setGroup($event)"></div>
    </template>
    <template v-else>
      <div class="rc-row"><span>平台</span>
        <select :value="ad" class="nodrag" @change="setAdapter($event)">
          <option value="aiocqhttp">OneBot</option>
          <option value="qq_official">官方机器人</option>
        </select>
      </div>
      <div class="rc-row"><span>目标类型</span>
        <select :value="kind" class="nodrag" @change="setKind($event)">
          <option value="group">群聊</option>
          <option value="private" :disabled="ad === 'qq_official'">私聊</option>
        </select>
      </div>
      <div class="rc-row"><span>{{ kind === 'private' ? 'OpenID' : '群号' }}</span>
        <input :value="t.value" :placeholder="kind === 'private' ? 'OpenID' : '群号'" class="nodrag" @change="setValue($event)">
      </div>
    </template>
    <div class="tc-sub">{{ count }} 条路由指向</div>
    <Handle type="target" :position="Position.Left" />
  </div>
</template>
