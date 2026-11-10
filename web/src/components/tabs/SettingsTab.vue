<script setup>
import ConfigTab from './ConfigTab.vue'
import { store } from '../../composables/store.js'
import { saveConfig } from '../../composables/actions.js'

async function toggleAdv(e) {
  store.advancedTargets = e.target.checked
  await saveConfig({ advanced_target_cards: !!store.advancedTargets })
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
      </div>
    </div>
  </section>
</template>
