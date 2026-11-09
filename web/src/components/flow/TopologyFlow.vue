<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { VueFlow, useVueFlow, MarkerType } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import SourceNode from './SourceNode.vue'
import RouteNode from './RouteNode.vue'
import TargetNode from './TargetNode.vue'
import { store, sendersTop } from '../../composables/store.js'
import { loadFriends } from '../../composables/actions.js'

const props = defineProps({ sourceMode: { type: String, default: 'senders' } })
const emit = defineEmits(['save'])
const { getNodes } = useVueFlow()

const sources = computed(() => {
  if (props.sourceMode === 'friends') return store.friends
  return sendersTop.value
})
const targets = computed(() => {
  const t = []
  store.routes.forEach(r => { if (r.target && !t.includes(r.target)) t.push(r.target) })
  return t
})

// ---- 节点/边 ----
const nodes = ref([])
const edges = ref([])
const X = [0, 440, 880]
const posOf = id => { const n = getNodes.value.find(x => x.id === id); return n ? { x: n.position.x, y: n.position.y } : null }
const key = id => id.split('|').pop()
const sidOf = s => (props.sourceMode === 'friends' ? (s.uid || s.peer_id || '') : (s.peer_id || ''))

function moveRoute(i, d) {
  const j = i + d
  if (j < 0 || j >= store.routes.length) return
  const t = store.routes[i]; store.routes[i] = store.routes[j]; store.routes[j] = t
}
function delRoute(i) { store.routes.splice(i, 1) }
function applyTarget(t, ad, gr) {
  const nt = gr.trim() ? (ad + ':GroupMessage:' + gr.trim()) : ''
  store.routes.forEach(r => { if (r.target === t) r.target = nt })
}
function friendOf(s) {
  return {
    id: 'src|' + sidOf(s), type: 'source',
    data: {
      name: (s.nickname || s.peer_name || '抖音来源').slice(0, 16),
      sub: props.sourceMode === 'friends'
        ? ((s.remark_name || s.signature || (s.uid ? 'uid ' + s.uid : '')).slice(0, 30))
        : (s.peer_id ? 'uid ' + s.peer_id : '抖音私信'),
      avatar: s.avatar || '', uid: sidOf(s)
    }
  }
}
function routeOf(r, i) {
  return { id: 'route|' + i, type: 'route', data: { route: r, index: i, move: moveRoute, del: delRoute } }
}
function targetOf(t, i) {
  return { id: 'tgt|' + t, type: 'target', data: { target: t, apply: applyTarget } }
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
    const n = friendOf(s)
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
  sources.value.forEach(s => {
    const sid = sidOf(s)
    store.routes.forEach((r, ri) => {
      es.push(edgeTo(`e|src|${sid}|${ri}`, 'src|' + sid, 'route|' + ri, edgeCls(sid, r)))
    })
  })
  store.routes.forEach((r, ri) => {
    const ti = targets.value.indexOf(r.target)
    if (ti >= 0) es.push(edgeTo(`e|route|${ri}|${ti}`, 'route|' + ri, 'tgt|' + r.target, 'hit'))
  })
  edges.value = es
}
function build() { buildNodes(); buildEdges() }

// 结构变化（增删路由/目标值或集合/来源切换）→ 重建节点+边；内容变化（类型/名单）→ 只重建边（保焦点）
watch(() => JSON.stringify({ r: store.routes.length, t: targets.value, s: props.sourceMode,
  g: store.routes.map(r => r.target).join('|') }), build)
watch(() => JSON.stringify(store.routes.map(r => r.target + '|' + ((r.match && r.match.types) || []).join(',') + '|' +
  ((r.match && r.match.senders_include) || []).join(',') + '|' + ((r.match && r.match.senders_exclude) || []).join(','))), buildEdges)
onMounted(build)
</script>

<template>
  <div class="vf-wrap">
    <div class="bar" style="margin-bottom:10px">
      <button class="ghost" @click="store.routes.push({ name: 'route' + (store.routes.length + 1), target: 'aiocqhttp:GroupMessage:',
        match: { types: ['text', 'video_card'], senders_include: [], senders_exclude: [] } })">+ 添加路由</button>
      <button class="primary" @click="emit('save')">保存路由</button>
      <span class="muted">{{ store.routes.length }} 条路由 · 拖拽节点布局</span>
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
    </div>
  </div>
</template>
