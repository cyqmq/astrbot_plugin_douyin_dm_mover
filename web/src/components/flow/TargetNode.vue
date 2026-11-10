<script setup>
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import { store } from '../../composables/store.js'
import { loadGroups, loadPlatforms } from '../../composables/actions.js'

const props = defineProps({ data: { type: Object, required: true } })
const t = props.data.target
const advanced = props.data.advanced
const ad = computed(() => t.adapter || 'aiocqhttp')
const kind = computed(() => (t.kind === 'private' ? 'private' : (t.kind === 'qq_group' ? 'group' : (t.kind || 'group'))))
const umo = computed(() => ad.value + ':' + (kind.value === 'private' ? 'PrivateMessage' : 'GroupMessage') + ':' + (t.value || ''))
const count = computed(() => store.routes.filter(r => r.target === umo.value).length)
const selPlatform = computed(() => store.platforms.find(p => p.id === ad.value) || null)
const isOfficial = computed(() => (selPlatform.value ? selPlatform.value.type === 'qq_official' : ad.value === 'qq_official'))

function setAdapter(e) {
  const v = e.target.value
  if (isOfficial.value && kind.value === 'private') props.data.update(t, { adapter: v, kind: 'group' })
  else props.data.update(t, { adapter: v })
  if (!store.platforms.length && !store.platformsLoading) loadPlatforms()
  if (v && kind.value !== 'private') loadGroups(v)
}
function setKind(e) {
  props.data.update(t, { kind: e.target.value })
  if (e.target.value !== 'private' && (!store.groups.length || store.groupsPlatform !== ad.value) && !store.groupsLoading) loadGroups(ad.value)
}
function setValue(e) { props.data.update(t, { value: e.target.value }) }
function setGroup(e) { props.data.update(t, { group: e.target.value }) }
function onGroupFocus() { if (!store.groups.length && !store.groupsLoading) loadGroups(ad.value) }
</script>

<template>
  <div class="target-card">
    <div class="tc-head">目标{{ advanced ? '（高级）' : '' }}
      <span class="rc-btns" style="float:right"><button class="danger nodrag" title="删除目标" @click="data.del(t)">×</button></span>
    </div>
    <div class="rc-row"><span>平台实例</span>
      <select :value="ad" class="nodrag" @change="setAdapter($event)">
        <option v-if="!store.platforms.length" value="aiocqhttp">OneBot（未检测到实例）</option>
        <option v-else-if="!store.platforms.find(p => p.id === ad)" :value="ad">{{ ad }}（已失效）</option>
        <option v-for="p in store.platforms" :key="p.id" :value="p.id">{{ p.name || p.type || p.id }}{{ p.type && p.type !== p.name ? '（' + p.type + '）' : '' }}</option>
      </select>
      <button class="mini nodrag" title="刷新平台实例" @click="loadPlatforms()">↻</button>
    </div>
    <template v-if="advanced">
      <div class="rc-row"><span>群号</span>
        <template v-if="store.groups.length">
          <select :value="t.group" class="nodrag" @focus="onGroupFocus" @change="setGroup($event)">
            <option value="">选择群…</option>
            <option v-for="g in store.groups" :key="g.group_id" :value="g.group_id">{{ g.group_name || ('群 ' + g.group_id) }}（{{ g.group_id }}）</option>
          </select>
          <button class="mini nodrag" title="刷新群列表" @click="loadGroups(ad)">↻</button>
        </template>
        <input v-else :value="t.group" placeholder="群号（无群列表，手动输入）" class="nodrag" @change="setGroup($event)">
      </div>
    </template>
    <template v-else>
      <div class="rc-row"><span>目标类型</span>
        <select :value="kind" class="nodrag" @change="setKind($event)">
          <option value="group">群聊</option>
          <option value="private" :disabled="isOfficial">私聊</option>
        </select>
      </div>
      <div class="rc-row"><span>{{ kind === 'private' ? 'OpenID' : '群号' }}</span>
        <template v-if="kind === 'group' && store.groups.length">
          <select :value="t.value" class="nodrag" @focus="onGroupFocus" @change="setValue($event)">
            <option value="">选择群…</option>
            <option v-for="g in store.groups" :key="g.group_id" :value="g.group_id">{{ g.group_name || ('群 ' + g.group_id) }}（{{ g.group_id }}）</option>
          </select>
          <button class="mini nodrag" title="刷新群列表" @click="loadGroups(ad)">↻</button>
        </template>
        <input v-else :value="t.value"
          :placeholder="kind === 'private' ? 'OpenID' : (store.groupsDetail || '群号（无群列表，手动输入）')"
          class="nodrag" @change="setValue($event)">
      </div>
    </template>
    <div class="tc-sub">{{ count }} 条路由指向</div>
    <Handle type="target" :position="Position.Left" title="接收路由连接（从路由卡右桩拖来）" />
  </div>
</template>
