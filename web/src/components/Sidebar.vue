<script setup>
import { computed, watch } from 'vue'
import { store, ST_MAP, apiGet } from '../composables/store.js'
import logo from '../assets/logo.png'

const NAV = [
  ['overview', '总览', 'M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z'],
  ['routes', '路由', 'M9 6l6 6-6 6'],
  ['friends', '好友', 'M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5s-3 1.34-3 3 1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z'],
  ['policy', '策略', 'M4 7h16M4 12h16M4 17h9'],
  ['monitor', '监控', 'M12 12a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 7v5l3 2'],
  ['logs', '日志', 'M4 6h16M4 12h16M4 18h10'],
  ['settings', '设置', 'M12 12a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M19.1 4.9L17 7M7 17l-2.1 2.1']
]

const st = computed(() => ST_MAP[store.authState] || ST_MAP.idle)
const stateLabel = computed(() => st.value[1])
const stateSub = computed(() => {
  if (store.authState === 'ok') return store.profile.nickname || (store.authUid ? ('uid ' + store.authUid) : '已连接')
  return st.value[2]
})
const AV_KEY = 'dyf_avatar_cache'
const avatar = computed(() => store.profile.avatar || readCachedAvatar() || logo)
function readCachedAvatar() {
  try { return localStorage.getItem(AV_KEY) || '' } catch { return '' }
}
function onAvatarLoad(e) {
  try { localStorage.setItem(AV_KEY, e.target.src) } catch {}
}
function onAvatarError(e) {
  // URL 失效/防盗链 → 回退本地缓存的头像（仅一次，防循环）
  const cached = readCachedAvatar()
  if (cached && e.target.src !== cached && !e.target.src.startsWith('data:')) e.target.src = cached
  else e.target.src = logo
}

async function loadProfile() {
  if (store.authState !== 'ok') return
  const d = await apiGet('profile')
  if (d.profile) store.profile = d.profile
}
// 已登录即拉一次账户档案（含挂载时已是登录态）
watch(() => store.authState, s => { if (s === 'ok') loadProfile() }, { immediate: true })

</script>

<template>
  <aside>
    <div class="side-head">
      <div class="side-logo"><img :src="logo" alt="logo"></div>
      <span class="side-title">抖音私信搬运</span>
    </div>
    <nav class="side-nav">
      <div v-for="[key, label, d] in NAV" :key="key" class="nav-item" :class="{ active: store.tab === key }"
           @click="store.tab = key">
        <svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path :d="d"/></svg>
        {{ label }}
      </div>
    </nav>
    <div class="side-foot">
      <div class="side-user" title="点击扫码登录" @click="store.modalOpen = true">
        <img v-if="store.authState === 'ok'" :src="avatar" class="side-avatar" alt="" @load="onAvatarLoad" @error="onAvatarError">
        <span v-else class="dot" :class="'dot-' + st[0]"></span>
        <div style="flex:1;min-width:0">
          <div class="lbl">{{ stateLabel }}</div>
          <div class="sub">{{ stateSub }}</div>
        </div>
      </div>
    </div>
  </aside>
</template>
