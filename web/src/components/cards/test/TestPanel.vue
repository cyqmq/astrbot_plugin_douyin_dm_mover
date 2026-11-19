<script setup>
// 卡片测试页区域通用外壳：标题栏 + 内容槽。
// 各区域组件复用本壳，保证外观一致；区域差异只体现在内容与标题上。
defineProps({
  title: { type: String, default: '' },
  hint: { type: String, default: '' },
})
</script>

<template>
  <section class="test-panel">
    <header class="tp-head">
      <h3>{{ title }}</h3>
      <span v-if="hint" class="tp-hint">{{ hint }}</span>
    </header>
    <div class="tp-body">
      <slot />
    </div>
  </section>
</template>

<style scoped>
.test-panel {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  min-height: 0;
  min-width: 0;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
}
.tp-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex: none;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
}
.tp-head h3 {
  font-size: 12px;
  font-weight: 600;
  color: var(--text);
}
.tp-hint {
  font-size: 11px;
  color: var(--muted);
}
.tp-body {
  flex: 1;
  min-height: 0;
  min-width: 0;
  overflow: auto;
  padding: 10px 12px;
}
</style>
