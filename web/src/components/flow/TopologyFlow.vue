<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { VueFlow, useVueFlow, MarkerType } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import SourceNode from './SourceNode.vue'
import RouteNode from './RouteNode.vue'
import TargetNode from './TargetNode.vue'
import { store } from '../../composables/store.js'
import { scheduleLiveSave } from '../../composables/actions.js'
import { toast } from '../../composables/store.js'

const { getNodes, getEdges } = useVueFlow()
const X = [0, 440, 880]
const nodes = ref([])
const edges = ref([])

// 来源 = 自定义来源卡（卡内下拉选来源）；目标 = 高级卡片(custom_targets) 或 简单 qq群/私聊(simple_targets)
const sources = computed(() => store.customSources)
const targetList = computed(() => (store.advancedTargets ? store.customTargets : store.simpleTargets))

// 目标 UMO：高级卡(adapter+group) 无 kind；简单卡(adapter+kind+value) 有 kind
const umoOf = t => ('kind' in t)
  ? ((t.adapter || 'aiocqhttp') + ':' + (t.kind === 'private' ? 'PrivateMessage' : 'GroupMessage') + ':' + (t.value || ''))
  : (t.adapter + ':GroupMessage:' + (t.group || ''))
const findTargetByUmo = umo => targetList.value.find(t => umoOf(t) === umo)

// ---- 添加 / 删除 ----
function addSource() {
  // 动态分配不冲突 id：加载旧卡 id 可能保留 src1/src2…，新卡 id 永远唯一，
  // 避免新建来源顶掉旧卡（旧卡 id 与新卡冲突时 VueFlow 复用节点）。
  const ids = new Set(store.customSources.map(s => s.id))
  let n = 1
  while (ids.has('src' + n)) n++
  store.customSources.push({ id: 'src' + n, uid: '', nickname: '' })
  scheduleLiveSave()
}
function delSource(source) {
  const i = store.customSources.indexOf(source)
  if (i >= 0) { store.customSources.splice(i, 1); scheduleLiveSave() }
}
function addTarget() {
  const defAd = (store.platforms[0] && store.platforms[0].id) || 'aiocqhttp'
  if (store.advancedTargets) store.customTargets.push({ id: 'tgt' + (store.customTargets.length + 1), adapter: defAd, group: '' })
  else store.simpleTargets.push({ id: 's' + (store.simpleTargets.length + 1), adapter: defAd, kind: 'group', value: '' })
  scheduleLiveSave()
}
function delTarget(t) {
  const old = umoOf(t)
  const list = store.advancedTargets ? store.customTargets : store.simpleTargets
  const i = list.indexOf(t)
  if (i >= 0) list.splice(i, 1)
  store.routes.forEach(r => {
    const ts = r.targets || []
    const k = ts.indexOf(old)
    if (k >= 0) ts.splice(k, 1)
    if (r.target === old) r.target = ''
  })
  scheduleLiveSave()
}
function updateTarget(t, patch) {
  const old = umoOf(t)
  Object.assign(t, patch)
  const neu = umoOf(t)
  store.routes.forEach(r => {
    const ts = r.targets || []
    const k = ts.indexOf(old)
    if (k >= 0) ts[k] = neu
    if (r.target === old) r.target = neu
  })
  scheduleLiveSave()
}
let routeSeq = 0
function addRoute() {
  // 唯一名称：时间戳 + 序号，避免删中间路由后重名（_route_diff 按 name 匹配）
  store.routes.push({ name: 'route' + Date.now().toString(36) + '_' + (++routeSeq), target: '', targets: [], pos: null,
    match: { types: ['text', 'video_card'], senders_include: [] } })
  scheduleLiveSave()
}
function moveRoute(route, d) {
  const i = store.routes.indexOf(route)
  const j = i + d
  if (i < 0 || j < 0 || j >= store.routes.length) return
  const t = store.routes[i]; store.routes[i] = store.routes[j]; store.routes[j] = t
  scheduleLiveSave()
}
function delRoute(route) {
  const i = store.routes.indexOf(route)
  if (i >= 0) store.routes.splice(i, 1)
  scheduleLiveSave()
}

