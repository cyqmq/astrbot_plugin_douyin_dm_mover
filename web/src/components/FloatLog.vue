<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { store, apiGet, apiPost, toast, fmtTs, esc } from '../composables/store.js'

const POS_KEY = 'dyf_float_log_pos'
const DEF_W = 320, DEF_H = 260
const panel = ref(null)
let timer = null
let pullSeq = 0

// 位置：localStorage 记住，默认右下角
const pos = ref(loadPos())
function loadPos() {
  try { const p = JSON.parse(localStorage.getItem(POS_KEY) || 'null'); if (p && typeof p.x === 'number') return p } catch {}
  return { x: Math.max(8, window.innerWidth - DEF_W - 16), y: Math.max(8, window.innerHeight - DEF_H - 56) }
}
function savePos() { try { localStorage.setItem(POS_KEY, JSON.stringify(pos.value)) } catch {} }

function toggle() {
  if (suppressClick) { suppressClick = false; return }
  store.floatLog.open = !store.floatLog.open
  if (store.floatLog.open) startPoll()
  else stopPoll()
}
function startPoll() {
  stopPoll()
  pull()
  timer = setInterval(pull, 3000)
}
function stopPoll() { if (timer) { clearInterval(timer); timer = null } }
async function pull() {
  const my = ++pullSeq
  const d = await apiGet('logs')
  if (my !== pullSeq) return // 过期轮询结果丢弃，避免清空后旧数据回填
  store.floatLog.logs = d.logs || []
}
async function clearLogs() {
  pullSeq++                 // 使进行中的 pull 结果过期
  store.floatLog.logs = []  // 乐观清空，立即反馈
  const d = await apiPost('logs/clear')
  toast(d.detail || '已清空')
  await pull()              // 与后端同步（已空），保证最终一致
}

// 拖动：面板头部 + 胶囊（悬浮球）；拖动后抑制 click 防误展开
let drag = null
let suppressClick = false
function onDown(e) {
  if (e.target.closest('.fl-btn')) return
  drag = { sx: e.clientX, sy: e.clientY, x: e.clientX - pos.value.x, y: e.clientY - pos.value.y, moved: false }
  window.addEventListener('pointermove', onMove)
  window.addEventListener('pointerup', onUp)
}
function onMove(e) {
  if (!drag) return
  if (Math.abs(e.clientX - drag.sx) > 3 || Math.abs(e.clientY - drag.sy) > 3) drag.moved = true
  pos.value.x = Math.max(0, Math.min(e.clientX - drag.x, window.innerWidth - 120))
  pos.value.y = Math.max(0, Math.min(e.clientY - drag.y, window.innerHeight - 40))
}
function onUp() {
  suppressClick = !!(drag && drag.moved)
  drag = null
  window.removeEventListener('pointermove', onMove)
  window.removeEventListener('pointerup', onUp)
  savePos()
}

// 新日志在顶部：保持相对位置——在顶部则看最新，已滚动则补偿新增高度不跳动
watch(() => store.floatLog.logs.length, (n, o) => {
  if (!store.floatLog.open) return
  const before = panel.value ? panel.value.scrollHeight : 0
  nextTick(() => {
    const el = panel.value
    if (!el) return
    const diff = el.scrollHeight - before
    if (el.scrollTop <= 1 || diff <= 0) { el.scrollTop = 0; return }
    el.scrollTop += diff // 保持视觉相对位置
  })
})

const lvlCls = l => l.level === 'error' ? 'ferr' : (l.level === 'warning' ? 'fwarn' : 'finfo')
const line = l => `${fmtTs(l.ts)} [${l.level}] ${esc(l.msg)}`

onBeforeUnmount(stopPoll)
</script>

<template>
  <div class="float-log" :style="{ left: pos.x + 'px', top: pos.y + 'px' }">
    <template v-if="store.floatLog.open">
      <div class="fl-head" @pointerdown="onDown">
        <span class="fl-title">调试日志</span>
        <span class="fl-btns">
          <button class="fl-btn" title="清屏" @click="clearLogs">清</button>
          <button class="fl-btn" title="折叠" @click="store.floatLog.open = false; stopPoll()">–</button>
        </span>
      </div>
      <div class="fl-body" ref="panel">
        <div v-for="(l, i) in store.floatLog.logs" :key="i" class="fl-line" :class="lvlCls(l)" v-html="line(l)"></div>
        <div v-if="!store.floatLog.logs.length" class="fl-line finfo">暂无日志</div>
      </div>
    </template>
    <button v-else class="fl-ball" @pointerdown="onDown" @click="toggle" title="展开调试日志">
      <span class="fl-dot"></span>日志
    </button>
  </div>
</template>
