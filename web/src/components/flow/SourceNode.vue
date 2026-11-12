<script setup>
import { computed, ref } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import { store } from '../../composables/store.js'
import { loadFriends, loadSourceGroups, scheduleLiveSave } from '../../composables/actions.js'

const props = defineProps({ data: { type: Object, required: true } })
const d = props.data
const src = computed(() => d.source || { uid: '', nickname: '', type: 'friend' })
const isGroup = computed(() => src.value.type === 'group')

const search = ref('')
const open = ref(true) // 常态展开：下拉始终显示好友/群列表，搜索框直接过滤

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

// 群即时过滤：群名/group_id 子串匹配
const filteredGroups = computed(() => {
  const q = search.value.trim().toLowerCase()
  const list = store.sourceGroups || []
  if (!q) return list
  return list.filter(g =>
    (g.name || '').toLowerCase().includes(q) ||
    String(g.group_id || '').toLowerCase().includes(q))
})

function pick(f) {
  src.value.type = 'friend'
  src.value.uid = f.uid || ''
  src.value.nickname = f.nickname || f.remark_name || ''
  src.value.group_id = ''
  src.value.group_name = ''
  scheduleLiveSave()
}
function pickGroup(g) {
  src.value.type = 'group'
  src.value.group_id = g.group_id || ''
  src.value.group_name = g.name || ''
  src.value.uid = ''
  src.value.nickname = g.name || ''
  scheduleLiveSave()
}
function setMode(t) {
  src.value.type = t
  if (t === 'group') { src.value.uid = '' } else { src.value.group_id = ''; src.value.group_name = '' }
  scheduleLiveSave()
}
function onFocus() {
  open.value = true
  // 好友/群为空或距上次拉取超 30s：强制重拉（跳过 300s 缓存）
  const stale = Date.now() - (store.friendsLoadedAt || 0) > 30000
  if ((!store.friends.length || stale) && !store.friendsLoading) loadFriends(true)
  const gs = Date.now() - (store.sourceGroupsLoadedAt || 0) > 30000
  if ((!store.sourceGroups.length || gs) && !store.sourceGroupsLoading) loadSourceGroups(true)
}
function refresh() {
  if (isGroup.value) loadSourceGroups(true)
  else loadFriends(true)
}
function setNick(e) { src.value.nickname = e.target.value; scheduleLiveSave() }
</script>

<template>
  <div class="vf-src">
    <div class="src-mode nodrag">
      <button :class="{ on: !isGroup }" @click="setMode('friend')">好友</button>
      <button :class="{ on: isGroup }" @click="setMode('group')">群聊</button>
    </div>
    <div class="src-dropwrap">
      <input class="nodrag src-search" :placeholder="isGroup ? '搜索群名/群ID…' : '搜索好友昵称/备注/UID…'"
        v-model="search" @focus="onFocus">
      <div v-if="open" class="nodrag src-drop">
        <template v-if="!isGroup">
          <div v-if="store.friendsLoading" class="src-drop-empty">加载中…</div>
          <div v-else-if="!filtered.length" class="src-drop-empty">无匹配好友</div>
          <div v-for="f in filtered" :key="f.uid" class="src-drop-item"
            :class="{ sel: !isGroup && src.uid === String(f.uid || '') }"
            @mousedown.prevent="pick(f)">
            <span class="src-drop-name">{{ f.nickname || f.remark_name || '好友' }}</span>
            <span class="src-drop-uid">{{ f.uid }}</span>
          </div>
        </template>
        <template v-else>
          <div v-if="store.sourceGroupsLoading" class="src-drop-empty">加载中…</div>
          <div v-else-if="!filteredGroups.length" class="src-drop-empty">无匹配群（未登录或拉取失败）</div>
          <div v-for="g in filteredGroups" :key="g.group_id" class="src-drop-item"
            :class="{ sel: isGroup && src.group_id === String(g.group_id || '') }"
            @mousedown.prevent="pickGroup(g)">
            <div class="src-drop-main">
              <span class="src-drop-name">{{ g.name || '群' }}</span>
              <span class="src-drop-sub" v-if="g.member_count || g.last_sender_nickname">
                {{ g.member_count ? `${g.member_count}人` : '' }}<template v-if="g.member_count && g.last_sender_nickname"> · </template><template v-if="g.last_sender_nickname">最后:{{ g.last_sender_nickname }}</template>
              </span>
            </div>
            <span class="src-drop-uid">{{ g.group_id }}</span>
          </div>
        </template>
      </div>
    </div>
    <template v-if="isGroup">
      <span class="src-picked" v-if="src.group_id">{{ src.group_name || src.group_id }}</span>
      <input :value="src.nickname" placeholder="群名（可选）" class="nodrag src-nick" @change="setNick($event)">
    </template>
    <template v-else>
      <span class="src-picked" v-if="src.uid">{{ src.nickname || src.uid }}</span>
      <input :value="src.nickname" placeholder="昵称（可选）" class="nodrag src-nick" @change="setNick($event)">
    </template>
    <button class="mini nodrag" :title="isGroup ? '强制重拉群列表' : '强制重拉好友列表'" @click="refresh">↻ 刷新</button>
    <button class="mini danger nodrag" title="移除该来源" @click="d.del(src)">×</button>
    <Handle type="source" :position="Position.Right" title="拖到路由卡左侧连接桩（连入路由）" />
  </div>
</template>
