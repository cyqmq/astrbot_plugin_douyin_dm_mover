<script setup>
import { computed } from 'vue'
import { store, TITLES, toastMsg } from './composables/store.js'
import Sidebar from './components/Sidebar.vue'
import MobileNav from './components/MobileNav.vue'
import LoginModal from './components/LoginModal.vue'
import OverviewTab from './components/tabs/OverviewTab.vue'
import RoutesTab from './components/tabs/RoutesTab.vue'
import FriendsTab from './components/tabs/FriendsTab.vue'
import PolicyTab from './components/tabs/PolicyTab.vue'
import MonitorTab from './components/tabs/MonitorTab.vue'
import LogsTab from './components/tabs/LogsTab.vue'
import SettingsTab from './components/tabs/SettingsTab.vue'
import FloatLog from './components/FloatLog.vue'

const title = computed(() => TITLES[store.tab]?.[0] || '')
const sub = computed(() => TITLES[store.tab]?.[1] || '')
</script>

<template>
  <div class="app">
    <Sidebar />
    <main>
      <div class="top">
        <div>
          <h1>{{ title }}</h1>
          <p>{{ sub }}</p>
        </div>
        <div class="bar">
          <label class="muted"><input type="checkbox" v-model="store.auto"> 自动</label>
          <input type="number" v-model.number="store.autoSec" min="2" max="120" style="width:58px" title="自动刷新间隔(秒)">
        </div>
      </div>
      <OverviewTab v-if="store.tab === 'overview'" />
      <RoutesTab v-else-if="store.tab === 'routes'" />
      <FriendsTab v-else-if="store.tab === 'friends'" />
      <PolicyTab v-else-if="store.tab === 'policy'" />
      <MonitorTab v-else-if="store.tab === 'monitor'" />
      <LogsTab v-else-if="store.tab === 'logs'" />
      <SettingsTab v-else-if="store.tab === 'settings'" />
    </main>
    <MobileNav />
  </div>
  <LoginModal />
  <FloatLog v-if="store.floatLog.enabled" />
  <div id="toast" :style="{ opacity: toastMsg.on ? 1 : 0 }">{{ toastMsg.text }}</div>
</template>
