<script setup>
// 区域 B：装配画布（全画布，无标题栏）。网格画布：
//   可缩放（滚轮）、仅向右/下拖动（左/上为边界，不能拖出内容原点）、
//   行号列标冻结在画布内（覆盖在内容上方，内容在标尺下平移）、
//   卡片可拖动、物理碰撞不可重叠、卡片固定高度、宽度由内容决定、右下角「预览」。
// 冻结安全：不用 ResizeObserver（避免观察者写入响应式导致渲染环），
//   仅在 onMounted + window resize 测量，且尺寸不变时不写值。
import { ref, reactive, computed, watch, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps({
  cards: { type: Array, default: null },   // 选中模板的 blocks（null=无模板→演示）
  templateId: { type: String, default: '' },
  addRequest: { type: Object, default: null },   // 点击积木区添加：{seq, type, label}
  exportSignal: { type: Number, default: 0 },   // 按住保存导出触发（自增）
  selId: { type: String, default: '' },   // 选中卡 id（点击卡选中，D 区同步行约束区）
})
const emit = defineEmits(['preview', 'change', 'export', 'select-card'])

// 画布常量
const RULER = 24          // 行号列标条宽/高
const COL_W = 100         // 列宽（标尺参考）
const ROW_H = 44          // 行高 = 卡片固定高度
// 单元格吸附机制：格不可见，仅在松手时吸附；拖动中自由移动不吸附
const CELL_W = COL_W      // 横向吸附步长（与列标对齐）
const CELL_H = ROW_H      // 纵向吸附步长（与行号对齐）
const MIN_S = 0.3
const MAX_S = 1.8
const BOARD_W = 4000
const BOARD_H = 3000

// 视口
const canvasRef = ref(null)
const vw = ref(0)
const vh = ref(0)
// 视图变换：内容 translate(tx,ty) scale(s)
const tx = ref(0)
const ty = ref(0)
const s = ref(1)

// 卡片：本地副本（可拖位）；空则种子演示卡
const list = ref([])
// 卡片标准宽度 = 整数个单元格（无 1.5 格）：cellN[id] = 占几格，由内容自然宽度决定
const cellN = reactive({})
// 卡片新标签元数据：能否与其他卡片同行 / 能否与自己（同类型）同行 / 一行内最多同类型数量
const CARD_META = {
  text:    { canShareRow: true,  canSelfRow: true,  maxSameTypePerRow: 2 },
  image:   { canShareRow: false, canSelfRow: false, maxSameTypePerRow: 1 },
  button:  { canShareRow: true,  canSelfRow: false, maxSameTypePerRow: 5 },
  divider: { canShareRow: false, canSelfRow: false, maxSameTypePerRow: 1 },
}
const cardMeta = (c) => CARD_META[c.type] || { canShareRow: true, canSelfRow: true, maxSameTypePerRow: 2 }

// 细类型元数据：type=粗分类（约束/配色），label=类型名，props=右键「属性」可编辑字段。
// props[].key 对应卡片字段（label/url/value），type: 'text'|'number'。
const KIND_INFO = {
  text:    { type: 'text',    label: '文本卡',   props: [{ key: 'label', label: '内容', type: 'text', ph: '请输入文本内容' }] },
  title:   { type: 'text',    label: '标题',     props: [{ key: 'label', label: '标题文字', type: 'text', ph: '请输入标题' }] },
  desc:    { type: 'text',    label: '描述文字', props: [{ key: 'label', label: '描述文字', type: 'text', ph: '请输入描述' }] },
  image:    { type: 'image', label: '转发的图片',   props: [{ key: 'label', label: '说明文字', type: 'text', ph: '可选' }] },
  image_url:{ type: 'image', label: '自定义地址图片', props: [{ key: 'url', label: '图片地址', type: 'text', ph: 'https://…' }, { key: 'label', label: '说明文字', type: 'text', ph: '可选' }] },
  video:    { type: 'image', label: '转发的视频',   props: [{ key: 'label', label: '说明文字', type: 'text', ph: '可选' }] },
  video_url:{ type: 'image', label: '自定义地址视频', props: [{ key: 'url', label: '视频地址', type: 'text', ph: 'https://…' }] },
  gif:      { type: 'image', label: 'GIF动图',     props: [{ key: 'url', label: '动图地址', type: 'text', ph: 'https://…' }] },
  button:  { type: 'button',  label: '按钮',     props: [{ key: 'label', label: '按钮文字', type: 'text', ph: '请输入按钮文字' }, { key: 'url', label: '跳转链接', type: 'text', ph: '可选' }] },
  link:    { type: 'button',  label: '链接按钮', props: [{ key: 'label', label: '链接文字', type: 'text', ph: '请输入链接文字' }, { key: 'url', label: '跳转链接', type: 'text', ph: '可选' }] },
  divider: { type: 'divider', label: '分割线',   props: [] },
  gap:     { type: 'divider', label: '间距',     props: [{ key: 'value', label: '间距(px)', type: 'number', ph: '' }] },
}
// 旧卡/外部卡无 kind 时，按 type+label 推断（兼容持久化数据）
function deriveKind(c) {
  if (c.kind && KIND_INFO[c.kind]) return c.kind
  const m = { '标题': 'title', '描述文字': 'desc', '视频': 'video', 'GIF动图': 'gif', '链接按钮': 'link', '间距': 'gap' }
  return m[c.label] || c.type
}
const kindOf = (c) => deriveKind(c)
// 视频卡只能在首/末行（拆两条消息：视频气泡 + 正文，_chains_from_markdown 只拆一个）：
// 拖放落中间行 → 违规（保存前即阻止，配合后端 templates_set 视频规则双保险）
function videoRowViolation(card, y) {
  const k = kindOf(card)
  if (k !== 'video' && k !== 'video_url') return false
  const ys = list.value.filter((x) => x.id !== card.id).map((x) => x.y)
  if (!ys.length) return false
  const minY = Math.min(...ys)
  const maxY = Math.max(...ys)
  return y > minY && y < maxY
}
// 类型「家族」：同一家族内的 kind 可经右键菜单互切（如 转发/自定义地址、按钮/链接按钮）
const KIND_FAMILIES = [
  { kinds: ['button', 'link'], labels: { button: '按钮', link: '链接按钮' } },
  { kinds: ['image', 'image_url'], labels: { image: '转发的图片', image_url: '自定义地址图片' } },
  { kinds: ['video', 'video_url'], labels: { video: '转发的视频', video_url: '自定义地址视频' } },
]
const familyOf = (kind) => KIND_FAMILIES.find((f) => f.kinds.includes(kind)) || null
// 卡片显示文本：文本类=内容(label)；媒体转发类=说明(label)，自定义地址类=url；按钮类=按钮文字；装饰类=类型名/值
function cardDisplay(c) {
  const k = kindOf(c)
  if (k === 'image' || k === 'video') return c.label || KIND_INFO[k].label
  if (k === 'image_url' || k === 'video_url' || k === 'gif') return c.url || c.label || KIND_INFO[k].label
  if (k === 'gap') return c.value ? c.value + 'px' : KIND_INFO[k].label
  if (k === 'divider') return KIND_INFO[k].label
  return c.label || KIND_INFO[k].label
}

function syncCards() {
  // 有选中模板（blocks 为数组，可为空）→ 用模板数据；无模板（null）→ 画布留空。
  // 归一化 kind：兼容无 kind 的旧数据（按 type+label 推断）。
  const src = Array.isArray(props.cards) ? JSON.parse(JSON.stringify(props.cards)) : []
  for (const c of src) c.kind = deriveKind(c)
  // 清残留宽度 + 回填持久化宽度（width_cells）：切换模板/刷新后保持原宽
  for (const k of Object.keys(cellN)) delete cellN[k]
  for (const c of src) if (c.width_cells) cellN[c.id] = c.width_cells
  list.value = src
}

// 卡片渲染/碰撞宽度 = cellN * CELL_W（未测量时按 1 格）
const cardW = (c) => (cellN[c.id] || 1) * CELL_W
const cw = (c) => cardW(c)
// 碰撞判定：矩形与其它卡重叠（含边）
function collides(c, x, y) {
  return list.value.some((o) => o.id !== c.id && x < o.x + cw(o) && x + cw(c) > o.x && y < o.y + ROW_H && y + ROW_H > o.y)
}

// 行约束强制排版（对称判定，不能只查被拖卡）：
//   独占规则：行内多于 1 张时，行内【每一张】都必须 canShareRow=true（否则独占卡被挤同行）。
//   同类型上限：本卡类型在行内数量（含本卡）不得超过该类型上限（canSelfRow=false 由上限=1 覆盖）。
// 行号按吸附后的单元格行判定（round(y/CELL_H)），与吸附模型一致。
function rowViolation(c, x, y) {
  const crow = Math.round(y / CELL_H)
  const others = list.value.filter((o) => o.id !== c.id && Math.round(o.y / CELL_H) === crow)
  const total = others.length + 1
  // 按钮固定底部（官方：按钮仅挂载 Markdown 消息最底部，任何内容都不能低于按钮行）。
  // 非按钮卡必须在所有按钮行之上；按钮卡必须在所有非按钮行之下。该规则同时覆盖：
  //   - 同行混放禁止（按钮与非按钮同行 → 下方判定必然违规）。
  //   - 内容卡低于按钮行禁止（如图片被加到按钮下方 → 违规，红影回退）。
  if (c.type === 'button') {
    const maxNonRow = list.value
      .filter((o) => o.id !== c.id && o.type !== 'button')
      .reduce((m, o) => Math.max(m, Math.round(o.y / CELL_H)), -1)
    if (crow <= maxNonRow) return true
  } else {
    const minBtnRow = list.value
      .filter((o) => o.id !== c.id && o.type === 'button')
      .reduce((m, o) => Math.min(m, Math.round(o.y / CELL_H)), Infinity)
    if (crow >= minBtnRow) return true
  }
  // 独占规则：行内多于 1 张 → 每一张都必须可同行；任一独占即违规
  if (total >= 2) {
    if (!cardMeta(c).canShareRow) return true
    for (const o of others) if (!cardMeta(o).canShareRow) return true
  }
  // 同类型上限：本卡类型数量（含本卡）不得超过上限
  const sameType = others.filter((o) => o.type === c.type).length + 1
  if (sameType > cardMeta(c).maxSameTypePerRow) return true
  // 官方约束：按钮仅支持 Markdown（msg_type=2），最多 5 行按钮，每行最多 5 个；一张按钮卡 = 一个按钮。
  // 整页按钮所占行数（含本卡落位行）不得超过 5。
  if (c.type === 'button') {
    const rows = new Set()
    for (const o of list.value) {
      if (o.id === c.id) continue
      if (o.type === 'button') rows.add(Math.round(o.y / CELL_H))
    }
    rows.add(crow)
    if (rows.size > 5) return true
  }
  return false
}
// 落点是否可用：几何碰撞 或 行约束违规
const placeOk = (c, x, y) => !collides(c, x, y) && !rowViolation(c, x, y)

// ---- 单元格吸附 + 虚影 ----
// 吸附：就近取整到单元格边界；格不可见，仅松手吸附；拖动中自由（不吸附）
const snap = (v, cell) => Math.round(v / cell) * cell
const ghostX = ref(0)
const ghostY = ref(0)
const ghostInvalid = ref(false)

// ---- 标尺（Excel 行号列标，冻结显示可视区；content 偏移 RULER，标尺在画布内覆盖内容） ----
function colLabel(i) {
  let s = ''
  i = i + 1
  while (i > 0) { const m = (i - 1) % 26; s = String.fromCharCode(65 + m) + s; i = Math.floor((i - 1) / 26) }
  return s
}
const topCols = computed(() => {
  const cols = []
  if (vw.value <= 0) return cols
  const cwz = COL_W * s.value
  const i0 = Math.max(0, Math.floor((-tx.value - RULER) / cwz))
  const i1 = Math.min(Math.ceil((vw.value - tx.value) / cwz), Math.ceil(BOARD_W / cwz))
  for (let i = i0; i < i1; i++) cols.push({ i, label: colLabel(i), sx: tx.value + i * cwz, sw: cwz })
  return cols
})
const leftRows = computed(() => {
  const rows = []
  if (vh.value <= 0) return rows
  const rh = ROW_H * s.value
  const j0 = Math.max(0, Math.floor((-ty.value - RULER) / rh))
  const j1 = Math.min(Math.ceil((vh.value - ty.value) / rh), Math.ceil(BOARD_H / rh))
  for (let j = j0; j < j1; j++) rows.push({ j, label: j + 1, sy: ty.value + j * rh, sh: rh })
  return rows
})

// ---- 变换边界（左/上为边界：tx/ty <= 0） ----
function minTx() { return Math.min(0, vw.value - BOARD_W * s.value) }
function minTy() { return Math.min(0, vh.value - BOARD_H * s.value) }
const clampTx = (v) => Math.max(minTx(), Math.min(0, v))
const clampTy = (v) => Math.max(minTy(), Math.min(0, v))

// ---- 视口尺寸（onMounted + window resize；仅在变化时写值，避免无用写入） ----
function measure() {
  if (!canvasRef.value) return
  const w = canvasRef.value.clientWidth
  const h = canvasRef.value.clientHeight
  if (w === vw.value && h === vh.value) return
  vw.value = w
  vh.value = h
  tx.value = clampTx(tx.value)
  ty.value = clampTy(ty.value)
}

// ---- 滚轮缩放（以光标为中心） ----
function onWheel(e) {
  const rect = canvasRef.value.getBoundingClientRect()
  const mx = e.clientX - rect.left
  const my = e.clientY - rect.top
  const bx = (mx - tx.value) / s.value
  const by = (my - ty.value) / s.value
  const factor = e.deltaY < 0 ? 1.1 : 1 / 1.1
  s.value = Math.max(MIN_S, Math.min(MAX_S, s.value * factor))
  tx.value = clampTx(mx - bx * s.value)
  ty.value = clampTy(my - by * s.value)
}

// ---- 拖动（空白=平移；卡片=拖卡碰撞） ----
// 位置计算均为「视口平移感知」：用当前 tx/ty 反推指针画布坐标，
// 使边缘滚动（edge scroll）平移视口时，被拖对象仍跟随指针，无需松手即可移出当前视野。
// drag: {mode:'pan'|'card', card, startX,startY, sx,sy, ox0,oy0, bx0,by0, lastX,lastY}
const drag = ref(null)
// 拖动监听挂在 window（而非依赖 canvas 的 pointer capture）：指针到视口边缘、甚至离开画布，
// 都能持续收到 pointermove，保证边缘滚动与拖动不因 capture 行为而失效。
function onPointerDown(e) {
  if (e.button !== 0) return   // 仅左键平移；右键交给 contextmenu 菜单
  // 画布平移不触发边缘滚动（边缘滚动仅用于拖动卡片）
  drag.value = { mode: 'pan', startX: e.clientX, startY: e.clientY, sx: tx.value, sy: ty.value, lastX: e.clientX, lastY: e.clientY }
  startDragListeners()
}
function onCardDown(c, e) {
  if (e.button !== 0) return   // 仅左键拖卡；右键由 contextmenu 打开菜单
  const rect = canvasRef.value.getBoundingClientRect()
  drag.value = {
    mode: 'card', card: c, startX: e.clientX, startY: e.clientY,
    ox0: c.x, oy0: c.y,   // 拖动起点画布坐标（违规落点回退用）
    bx0: (e.clientX - rect.left - tx.value) / s.value,   // 起点指针画布坐标
    by0: (e.clientY - rect.top - ty.value) / s.value,
    lastX: e.clientX, lastY: e.clientY,
    moved: false,   // 是否真正拖动了（边缘滚动需实际拖动才生效，按下不动不自动滚）
  }
  ghostX.value = snap(c.x, CELL_W)
  ghostY.value = snap(c.y, CELL_H)
  ghostInvalid.value = !placeOk(c, ghostX.value, ghostY.value)
  startDragListeners()
  startEdgeScroll()   // 边缘滚动：仅拖动卡片时启用
}
// 卡片按指针画布坐标更新（含分轴碰撞 + 虚影吸附）；edge scroll 也用此以当前 tx/ty 重算
function updateCardDrag(d, clientX, clientY) {
  const c = d.card
  const rect = canvasRef.value.getBoundingClientRect()
  const bx = (clientX - rect.left - tx.value) / s.value
  const by = (clientY - rect.top - ty.value) / s.value
  const nx = Math.max(0, Math.min(BOARD_W - cw(c), d.ox0 + (bx - d.bx0)))
  const ny = Math.max(0, Math.min(BOARD_H - ROW_H, d.oy0 + (by - d.by0)))
  // 分轴碰撞：先 x 后 y，撞到则卡在接触边界（可沿障碍滑动，物理碰撞不重叠）
  let cx = c.x, cy = c.y
  if (!collides(c, nx, cy)) cx = nx
  if (!collides(c, cx, ny)) cy = ny
  if (cx !== c.x || cy !== c.y) { c.x = cx; c.y = cy }
  // 虚影跟随卡片，自动吸附单元格（格不可见，仅虚影体现吸附落点；违规则标红）
  ghostX.value = snap(c.x, CELL_W)
  ghostY.value = snap(c.y, CELL_H)
  ghostInvalid.value = !placeOk(c, ghostX.value, ghostY.value)
}
function onWinMove(e) {
  const d = drag.value
  if (!d) return
  d.lastX = e.clientX; d.lastY = e.clientY
  // 实际拖过一小段才视为拖动（否则按下不动不触发边缘滚动）
  if (!d.moved && Math.abs(e.clientX - d.startX) + Math.abs(e.clientY - d.startY) > 3) d.moved = true
  if (d.mode === 'pan') {
    tx.value = clampTx(d.sx + (e.clientX - d.startX))
    ty.value = clampTy(d.sy + (e.clientY - d.startY))
    return
  }
  updateCardDrag(d, e.clientX, e.clientY)
}
function onWinUp() {
  const d = drag.value
  if (d && d.mode === 'card') {
    const gx = Math.max(0, Math.min(BOARD_W - cw(d.card), ghostX.value))
    const gy = Math.max(0, Math.min(BOARD_H - ROW_H, ghostY.value))
    if (!ghostInvalid.value && placeOk(d.card, gx, gy)) {
      if (videoRowViolation(d.card, gy)) {
        // 视频卡落中间行：提示（震动）+ 回退原位（保存前即阻止，配合后端双保险）
        flashFail([d.card.id])
      } else {
        // 合法落点：吸附到虚影所在单元格
        d.card.x = gx; d.card.y = gy
        syncWidths()
        emit('change', JSON.parse(JSON.stringify(list.value)))
      }
    } else if (d.card.x !== d.ox0 || d.card.y !== d.oy0) {
      // 违规落点：回退到拖动前位置（保证结果始终符合行约束）
      d.card.x = d.ox0; d.card.y = d.oy0
      syncWidths()
      emit('change', JSON.parse(JSON.stringify(list.value)))
    }
  }
  drag.value = null
  ghostX.value = 0
  ghostY.value = 0
  ghostInvalid.value = false
  stopEdgeScroll()
  stopDragListeners()
}
function startDragListeners() {
  window.addEventListener('pointermove', onWinMove)
  window.addEventListener('pointerup', onWinUp)
  window.addEventListener('pointercancel', onWinUp)
}
function stopDragListeners() {
  window.removeEventListener('pointermove', onWinMove)
  window.removeEventListener('pointerup', onWinUp)
  window.removeEventListener('pointercancel', onWinUp)
}

// ---- 边缘滚动（Edge Scroll / Auto-Scroll） ----
// 拖动中指针靠近画布视口边缘时，每帧按接近程度加速平移视口（越贴边越快），
// 无需松手或手动滚动即可把对象拖到当前视野之外。深度越大速度越快。
// 边缘滚动严格以画布窗口边缘为界：区域收窄到 24px（< 左上角卡片距窗口边的 24/68px），
// 避免「角落卡片一拖动就误触发滚动」；越贴边速度越快。
// 方向语义：向哪个边缘拖，视图就朝那个方向滚（露出更远处内容，让卡片能继续拖出视野）。
// 因 translate(tx,ty) 且 tx/ty<=0，左/上边缘取正 dx/dy（tx/ty 增大→内容右/下移→露出左/上）。
const EDGE_ZONE = 24    // 触发边缘滚动的窗口边距(px)
const EDGE_MAX = 20     // 最贴边时每帧最大平移(px)
let edgeRaf = null
function startEdgeScroll() {
  if (edgeRaf) return
  edgeRaf = requestAnimationFrame(edgeTick)
}
function stopEdgeScroll() {
  if (edgeRaf) { cancelAnimationFrame(edgeRaf); edgeRaf = null }
}
function edgeTick() {
  const d = drag.value
  if (!d || d.mode !== 'card') { stopEdgeScroll(); return }   // 边缘滚动仅卡片拖动
  if (!d.moved) { edgeRaf = requestAnimationFrame(edgeTick); return }   // 未真正拖动不滚动
  const rect = canvasRef.value.getBoundingClientRect()
  const px = d.lastX, py = d.lastY
  if (px != null && py != null) {
    let dx = 0, dy = 0
    if (px < rect.left + EDGE_ZONE) dx = ((EDGE_ZONE - (px - rect.left)) / EDGE_ZONE) * EDGE_MAX
    else if (px > rect.right - EDGE_ZONE) dx = -((EDGE_ZONE - (rect.right - px)) / EDGE_ZONE) * EDGE_MAX
    if (py < rect.top + EDGE_ZONE) dy = ((EDGE_ZONE - (py - rect.top)) / EDGE_ZONE) * EDGE_MAX
    else if (py > rect.bottom - EDGE_ZONE) dy = -((EDGE_ZONE - (rect.bottom - py)) / EDGE_ZONE) * EDGE_MAX
    if (dx || dy) {
      tx.value = clampTx(tx.value + dx)
      ty.value = clampTy(ty.value + dy)
      // 卡片跟随指针重算（利用新 tx/ty 反推），实现边滚不松手拖出视野
      updateCardDrag(d, px, py)
    }
  }
  edgeRaf = requestAnimationFrame(edgeTick)
}

// 卡片宽度（函数 ref：挂载后换算成整数格数）。
// 用 max(offsetWidth, scrollWidth) 读真实内容宽（scrollWidth 含未截断内容，抗钳制），
// 并以确定性下限 estN(type,label)（由文字长度推算，恒≥2格）兜底，绝不让宽卡回落到 1 格。
function setCardEl(el) {
  if (!el || !el.dataset || !el.dataset.id) return
  const c = list.value.find((x) => x.id === el.dataset.id)
  const nat = Math.max(el.offsetWidth, el.scrollWidth)
  const floor = estN(c ? c.type : '', c ? c.label : '')
  const n = Math.max(floor, Math.max(1, Math.ceil(nat / CELL_W)))
  // 持久化宽度优先：syncCards 已回填 cellN[id]（width_cells），DOM 测量不超则保持；DOM 超出才更新
  const saved = cellN[el.dataset.id]
  if (saved && saved >= n) return
  if (cellN[el.dataset.id] !== n) cellN[el.dataset.id] = n
}

// ---- 点击积木区添加：自动寻下一个合法空格（按行约束 + 碰撞） ----
// 预留格数估计：文字宽度 + 类型徽标 + 新标签 + 内边距（保守偏大，防放后重叠）
function estN(type, label) {
  const w = String(label || '').length * 14 + 150
  return Math.max(1, Math.ceil(w / CELL_W))
}
function nextFreeCell(type, label) {
  const est = estN(type, label)
  const cand = { id: '_', type, label, x: 0, y: 0 }
  cellN['_'] = est   // 临时让 cw(cand)=est*CELL_W 参与碰撞判定
  let found = null
  for (let row = 0; row < 200 && !found; row++) {
    const y = row * CELL_H
    for (let col = 0; col < 200; col++) {
      const x = col * CELL_W
      cand.x = x; cand.y = y
      if (placeOk(cand, x, y)) { found = { x, y, n: est }; break }
    }
  }
  delete cellN['_']
  return found   // 找不到合法格返回 null（调用方不再添加，避免静默重叠）
}
// 添加失败就地提示（画布内的原因卡片）：纯震动 + 左上角「！」，1.5s 自动消失（无边缘发光）。
// 原因卡片 = 阻塞添加的卡：非按钮且存在按钮 → 按钮卡（固定底部挤占）；否则画布已满 → 全部卡。
const failCards = ref([])
let failTimer = null
function flashFail(ids) {
  failCards.value = ids
  if (failTimer) clearTimeout(failTimer)
  failTimer = setTimeout(() => { failCards.value = [] }, 1500)
}
// ---- hover 详情浮层：卡片只留 label+type，行约束/占用/视频规则信息移入浮层 ----
const hoverId = ref(null)
const hoverPos = ref({ left: 0, top: 0 })
let hoverTimer = null
const hovered = computed(() => list.value.find((c) => c.id === hoverId.value) || null)
const isVideoKind = (k) => k === 'video' || k === 'video_url'
function hoverRows(c) {
  const k = kindOf(c)
  const same = list.value.filter((x) => x.y === c.y && kindOf(x) === k)
  return `${same.length} / ${cardMeta(c).maxSameTypePerRow}`
}
function onHover(c, e) {
  clearTimeout(hoverTimer)
  hoverId.value = c.id
  const r = e.currentTarget.getBoundingClientRect()
  // 浮层卡上方（translateY(-100%)），左缘对齐卡左缘；画布边缘防溢出
  hoverPos.value = { left: Math.max(8, Math.min(r.left, window.innerWidth - 248)), top: r.top - 8 }
}
function clearHoverTimer() { clearTimeout(hoverTimer) }
function offHover() {
  clearTimeout(hoverTimer)
  // 延迟关闭：鼠标卡→浮层过渡不闪烁（浮层 mouseenter 取消）
  hoverTimer = setTimeout(() => { hoverId.value = null }, 150)
}
// 点击选中卡：D 区同步行约束区（选中即看，不依赖 hover）
function onCardClick(c) {
  const k = kindOf(c)
  const same = list.value.filter((x) => x.y === c.y && kindOf(x) === k)
  const meta = cardMeta(c)
  const isVideo = isVideoKind(k)
  let videoWarn = false
  if (isVideo) {
    const ys = list.value.filter((x) => x.id !== c.id).map((x) => x.y)
    if (ys.length) {
      const mi = Math.min(...ys), ma = Math.max(...ys)
      videoWarn = c.y > mi && c.y < ma
    }
  }
  emit('select-card', {
    id: c.id,
    info: {
      label: KIND_INFO[k].label, share: meta.canShareRow ? '可同行' : '独占',
      self: meta.canSelfRow ? '可自排' : '独排', max: meta.maxSameTypePerRow,
      rowCount: same.length, isVideo, videoWarn,
    },
  })
}

// 阻塞添加的原因卡 id：非按钮且存在按钮 → 按钮卡（固定底部挤占）；否则画布已满 → 全部卡
function findBlockers(type) {
  return type !== 'button' && list.value.some((c) => c.type === 'button')
    ? list.value.filter((c) => c.type === 'button').map((c) => c.id)
    : list.value.map((c) => c.id)
}
function pushCard(type, kind, label, n, x, y, extra = {}) {
  const cid = 'c_' + Date.now() + Math.random().toString(36).slice(2, 6)
  cellN[cid] = n
  list.value.push({ id: cid, type, kind, label, x, y, ...extra })
  syncWidths()
  emit('change', JSON.parse(JSON.stringify(list.value)))
}
// 任一变更后：把当前格宽写回卡，随 change 持久化（宽度落块，刷新后保持原宽）
function syncWidths() {
  for (const c of list.value) c.width_cells = cellN[c.id] || 1
}
function addBlock({ type, kind, label, url }) {
  const p = nextFreeCell(type, label)
  if (!p) { flashFail(findBlockers(type)); return }
  pushCard(type, kind, label, p.n, p.x, p.y, url ? { url } : {})
}

// ---- 卡片右键悬停菜单（类型/属性/复制/删除） ----
const menu = ref(null)   // {x,y,cardId} 视口坐标；null=关闭
const editing = ref(false)  // 属性内联编辑态
const editForm = ref({})    // 属性表单值：{propKey: value}
const typeOpen = ref(false) // 按钮卡「类型」子菜单展开
const menuEl = ref(null)
const menuCard = () => list.value.find((x) => x.id === menu.value?.cardId) || null
const curProps = () => { const c = menuCard(); return c ? KIND_INFO[kindOf(c)].props : [] }
// canvas 级右键：整板禁用浏览器原生菜单，命中卡片则打开悬停菜单，否则关闭
function onCanvasMenu(e) {
  const el = e.target.closest('.card')
  const c = el && el.dataset.id ? list.value.find((x) => x.id === el.dataset.id) : null
  if (c) onCardMenu(c, e)
  else closeMenu()
}
function onCardMenu(c, e) {
  editing.value = false
  typeOpen.value = false
  // 夹在视口内（菜单约 180×200）
  const mx = Math.max(4, Math.min(e.clientX, window.innerWidth - 190))
  const my = Math.max(4, Math.min(e.clientY, window.innerHeight - 200))
  menu.value = { x: mx, y: my, cardId: c.id }
}
function closeMenu() { menu.value = null; editing.value = false; typeOpen.value = false }
function openEdit() {
  const c = menuCard()
  if (!c) return closeMenu()
  const f = {}
  for (const p of KIND_INFO[kindOf(c)].props) f[p.key] = c[p.key] ?? ''
  editForm.value = f
  editing.value = true
}
function confirmEdit() {
  const c = menuCard()
  if (!c) return closeMenu()
  for (const p of KIND_INFO[kindOf(c)].props) {
    const v = editForm.value[p.key]
    if (p.type === 'number') c[p.key] = Number(v) || 0
    else c[p.key] = String(v ?? '').trim()
  }
  syncWidths()
  emit('change', JSON.parse(JSON.stringify(list.value)))
  closeMenu()
}
// 右键「类型」子菜单：同一家族内 kind 互切（button|link、image|image_url、video|video_url）。
// 同家族内 type 不变 → 约束不变；label 为内容（如按钮文字），切换类型时保留。
function setKind(k) {
  const c = menuCard()
  if (!c) return closeMenu()
  c.kind = k
  syncWidths()
  emit('change', JSON.parse(JSON.stringify(list.value)))
  closeMenu()
}
function dupCard() {
  const c = menuCard()
  if (!c) return closeMenu()
  const p = nextFreeCell(c.type, c.label)
  if (!p) { flashFail(findBlockers(c.type)); closeMenu(); return }
  // 复制保留内容（url/value）：自定义地址/间距卡复制后不丢内容
  pushCard(c.type, c.kind, c.label, p.n, p.x, p.y, { url: c.url || '', value: c.value || 0 })
  closeMenu()
}
function delCard() {
  const c = list.value.find((x) => x.id === menu.value?.cardId)
  if (!c) return closeMenu()
  list.value = list.value.filter((x) => x.id !== c.id)
  delete cellN[c.id]
  syncWidths()
  emit('change', JSON.parse(JSON.stringify(list.value)))
  closeMenu()
}
function onWindowPointerDown(e) {
  // 点击菜单外（含左键画布/其他）关闭菜单；右键再次打开由 onCardMenu 处理
  if (menuEl.value && menuEl.value.contains(e.target)) return
  closeMenu()
}
function onWindowKeyDown(e) { if (e.key === 'Escape') closeMenu() }
onMounted(() => {
  window.addEventListener('pointerdown', onWindowPointerDown, true)
  window.addEventListener('keydown', onWindowKeyDown)
})
onBeforeUnmount(() => {
  window.removeEventListener('pointerdown', onWindowPointerDown, true)
  window.removeEventListener('keydown', onWindowKeyDown)
})

// 按住保存导出（内部调试，无用户提示，仅 console）：把当前布局渲染为 QQ 消息文本。
// 空格/空行映射：
//   两卡之间空单元格 = 一个空格；最末尾卡之后的空单元格 ≠ 空格；
//   上下卡之间无卡的行 = QQ 群里一条空白行（行首/行尾空行不输出）。
function exportContent(c) {
  const k = kindOf(c)
  if (k === 'text' || k === 'title' || k === 'desc') return c.label || ''
  if (k === 'image' || k === 'image_url' || k === 'video' || k === 'video_url' || k === 'gif')
    return '[' + KIND_INFO[k].label + ':' + (c.url || c.label || '') + ']'
  if (k === 'button' || k === 'link') return '[' + (k === 'link' ? '链接按钮' : '按钮') + ':' + (c.label || '') + ']'
  if (k === 'divider') return '[分割线]'
  if (k === 'gap') return '[间距:' + (c.value || '') + ']'
  return '[' + k + ':' + (c.label || '') + ']'
}
function computeExport() {
  // 按行分组（round(y/CELL_H)），只输出 minRow..maxRow 区间内的行。
  const rows = new Map()
  for (const c of list.value) {
    const r = Math.round(c.y / CELL_H)
    if (!rows.has(r)) rows.set(r, [])
    rows.get(r).push(c)
  }
  const rk = [...rows.keys()].sort((a, b) => a - b)
  const minR = rk.length ? rk[0] : 0
  const maxR = rk.length ? rk[rk.length - 1] : -1
  const outRows = []
  for (let r = minR; r <= maxR; r++) {
    const rowCards = (rows.get(r) || []).sort((a, b) => a.x - b.x)
    if (!rowCards.length) { outRows.push({ row_index: r, text: '', cards: [] }); continue }
    let text = ''
    let prevEnd = null
    const cardsOut = []
    for (const c of rowCards) {
      const start = Math.round(c.x / CELL_W)
      const w = cellN[c.id] || 1
      if (prevEnd !== null && start > prevEnd) text += ' '.repeat(start - prevEnd)   // 两卡间空格
      text += exportContent(c)
      cardsOut.push({ type: c.type, kind: kindOf(c), label: c.label || '', url: c.url || '', value: c.value || 0, x_cell: start, width_cells: w })
      prevEnd = start + w
    }
    outRows.push({ row_index: r, text, cards: cardsOut })
  }
  // 把行结构交给父层（父层组装完整 JSON 并下载；B 区不持有模板名/类型等元数据）
  emit('export', { cell_w: CELL_W, cell_h: CELL_H, row_count: outRows.length, rows: outRows })
}

// 同步：切换模板 → 从 props.cards 重建；添加请求 → 插入卡片；导出信号 → 导出
watch(() => props.templateId, () => { syncCards() }, { immediate: true })
watch(() => props.addRequest, (r) => { if (r && r.type) addBlock(r) })
watch(() => props.exportSignal, () => { computeExport() })

function onResize() { measure() }
onMounted(() => {
  measure()
  window.addEventListener('resize', onResize)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  if (failTimer) clearTimeout(failTimer)
  stopEdgeScroll()
  stopDragListeners()
})
</script>

<template>
  <div class="board">
    <div ref="canvasRef" class="canvas" @wheel.prevent="onWheel"
      @pointerdown="onPointerDown" @contextmenu.prevent="onCanvasMenu">
      <!-- 内容层：偏移 RULER（内容在标尺下平移），transform 平移缩放；无可见单元格 -->
      <div class="content" :style="{
        left: RULER + 'px', top: RULER + 'px',
        width: BOARD_W + 'px', height: BOARD_H + 'px',
        transform: `translate(${tx}px, ${ty}px) scale(${s})`,
      }">
        <!-- 虚影：自动吸附单元格，跟随卡片（低透明度，不抢眼），拖动时显示 -->
        <div v-if="drag && drag.mode === 'card'" class="ghost" :class="{ invalid: ghostInvalid }"
          :style="{ left: ghostX + 'px', top: ghostY + 'px', width: cw(drag.card) + 'px', height: ROW_H + 'px' }"></div>
        <div v-for="c in list" :key="c.id" class="card" :class="['t-' + c.type, { fail: failCards.includes(c.id), selected: c.id === selId }]"
          :style="{ left: c.x + 'px', top: c.y + 'px', height: ROW_H + 'px', ...(cellN[c.id] ? { width: (cellN[c.id] * CELL_W) + 'px' } : {}) }"
          :data-id="c.id" :ref="setCardEl" @pointerdown.stop="onCardDown(c, $event)"
          @mouseenter="onHover(c, $event)" @mouseleave="offHover" @click.stop="onCardClick(c)">
          <span v-if="failCards.includes(c.id)" class="fail-badge">!</span>
          <span class="card-label">{{ cardDisplay(c) }}</span>
          <span class="card-type">{{ KIND_INFO[kindOf(c)].label }}</span>
        </div>
      </div>

      <!-- hover 详情浮层：Teleport 到 body，fixed 视口定位，卡片上方弹出（行约束/占用/视频规则） -->
      <Teleport to="body">
        <div v-if="hovered" class="card-hover" :style="{ left: hoverPos.left + 'px', top: hoverPos.top + 'px' }"
          @pointerdown.stop @contextmenu.prevent @mouseenter="clearHoverTimer" @mouseleave="offHover">
          <div class="h-title">{{ KIND_INFO[kindOf(hovered)].label }}</div>
          <div class="h-row"><span class="h-k">行约束</span><span class="h-v">{{ cardMeta(hovered).canShareRow ? '可同行' : '独占' }} · {{ cardMeta(hovered).canSelfRow ? '可自排' : '独排' }} · 每行≤{{ cardMeta(hovered).maxSameTypePerRow }}</span></div>
          <div class="h-row"><span class="h-k">本行占用</span><span class="h-v">{{ hoverRows(hovered) }}</span></div>
          <div v-if="isVideoKind(kindOf(hovered))" class="h-row">
            <span class="h-k">视频规则</span>
            <span class="h-v" :class="{ warn: videoRowViolation(hovered, hovered.y) }">视频只能在首/末行{{ videoRowViolation(hovered, hovered.y) ? '（当前中间行）' : '' }}</span>
          </div>
        </div>
      </Teleport>

      <!-- 卡片右键悬停菜单：Teleport 到 body，fixed 视口定位，不被画布 transform/overflow 干扰或裁剪 -->
      <Teleport to="body">
        <div v-if="menu" ref="menuEl" class="card-menu" :style="{ left: menu.x + 'px', top: menu.y + 'px' }"
          @pointerdown.stop @contextmenu.prevent>
          <template v-if="!editing">
            <!-- 类型子菜单（同一家族内互切：按钮/链接按钮、转发/自定义地址图片、转发/自定义地址视频） -->
            <template v-if="menuCard() && familyOf(kindOf(menuCard()))">
              <button class="menu-item" @click="typeOpen = !typeOpen">
                类型: {{ KIND_INFO[kindOf(menuCard())].label }} <span class="menu-arrow">▸</span>
              </button>
              <div v-if="typeOpen" class="menu-sub">
                <button v-for="k in familyOf(kindOf(menuCard())).kinds" :key="k" class="menu-item"
                  @click="setKind(k)">{{ familyOf(kindOf(menuCard())).labels[k] }}</button>
              </div>
            </template>
            <button class="menu-item" @click="openEdit">属性</button>
            <button class="menu-item" @click="dupCard">复制</button>
            <button class="menu-item danger" @click="delCard">删除</button>
          </template>
          <template v-else>
            <div class="menu-form">
              <template v-for="p in curProps()" :key="p.key">
                <label>{{ p.label }}</label>
                <input v-model="editForm[p.key]" class="menu-input"
                  :type="p.type === 'number' ? 'number' : 'text'" min="0" :placeholder="p.ph || ''" />
              </template>
              <div v-if="!curProps().length" class="menu-empty">无内容属性</div>
              <div class="menu-actions">
                <button class="menu-item" @click="confirmEdit">确认</button>
                <button class="menu-item" @click="closeMenu">取消</button>
              </div>
            </div>
          </template>
        </div>
      </Teleport>

      <!-- 行号列标（画布内，冻结，覆盖内容上方，内容在其下平移） -->
      <div class="ruler-top"><span v-for="cc in topCols" :key="cc.i" class="ruler-cell" :style="{ left: cc.sx + 'px', width: cc.sw + 'px' }">{{ cc.label }}</span></div>
      <div class="ruler-left"><span v-for="rr in leftRows" :key="rr.j" class="ruler-cell" :style="{ top: rr.sy + 'px', height: rr.sh + 'px' }">{{ rr.label }}</span></div>
      <div class="ruler-corner"></div>

      <button class="btn-preview" title="预览当前卡片布局" @click="emit('preview', list.value)">预览</button>
    </div>
  </div>
