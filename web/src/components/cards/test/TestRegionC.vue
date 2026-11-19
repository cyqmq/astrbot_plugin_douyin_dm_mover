<script setup>
// 区域 C：积木区（同 B 区画布感，无标题栏）。上方分类标签在画布外，下方画布：
//   仅竖直滑动（拖动/滚轮，无横向、无缩放、无滚动条）、积木卡不可拖动、
//   卡片外观仿 B 区（固定高、宽由内容、类型色左边条、标签+类型徽标）。
// 分类与积木：由模型决定——分类=全部/文本/媒体/按钮/装饰，积木按分类归属。
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'

const emit = defineEmits(['add'])
// 添加失败提示已移至画布内的原因卡片（B 区）

// 分类（第一个固定「全部」，其余顺序由模型决定）
const CATS = [
  { id: 'all', label: '全部' },
  { id: 'text', label: '文本' },
  { id: 'media', label: '媒体' },
  { id: 'button', label: '按钮' },
  { id: 'decor', label: '装饰' },
]

// 积木卡片（type 与 B 区一致，决定左边条颜色与徽标）
// 积木：type=粗分类（约束/配色），kind=细类型（属性/内容语义）。
// 按钮与链接按钮合并为一个「按钮」积木；链接按钮通过画布内右键菜单的「类型」子菜单切换（kind: button|link）。
const BLOCKS = [
  { id: 'b_txt', type: 'text', kind: 'text', cat: 'text', label: '文本卡' },
  { id: 'b_title', type: 'text', kind: 'title', cat: 'text', label: '标题' },
  { id: 'b_desc', type: 'text', kind: 'desc', cat: 'text', label: '描述文字' },
  { id: 'b_img', type: 'image', kind: 'image', cat: 'media', label: '图片' },
  { id: 'b_video', type: 'image', kind: 'video', cat: 'media', label: '视频' },
  { id: 'b_gif', type: 'image', kind: 'gif', cat: 'media', label: 'GIF动图' },
  { id: 'b_btn', type: 'button', kind: 'button', cat: 'button', label: '按钮' },
  { id: 'b_div', type: 'divider', kind: 'divider', cat: 'decor', label: '分割线' },
  { id: 'b_gap', type: 'divider', kind: 'gap', cat: 'decor', label: '间距' },
]

const activeCat = ref('all')
const filtered = computed(() =>
  activeCat.value === 'all' ? BLOCKS : BLOCKS.filter((b) => b.cat === activeCat.value)
)

// 画布：仅竖直滑动
const canvasRef = ref(null)
const contentRef = ref(null)
const vh = ref(0)
const contentH = ref(0)
const ty = ref(0)

const minTy = () => Math.min(0, vh.value - contentH.value)
const clampTy = (v) => Math.max(minTy(), Math.min(0, v))

function measure() {
  if (!canvasRef.value) return
  vh.value = canvasRef.value.clientHeight
  contentH.value = contentRef.value ? contentRef.value.offsetHeight : 0
  ty.value = clampTy(ty.value)
}

// 滚轮：竖直滚动（preventDefault 去掉原生滚动）
function onWheel(e) {
  ty.value = clampTy(ty.value - e.deltaY)
}

// 拖动：竖直平移
const drag = ref(null)
function onPointerDown(e) {
  drag.value = { startY: e.clientY, sy: ty.value }
  if (canvasRef.value) canvasRef.value.setPointerCapture(e.pointerId)
}
function onPointerMove(e) {
  const d = drag.value
  if (!d) return
  ty.value = clampTy(d.sy + (e.clientY - d.startY))
}
function onPointerUp() {
  drag.value = null
}

// 切换分类：更新过滤并回顶
function selectCat(id) {
  if (activeCat.value === id) return
  activeCat.value = id
  nextTick(() => { ty.value = 0; measure() })
}

function onResize() { measure() }
onMounted(() => {
  measure()
  window.addEventListener('resize', onResize)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
})
</script>

<template>
  <div class="blocks-region">
    <!-- 分类标签：画布外（顶部），第一个为「全部」 -->
    <div class="cat-bar">
      <button v-for="cat in CATS" :key="cat.id" class="cat-tab" :class="{ active: cat.id === activeCat }"
        @click="selectCat(cat.id)">{{ cat.label }}</button>
    </div>

    <!-- 画布：仅竖直滑动，无滚动条 -->
    <div ref="canvasRef" class="c-canvas" @wheel.prevent="onWheel"
      @pointerdown="onPointerDown" @pointermove="onPointerMove" @pointerup="onPointerUp" @pointercancel="onPointerUp">
      <div ref="contentRef" class="c-content" :style="{ transform: `translateY(${ty}px)` }">
        <div v-for="b in filtered" :key="b.id" class="block" :class="'t-' + b.type"
          title="点击添加到画布"
          @pointerdown.stop @click.stop="emit('add', { type: b.type, kind: b.kind, label: b.label })">
          <span class="block-label">{{ b.label }}</span>
          <span class="block-type">{{ b.type }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.blocks-region {
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

/* 分类标签栏：画布外，固定顶部 */
.cat-bar {
  flex: none;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
  overflow-x: auto;
}
.cat-tab {
  flex: none;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--muted);
  border-radius: 6px;
  padding: 4px 12px;
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
  transition: 0.15s;
}
.cat-tab:hover { border-color: var(--accent); color: var(--text); }
.cat-tab.active { background: var(--accent); border-color: var(--accent); color: var(--card); font-weight: 600; }

/* 画布：仅竖直滑动 */
.c-canvas {
  flex: 1;
  min-height: 0;
  position: relative;
  overflow: hidden;
  cursor: grab;
  touch-action: none;
}
.c-canvas:active { cursor: grabbing; }
.c-content {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  display: flex;
  flex-wrap: wrap;
  align-content: flex-start;
  gap: 8px;
  padding: 12px;
  box-sizing: border-box;
  will-change: transform;
}

/* 积木卡：外观仿 B 区（固定高、宽由内容、类型色左边条），不可拖动 */
.block {
  flex: none;
  display: flex;
  align-items: center;
  gap: 6px;
  height: 44px;
  padding: 0 10px;
  box-sizing: border-box;
  background: var(--card);
  border: 1px solid var(--border);
  border-left: 3px solid var(--accent);
  border-radius: 8px;
  user-select: none;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}
.block { cursor: pointer; }
.block:hover { border-color: var(--accent); }
.block.t-image { border-left-color: #a78bfa; }
.block.t-button { border-left-color: #f59e0b; }
.block.t-divider { border-left-color: #94a3b8; }
.block-label { font-size: 12px; color: var(--text); white-space: nowrap; }
.block-type { font-size: 10px; color: var(--muted); }
</style>
