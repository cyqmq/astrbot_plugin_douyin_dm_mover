<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { store, sendersTop, ROUTE_TYPES, SELECTS, umoSplit } from '../../composables/store.js'
import { saveConfig } from '../../composables/actions.js'

const box = ref(null)
const COL_TITLES = ['抖音来源', '路由', '目标群']

const sources = computed(() => sendersTop.value.length ? sendersTop.value : [{ peer_name: '抖音来源', peer_id: '' }])
const targets = computed(() => {
  const t = []
  store.routes.forEach(r => { if (r.target && !t.includes(r.target)) t.push(r.target) })
  return t
})

function addRoute() {
  store.routes.push({ name: 'route' + (store.routes.length + 1), target: 'aiocqhttp:GroupMessage:',
    match: { types: ['text', 'video_card'], senders_include: [], senders_exclude: [] } })
  nextTick(drawEdges)
}
async function saveRoutes() { await saveConfig({ routes: JSON.parse(JSON.stringify(store.routes)) }) }

function moveRoute(i, d) {
  const j = i + d
  if (j < 0 || j >= store.routes.length) return
  const t = store.routes[i]; store.routes[i] = store.routes[j]; store.routes[j] = t
  nextTick(drawEdges)
}
function delRoute(i) { store.routes.splice(i, 1); nextTick(drawEdges) }

function toggleType(r, v) {
  if (!r.match) r.match = { types: [], senders_include: [], senders_exclude: [] }
  const types = r.match.types
  const i = types.indexOf(v)
  if (i >= 0) types.splice(i, 1); else types.push(v)
  nextTick(drawEdges)
}

function umoOf(el) {
  const ad = el.querySelector('[data-e="adapter"]')
  const gr = el.querySelector('[data-e="group"]')
  const g = (gr && gr.value.trim()) || ''
  return g ? ((ad ? ad.value : 'aiocqhttp') + ':GroupMessage:' + g) : ''
}
function commitRoute(i, el) {
  const r = store.routes[i]; if (!r || !el) return
  const name = el.querySelector('[data-e="name"]')
  r.name = (name && name.value.trim()) || ('route' + (i + 1))
  r.target = umoOf(el)
  const types = Array.from(el.querySelectorAll('[data-rt].on')).map(t => t.dataset.rt)
  const inc = el.querySelector('[data-e="inc"]'), exc = el.querySelector('[data-e="exc"]')
  r.match = { types, senders_include: splitLst(inc && inc.value), senders_exclude: splitLst(exc && exc.value) }
}
const splitLst = v => String(v || '').split(',').map(s => s.trim()).filter(Boolean)

// 目标卡片编辑：改适配器/群号 → 更新所有指向该目标的路由
function applyTarget(t, newAdapter, newGroup) {
  const newT = newGroup.trim() ? (newAdapter + ':GroupMessage:' + newGroup.trim()) : ''
  store.routes.forEach(r => { if (r.target === t) r.target = newT })
  nextTick(drawEdges)
}

// ---- SVG 连线 ----
function topoPos(el) {
  const br = el.getBoundingClientRect(), bb = box.value.getBoundingClientRect()
  return { x: br.left - bb.left, y: br.top - bb.top, w: br.width, h: br.height }
}
function drawEdges() {
  if (!box.value) return
  const svg = box.value.querySelector('.topo-svg')
  if (!svg) return
  const css = getComputedStyle(document.documentElement)
  const accent = css.getPropertyValue('--accent').trim() || '#0969da'
  const muted = css.getPropertyValue('--muted').trim() || '#666'
  const sEls = box.value.querySelectorAll('#td-src .src-card')
  const rEls = box.value.querySelectorAll('#td-route .src-card:not(.empty)')
  const tEls = box.value.querySelectorAll('#td-tgt .target-card')
  let p = ''
  const bez = (x1, y1, x2, y2, cls) => {
    const mx = (x1 + x2) / 2
    p += `<path class="tline ${cls}" d="M${x1} ${y1} C${mx} ${y1} ${mx} ${y2} ${x2} ${y2}"/>`
  }
  sources.value.forEach((src, si) => {
    const se = sEls[si]; if (!se) return
    const sp = topoPos(se)
    const sy = sp.y + sp.h / 2, x1 = sp.x + sp.w
    store.routes.forEach((r, ri) => {
      const re = rEls[ri]; if (!re) return
      const rp = topoPos(re)
      const inc = (r.match && r.match.senders_include) || []
      const exc = (r.match && r.match.senders_exclude) || []
      const sid = src.peer_id || ''
      const included = inc.includes(sid) || (!inc.length)
      const excluded = exc.includes(sid)
      const any = inc.length || exc.length
      let cls = 'hit'
      if (excluded || !included) cls = 'off'
      else if (!any) cls = 'dim'
      bez(x1, sy, rp.x, rp.y + rp.h / 2, cls)
    })
  })
  store.routes.forEach((r, ri) => {
    const re = rEls[ri]; if (!re) return
    const ti = targets.value.indexOf(r.target)
    if (ti < 0) return
    const te = tEls[ti]; if (!te) return
    const rp = topoPos(re), tp = topoPos(te)
    bez(rp.x + rp.w, rp.y + rp.h / 2, tp.x, tp.y + tp.h / 2, 'hit')
  })
  svg.setAttribute('width', box.value.scrollWidth)
  svg.setAttribute('height', box.value.scrollHeight)
  svg.innerHTML = p
}

