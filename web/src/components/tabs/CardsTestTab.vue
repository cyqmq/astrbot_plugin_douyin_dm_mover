<script setup>
// 卡片编辑器（重写版）——步骤 2：三栏框架 + 左栏手机预览
// 三栏布局由 CardsTab 统一控制宽度/高度/间距，各栏组件内不写
// 任务 2：中栏线性拖拽列表 → 二维装配画布（gridstack），属性面板改 data 实时更新画布
import { ref, watch, onMounted } from 'vue'
import { apiGet, apiPostBody, toast } from '../../composables/store.js'
import PhonePreview from '../cards/PhonePreview.vue'
import PlaceholderLibrary from '../cards/PlaceholderLibrary.vue'
import CardAssemblyCanvas from '../grid/CardAssemblyCanvas.vue'
import { createBlock, validateBlocks } from '../cards/blockTypes.js'
import { useBlocks } from '../../composables/useBlocks.js'

const {
  blocks,
  layout,
  videoCount,
  applyChange,
  addBlock,
  removeBlock,
  duplicateBlock,
  resetBlocks,
} = useBlocks()

const selectedBlock = ref(null)
const loading = ref(false)
const saving = ref(false)
const status = ref('idle')  // 预览状态：idle/loading/error
const errorMsg = ref('')
const saveHint = ref('')

// 归一化积木（补 id、disabled 字段）
function normalizeBlock(b) {
  return {
    id: b.id || 'b' + Date.now() + Math.random().toString(36).slice(2, 6),
    ...b,
    disabled: b.disabled !== false,
  }
}

// 加载草稿/模板：视频积木若在中间移到末位（保持首位/末位约束）
function normalizeBlocks(arr) {
  const b = (arr || []).map(normalizeBlock)
  const vi = b.findIndex((x) => x && x.type === 'video')
  if (vi > 0 && vi < b.length - 1) {
    const [v] = b.splice(vi, 1)
    b.push(v)
  }
  return b
}

// 加载：先草稿，无草稿用模板，无模板用默认（回填用 resetBlocks 整体重分配 layout）
async function loadInitial() {
  loading.value = true
  status.value = 'loading'
  try {
    const d = await apiGet('messages/draft')
    if (d && d.ok && Array.isArray(d.blocks) && d.blocks.length) {
      resetBlocks(normalizeBlocks(d.blocks))
    } else {
      const t = await apiGet('templates/get')
      if (t && t.ok && Array.isArray(t.templates) && t.templates.length) {
        const first = t.templates[0]
        resetBlocks(normalizeBlocks(first.blocks || []))
      } else {
        resetBlocks([createBlock('text', { text: '{desc}' })])
      }
    }
    status.value = 'idle'
  } catch (e) {
    // 测试页离线容错：无后端也能展示画布（生产 CardsTab 不依赖此路径）
    resetBlocks([createBlock('text', { text: '{desc}' })])
    status.value = 'idle'
  } finally {
    loading.value = false
  }
}

// 积木库添加：video 不选中（等顺序窗口）；非视频立即选中新积木
function onAddBlock(type) {
  const r = addBlock(type)
  if (r.error) { toast(r.error); return }
  if (r.block && !r.isVideo) {
    selectedBlock.value = r.block
  }
}

// 画布点击选中 → 右栏属性面板
function selectBlock(block) {
  selectedBlock.value = block
}

// 画布积木操作（用积木对象，非索引）
function toggleBlock(block) {
  if (block) block.disabled = !block.disabled
}
function onDuplicateBlock(block) {
  const r = duplicateBlock(block.id)
  if (r.error) { toast(r.error); return }
  if (r.block) selectedBlock.value = r.block
}
function onRemoveBlock(block) {
  removeBlock(block.id)
  if (selectedBlock.value && selectedBlock.value.id === block.id) {
    selectedBlock.value = null
  }
}

// 自动保存草稿（防抖 1.5 秒）
let draftTimer
function scheduleDraftSave() {
  clearTimeout(draftTimer)
  draftTimer = setTimeout(saveDraft, 1500)
}
async function saveDraft() {
  const r = validateBlocks(blocks.value)
  if (!r.ok) return
  try {
    // 深拷贝剥离 Vue 响应式 Proxy（postMessage structured clone 无法克隆 Proxy），
    // 与 actions.js saveConfig 的 JSON 深拷贝约定一致
    const d = await apiPostBody('messages/draft', { blocks: JSON.parse(JSON.stringify(blocks.value)) })
    saveHint.value = (d && d.ok) ? '草稿已自动保存' : ('草稿保存失败: ' + ((d && d.detail) || ''))
  } catch (e) {
    saveHint.value = '草稿保存失败'
  }
}

