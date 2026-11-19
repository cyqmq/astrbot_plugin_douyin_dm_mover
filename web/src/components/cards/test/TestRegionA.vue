<script setup>
// 区域 A：已保存模板卡片列表（底部「添加空白模板」卡）。
// 展示型组件：templates/selectedId 由父层持有，选择/新建经事件上抛。
import TestPanel from './TestPanel.vue'

defineProps({
  templates: { type: Array, default: () => [] },
  selectedId: { type: String, default: '' },
})
defineEmits(['select', 'create'])

// 画布渲染模式徽标样式（auto/markdown/media）
function mtClass(mt) {
  return 'mt-' + (mt || 'auto')
}
</script>

<template>
  <TestPanel title="模板" hint="已保存">
    <div class="tpl-list">
      <button
        v-for="t in templates"
        :key="t.id"
        class="tpl-card"
        :class="{ active: t.id === selectedId }"
        @click="$emit('select', t)"
      >
        <span class="tpl-name">{{ t.name || '未命名' }}</span>
        <span class="tpl-meta">
          <span class="tpl-badge" :class="mtClass(t.msg_type)">{{ t.msg_type || 'auto' }}</span>
          <span class="tpl-count">{{ (t.blocks || []).length }} 块</span>
        </span>
      </button>
      <button class="tpl-card tpl-add" @click="$emit('create')">
        <span class="tpl-add-icon">＋</span>
        <span>添加空白模板</span>
      </button>
      <p v-if="!templates.length" class="tpl-empty">暂无模板，点下方新建</p>
    </div>
  </TestPanel>
</template>

<style scoped>
.tpl-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.tpl-card {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 6px;
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--card);
  color: var(--text);
  cursor: pointer;
  text-align: left;
  transition: border-color 0.15s, background 0.15s;
}
.tpl-card:hover {
  border-color: var(--accent);
}
.tpl-card.active {
  border-color: var(--accent);
  background: color-mix(in srgb, var(--accent) 10%, var(--card));
}
.tpl-name {
  font-size: 13px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tpl-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}
.tpl-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 6px;
  background: rgba(88, 166, 255, 0.12);
  color: var(--accent);
}
.tpl-badge.mt-media {
  background: rgba(167, 139, 250, 0.14);
  color: #a78bfa;
}
.tpl-badge.mt-markdown {
  background: rgba(52, 211, 153, 0.12);
  color: #34d399;
}
.tpl-count {
  font-size: 11px;
  color: var(--muted);
}
.tpl-add {
  flex-direction: row;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border-style: dashed;
  color: var(--muted);
  font-size: 12px;
  font-weight: 500;
}
.tpl-add:hover {
  color: var(--accent);
  border-color: var(--accent);
}
.tpl-add-icon {
  font-size: 14px;
  line-height: 1;
}
.tpl-empty {
  font-size: 11px;
  color: var(--muted);
  text-align: center;
  margin: 4px 0 0;
}
</style>
