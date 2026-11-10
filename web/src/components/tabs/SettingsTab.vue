<script setup>
import ConfigTab from './ConfigTab.vue'
import { store } from '../../composables/store.js'
import { saveConfig } from '../../composables/actions.js'

async function toggleAdv(e) {
  store.advancedTargets = e.target.checked
  await saveConfig({ advanced_target_cards: !!store.advancedTargets })
}
async function toggleFloat(e) {
  store.floatLog.enabled = e.target.checked
  if (!e.target.checked) store.floatLog.open = false
  await saveConfig({ float_log_enabled: !!store.floatLog.enabled })
}
</script>
<template>
  <ConfigTab mode="settings" />
  <section>
    <div class="card cfg">
      <div class="gcard">
        <h2>高级</h2>
        <label class="f">
          <span>目标群卡片（高级）</span>
          <input type="checkbox" :checked="store.advancedTargets" @change="toggleAdv($event)">
          <span class="hint">开启后路由页目标列使用「适配器 + 群号」高级卡片；默认仅需 QQ群 / 私聊 两种目标。</span>
        </label>
        <label class="f">
          <span>全局浮动调试日志</span>
          <input type="checkbox" :checked="store.floatLog.enabled" @change="toggleFloat($event)">
          <span class="hint">右下角悬浮日志球，展开后可拖动监控运行日志（复用日志数据源，展开时拉取、折叠即停）。</span>
        </label>
      </div>
    </div>
  </section>
</template>