// 保存为模板
async function saveAsTemplate() {
  const r = validateBlocks(blocks.value)
  if (!r.ok) { toast(r.detail); return }
  saving.value = true
  try {
    const d = await apiPostBody('templates/set', {
      // 深拷贝剥离 Vue 响应式 Proxy（postMessage structured clone 无法克隆 Proxy）
      templates: [{ id: 'default', name: '默认模板', blocks: JSON.parse(JSON.stringify(blocks.value)), for_media: false }],
    })
    if (d && d.ok) {
      toast(d.detail || '已保存为模板')
      saveHint.value = '已保存为模板'
    } else {
      toast((d && d.detail) || '保存失败')
      saveHint.value = '保存失败'
    }
  } catch (e) {
    toast('保存失败')
    saveHint.value = '保存失败'
  } finally {
    saving.value = false
  }
}

// 监听 blocks 变化，自动保存草稿
watch(blocks, scheduleDraftSave, { deep: true })

onMounted(loadInitial)
</script>

<template>
  <div class="cards-app">
    <aside class="col col-left">
      <div class="col-head"><h2>手机预览</h2></div>
      <PhonePreview :blocks="blocks" />
    </aside>

    <main class="col col-center">
      <div class="col-head">
        <h2>消息拼装</h2>
        <div class="head-actions">
          <span class="save-hint">{{ saveHint }}</span>
          <button class="btn-save" :disabled="saving" @click="saveAsTemplate">
            {{ saving ? '保存中…' : '保存为模板' }}
          </button>
        </div>
      </div>
      <CardAssemblyCanvas
        :blocks="blocks"
        :layout="layout"
        :video-count="videoCount"
        @change="applyChange"
        @select="selectBlock"
        @toggle="toggleBlock"
        @duplicate="onDuplicateBlock"
        @remove="onRemoveBlock"
      />
    </main>

    <aside class="col col-right">
      <div class="col-head"><h2>积木</h2></div>
      <PlaceholderLibrary :selected-block="selectedBlock" @add="onAddBlock" />
    </aside>
  </div>
</template>

<style scoped>
/* 三栏布局（CardsTab 统一控制，宽度比例/高度/间距） */
.cards-app{
  display:grid;
  grid-template-columns:3fr 4fr 3fr;
  grid-template-rows:minmax(0, 1fr);
  gap:8px;
  padding:8px;
  height:calc(100vh - 120px);
  min-height:520px;
  width:100%;
  box-sizing:border-box;
}

.col{
  background:var(--card);
  border:1px solid var(--border);
  border-radius:14px;
  display:flex;
  flex-direction:column;
  min-height:0;
  min-width:0;
  width:100%;
  height:100%;
  overflow:hidden;
}

.col-head{
  display:flex;
  align-items:center;
  justify-content:space-between;
  padding:12px 14px;
  border-bottom:1px solid var(--border);
  flex:none;
  gap:8px;
}
.col-head h2{
  font-size:14px;
  font-weight:600;
}

/* 隐藏左右栏标题（中栏标题不动，保存按钮还在） */
.cards-app .col-left .col-head,
.cards-app .col-right .col-head {
  display: none;
}

.head-actions{
  display:flex;
  align-items:center;
  gap:10px;
}
.save-hint{
  font-size:11px;
  color:var(--muted);
}
.btn-save{
  border:none;
  border-radius:8px;
  padding:6px 12px;
  font-size:12px;
  font-weight:500;
  cursor:pointer;
  background:var(--accent);
  color:var(--card);
  transition:.15s;
}
.btn-save:hover{ filter:brightness(.9); }
.btn-save:disabled{ background:var(--border2); cursor:not-allowed; }

.col-body{
  flex:1;
  overflow:auto;
  padding:14px;
  min-height:0;
  display:flex;
  align-items:flex-start;
  justify-content:flex-start;
}

/* 左栏：渐变背景（手机预览直接撑满，无外部容器） */
.col-left{
  background:linear-gradient(180deg,var(--bg) 0%,var(--border) 100%);
}
</style>
