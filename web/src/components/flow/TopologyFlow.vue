<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { VueFlow, useVueFlow, MarkerType } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import SourceNode from './SourceNode.vue'
import RouteNode from './RouteNode.vue'
import TargetNode from './TargetNode.vue'
import { store, sendersTop, SELECTS } from '../../composables/store.js'
import { loadFriends, scheduleLiveSave } from '../../composables/actions.js'

const { getNodes } = useVueFlow()
const X = [0, 440, 880]

// ---- 来源：自定义(持久化) + 动态(最近发石者 / 抖音好友) ----
const sources = computed(() => {
  const dyn = store.sourceMode === 'friends'
    ? store.friends.map(f => ({ custom: false, name: (f.nickname || '抖音用户').slice(0, 16),
        sub: (f.remark_name || f.signature || (f.uid ? 'uid ' + f.uid : '')).slice(0, 30),
        avatar: f.avatar || '', uid: f.uid || f.peer_id || '' }))
    : sendersTop.value.map(s => ({ custom: false, name: (s.peer_name || '抖音来源').slice(0, 16),
        sub: s.peer_id ? 'uid ' + s.peer_id : '抖音私信', avatar: '', uid: s.peer_id || '' }))
  const custom = store.customSources.map(c => ({ custom: true, name: (c.nickname || c.uid || '来源').slice(0, 16),
    sub: 'uid ' + (c.uid || ''), avatar: '', uid: c.uid || '' }))
  const customUids = new Set(custom.map(c => c.uid))
  return [...custom, ...dyn.filter(d => !customUids.has(d.uid))]
})
const targets = computed(() => {
  const t = []
  store.routes.forEach(r => { if (r.target && !t.includes(r.target)) t.push(r.target) })
  return t
})

// ---- 添加来源 / 目标弹窗 ----
const srcOpen = ref(false), tgtOpen = ref(false)
const srcForm = reactive({ nickname: '', uid: '' })
const tgtForm = reactive({ adapter: 'aiocqhttp', group: '' })
function addSource() {
  const uid = srcForm.uid.trim()
  if (!uid) return
  if (!store.customSources.some(c => c.uid === uid)) {
    store.customSources.push({ uid, nickname: srcForm.nickname.trim() || uid })
    scheduleLiveSave()
  }
  srcOpen.value = false; srcForm.uid = ''; srcForm.nickname = ''
}
function delSource(uid) {
  const i = store.customSources.findIndex(c => c.uid === uid)
  if (i >= 0) { store.customSources.splice(i, 1); scheduleLiveSave() }
}
function addTarget() {
  const g = tgtForm.group.trim()
  if (!g) return
  const target = tgtForm.adapter + ':GroupMessage:' + g
  if (!store.routes.some(r => r.target === target)) {
    store.routes.push({ name: '目标' + (targets.value.length + 1), target,
      match: { types: ['text', 'video_card'], senders_include: [], senders_exclude: [] } })
    scheduleLiveSave()
  }
  tgtOpen.value = false; tgtForm.group = ''
}
function addRoute() {
  store.routes.push({ name: 'route' + (store.routes.length + 1), target: 'aiocqhttp:GroupMessage:',
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
function applyTarget(t, ad, gr) {
  const nt = gr.trim() ? (ad + ':GroupMessage:' + gr.trim()) : ''
  store.routes.forEach(r => { if (r.target === t) r.target = nt })
  scheduleLiveSave()
}
async function switchSource(mode) {
  store.sourceMode = mode
  if (mode === 'friends' && !store.friends.length) await loadFriends()
}
async function refreshFriends() { await loadFriends() }

// ---- 节点/边 ----
const nodes = ref([])
const edges = ref([])
const posOf = id => { const n = getNodes.value.find(x => x.id === id); return n ? { x: n.position.x, y: n.position.y } : null }
const sidOf = s => s.uid
function friendOf(s, i) {
  return { id: 'src|' + sidOf(s) + '|' + i, type: 'source',
    data: { name: s.name, sub: s.sub, avatar: s.avatar || '', uid: sidOf(s), custom: !!s.custom, del: delSource } }
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
    const n = friendOf(s, i)
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
    store.routes.forEach((r, ri) => {
      es.push(edgeTo(`e|src|${sid}|${si}|${ri}`, 'src|' + sid + '|' + si, 'route|' + ri, edgeCls(sid, r)))
    })
  })
  store.routes.forEach((r, ri) => {
    const ti = targets.value.indexOf(r.target)
    if (ti >= 0) es.push(edgeTo(`e|route|${ri}|${ti}`, 'route|' + ri, 'tgt|' + r.target, 'hit'))
  })
  edges.value = es
}
function build() { buildNodes(); buildEdges() }

// 结构变化 → 重建节点+边；内容变化（类型/名单）→ 只重建边（保焦点）
watch(() => JSON.stringify({ r: store.routes.length, t: targets.value, s: store.sourceMode,
  c: store.customSources, g: store.routes.map(r => r.target).join('|') }), build)
watch(() => JSON.stringify(store.routes.map(r => ((r.match && r.match.types) || []).join(',') + '|' +
  ((r.match && r.match.senders_include) || []).join(',') + '|' + ((r.match && r.match.senders_exclude) || []).join(','))), buildEdges)

// 实时保存：路由/自定义来源任何改动 → 防抖静默落盘
let liveReady = false
watch(() => JSON.stringify({ r: store.routes, c: store.customSources }), () => { if (liveReady) scheduleLiveSave() })
onMounted(() => { build(); setTimeout(() => { liveReady = true }, 600) })
</script>

<template>
  <div class="vf-wrap">
    <div class="bar" style="margin-bottom:10px">
      <button class="ghost" @click="srcOpen = !srcOpen">+ 添加来源</button>
      <button class="ghost" @click="addRoute">+ 添加路由</button>
      <button class="ghost" @click="tgtOpen = !tgtOpen">+ 添加目标</button>
      <span class="muted">{{ store.routes.length }} 条路由 · 拖拽节点布局</span>
      <span v-if="store.liveSavedAt" class="muted save-state">已保存 {{ store.liveSavedAt }}</span>
    </div>

    <div v-if="srcOpen" class="add-form card-inline">
      <input v-model="srcForm.nickname" placeholder="昵称（可选）">
      <input v-model="srcForm.uid" placeholder="uid（必填，用于连线匹配）" @keyup.enter="addSource">
      <button class="primary" @click="addSource">添加来源</button>
      <button class="ghost" @click="srcOpen = false">取消</button>
    </div>
    <div v-if="tgtOpen" class="add-form card-inline">
      <select v-model="tgtForm.adapter">
        <option v-for="[v, l] in SELECTS.qq_adapter_id" :key="v" :value="v">{{ l }}</option>
      </select>
      <input v-model="tgtForm.group" placeholder="目标群号" @keyup.enter="addTarget">
      <button class="primary" @click="addTarget">添加目标</button>
      <button class="ghost" @click="tgtOpen = false">取消</button>
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
      <div class="vf-colbar" style="left:12px">
        <span>来源</span>
        <select :value="store.sourceMode" @change="switchSource($event.target.value)">
          <option value="senders">最近发石者</option>
          <option value="friends">抖音好友</option>
        </select>
        <button v-if="store.sourceMode === 'friends'" class="mini" @click="refreshFriends">刷新</button>
      </div>
      <div class="vf-colbar" style="left:452px">路由</div>
      <div class="vf-colbar" style="left:892px">目标群</div>
    </div>
  </div>
</template>
