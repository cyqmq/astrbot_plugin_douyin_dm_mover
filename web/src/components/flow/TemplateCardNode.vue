<script setup>
import { ref, computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'

// 模板卡节点：路由的模板卡替换配置（需求 5.1）。
// 左 target 接路由（启用 templateCard），右 source 接目标（模板卡替换发送到目标）。
// 顶部 enabled 开关；模板序列列表（从已保存模板下拉添加 + 上移/下移/移除），写回 route.templateCard。
const props = defineProps({ data: { type: Object, required: true } })
const d = props.data
const r = d.route
const tc = computed(() => r.templateCard || { enabled: true, templates: [] })
const addSel = ref('')

function toggleEnabled() { r.templateCard.enabled = !r.templateCard.enabled }
function addTpl() {
  const v = addSel.value
  if (v && !tc.value.templates.includes(v)) tc.value.templates.push(v)
  addSel.value = ''
}
function moveTpl(i, dir) {
  const a = tc.value.templates
  const j = i + dir
  if (i < 0 || j < 0 || j >= a.length) return
  const t = a[i]; a[i] = a[j]; a[j] = t
}
function delTpl(i) { tc.value.templates.splice(i, 1) }
</script>

<template>
  <div class="tcard">
    <div class="tc-head">
      <label class="tc-toggle" title="启用模板卡替换发送；关闭=直连（走现有转发）">
        <input type="checkbox" class="nodrag" :checked="tc.enabled" @change="toggleEnabled">
        <span>启用</span>
      </label>
      <span class="tc-btns">
        <button class="danger nodrag" title="删除模板卡节点" @click="d.del(r)">×</button>
      </span>
    </div>
    <div class="tc-row">
      <select v-model="addSel" class="nodrag" title="从已保存模板添加" @change="addTpl">
        <option value="">+ 添加模板</option>
        <option v-for="t in d.templates" :key="t.id" :value="t.name">{{ t.name }}</option>
      </select>
    </div>
    <div class="tc-list">
      <div v-for="(n, i) in tc.templates" :key="i" class="tc-item">
        <span class="tc-name" :title="n">{{ n }}</span>
        <span class="tc-ops">
          <button class="nodrag" title="上移" @click="moveTpl(i, -1)">↑</button>
          <button class="nodrag" title="下移" @click="moveTpl(i, 1)">↓</button>
          <button class="nodrag" title="移除" @click="delTpl(i)">×</button>
        </span>
      </div>
      <div v-if="!tc.templates.length" class="tc-empty">未选择模板（直连）</div>
    </div>
    <Handle type="target" :position="Position.Left" title="接收路由连接（启用模板卡）" />
    <Handle type="source" :position="Position.Right" title="连向目标（模板卡替换发送）" />
  </div>
</template>

<style scoped>
.tcard {
  position: relative;
  width: 230px;
  background: var(--card);
  border: 1px solid var(--border);
  border-left: 3px solid var(--accent);
  border-radius: 8px;
  padding: 8px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  font-size: 12px;
}
.tc-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}
.tc-toggle {
  display: flex;
  align-items: center;
  gap: 5px;
  color: var(--text);
  cursor: pointer;
  user-select: none;
}
.tc-toggle input { accent-color: var(--accent); cursor: pointer; }
.tc-btns button {
  border: none;
  background: transparent;
  color: var(--muted);
  font-size: 14px;
  cursor: pointer;
  padding: 0 4px;
}
.tc-btns button.danger { color: #dc2626; }
.tc-btns button:hover { opacity: 0.8; }
.tc-row { margin-bottom: 6px; }
.tc-row select {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 4px 6px;
  font-size: 12px;
  color: var(--text);
  background: var(--bg);
  outline: none;
  cursor: pointer;
}
.tc-list { display: flex; flex-direction: column; gap: 3px; }
.tc-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 4px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 5px;
  padding: 3px 6px;
}
.tc-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text);
}
.tc-ops { display: flex; align-items: center; gap: 1px; flex: none; }
.tc-ops button {
  border: none;
  background: transparent;
  color: var(--muted);
  font-size: 11px;
  cursor: pointer;
  padding: 0 3px;
}
.tc-ops button:hover { color: var(--text); }
.tc-empty { font-size: 11px; color: var(--muted); padding: 2px 4px; }
</style>
