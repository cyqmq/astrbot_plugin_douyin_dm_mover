<script setup>
// 中栏：消息拼装——积木序列编排（vue-draggable-plus useDraggable 拖拽排序）
// 点击选中 → 右栏编辑属性；启停/复制/删除
import { onMounted, ref } from 'vue'
import { useDraggable } from 'vue-draggable-plus'
import { BLOCK_TYPES, placeholderToken } from './blockTypes.js'

// blocks 双向绑定（父组件 v-model，默认 modelValue）
const blocks = defineModel({ type: Array, default: () => [] })

const props = defineProps({
  selectedIndex: { type: Number, default: -1 },
})

const emit = defineEmits(['select', 'toggle', 'duplicate', 'remove'])

// 拖拽容器 ref + useDraggable（onMounted 后调用，el 已挂载，需 start() 启动）
const seqEl = ref(null)
onMounted(() => {
  const drag = useDraggable(seqEl, blocks, { animation: 150, ghostClass: 'drag-ghost' })
  drag.start()
})

function blockLabel(type) {
  return (BLOCK_TYPES[type] && BLOCK_TYPES[type].label) || type
}

// 积木简要内容（列表摘要显示）
function summary(b) {
  const d = b.data || {}
  switch (b.type) {
    case 'text': return d.text || '（空）'
    case 'image': return '图片'
    case 'divider': return '分割线'
    default: return placeholderToken(b.type) || (BLOCK_TYPES[b.type] && BLOCK_TYPES[b.type].label) || ''
  }
}
</script>

<template>
  <div class="composer">
    <div class="composer-hint">拖拽排序 · 点击选中后在右侧编辑属性</div>

    <div ref="seqEl" class="seq">
      <div
        v-for="(b, i) in blocks"
        :key="b.id"
        class="seq-item"
        :class="{ selected: i === selectedIndex, off: b.disabled }"
        @click="emit('select', i)"
      >
        <span class="grip">⋮⋮</span>
        <span class="seq-index">{{ i + 1 }}</span>
        <span class="seq-info">
          <span class="seq-name">{{ blockLabel(b.type) }}</span>
          <span class="seq-meta">{{ summary(b) }}</span>
        </span>
        <span class="seq-acts">
          <button class="ico" title="启用/停用" @click.stop="emit('toggle', i)">
            {{ b.disabled ? '◌' : '◉' }}
          </button>
          <button class="ico" title="复制" @click.stop="emit('duplicate', i)">⧉</button>
          <button class="ico danger" title="删除" @click.stop="emit('remove', i)">✕</button>
        </span>
      </div>
    </div>

    <div v-if="!blocks.length" class="empty">暂无积木，从右侧积木库添加</div>
  </div>
</template>

<style scoped>
.composer {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  gap: 10px;
}
.composer-hint {
  font-size: 11px;
  color: var(--muted);
  flex: none;
}
.seq {
  flex: 1;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
  min-height: 0;
  padding-right: 4px;
}
.seq::-webkit-scrollbar { width: 6px; }
.seq::-webkit-scrollbar-thumb { background: var(--border2); border-radius: 3px; }
.seq-item {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 9px 10px;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  cursor: pointer;
  position: relative;
  transition: .15s;
}
.seq-item:hover {
  border-color: var(--accent);
  box-shadow: 0 3px 10px rgba(16, 24, 40, .07);
}
.seq-item.selected {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
}
.seq-item.off {
  background: var(--bg);
  opacity: .6;
}
.seq-item.off .seq-name { color: var(--muted); }
.grip {
  color: var(--muted);
  font-size: 14px;
  line-height: 1;
  cursor: grab;
  user-select: none;
  width: 10px;
  flex: none;
  letter-spacing: -1px;
}
.seq-index {
  width: 20px;
  height: 20px;
  border-radius: 6px;
  flex: none;
  background: var(--bg);
  color: var(--muted);
  font-size: 11px;
  font-weight: 600;
  display: grid;
  place-items: center;
}
.seq-item.selected .seq-index {
  background: var(--accent);
  color: var(--card);
}
.seq-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.seq-name { font-size: 13px; font-weight: 500; color: var(--text); }
.seq-meta {
  font-size: 11px;
  color: var(--muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.seq-acts {
  display: flex;
  gap: 2px;
  flex: none;
  opacity: .55;
  transition: .15s;
}
.seq-item:hover .seq-acts,
.seq-item.selected .seq-acts { opacity: 1; }
.ico {
  width: 26px;
  height: 26px;
  border-radius: 7px;
  border: none;
  background: transparent;
  display: grid;
  place-items: center;
  cursor: pointer;
  color: var(--muted);
  font-size: 13px;
}
.ico:hover { background: var(--bg); color: var(--text); }
.ico.danger:hover { background: rgba(248,81,73,.14); color: var(--bad); }
.drag-ghost {
  opacity: .4;
  border-style: dashed;
}
.empty {
  padding: 30px 16px;
  text-align: center;
  font-size: 12px;
  color: var(--muted);
}
</style>
