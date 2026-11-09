<script setup>
import { computed } from 'vue'
import { store, fmtTs, esc, apiPost, toast } from '../../composables/store.js'
import { refreshLogs } from '../../composables/actions.js'

async function clearLogs() { const d = await apiPost('logs/clear'); toast(d.detail || '已清空'); await refreshLogs() }
const logText = computed(() => store.logs.map(l => `${fmtTs(l.ts)} [${l.level}] ${l.msg}`).join('\n'))
const lvl = l => l.level === 'error' ? 'error' : (l.level === 'warning' ? 'warning' : 'info')
</script>

<template>
  <section>
    <div class="card">
      <h2>运行日志 <span class="muted">{{ store.logs.length ? (store.logs.length + ' 条') : '' }}</span></h2>
      <div class="bar" style="margin-bottom:8px">
        <button @click="refreshLogs">刷新日志</button>
        <button @click="clearLogs">清空日志</button>
      </div>
      <pre class="logs">{{ logText || '暂无日志' }}</pre>
    </div>
  </section>
</template>
