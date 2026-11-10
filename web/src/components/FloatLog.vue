<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { store, apiGet, apiPost, toast, fmtTs, esc } from '../composables/store.js'

const POS_KEY = 'dyf_float_log_pos'
const DEF_W = 320, DEF_H = 260
const panel = ref(null)
let timer = null

// 位置：localStorage 记住，默认右下角
const pos = ref(loadPos())
function loadPos() {
  try { const p = JSON.parse(localStorage.getItem(POS_KEY) || 'null'); if (p && typeof p.x === 'number') return p } catch {}
  return { x: Math.max(8, window.innerWidth - DEF_W - 16), y: Math.max(8, window.innerHeight - DEF_H - 56) }
}
function savePos() { try { localStorage.setItem(POS_KEY, JSON.stringify(pos.value)) } catch {} }

function toggle() {
  store.floatLog.open = !store.floatLog.open
  if (store.floatLog.open) startPoll()
  else stopPoll()
}
function close() {
  store.floatLog.open = false
  store.floatLog.enabled = false
  stopPoll()
}
function startPoll() {
  stopPoll()
  pull()
  timer = setInterval(pull, 3000)
}
function stopPoll() { if (timer) { clearInterval(timer); timer = null } }
async function pull() {
  store.floatLog.loading = true
  const d = await apiGet('logs')
  store.floatLog.loading = false
  store.floatLog.logs = d.logs || []
}
async function clearLogs() {
  const d = await apiPost('logs/clear')
  toast(d.detail || '已清空')
  store.floatLog.logs = []
}

// 头部拖动面板
let drag = null
function onDown(e) {
  if (e.target.closest('.fl-btn')) return
  drag = { x: e.clientX - pos.value.x, y: e.clientY - pos.value.y }
  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup', onUp)
}
function onMove(e) {
  if (!drag) return
  pos.value.x = Math.max(0, Math.min(e.clientX - drag.x, window.innerWidth - 120))
  pos.value.y = Math.max(0, Math.min(e.clientY - drag.y, window.innerHeight - 40))
}
function onUp() {
  drag = null
  window.removeEventListener('mousemove', onMove)
  window.removeEventListener('mouseup', onUp)
  savePos()
}

// 自动滚底
watch(() => store.floatLog.logs.length, () => {
  if (!store.floatLog.open) return
  nextTick(() => { const el = panel.value; if (el) el.scrollTop = el.scrollHeight })
})

const lvlCls = l => l.level === 'error' ? 'ferr' : (l.level === 'warning' ? 'fwarn' : 'finfo')
const line = l => `${fmtTs(l.ts)} [${l.level}] ${esc(l.msg)}`

onBeforeUnmount(stopPoll)
</script>

<template>
  <div class="float-log" :style="{ left: pos.x + 'px', top: pos.y + 'px' }">
    <template v-if="store.floatLog.open">
      <div class="fl-head" @mousedown="onDown">
        <span class="fl-title">调试日志</span>
        <span class="fl-btns">
          <button class="fl-btn" title="清屏" @click="clearLogs">清</button>
          <button class="fl-btn" title="折叠" @click="store.floatLog.open = false; stopPoll()">–</button>
          <button class="fl-btn" title="关闭" @click="close">×</button>
        </span>
      </div>
      <div class="fl-body" ref="panel">
        <div v-for="(l, i) in store.floatLog.logs" :key="i" class="fl-line" :class="lvlCls(l)" v-html="line(l)"></div>
        <div v-if="!store.floatLog.logs.length" class="fl-line finfo">暂无日志</div>
      </div>
    </template>
    <button v-else class="fl-ball" @click="toggle" title="展开调试日志">
      <span class="fl-dot"></span>日志
    </button>
  </div>
</template>
