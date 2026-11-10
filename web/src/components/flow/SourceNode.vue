<script setup>
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import { store, sendersTop } from '../../composables/store.js'
import { loadFriends, scheduleLiveSave } from '../../composables/actions.js'

const props = defineProps({ data: { type: Object, required: true } })
const d = props.data
const src = computed(() => d.source || { uid: '', nickname: '' })

const opts = computed(() => [
  { label: '最近发石者', items: sendersTop.value.map(s => ({ uid: s.peer_id || '', name: s.peer_name || '发石者' })) },
  { label: '抖音好友', items: store.friends.map(f => ({ uid: f.uid || '', name: f.nickname || f.remark_name || '好友' })) }
])
function onPick(e) {
  const uid = e.target.value
  if (!uid) return
  for (const g of opts.value) for (const it of g.items) {
    if (it.uid === uid) { src.value.uid = uid; src.value.nickname = it.name; break }
  }
  scheduleLiveSave()
}
function onFocus() { if (!store.friends.length && !store.friendsLoading) loadFriends() }
function setNick(e) { src.value.nickname = e.target.value; scheduleLiveSave() }
</script>

<template>
  <div class="vf-src">
    <select class="nodrag src-pick" :value="src.uid" @focus="onFocus" @change="onPick($event)">
      <option value="">选择来源…</option>
      <optgroup v-for="g in opts" :key="g.label" :label="g.label">
        <option v-for="it in g.items" :key="g.label + it.uid" :value="it.uid">{{ it.name }}（{{ it.uid }}）</option>
      </optgroup>
    </select>
    <template v-if="src.uid">
      <span class="src-picked">{{ src.nickname || src.uid }}</span>
    </template>
    <input :value="src.nickname" placeholder="昵称（可选）" class="nodrag src-nick" @change="setNick($event)">
    <button class="mini danger nodrag" title="移除该来源" @click="d.del(src)">×</button>
    <Handle type="source" :position="Position.Right" />
  </div>
</template>
