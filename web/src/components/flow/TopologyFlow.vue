<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { VueFlow, useVueFlow, MarkerType } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import SourceNode from './SourceNode.vue'
import RouteNode from './RouteNode.vue'
import TargetNode from './TargetNode.vue'
import { store, sendersTop } from '../../composables/store.js'
import { loadFriends, scheduleLiveSave } from '../../composables/actions.js'

const { getNodes } = useVueFlow()
const X = [0, 440, 880]

// 来源 = 自定义来源卡（卡内下拉选「最近发石者 / 抖音好友」）；目标 = 独立目标实体
const sources = computed(() => store.customSources)
const targets = computed(() => store.customTargets)

// ---- 添加：直接生成卡片（卡上可编辑） ----
function addSource() {
  store.customSources.push({ uid: '', nickname: '' })
  scheduleLiveSave()
}
function delSource(source) {
  const i = store.customSources.indexOf(source)
  if (i >= 0) { store.customSources.splice(i, 1); scheduleLiveSave() }
}
function addTarget() {
  const n = store.customTargets.length + 1
  store.customTargets.push({ id: 'tgt' + n, adapter: 'aiocqhttp', group: '' })
  scheduleLiveSave()
}
function delTarget(t) {
  const i = store.customTargets.indexOf(t)
  if (i >= 0) store.customTargets.splice(i, 1)
  const old = t.adapter + ':GroupMessage:' + t.group
  store.routes.forEach(r => { if (r.target === old) r.target = '' })
  scheduleLiveSave()
}
function updateTarget(t, ad, gr) {
  const old = t.adapter + ':GroupMessage:' + t.group
  t.adapter = ad; t.group = gr
  const neu = ad + ':GroupMessage:' + gr
  store.routes.forEach(r => { if (r.target === old) r.target = neu })
  scheduleLiveSave()
}
function addRoute() {
  store.routes.push({ name: 'route' + (store.routes.length + 1), target: '',
    match: { types: ['text', 'video_card'], senders_include: [], senders_exclude: [] } })
  scheduleLiveSave()
}
function moveRoute(i, d) {
  const j = i + d
  if (j < 0 || j >= store.routes.length) return
  const t = store.routes[i]; store.routes[i] = store.routes[j]; store.routes[j] = t
  scheduleLiveSave()
}
function delRoute(i) { store.routes.splice(i, 1); scheduleLiveSave() }

// ---- 节点/边 ----
const nodes = ref([])
const edges = ref([])
const posOf = id => { const n = getNodes.value.find(x => x.id === id); return n ? { x: n.position.x, y: n.position.y } : null }
const sidOf = s => s.uid || ''
function sourceNode(s, i) {
  return { id: 'src|' + sidOf(s) + '|' + i, type: 'source', data: { custom: true, source: s, del: delSource } }
}
function routeOf(r, i) {
  return { id: 'route|' + i, type: 'route', data: { route: r, index: i, move: moveRoute, del: delRoute,
    targets: targets.value, sync: scheduleLiveSave } }
}
function targetOf(t, i) {
  return { id: 'tgt|' + t.id, type: 'target', data: { target: t, apply: updateTarget, del: delTarget } }
}
function edgeCls(sid, r) {
  const inc = (r.match && r.match.senders_include) || []
  const exc = (r.match && r.match.senders_exclude) || []
  const included = inc.includes(sid) || !inc.length
  if (exc.includes(sid) || !included) return 'off'
  if (inc.length || exc.length) return 'hit'
  return 'dim'
}
function edgeTo(id, s, t, cls) {
  return { id, source: s, target: t, type: 'bezier', animated: cls === 'hit',
    markerEnd: { type: MarkerType.ArrowClosed, width: 14, height: 14 },
    style: { stroke: cls === 'hit' ? '#0969da' : (cls === 'off' ? '#d1242f' : '#a0a0a0'),
      strokeWidth: cls === 'dim' ? 1.4 : 2.2, strokeDasharray: cls === 'off' ? '6 4' : undefined } }
}

function buildNodes() {
  const ns = []
  sources.value.forEach((s, i) => {
    const n = sourceNode(s, i)
    n.position = posOf(n.id) || { x: X[0], y: i * 150 }
    ns.push(n)
  })
  store.routes.forEach((r, i) => {
    const n = routeOf(r, i)
    n.position = posOf(n.id) || { x: X[1], y: i * 230 }
    ns.push(n)
  })
  targets.value.forEach((t, i) => {
    const n = targetOf(t, i)
    n.position = posOf(n.id) || { x: X[2], y: i * 180 }
    ns.push(n)
  })
  nodes.value = ns
}
function buildEdges() {
  const es = []
  sources.value.forEach((s, si) => {
    const sid = sidOf(s)
    if (!sid) return
    store.routes.forEach((r, ri) => {
      es.push(edgeTo(`e|src|${sid}|${si}|${ri}`, 'src|' + sid + '|' + si, 'route|' + ri, edgeCls(sid, r)))
    })
  })
  store.routes.forEach((r, ri) => {
    if (!r.target) return
    const ti = targets.value.findIndex(t => (t.adapter + ':GroupMessage:' + t.group) === r.target)
    if (ti >= 0) es.push(edgeTo(`e|route|${ri}|${ti}`, 'route|' + ri, 'tgt|' + targets.value[ti].id, 'hit'))
  })
  edges.value = es
}
function build() { buildNodes(); buildEdges() }

// 结构变化 → 重建节点+边；内容变化（类型/名单）→ 只重建边（保焦点）
watch(() => JSON.stringify({ r: store.routes.length, t: targets.value, c: store.customSources,
  g: store.routes.map(r => r.target).join('|') }), build)
watch(() => JSON.stringify(store.routes.map(r => ((r.match && r.match.types) || []).join(',') + '|' +
  ((r.match && r.match.senders_include) || []).join(',') + '|' + ((r.match && r.match.senders_exclude) || []).join(','))), buildEdges)

// 实时保存
let liveReady = false
watch(() => JSON.stringify({ r: store.routes, c: store.customSources, t: store.customTargets }), () => { if (liveReady) scheduleLiveSave() })
onMounted(() => { build(); setTimeout(() => { liveReady = true }, 600) })
</script>

<template>
  <div class="vf-wrap">
    <div class="bar" style="margin-bottom:10px">
      <button class="ghost" @click="addSource">+ 添加来源</button>
      <button class="ghost" @click="addRoute">+ 添加路由</button>
      <button class="ghost" @click="addTarget">+ 添加目标</button>
      <span class="muted">{{ store.routes.length }} 条路由 · {{ store.customTargets.length }} 个目标 · 拖拽节点布局</span>
      <span v-if="store.liveSavedAt" class="muted save-state">已保存 {{ store.liveSavedAt }}</span>
    </div>

    <div class="topo tall">
      <VueFlow :nodes="nodes" :edges="edges" :min-zoom="0.3" :max-zoom="1.8"
        :default-edge-options="{ type: 'bezier' }" :nodes-connectable="false" :nodes-draggable="true"
        :pan-on-drag="true" fit-view-on-init>
        <template #node-source="p"><SourceNode :data="p.data" /></template>
        <template #node-route="p"><RouteNode :data="p.data" /></template>
        <template #node-target="p"><TargetNode :data="p.data" /></template>
        <Background pattern-color="#e2e2e2" :gap="18" :size="1.2" />
      </VueFlow>
      <div class="vf-colbar" style="left:12px">来源</div>
      <div class="vf-colbar" style="left:452px">路由</div>
      <div class="vf-colbar" style="left:892px">目标群</div>
    </div>
  </div>
</template>
