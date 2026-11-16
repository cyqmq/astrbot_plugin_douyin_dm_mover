<script setup>
// 占位符积木薄壳（画布编辑态表示）：显示 token chip + 类型名
// 编辑态显示 {title}，转发时由后端 _context 替换真实值；预览仍输出替换后值
import { computed } from 'vue'
import { PLACEHOLDERS } from '../cards/blockTypes.js'

const props = defineProps({
  block: { type: Object, default: null },
  disabled: { type: Boolean, default: false },
})

const meta = computed(() => (props.block ? PLACEHOLDERS[props.block.type] : null))
</script>

<template>
  <div class="block-placeholder" :class="{ disabled }">
    <span class="ph-chip">{{ meta?.token }}</span>
    <span class="ph-label">{{ meta?.label }}</span>
  </div>
</template>

<style scoped>
.block-placeholder {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  width: 100%;
}
.block-placeholder.disabled {
  opacity: 0.5;
}
.ph-chip {
  flex: none;
  font-family: monospace;
  font-size: 11px;
  color: var(--accent);
  background: var(--accent-soft);
  border-radius: 6px;
  padding: 3px 7px;
  line-height: 1.4;
}
.ph-label {
  flex: 1;
  min-width: 0;
  font-size: 12px;
  color: var(--muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