</template>

<style scoped>
.board {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 0;
  min-width: 0;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
}
.canvas {
  position: absolute;
  inset: 0;
  overflow: hidden;
  cursor: grab;
  touch-action: none;
}
.canvas:active { cursor: grabbing; }
.content {
  position: absolute;
  transform-origin: 0 0;
  will-change: transform;
}

/* 虚影：自动吸附单元格，跟随卡片；低透明度不抢眼；违规落点标红 */
.ghost {
  position: absolute;
  background: var(--accent);
  opacity: 0.25;
  border: 1px dashed var(--accent);
  border-radius: 8px;
  box-sizing: border-box;
  pointer-events: none;
  z-index: 0;
}
.ghost.invalid {
  background: #dc2626;
  border-color: #dc2626;
  opacity: 0.3;
}

/* 卡片：固定高（ROW_H），标准宽度=整数格（无 1.5 格），文字居中；可拖，物理碰撞 */
.card {
  position: absolute;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 0 10px;
  box-sizing: border-box;
  background: var(--card);
  border: 1px solid var(--border);
  border-left: 3px solid var(--accent);
  border-radius: 8px;
  cursor: grab;
  user-select: none;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
  /* 挂载测量态：自然宽度（至少 1 格），测量后由内联宽度覆盖为 N*CELL_W */
  width: max-content;
  min-width: 100px;
}
.card:active { cursor: grabbing; }
.card.t-image { border-left-color: #a78bfa; }
.card.t-button { border-left-color: #f59e0b; }
.card.t-divider { border-left-color: #94a3b8; }
.card-label { font-size: 12px; color: var(--text); white-space: nowrap; }
.card-type { font-size: 10px; color: var(--muted); }
/* 选中卡：accent 描边 + 外发光（点击选中，D 区同步） */
.card.selected { border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent), 0 2px 6px rgba(0, 0, 0, 0.1); }
/* 添加失败原因卡：纯震动 + 左上角「！」（无边缘发光） */
.card.fail { animation: card-shake 0.5s ease; }
.fail-badge {
  position: absolute;
  top: -7px;
  left: -7px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #dc2626;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  line-height: 16px;
  text-align: center;
  z-index: 3;
  pointer-events: none;
}
@keyframes card-shake {
  0%, 100% { transform: translateX(0); }
  20% { transform: translateX(-3px); }
  40% { transform: translateX(3px); }
  60% { transform: translateX(-3px); }
  80% { transform: translateX(3px); }
}

/* hover 详情浮层（卡片上方，视口坐标） */
.card-hover {
  position: fixed;
  z-index: 999;
  min-width: 210px;
  max-width: 280px;
  padding: 8px 10px;
  box-sizing: border-box;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.16);
  user-select: none;
  pointer-events: auto;
  transform: translateY(-100%);
}
.h-title { font-size: 12px; font-weight: 600; color: var(--text); margin-bottom: 5px; }
.h-row { display: flex; justify-content: space-between; gap: 10px; font-size: 11px; padding: 1px 0; }
.h-k { color: var(--muted); flex: none; }
.h-v { color: var(--text); text-align: right; }
.h-v.warn { color: #dc2626; font-weight: 600; }

/* 行号列标：画布内冻结，强对比保证可见 */
.ruler-top, .ruler-left, .ruler-corner {
  position: absolute;
  z-index: 3;
  background: var(--bg);
  box-sizing: border-box;
}
.ruler-top {
  top: 0; left: 24px; right: 0; height: 24px;
  border-bottom: 1px solid var(--border);
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}
.ruler-left {
  top: 24px; left: 0; bottom: 0; width: 24px;
  border-right: 1px solid var(--border);
  overflow: hidden;
  box-shadow: 1px 0 3px rgba(0, 0, 0, 0.08);
}
.ruler-corner {
  top: 0; left: 0; width: 24px; height: 24px;
  background: var(--bg);
  border-right: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
}
.ruler-cell {
  position: absolute;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 500;
  color: var(--muted);
  box-sizing: border-box;
  border-right: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
}
.ruler-top .ruler-cell { top: 0; height: 24px; }
.ruler-left .ruler-cell { left: 0; width: 24px; }

/* 预览按钮（右下角） */
.btn-preview {
  position: absolute;
  right: 12px;
  bottom: 12px;
  z-index: 4;
  border: none;
  border-radius: 8px;
  padding: 8px 16px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  background: var(--accent);
  color: var(--card);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.18);
  transition: 0.15s;
}
.btn-preview:hover { filter: brightness(0.92); }

/* 卡片右键悬停菜单（浮于画布，视口坐标） */
.card-menu {
  position: fixed;
  z-index: 1000;
  min-width: 150px;
  padding: 4px;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.16);
  user-select: none;
}
.menu-item {
  display: block;
  width: 100%;
  padding: 7px 12px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--text);
  font-size: 13px;
  text-align: left;
  cursor: pointer;
}
.menu-item:hover { background: var(--bg); }
.menu-item.danger { color: #dc2626; }
.menu-item.danger:hover { background: #fde8e8; }
.menu-form { display: flex; flex-direction: column; gap: 5px; padding: 6px 4px; }
.menu-form label { font-size: 11px; color: var(--muted); }
.menu-input {
  width: 100%;
  box-sizing: border-box;
  padding: 5px 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 13px;
}
.menu-actions { display: flex; gap: 6px; margin-top: 4px; }
.menu-actions .menu-item { flex: 1; text-align: center; }
.menu-arrow { float: right; color: var(--muted); font-size: 11px; }
.menu-sub { padding-left: 14px; border-left: 2px solid #e2e8f0; margin: 2px 0 2px 10px; }
.menu-sub .menu-item { font-size: 12px; padding: 6px 10px; }
.menu-empty { font-size: 12px; color: var(--muted); padding: 8px 2px; text-align: center; }
</style>
