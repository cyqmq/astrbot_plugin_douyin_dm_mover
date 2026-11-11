<script setup>
import { computed, ref } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import { store } from '../../composables/store.js'
import { loadFriends, scheduleLiveSave } from '../../composables/actions.js'

const props = defineProps({ data: { type: Object, required: true } })
const d = props.data
const src = computed(() => d.source || { uid: '', nickname: '' })

const search = ref('')
const open = ref(true) // 常态展开：下拉始终显示好友列表，搜索框直接过滤

// 好友即时过滤：昵称/备注/UID 子串匹配（大小写不敏感）
const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  const list = store.friends || []
  if (!q) return list
  return list.filter(f =>
    (f.nickname || '').toLowerCase().includes(q) ||
    (f.remark_name || '').toLowerCase().includes(q) ||
    String(f.uid || '').toLowerCase().includes(q))
})

function pick(f) {
  src.value.uid = f.uid || ''
  src.value.nickname = f.nickname || f.remark_name || ''
  scheduleLiveSave()
}
function onFocus() {
  open.value = true
  // 好友为空或距上次拉取超 30s：强制重拉（跳过 300s 缓存）
  const stale = Date.now() - (store.friendsLoadedAt || 0) > 30000
  if ((!store.friends.length || stale) && !store.friendsLoading) loadFriends(true)
}
function setNick(e) { src.value.nickname = e.target.value; scheduleLiveSave() }
</script>

<template>
  <div class="vf-src">
    <div class="src-dropwrap">
      <input class="nodrag src-search" placeholder="搜索好友昵称/备注/UID…"
        v-model="search" @focus="onFocus">
      <div v-if="open" class="nodrag src-drop">
        <div v-if="store.friendsLoading" class="src-drop-empty">加载中…</div>
        <div v-else-if="!filtered.length" class="src-drop-empty">无匹配好友</div>
        <div v-for="f in filtered" :key="f.uid" class="src-drop-item"
          :class="{ sel: src.uid === String(f.uid || '') }"
          @mousedown.prevent="pick(f)">
          <span class="src-drop-name">{{ f.nickname || f.remark_name || '好友' }}</span>
          <span class="src-drop-uid">{{ f.uid }}</span>
        </div>
      </div>
    </div>
    <template v-if="src.uid">
      <span class="src-picked">{{ src.nickname || src.uid }}</span>
    </template>
    <input :value="src.nickname" placeholder="昵称（可选）" class="nodrag src-nick" @change="setNick($event)">
    <button class="mini nodrag" title="强制重拉好友列表，跳过 300s 缓存" @click="loadFriends(true)">↻ 刷新</button>
    <button class="mini danger nodrag" title="移除该来源" @click="d.del(src)">×</button>
    <Handle type="source" :position="Position.Right" title="拖到路由卡左侧连接桩（连入路由）" />
  </div>
</template>