// ---- 手动连接：来源→路由（uid 进 senders_include）/ 路由→目标（target=UMO） ----
function onConnect(c) {
  const s = c.source || '', t = c.target || ''
  if (s.startsWith('src|') && t.startsWith('route|')) {
    const sid = s.split('|')[1]
    const rn = nodes.value.find(n => n.id === t)
    const r = rn && rn.data && rn.data.route
    const srcObj = sources.value.find(x => x.id === sid)
    const uid = srcObj ? (srcObj.uid || '') : ''
    if (r && !uid) { toast('请先在来源卡选择来源，再连接到路由'); return }
    if (r && uid) {
      if (!r.match) r.match = { types: [], senders_include: [] }
      if (!r.match.senders_include.includes(uid)) r.match.senders_include.push(uid)
      scheduleLiveSave()
      buildEdges()
    }
  } else if (s.startsWith('route|') && t.startsWith('tgt|')) {
    const tid = t.split('|')[1]
    const rn = nodes.value.find(n => n.id === s)
    const r = rn && rn.data && rn.data.route
    const tgt = targetList.value.find(x => x.id === tid)
    if (r && tgt) {
      const umo = umoOf(tgt)
      const sess = String(umo).split(':')[2] || ''
      if (!sess) { toast('目标未填写群号/OpenID，请先填写目标再连接'); return }
      if (!r.targets) r.targets = []
      if (!r.targets.includes(umo)) r.targets.push(umo)
      scheduleLiveSave(); buildEdges()
    }
  }
}
function onEdgesDelete(list) {
  (list || []).forEach(e => {
    const d = e.data || {}
    const r = d.route
    if (!r) return
    if (d.kind === 'src-route') {
      if (r.match) {
        const i = r.match.senders_include.indexOf(d.uid)
        if (i >= 0) r.match.senders_include.splice(i, 1)
      }
    } else if (d.kind === 'route-tgt') {
      const ts = r.targets || []
      const i = ts.indexOf(d.umo)
      if (i >= 0) ts.splice(i, 1)
      if (r.target === d.umo) r.target = ''  // 兼容旧单 target
    }
  })
  scheduleLiveSave()
  buildEdges()
}

// ---- 拖拽位置持久化 ----
function onDragStop({ node }) {
  if (!node) return
  const id = node.id || '', p = { x: Math.round(node.position.x), y: Math.round(node.position.y) }
  if (id.startsWith('src|')) {
    const src = sources.value.find(x => x.id === id.split('|')[1])
    if (src) src.pos = p
  } else if (id.startsWith('route|')) {
    const rn = getNodes.value.find(n => n.id === id)
    const r = rn && rn.data && rn.data.route
    if (r) r.pos = p
  } else if (id.startsWith('tgt|')) {
    const t = targetList.value.find(x => x.id === id.split('|')[1])
    if (t) t.pos = p
  }
  scheduleLiveSave()
}

