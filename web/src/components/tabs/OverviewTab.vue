<script setup>
import { computed } from 'vue'
import { store, typeName, esc, fmtTs } from '../../composables/store.js'

const st = computed(() => store.status || {})
const pills = computed(() => {
  const auth = st.value.auth_state || 'idle'
  const cls = auth === 'ok' ? 'ok' : (auth === 'expired' ? 'bad' : 'warn')
  const label = { ok: '已登录', expired: '登录失效', unknown: '未知', idle: '未登录' }[auth] || '未登录'
  const d = st.value
  return [
    ['登录态', cls, label],
    ['抖音来源', d.douyin_enabled ? 'ok' : 'idle', d.douyin_enabled ? '启用' : '停用'],
    ['MFA', 'idle', d.mfa_mode || ''],
    ['路由', 'ok', (d.routes || 0) + ' 条'],
    ['网关', 'idle', d.gateway_mode || ''],
    ['失败缓存', d.failed_cache ? 'warn' : 'idle', d.failed_cache || '']
  ]
})
const stats = computed(() => {
  const d = st.value
  return [
    ['发石者', 'ok', d.senders_count || 0],
    ['搬运', 'idle', d.records_count || 0],
    ['路由', 'ok', d.routes || 0],
    ['去重', d.dedup ? 'ok' : 'idle', d.dedup ? '开' : '关']
  ]
})
const senderList = computed(() => store.senders)
const recordList = computed(() => store.records)
</script>

<template>
  <section>
    <div class="pills">
      <span v-for="[k, cls, v] in pills" :key="k" class="pill">
        <span class="dot" :class="'dot-' + cls"></span>{{ k }}：{{ v }}
      </span>
    </div>
    <div class="stats">
      <div v-for="[k, cls, v] in stats" :key="k" class="stat">
        <div class="k"><span class="dot" :class="'dot-' + cls"></span>{{ k }}</div>
        <div class="v">{{ v }}</div>
      </div>
    </div>
    <div class="grid2">
      <div class="card">
        <h2>最近发石者</h2>
        <ul class="list">
          <li v-for="s in senderList" :key="s.peer_id + s.ts" class="clickable" :title="'peer_id=' + s.peer_id">
            {{ fmtTs(s.ts) }} · {{ s.peer_name || ('用户 ' + s.peer_id) }}
            <span class="muted">[{{ typeName(s.type) }}]</span>
            <br v-if="s.text"><span class="muted">{{ s.text }}</span>
          </li>
          <li v-if="!senderList.length" class="empty">暂无</li>
        </ul>
      </div>
      <div class="card">
        <h2>最近搬运记录</h2>
        <ul class="list">
          <li v-for="x in recordList" :key="x.ts + x.peer" class="clickable" :title="x.error || ''">
            {{ fmtTs(x.ts) }} · [{{ x.type }}] {{ x.peer }} → {{ x.target }}
            <span class="muted">
              <span v-if="x.ok" style="color:var(--ok)">成功</span>
              <span v-else style="color:var(--bad)">失败 {{ x.error }}</span>
            </span>
          </li>
          <li v-if="!recordList.length" class="empty">暂无</li>
        </ul>
      </div>
    </div>
  </section>
</template>
