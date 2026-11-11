<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { store } from '../../composables/store.js'
import { followFriend, importCookies, loadFriends } from '../../composables/actions.js'

const q = ref('')
const followed = reactive({}) // uid -> true 本会话已回关
const showImport = ref(false)
const importing = ref(false)
const imp = reactive({ cookie_str: '', ts_sign: '', private_key: '', client_cert: '', server_cert: '' })

async function doImport() {
  if (!imp.cookie_str.trim()) { store.friendsDetail = '请粘贴 Cookie 串'; return }
  importing.value = true
  const payload = { ...imp }
  const ok = await importCookies(payload)
  importing.value = false
  if (ok) {
    showImport.value = false
    imp.cookie_str = ''; imp.ts_sign = ''; imp.private_key = ''; imp.client_cert = ''; imp.server_cert = ''
    loadFriends(true)
  }
}

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
      <button class="mini" title="手动导入 www 网页登录 Cookie（建 BDTicket，关注/粉丝/回关）" @click="showImport = true">导入 Cookie</button>
      <span class="muted">{{ store.friends.length }} 位好友</span>
    </div>
    <div v-if="showImport" class="card" style="margin-bottom:10px">
      <div style="margin-bottom:6px">
        <strong>导入 www 网页登录 Cookie</strong>
        <span class="muted">：浏览器打开 www.douyin.com 登录后复制完整 Cookie 串；票据可自动解析，或手动补填（ts_sign/private_key/client_cert/server_cert）</span>
      </div>
      <textarea v-model="imp.cookie_str" class="fr-search" rows="4" placeholder="粘贴 Cookie 串（含 sessionid）" style="width:100%;box-sizing:border-box"></textarea>
      <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:6px">
        <input v-model="imp.ts_sign" class="fr-search" placeholder="ts_sign（可选）" style="flex:1">
        <input v-model="imp.client_cert" class="fr-search" placeholder="client_cert（可选）" style="flex:1">
      </div>
      <div style="display:flex;gap:6px;margin-top:6px">
        <input v-model="imp.private_key" class="fr-search" placeholder="private_key（可选）" style="flex:1">
        <input v-model="imp.server_cert" class="fr-search" placeholder="server_cert（可选）" style="flex:1">
      </div>
      <div style="margin-top:8px;display:flex;gap:8px">
        <button class="mini" :disabled="importing" @click="doImport">{{ importing ? '导入中…' : '导入' }}</button>
        <button class="mini" @click="showImport = false">取消</button>
      </div>
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
