// 积木状态 + 二维布局逻辑（卡片装配画布，任务 2）
// blocks 契约不变；layout 按积木 id 关联 {x,y,w,h}
// 约定：h 恒 1；w 默认 2（整行），可拖成 1（半行）；column:2；视频积木不进画布、无 layout 条目
import { ref, computed } from 'vue'
import { createBlock } from '../components/cards/blockTypes.js'
import { CANVAS_TYPES } from '../components/blocks/index.js'

const DEFAULT_W = 2
const DEFAULT_H = 1
const COLS = 2

export function useBlocks() {
  const blocks = ref([])
  const layout = ref({})

  const canvasBlocks = computed(() =>
    (blocks.value || []).filter((b) => b && CANVAS_TYPES.includes(b.type))
  )
  const videoCount = computed(() =>
    (blocks.value || []).filter((b) => b && b.type === 'video').length
  )

  // 矩形相交判定（排除自身 id）
  function isOccupied(ln, id, x, y, w, h) {
    for (const [oid, o] of Object.entries(ln)) {
      if (oid === id) continue
      if (x < o.x + o.w && x + w > o.x && y < o.y + o.h && y + h > o.y) return true
    }
    return false
  }

  // 从 y=0 起逐行扫首个空位落位（w 恒 2 整行；column:2）
  function allocateLayout(block) {
    const ln = layout.value || {}
    const w = DEFAULT_W
    let y = 0
    while (true) {
      let placed = null
      for (let x = 0; x + w <= COLS; x++) {
        if (!isOccupied(ln, block.id, x, y, w, DEFAULT_H)) {
          placed = { x, y, w, h: DEFAULT_H }
          break
        }
      }
      if (placed) return placed
      y++
    }
  }

  // 回填/重置：清空后对每个画布积木逐个分配
  function allocateAllLayout() {
    const next = {}
    layout.value = next
    for (const b of canvasBlocks.value) {
      next[b.id] = allocateLayout(b)
    }
  }

  // gridstack change 回写：强制 h:1（二维画布恒一行）
  function applyChange(items) {
    if (!Array.isArray(items)) return
    const ln = { ...(layout.value || {}) }
    for (const it of items) {
      if (!it || !it.id) continue
      ln[it.id] = { x: it.x, y: it.y, w: it.w, h: DEFAULT_H }
    }
    layout.value = ln
  }

  // 添加积木：视频唯一 + 末尾、不进画布；非视频按视频位置插 + 分配 layout
  // 返回 { block, isVideo } 或 { error }
  function addBlock(type) {
    const b = createBlock(type)
    if (!b) return { error: '未知积木类型' }
    if (type === 'video') {
      if (videoCount.value >= 1) return { error: '视频积木最多 1 个（拆两条消息）' }
      blocks.value.push(b)
      return { block: b, isVideo: true }
    }
    const arr = blocks.value
    const vi = arr.findIndex((x) => x && x.type === 'video')
    let insertAt
    if (vi === 0) insertAt = 1 // 视频首位：插视频后（保持视频首位）
    else if (vi === arr.length - 1) insertAt = vi // 视频末位：插视频前（保持视频末位）
    else insertAt = arr.length
    arr.splice(insertAt, 0, b)
    layout.value = { ...(layout.value || {}), [b.id]: allocateLayout(b) }
    return { block: b, isVideo: false }
  }

  // 删除积木：清 blocks + 清 layout 条目
  function removeBlock(id) {
    const i = blocks.value.findIndex((b) => b && b.id === id)
    if (i < 0) return
    blocks.value.splice(i, 1)
    const ln = { ...(layout.value || {}) }
    delete ln[id]
    layout.value = ln
  }

  // 复制积木（视频禁止）：插其下 + 分配 layout
  function duplicateBlock(id) {
    const i = blocks.value.findIndex((b) => b && b.id === id)
    if (i < 0) return { error: '积木不存在' }
    const src = blocks.value[i]
    if (src.type === 'video') return { error: '视频积木最多 1 个，不能复制' }
    const copy = JSON.parse(JSON.stringify(src))
    copy.id = 'b' + Date.now() + Math.random().toString(36).slice(2, 6)
    blocks.value.splice(i + 1, 0, copy)
    layout.value = { ...(layout.value || {}), [copy.id]: allocateLayout(copy) }
    return { block: copy }
  }

  // 视频积木只能在首位/末位：拖拽/顺序变更后若在中间，自动吸附到最近端
  function fixVideoPosition() {
    const arr = blocks.value
    const vi = arr.findIndex((b) => b && b.type === 'video')
    if (vi < 0 || arr.length < 2) return
    if (vi === 0 || vi === arr.length - 1) return
    const toEnd = vi > (arr.length - 1) / 2
    const [v] = arr.splice(vi, 1)
    if (toEnd) arr.push(v)
    else arr.unshift(v)
  }

  // 重置积木（回填/默认）：新 blocks 后整体重分配 layout；
  // 可选 layoutOpt（模板/草稿带布局时）回填优先——保留 canvasBlocks 内 id 的坐标，
  // 缺布局/非法的 id 走 allocateLayout（宽容：残留/新增 id 不阻断）
  function resetBlocks(newBlocks, layoutOpt) {
    blocks.value = newBlocks || []
    if (layoutOpt && typeof layoutOpt === 'object' && !Array.isArray(layoutOpt)) {
      const ln = {}
      for (const b of canvasBlocks.value) {
        const pos = layoutOpt[b.id]
        if (
          pos && typeof pos === 'object' &&
          Number.isInteger(pos.x) && Number.isInteger(pos.y) &&
          (pos.w === 1 || pos.w === 2) && pos.h === 1
        ) {
          ln[b.id] = { x: pos.x, y: pos.y, w: pos.w, h: DEFAULT_H }
        } else {
          ln[b.id] = allocateLayout(b)
        }
      }
      layout.value = ln
    } else {
      allocateAllLayout()
    }
  }

  return {
    blocks,
    layout,
    canvasBlocks,
    videoCount,
    applyChange,
    addBlock,
    removeBlock,
    duplicateBlock,
    fixVideoPosition,
    resetBlocks,
  }
}