// 路由/来源变化 → 重绘
watch(() => JSON.stringify({ r: store.routes, s: sendersTop.value.map(x => x.peer_id + '|' + x.peer_name) }), () => nextTick(drawEdges))
watch(targets, () => nextTick(drawEdges))
onMounted(() => nextTick(drawEdges))

// 行内输入：目标变化才整体重绘（连线），否则只重算连线
function onRouteInput(i, el) {
  const before = umoOf(el)
  commitRoute(i, el)
  if (umoOf(el) !== before) nextTick(drawEdges)
  else nextTick(drawEdges)
}
</script>

<template>
  <section>
    <div class="card">
      <h2>转发拓扑与路由编辑 <span class="muted">直接在卡片上编辑 · 目标群/结构变化自动重连</span></h2>
      <div class="bar" style="margin-bottom:10px">
        <button class="ghost" @click="addRoute">+ 添加路由</button>
        <button class="primary" @click="saveRoutes">保存路由</button>
        <span class="muted">{{ store.routes.length }} 条路由</span>
      </div>
      <div class="topo tall" ref="box">
        <svg class="topo-svg"></svg>
        <div class="td-cols">
          <div class="td-col"><div class="td-colhead">{{ COL_TITLES[0] }}</div>
            <div class="td-list" id="td-src">
              <div v-for="s in sources" :key="s.peer_id" class="src-card">
                <div class="sc-name">{{ (s.peer_name || ('用户 ' + s.peer_id)).slice(0, 16) }}</div>
                <div class="sc-sub">{{ s.peer_id ? ('uid ' + s.peer_id) : '抖音私信' }}</div>
              </div>
            </div>
          </div>
          <div class="td-col"><div class="td-colhead">{{ COL_TITLES[1] }}</div>
            <div class="td-list" id="td-route">
              <div v-if="!store.routes.length" class="src-card empty">
                <div class="sc-name" style="color:var(--muted)">暂无路由</div>
                <div class="sc-sub" style="color:var(--muted)">点「+ 添加路由」</div>
              </div>
              <div v-for="(r, i) in store.routes" :key="i" class="route-card" @input="onRouteInput(i, $event.currentTarget)">
                <div class="rc-head">
                  <input :value="r.name" placeholder="路由名称" data-e="name" @input="r.name = $event.target.value || ('route' + (i+1))">
                  <span class="rc-btns">
                    <button title="上移" @click="moveRoute(i, -1)">↑</button>
                    <button title="下移" @click="moveRoute(i, 1)">↓</button>
                    <button class="danger" title="删除" @click="delRoute(i)">×</button>
                  </span>
                </div>
                <div class="rc-row"><span>目标</span><div class="umo-row">
                  <select :value="umoSplit(r.target).adapter" data-e="adapter" @change="r.target = $event.target.value + ':GroupMessage:' + umoSplit(r.target).group">
                    <option v-for="[v, l] in SELECTS.qq_adapter_id" :key="v" :value="v">{{ l }}</option>
                  </select>
                  <input :value="umoSplit(r.target).group" placeholder="群号" data-e="group" @input="r.target = umoSplit(r.target).adapter + ':GroupMessage:' + $event.target.value.trim()">
                </div></div>
                <div class="rc-row"><span>类型</span><div class="type-chips">
                  <span v-for="[v, l] in ROUTE_TYPES" :key="v" class="tc" :class="{ on: (r.match && r.match.types || []).includes(v) }"
                        :data-rt="v" @click="toggleType(r, v)">{{ l }}</span>
                </div></div>
                <div class="rc-row"><span>发送者包含</span><input :value="(r.match && (r.match.senders_include || [])).join(',')" placeholder="逗号分隔 uid" data-e="inc" @input="commitRoute(i, $event.currentTarget.parentElement.closest('.route-card'))"></div>
                <div class="rc-row"><span>发送者排除</span><input :value="(r.match && (r.match.senders_exclude || [])).join(',')" placeholder="逗号分隔 uid" data-e="exc" @input="commitRoute(i, $event.currentTarget.parentElement.closest('.route-card'))"></div>
              </div>
            </div>
          </div>
          <div class="td-col"><div class="td-colhead">{{ COL_TITLES[2] }}</div>
            <div class="td-list" id="td-tgt">
              <div v-for="(t, i) in targets" :key="t + i" class="target-card">
                <div class="tc-head">目标群</div>
                <div class="rc-row"><span>适配器</span>
                  <select :value="umoSplit(t).adapter" @change="applyTarget(t, $event.target.value, umoSplit(t).group)"><option v-for="[v, l] in SELECTS.qq_adapter_id" :key="v" :value="v">{{ l }}</option></select>
                </div>
                <div class="rc-row"><span>群号</span><input :value="umoSplit(t).group" placeholder="群号" @input="applyTarget(t, umoSplit(t).adapter, $event.target.value)"></div>
                <div class="tc-sub">{{ store.routes.filter(r => r.target === t).length }} 条路由指向</div>
              </div>
              <div v-if="!targets.length" class="src-card empty"><div class="sc-name" style="color:var(--muted)">暂无目标</div></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>
