<script setup>
// 卡片测试页——几何布局（封闭外框，A/B/C/D 四区，CSS Grid）：
//   列：A 左全高长条 | B 中上最大 | D 右上长条（上排）
//   行：上排 B/D | 下排 C（列 2-3，宽 = B+D）
// 各区域独立组件（cards/test/*），父层只负责网格定位与共享状态，不写区域内部。
// 共享状态：templates（模板列表）+ selectedId（当前选中，驱动 B 区预览）。
import { ref, computed, onMounted } from 'vue'
import { apiGet, apiPostBody, toast } from '../../composables/store.js'
import TestRegionA from '../cards/test/TestRegionA.vue'
import TestRegionB from '../cards/test/TestRegionB.vue'
import TestRegionC from '../cards/test/TestRegionC.vue'
import TestRegionD from '../cards/test/TestRegionD.vue'

const templates = ref([])
const selectedId = ref('')
// 当前选中模板对象（供 D 区属性面板）
const selectedTemplate = computed(() => templates.value.find((t) => t.id === selectedId.value) || null)
// 表单内联错误（D 区展示：保存/删除失败等）
const formError = ref('')
// 点击积木区添加请求（{seq,type,label}，驱动 B 区插入卡片）
const addRequest = ref(null)
// 按住保存导出请求（自增，驱动 B 区导出当前布局；内部调试，无用户提示）
const exportSignal = ref(0)

// 尽力持久化（templates/set 全量替换）；返回是否成功（失败不抛，调用方内联提示）
async function persist() {
  try {
    const res = await apiPostBody('templates/set', { templates: JSON.parse(JSON.stringify(templates.value)) })
    return !!(res && res.ok !== false)
  } catch (_) {
    return false
  }
}

// 加载模板列表（离线预览/后端不可用 → 空列表，A 区仍可本地新建）
async function loadTemplates() {
  try {
    const d = await apiGet('templates/get')
    templates.value = d && d.ok && Array.isArray(d.templates) ? d.templates : []
  } catch (_) {
    templates.value = []
  }
  if (templates.value.length && !selectedId.value) {
    selectedId.value = templates.value[0].id
  }
}

function selectTemplate(t) {
  selectedId.value = t.id
}

// 添加空白模板：本地加入列表 + 尽力持久化（templates/set 全量替换；离线失败静默，本地仍生效）
async function createTemplate() {
  const id = 'tpl_' + Date.now() + Math.random().toString(36).slice(2, 6)
  const tpl = {
    id,
    name: '空白模板 ' + (templates.value.length + 1),
    blocks: [],
    layout: {},
    for_media: false,
    msg_type: 'auto',
  }
  templates.value.push(tpl)
  selectedId.value = id
  await persist()
}

// 保存模板属性（名字/类型）；失败内联提示
async function saveTemplate({ name, msg_type }) {
  const t = templates.value.find((x) => x.id === selectedId.value)
  if (!t) return
  if (!String(name || '').trim()) {
    formError.value = '模板名称不能为空'
    return
  }
  formError.value = ''
  t.name = String(name || '').trim()
  t.msg_type = msg_type
  const ok = await persist()
  if (!ok) formError.value = '保存失败，请重试'
}

// 删除当前模板：父层维护列表（二次确认由 D 区按钮状态完成）；失败内联提示
async function deleteTemplate() {
  const idx = templates.value.findIndex((x) => x.id === selectedId.value)
  if (idx < 0) return
  formError.value = ''
  templates.value.splice(idx, 1)
  selectedId.value = (templates.value[0] && templates.value[0].id) || ''
  const ok = await persist()
  if (!ok) formError.value = '删除失败，请重试'
}

// 预览：右下角按钮回调（当前仅提示；后续可接真实渲染预览）
function onPreview(cards) {
  toast('预览（待实现）：' + (Array.isArray(cards) ? cards.length + ' 张卡' : ''))
}

// 按住保存导出：转发触发给 B 区（B 区持有卡片布局与格宽，计算导出）
function requestExport() { exportSignal.value++ }

// B 区算好行结构后：组装完整 JSON（含模板元数据）并触发下载（内部调试，无 toast）
function handleExport(payload) {
  const t = selectedTemplate.value
  const json = {
    name: (t && t.name) || '未命名模板',
    msg_type: (t && t.msg_type) || 'auto',
    cell_w: payload.cell_w,
    cell_h: payload.cell_h,
    exported_at: new Date().toISOString(),
    row_count: payload.row_count,
    rows: payload.rows,
  }
  console.log('[模板导出]', json)
  downloadJson(json, json.name + '.json')
}

// 触发浏览器下载（生成 Blob + 临时 <a> 点击）
function downloadJson(obj, filename) {
  const blob = new Blob([JSON.stringify(obj, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

// 点击积木区添加：确保有选中模板（无则建空白并选中），通知 B 区插入
function addBlock({ type, kind, label }) {
  if (!selectedTemplate.value) {
    if (!templates.value.length) {
      // 无任何模板：本地新建空白模板并选中（createTemplate 同步设置 selectedId）
      createTemplate()
    }
    if (!selectedTemplate.value && templates.value.length) {
      selectedId.value = templates.value[0].id
    }
  }
  if (!selectedTemplate.value) return
  addRequest.value = { seq: Date.now() + Math.random(), type, kind, label }
}

// B 区卡片布局变化（拖放落位/添加）：同步到选中模板 blocks 并持久化
async function onCardsChange(list) {
  const t = selectedTemplate.value
  if (!t) return
  t.blocks = list
  await persist()
}

onMounted(loadTemplates)
</script>

<template>
  <div class="cards-test-page">
    <div class="test-layout">
      <TestRegionA
        class="region-a"
        :templates="templates"
        :selected-id="selectedId"
        @select="selectTemplate"
        @create="createTemplate"
      />
      <TestRegionB
        class="region-b"
        :cards="selectedTemplate ? (selectedTemplate.blocks || []) : null"
        :template-id="selectedId"
        :add-request="addRequest"
        :export-signal="exportSignal"
        @preview="onPreview"
        @change="onCardsChange"
        @export="handleExport"
      />
      <TestRegionD
        class="region-d"
        :selected="selectedTemplate"
        :form-error="formError"
        @save="saveTemplate"
        @delete="deleteTemplate"
        @export="requestExport"
      />
      <TestRegionC class="region-c" @add="addBlock" />
    </div>
  </div>
</template>

<style scoped>
.cards-test-page {
  width: 100%;
  height: calc(100vh - 120px);
  min-height: 0;
  box-sizing: border-box;
  padding: 8px;
}
/* 封闭外框：A 左贯穿全高；B/D 上排并排；C 下排横跨 B+D 宽 */
.test-layout {
  display: grid;
  grid-template-columns: minmax(96px, 1fr) minmax(0, 3.5fr) minmax(88px, 1.3fr);
  grid-template-rows: minmax(0, 3fr) minmax(96px, 1fr);
  gap: 8px;
  width: 100%;
  height: 100%;
  min-height: 0;
  box-sizing: border-box;
}
/* 网格定位（作用于子组件根节点）：A 列1 全高；B 列2 上排；D 列3 上排；C 列2-3 下排 */
.region-a { grid-column: 1; grid-row: 1 / 3; }
.region-b { grid-column: 2; grid-row: 1; }
.region-d { grid-column: 3; grid-row: 1; }
.region-c { grid-column: 2 / 4; grid-row: 2; }
</style>
