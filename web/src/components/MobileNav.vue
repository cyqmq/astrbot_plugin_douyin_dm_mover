<script setup>
import { store } from '../composables/store.js'

const NAV = [
  ['overview', '总览', 'M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z'],
  ['routes', '路由', 'M9 6l6 6-6 6'],
  ['policy', '策略', 'M4 7h16M4 12h16M4 17h9'],
  ['monitor', '监控', 'M12 12a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 7v5l3 2'],
  ['logs', '日志', 'M4 6h16M4 12h16M4 18h10'],
  ['settings', '设置', 'M12 12a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M19.1 4.9L17 7M7 17l-2.1 2.1']
]
</script>

<template>
  <nav class="mobile-nav">
    <div v-for="[key, label, d] in NAV" :key="key" class="mnav-item" :class="{ active: store.tab === key }"
         @click="store.tab = key">
      <svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path :d="d"/></svg>
      <span>{{ label }}</span>
    </div>
  </nav>
</template>