// ---- 节点 / 边 ----
const posOf = id => { const n = getNodes.value.find(x => x.id === id); return n ? { x: n.position.x, y: n.position.y } : null }
function sourceNode(s, i) {
  const n = { id: 'src|' + s.id, type: 'source', data: { custom: true, source: s, del: delSource } }
  n.position = s.pos || posOf(n.id) || { x: X[0], y: i * 150 }
  return n
}
function routeNode(r, i) {
  const n = { id: 'route|' + i, type: 'route', data: { route: r, index: i, move: moveRoute, del: delRoute } }
  n.position = r.pos || posOf(n.id) || { x: X[1], y: i * 230 }
  return n
}
function targetNode(t, i) {
  const n = { id: 'tgt|' + t.id, type: 'target', data: { target: t, advanced: store.advancedTargets, update: updateTarget, del: delTarget } }
  n.position = t.pos || posOf(n.id) || { x: X[2], y: i * 180 }
  return n
}
function edgeTo(id, s, t, cls, data) {
  return { id, source: s, target: t, type: 'bezier', animated: cls === 'hit', data,
    markerEnd: { type: MarkerType.ArrowClosed, width: 14, height: 14 },
    style: { stroke: '#0969da', strokeWidth: 2.2 } }
}
function buildNodes() {
  const ns = []
  sources.value.forEach((s, i) => ns.push(sourceNode(s, i)))
  store.routes.forEach((r, i) => ns.push(routeNode(r, i)))
  targetList.value.forEach((t, i) => ns.push(targetNode(t, i)))
  nodes.value = ns
}
function buildEdges() {
  const es = []
  sources.value.forEach(s => {
    const uid = s.uid || ''
    if (!uid) return
    store.routes.forEach((r, ri) => {
      if ((r.match && r.match.senders_include || []).includes(uid))
        es.push(edgeTo(`e|src|${s.id}|${ri}`, 'src|' + s.id, 'route|' + ri, 'hit',
          { kind: 'src-route', uid, route: r }))
    })
  })
  store.routes.forEach((r, ri) => {
    const ts = r.targets && r.targets.length ? r.targets : (r.target ? [r.target] : [])
    ts.forEach((umo, k) => {
      const ti = targetList.value.findIndex(t => umoOf(t) === umo)
      if (ti >= 0) es.push(edgeTo(`e|route|${ri}|${k}|${ti}`, 'route|' + ri, 'tgt|' + targetList.value[ti].id, 'hit',
        { kind: 'route-tgt', umo, route: r }))
    })
  })
  edges.value = es
}
function build() { buildNodes(); buildEdges() }

// 结构变化 → 重建；内容变化（类型）→ 只重建边
watch(() => JSON.stringify({ r: store.routes.length, t: targetList.value, c: store.customSources,
  a: store.advancedTargets, g: store.routes.map(r => r.target).join('|') }), build)
// 内容变化（类型/来源连接）→ 只重建边（保焦点）
watch(() => JSON.stringify(store.routes.map(r => ((r.match && r.match.types) || []).join(',') + '|' +
  ((r.match && r.match.senders_include) || []).join(','))), buildEdges)

// 实时保存
let liveReady = false
watch(() => JSON.stringify({ r: store.routes, c: store.customSources, t: targetList.value, a: store.advancedTargets }),
  () => { if (liveReady) scheduleLiveSave() })
onMounted(() => { build(); setTimeout(() => { liveReady = true }, 600) })
</script>

<template>
  <div class="vf-wrap">
    <div class="bar" style="margin-bottom:10px">
      <button class="ghost" @click="addSource">+ 添加来源</button>
      <button class="ghost" @click="addRoute">+ 添加路由</button>
      <button class="ghost" @click="addTarget">+ 添加目标</button>
      <span class="muted">{{ store.routes.length }} 条路由 · {{ targetList.length }} 个目标 · 拖拽节点布局</span>
      <span v-if="store.liveSavedAt" class="muted save-state">已保存 {{ store.liveSavedAt }}</span>
    </div>
    <div class="bar" style="margin-bottom:10px">
      <span class="muted">从连接桩拖动到另一个连接桩建立连接：来源 <strong>→</strong> 路由 <strong>→</strong> 目标。选中连线按 <kbd>Delete</kbd> 断开。</span>
    </div>

    <div class="topo tall">
       <VueFlow :nodes="nodes" :edges="edges" :min-zoom="0.3" :max-zoom="1.8"
         :default-edge-options="{ type: 'bezier' }" :nodes-connectable="true" :edges-connectable="true"
         :nodes-draggable="true" :pan-on-drag="true" fit-view-on-init
         :delete-key-code="['Delete', 'Backspace']" :delete-key-code-prevent-default="true"
         @connect="onConnect" @edges-delete="onEdgesDelete" @node-drag-stop="onDragStop">
        <template #node-source="p"><SourceNode :data="p.data" /></template>
        <template #node-route="p"><RouteNode :data="p.data" /></template>
        <template #node-target="p"><TargetNode :data="p.data" /></template>
        <Background pattern-color="#e2e2e2" :gap="18" :size="1.2" />
      </VueFlow>
    </div>
  </div>
</template>
