<script setup>
// 区域 D：模板属性编辑（名字、类型、已插入卡片数量、保存/删除）。
// 删除采用二次确认：不是弹窗，点两下按钮，第一下按钮变状态（红色确认态），第二下才真正删除。
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import TestPanel from './TestPanel.vue'

const props = defineProps({
  selected: { type: Object, default: null },
  formError: { type: String, default: '' },
})
const emit = defineEmits(['save', 'delete', 'export'])

// 类型选项（与 A 区徽标配色一致）
const TYPES = [
  { id: 'auto', label: '自动', color: '#3b82f6' },
  { id: 'markdown', label: 'Markdown', color: '#34d399' },
  { id: 'media', label: '媒体', color: '#a78bfa' },
]

// 本地编辑态：名字 + 类型（随选中模板同步）
const name = ref('')
const msgType = ref('auto')
watch(
  () => props.selected,
  (t) => {
    name.value = (t && t.name) || ''
    msgType.value = (t && t.msg_type) || 'auto'
  },
  { immediate: true }
)

const cardCount = () => (props.selected && Array.isArray(props.selected.blocks) ? props.selected.blocks.length : 0)

// 空名字内联校验：常驻提示，直到用户改正（保存按钮同步禁用）
const nameError = computed(() => (!props.selected || !String(name.value || '').trim()) ? '模板名称不能为空' : '')

// 删除二次确认（点两下，按钮状态变化；3 秒内未点第二下则复位）
const confirmDel = ref(false)
let delTimer = null
function onDeleteClick() {
  if (!confirmDel.value) {
    confirmDel.value = true
    delTimer = setTimeout(() => { confirmDel.value = false }, 3000)
    return
  }
  clearTimeout(delTimer)
  confirmDel.value = false
  emit('delete')
}
function cancelConfirm() {
  if (confirmDel.value) { clearTimeout(delTimer); confirmDel.value = false }
}
onBeforeUnmount(() => { if (delTimer) clearTimeout(delTimer) })

// 按住保存导出（内部调试，无用户提示，仅 console）：长按 ≥600ms 触发导出，不触发保存；短按 = 保存。
// 导出不依赖空名校验（空名也能导出）；保存在点击回调按 nameError 拦截（不用 :disabled，
// 避免禁用态吞掉 pointerdown 导致长按失效）。
const HOLD_MS = 600
let holdTimer = null
let didExport = false
function onSaveDown() {
  didExport = false
  holdTimer = setTimeout(() => { didExport = true; emit('export') }, HOLD_MS)
}
function onSaveUp() { if (holdTimer) { clearTimeout(holdTimer); holdTimer = null } }
function onSaveClick() {
  if (didExport) { didExport = false; return }   // 长按导出已完成，忽略本次 click
  if (nameError.value) return                    // 空名不保存（沿用原有行为）
  emit('save', { name: name.value, msg_type: msgType.value })
}
</script>

<template>
  <TestPanel title="模板属性" hint="D">
    <!-- 未选中模板 -->
    <div v-if="!selected" class="d-empty">请先在左侧选择一个模板</div>

    <div v-else class="d-form">
      <!-- 模板名称 -->
      <label class="field">
        <span class="field-label">模板名称</span>
        <input v-model="name" class="field-input" :class="{ 'invalid': nameError }" placeholder="输入模板名称" @input="cancelConfirm" />
        <span v-if="nameError" class="err-text">{{ nameError }}</span>
      </label>

      <!-- 模板类型 -->
      <div class="field">
        <span class="field-label">类型</span>
        <div class="type-row">
          <button v-for="t in TYPES" :key="t.id" class="type-btn" :class="{ active: t.id === msgType }"
            :style="t.id === msgType ? { background: t.color, borderColor: t.color } : {}"
            @click="msgType = t.id; cancelConfirm()">
            <span class="type-dot" :style="{ background: t.color }"></span>{{ t.label }}
          </button>
        </div>
      </div>

      <!-- 已插入卡片数量 -->
      <div class="field">
        <span class="field-label">已插入卡片</span>
        <div class="count-box">{{ cardCount() }} 张</div>
      </div>

      <!-- 保存 / 删除 -->
      <div class="actions">
        <button class="btn btn-save" :class="{ dim: !!nameError }"
          title="点击保存；长按导出（内部调试）"
          @pointerdown="onSaveDown" @pointerup="onSaveUp" @pointerleave="onSaveUp" @click="onSaveClick">保存</button>
        <button class="btn btn-del" :class="{ 'confirming': confirmDel }" @click="onDeleteClick">
          {{ confirmDel ? '确认删除' : '删除' }}
        </button>
      </div>
      <!-- 操作失败内联提示（保存/删除） -->
      <span v-if="formError" class="err-text">{{ formError }}</span>
    </div>
  </TestPanel>
</template>

<style scoped>
.d-empty {
  font-size: 12px;
  color: var(--muted);
  padding: 8px 2px;
  line-height: 1.6;
}
.d-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.field-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--muted);
}
.field-input {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 7px 10px;
  font-size: 13px;
  color: var(--text);
  background: var(--bg);
  outline: none;
  transition: 0.15s;
}
.field-input:focus { border-color: var(--accent); }
.field-input.invalid { border-color: #dc2626; }

/* 内联报错：红色小字，常驻（不闪烁），直到改正 */
.err-text {
  font-size: 11px;
  color: #dc2626;
  line-height: 1.4;
}

/* 类型按钮 */
.type-row { display: flex; gap: 6px; }
.type-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--text);
  border-radius: 6px;
  padding: 5px 10px;
  font-size: 12px;
  cursor: pointer;
  transition: 0.15s;
}
/* 选中态：隐藏圆点、文字居中；切到其它类型恢复（圆点+左对齐） */
.type-btn.active { color: #fff; font-weight: 600; justify-content: center; }
.type-btn.active .type-dot { display: none; }
.type-dot { width: 8px; height: 8px; border-radius: 50%; flex: none; }

/* 卡片数量 */
.count-box {
  font-size: 13px;
  color: var(--text);
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 7px 10px;
}

/* 操作按钮 */
.actions { display: flex; gap: 8px; margin-top: 4px; }
.btn {
  flex: 1;
  min-width: 0;
  border: none;
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: 0.15s;
  /* 文案变化不改变按钮宽/高：不换行 + 溢出隐藏（flex 项可收缩，不被 min-content 撑宽） */
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  /* 长按导出：禁用文本选中，避免按住时选中按钮文字 */
  user-select: none;
  -webkit-user-select: none;
}
.btn-save { background: var(--accent); color: var(--card); }
.btn-save:hover { filter: brightness(0.92); }
.btn-save.dim { opacity: 0.6; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
/* 删除：默认描边态 → 第一下红色确认态（第二下才真正删除） */
.btn-del {
  background: transparent;
  color: #dc2626;
  border: 1px solid #dc2626;
}
.btn-del:hover { background: #fef2f2; }
/* 二次确认态：仅变色（不改尺寸/缩放），避免按钮变大 */
.btn-del.confirming {
  background: #dc2626;
  color: #fff;
  border-color: #dc2626;
  box-shadow: 0 0 0 2px rgba(220, 38, 38, 0.18);
}
</style>
