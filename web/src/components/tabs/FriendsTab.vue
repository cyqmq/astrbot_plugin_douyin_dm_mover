<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { store } from '../../composables/store.js'
import { followFriend, loadFriends } from '../../composables/actions.js'

const q = ref('')
const followed = reactive({}) // uid -> true 本会话已回关

const filtered = computed(() => {
  const s = q.value.trim().toLowerCase()
  const list = store.friends || []
  if (!s) return list
  return list.filter(f =>
    (f.nickname || '').toLowerCase().includes(s) ||
    (f.remark_name || '').toLowerCase().includes(s) ||
    String(f.uid || '').toLowerCase().includes(s))
})

async function doFollow(f) {
  if (!f || followed[f.uid]) return
  if (await followFriend(f)) followed[f.uid] = true
}
// 三态：'' 未回关（显示回关按钮）| '已回关'（乐观）| '互关' | '已关注'（持久）
// follow_status: 0 未 / 1,2 已关注（抖音已关注是 1 或 2，不能只判 ===1）
// follower_status: 1 = 他关注我
function stateOf(f) {
  if (followed[f.uid]) return '已回关'
  const fs = Number(f.follow_status || 0)
  const fs2 = Number(f.follower_status || 0)
  if (fs >= 1 && fs2) return '互关'
  if (fs >= 1) return '已关注'
  return ''
}
function onFocus() {
  const stale = Date.now() - (store.friendsLoadedAt || 0) > 30000
  if ((!store.friends.length || stale) && !store.friendsLoading) loadFriends(true)
}
onMounted(() => {
  // 首次进入：拉取一次（未加载或缓存超 300s）
  const stale = Date.now() - (store.friendsLoadedAt || 0) > 300000
  if (!store.friends.length || stale) loadFriends(!store.friends.length)
})
</script>

<template>
  <section>
    <div class="bar" style="margin-bottom:10px">
      <input v-model="q" class="fr-search" placeholder="搜索昵称/备注/UID…" @focus="onFocus">
      <button class="mini" title="强制重拉好友列表，跳过 300s 缓存" @click="loadFriends(true)">↻ 刷新</button>
      <span class="muted">{{ store.friends.length }} 位好友</span>
    </div>
    <div class="card">
      <ul class="list">
        <li v-for="f in filtered" :key="f.uid">
          <div class="fr-item">
            <div class="fr-info">
              <span class="fr-name">{{ f.nickname || f.remark_name || '好友' }}</span>
              <span class="muted">{{ f.uid }}<template v-if="f.sec_uid"> · {{ f.sec_uid }}</template></span>
            </div>
            <button v-if="!stateOf(f)" class="mini fr-follow" title="回关该好友（关注）" @click="doFollow(f)">回关</button>
            <span v-else class="fr-followed">{{ stateOf(f) }}</span>
          </div>
        </li>
        <li v-if="store.friendsLoading" class="empty">加载中…</li>
        <li v-else-if="!store.friends.length" class="empty">{{ store.friendsDetail || '暂无好友（未登录或拉取失败）' }}</li>
      </ul>
    </div>
  </section>
</template>
