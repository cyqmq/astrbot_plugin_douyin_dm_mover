<script setup>
import { ref } from 'vue'
import { store } from '../../composables/store.js'
import { saveConfig, loadFriends } from '../../composables/actions.js'
import TopologyFlow from '../flow/TopologyFlow.vue'

async function switchSource(mode) {
  store.sourceMode = mode
  if (mode === 'friends' && !store.friends.length) await loadFriends()
}
async function refreshFriends() { await loadFriends() }
async function saveRoutes() { await saveConfig({ routes: JSON.parse(JSON.stringify(store.routes)) }) }
</script>

<template>
  <section>
    <div class="card">
      <h2>转发拓扑与路由编辑
        <span class="muted">来源 <strong>连接桩 →</strong> 路由 <strong>→</strong> 目标群 · 贝塞尔连线 · 卡片可编辑 · 拖拽布局</span>
      </h2>
      <div class="bar" style="margin-bottom:10px">
        <select :value="store.sourceMode" @change="switchSource($event.target.value)">
          <option value="senders">最近发石者</option>
          <option value="friends">抖音好友</option>
        </select>
        <button v-if="store.sourceMode === 'friends'" class="mini" @click="refreshFriends">刷新好友</button>
        <span v-if="store.sourceMode === 'friends' && store.friendsLoading" class="muted">加载好友中…</span>
        <span v-else-if="store.sourceMode === 'friends' && !store.friends.length" class="muted">{{ store.friendsDetail || '暂无好友（未登录或为空）' }}</span>
      </div>
      <TopologyFlow :source-mode="store.sourceMode" @save="saveRoutes" />
    </div>
  </section>
</template>
