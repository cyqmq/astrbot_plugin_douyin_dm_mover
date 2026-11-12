<script setup>
import { computed, onMounted, ref } from 'vue'
import { store } from '../../composables/store.js'
import { loadSourceGroups } from '../../composables/actions.js'

const q = ref('')
const sel = ref(null) // 选中群详情
const ROLE = { 1: '群主', 2: '管理员', 3: '成员' }

const filtered = computed(() => {
  const s = q.value.trim().toLowerCase()
  const list = store.sourceGroups || []
  if (!s) return list
  return list.filter(g =>
    (g.name || '').toLowerCase().includes(s) ||
    String(g.group_id || '').toLowerCase().includes(s))
})

function roleOf(r) { return ROLE[Number(r || 0)] || '成员' }
function avatarChar(g) { return (g.name || '群').slice(0, 1) }
function lastSender(g) { return g.last_sender_nickname || g.last_sender_uid || '—' }

onMounted(() => {
  const stale = Date.now() - (store.sourceGroupsLoadedAt || 0) > 300000
  if (!store.sourceGroups.length || stale) loadSourceGroups(!store.sourceGroups.length)
})
</script>

<template>
  <section>
    <div class="bar" style="margin-bottom:10px">
      <input v-model="q" class="fr-search" placeholder="搜索群名/群ID…">
      <button class="mini" title="强制重拉群列表" @click="loadSourceGroups(true)">↻ 刷新</button>
      <span class="muted">{{ store.sourceGroups.length }} 个群聊</span>
    </div>

    <div v-if="store.sourceGroupsLoading" class="card muted" style="padding:16px;text-align:center">加载中…</div>
    <div v-else-if="!store.sourceGroups.length" class="card" style="padding:16px;text-align:center">
      <span class="muted">暂无群聊（未登录或拉取失败）</span>
    </div>

    <!-- 群卡片网格 -->
    <div v-else class="gr-grid">
      <div v-for="g in filtered" :key="g.group_id" class="card gr-card"
        :class="{ sel: sel && sel.group_id === g.group_id }" @click="sel = sel && sel.group_id === g.group_id ? null : g">
        <div class="gr-head">
          <div class="gr-avatar">{{ avatarChar(g) }}</div>
          <div class="gr-title">
            <div class="gr-name">{{ g.name || '群' }}</div>
            <div class="muted">{{ g.group_id }}</div>
          </div>
        </div>
        <div class="gr-meta">
          <span>{{ g.member_count || 0 }} 人</span>
          <span class="muted">最后:{{ lastSender(g) }}</span>
        </div>
        <div class="gr-more muted">{{ sel && sel.group_id === g.group_id ? '收起详情' : '点击查看成员' }}</div>
      </div>
    </div>

    <!-- 群详情：成员列表 -->
    <div v-if="sel" class="card gr-detail">
      <div class="gr-detail-head">
        <strong>{{ sel.name || '群' }}</strong>
        <span class="muted">{{ sel.group_id }} · {{ sel.member_count || 0 }} 人</span>
        <button class="mini" @click="sel = null">收起</button>
      </div>
      <ul class="list gr-members">
        <li v-for="m in (sel.members || [])" :key="m.uid">
          <span class="fr-name">{{ m.nickname || m.uid }}</span>
          <span class="gr-role" :class="{ lead: Number(m.role) === 1 }">{{ roleOf(m.role) }}</span>
          <span class="muted">{{ m.uid }}</span>
        </li>
        <li v-if="!(sel.members || []).length" class="empty">无成员数据（群列表仅返回前 100 人，更大群需 cmd=605 分页）</li>
      </ul>
    </div>
  </section>
</template>
