<script setup>
// 卡片装配画布：二维排版（gridstack 官方 v14）
// 线性拖拽列表 → 二维画布；h 恒 1、w 整行(2)/半行(1)、column:2、mode:'float'
// 关键：childrenSnapshot 只随 idsKey（增删积木 id）变；layout 用 toRaw 读坐标，不建响应式追踪
// —— 拖拽/resize 只改 layout，不触发 GridStack 重建、不重挂载组件、不丢焦点
import { computed, ref, watch, toRaw, h } from 'vue'
import { GridStack } from 'gridstack/dist/vue'
import 'gridstack/dist/gridstack.css'
import { CANVAS_TYPES, componentMap } from '../blocks/index.js'

const props = defineProps({
  blocks: { type: Array, default: () => [] },
  layout: { type: Object, default: () => ({}) },
  videoCount: { type: Number, default: 0 },
})
const emit = defineEmits(['change', 'select', 'toggle', 'duplicate', 'remove'])

// 画布只认 text/image/button/divider（视频不进画布）
const canvasBlocks = computed(() =>
  (props.blocks || []).filter((b) => b && CANVAS_TYPES.includes(b.type))
)
const idsKey = computed(() => canvasBlocks.value.map((b) => b.id).join(','))

// children 快照：只随 idsKey 变。布局坐标经 toRaw(props.layout) 读，不建立响应式追踪
const childrenSnapshot = ref([])
watch(
  idsKey,
  () => {
    const ln = toRaw(props.layout) || {}
    childrenSnapshot.value = canvasBlocks.value.map((b) => {
      const pos = ln[b.id] || { x: 0, y: 0, w: 2, h: 1 }
      // 非按钮恒 w:2 不可缩（QQ 全宽垂直堆叠，画布预览恒一致）；按钮唯一可 w:1/w:2
      const isButton = b.type === 'button'
      return {
        id: b.id,
        x: pos.x,
        y: pos.y,
        w: isButton ? pos.w : 2,
        h: 1,
        minW: isButton ? 1 : 2,
        maxW: 2,
        noResize: !isButton,
        component: b.type,
        // block 原样透传（响应式对象），属性面板改 data 触发薄壳组件 computed 重算
        props: { block: b, disabled: b.disabled !== false },
      }
    })
  },
  { immediate: true }
)

// options：children 用快照引用；不直接依赖 props.layout（避免拖拽回写重算 → 重挂载）
const options = computed(() => ({
  column: 2,
  cellHeight: 80,
  margin: 8,
  mode: 'float',
  maxRow: 0,
  resizable: { handles: 'e,w' },
  // 与后端 validate_layout 对齐：w∈[1,2]、h 恒 1（用户拉不出非法尺寸）
  minW: 1,
  maxW: 2,
  minH: 1,
  maxH: 1,
  children: childrenSnapshot.value,
}))

// 薄壳组件包一层可交互 wrapper（保持薄壳纯内容层）：
// 点击选中 → 父 select；卡片右上角操作（停用/复制/删除，.stop 不触发选中）
function withSelect(Comp) {
  return {
    name: 'SelectableBlock',
    props: ['block', 'disabled'],
    setup(p) {
      const act = (name) => (e) => {
        e.stopPropagation()
        emit(name, p.block)
      }
      return () =>
        h(
          'div',
          { class: ['assembly-item', { off: p.disabled }], onClick: () => emit('select', p.block) },
          [
            h('div', { class: 'assembly-item-body' }, [
              h(Comp, { block: p.block, disabled: p.disabled }),
            ]),
            h('div', { class: 'assembly-item-acts' }, [
              h('button', { class: 'act', title: '启用/停用', onClick: act('toggle') }, p.disabled ? '◌' : '◉'),
              h('button', { class: 'act', title: '复制', onClick: act('duplicate') }, '⧉'),
              h('button', { class: 'act danger', title: '删除', onClick: act('remove') }, '✕'),
            ]),
          ]
        )
    },
  }
}
// selectableMap 从 componentMap 派生（后续新增类型自动纳入画布，不硬编码）
const selectableMap = Object.fromEntries(
  Object.entries(componentMap).map(([type, Comp]) => [type, withSelect(Comp)])
)

function onChange(e, items) {
  emit('change', items || [])
}
</script>

<template>
  <div class="assembly">
    <div v-if="videoCount > 0" class="video-banner">
      视频积木：{{ videoCount }} 个（不进画布，顺序由积木顺序决定）
    </div>
    <div class="grid-wrap">
      <GridStack
        :key="idsKey"
        :options="options"
        :components="selectableMap"
        @change="onChange"
      />
    </div>
  </div>
</template>

<style scoped>
.assembly {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  gap: 8px;
}
.video-banner {
  flex: none;
  font-size: 11px;
  color: var(--muted);
  background: var(--bg);
  border: 1px dashed var(--border2);
  border-radius: 8px;
  padding: 6px 10px;
}
.grid-wrap {
  flex: 1;
  overflow: auto;
  min-height: 0;
  padding: 6px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 12px;
}
.grid-wrap :deep(.grid-stack) {
  background: transparent;
}
/* 卡片视觉：白底 + 边框 + 圆角 + 阴影（与 PhonePreview 气泡一致），薄壳组件保持纯内容层 */
.grid-wrap :deep(.grid-stack-item-content) {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  box-shadow: 0 3px 10px rgba(16, 24, 40, 0.07);
  overflow: hidden;
  cursor: pointer;
}
.grid-wrap :deep(.assembly-item) {
  position: relative;
  height: 100%;
  display: flex;
  align-items: stretch;
  box-sizing: border-box;
  padding: 8px;
}
.grid-wrap :deep(.assembly-item.off) {
  opacity: 0.55;
}
.grid-wrap :deep(.assembly-item-body) {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  display: flex;
  align-items: center;
}
.grid-wrap :deep(.assembly-item-acts) {
  position: absolute;
  top: 4px;
  right: 4px;
  display: flex;
  gap: 2px;
  opacity: 0;
  transition: 0.15s;
  background: var(--card);
  border-radius: 6px;
  padding: 2px;
  border: 1px solid var(--border);
}
.grid-wrap :deep(.assembly-item:hover .assembly-item-acts) {
  opacity: 1;
}
.grid-wrap :deep(.act) {
  width: 22px;
  height: 22px;
  border: none;
  border-radius: 5px;
  background: transparent;
  display: grid;
  place-items: center;
  cursor: pointer;
  color: var(--muted);
  font-size: 11px;
  padding: 0;
}
.grid-wrap :deep(.act:hover) {
  background: var(--bg);
  color: var(--text);
}
.grid-wrap :deep(.act.danger:hover) {
  background: rgba(248, 81, 73, 0.14);
  color: var(--bad);
}
</style>
