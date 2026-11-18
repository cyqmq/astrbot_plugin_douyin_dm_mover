<script setup>
// 右栏：占位符积木库（上） + 结构积木（中） + 选中属性（下）
// 占位符积木点击添加到消息；选中积木后编辑属性
import { ref, nextTick } from 'vue'
import {
  PLACEHOLDER_LIST,
  STRUCTURAL_TYPES,
  BLOCK_TYPE_LIST,
  PLACEHOLDERS,
  isPlaceholder,
  placeholderToken,
  blockMsgType,
} from './blockTypes.js'

defineProps({
  selectedBlock: { type: Object, default: null },
})

defineEmits(['add'])

// 结构积木列表（纯文本/分割线）
const STRUCT_LIST = STRUCTURAL_TYPES.map((key) => ({
  key,
  ...BLOCK_TYPE_LIST.find((t) => t.key === key),
})).filter((t) => t.key)

// 纯文本输入框 ref（占位符快捷插入用）
const textRef = ref(null)

// 在当前光标处插入占位符 token（无焦点则追加末尾）
function insertToken(token) {
  const el = textRef.value
  if (!el) return
  const start = el.selectionStart
  const end = el.selectionEnd
  const v = el.value
  el.value = v.slice(0, start) + token + v.slice(end)
  const pos = start + token.length
  el.selectionStart = el.selectionEnd = pos
  el.focus()
}
</script>

<template>
  <div class="library">
    <!-- 上：占位符积木 -->
    <div class="lib-section">
      <div class="lib-title">占位符积木</div>
      <div class="lib-grid ph-grid">
        <button
          v-for="p in PLACEHOLDER_LIST"
          :key="p.key"
          class="lib-item ph-item"
          :title="p.hint"
          @click="$emit('add', p.key)"
        >
          <span class="lib-badge" :class="blockMsgType(p.key)">{{ blockMsgType(p.key) === 'media' ? 'M7' : 'M' }}</span>
          <span class="ph-label">{{ p.label }}</span>
          <code class="ph-token">{{ p.token }}</code>
        </button>
      </div>
    </div>

    <!-- 中：结构积木 -->
    <div class="lib-section">
      <div class="lib-title">结构积木</div>
      <div class="lib-grid">
        <button
          v-for="s in STRUCT_LIST"
          :key="s.key"
          class="lib-item"
          @click="$emit('add', s.key)"
        >
          <span class="lib-badge" :class="blockMsgType(s.key)">{{ blockMsgType(s.key) === 'media' ? 'M7' : 'M' }}</span>
          <span class="lib-label">{{ s.label }}</span>
        </button>
      </div>
    </div>

    <!-- 下：选中属性（flex:1 填充剩余空间） -->
    <div class="lib-section props">
      <div class="lib-title">积木属性</div>
      <template v-if="selectedBlock">
        <!-- 占位符积木：只读说明（无属性可编辑，type 即占位符） -->
        <div v-if="isPlaceholder(selectedBlock.type)" class="ph-info">
          <code class="ph-info-token">{{ placeholderToken(selectedBlock.type) }}</code>
          <span class="ph-info-hint">{{ PLACEHOLDERS[selectedBlock.type]?.hint }}</span>
          <div class="ph-info-desc">该积木转发时替换为真实值，无需配置。</div>
        </div>

        <!-- 图片：alt 描述 -->
        <div v-else-if="selectedBlock.type === 'image'" class="field">
          <label>图片描述（alt）</label>
          <input v-model="selectedBlock.data.alt" placeholder="可留空，默认用标题" />
        </div>

        <!-- 视频：alt 描述 -->
        <div v-else-if="selectedBlock.type === 'video'" class="field">
          <label>视频描述（alt）</label>
          <input v-model="selectedBlock.data.alt" placeholder="可留空，默认用视频" />
        </div>

        <!-- 按钮：不可配置，恒跳转视频链接 -->
        <div v-else-if="selectedBlock.type === 'button'" class="field">
          <div class="ph-info-desc">该按钮转发时自动跳转视频链接，无需配置。</div>
        </div>

        <!-- 纯文本：文本域 + 占位符快捷插入 -->
        <div v-else-if="selectedBlock.type === 'text'" class="field">
          <label>文本内容</label>
          <textarea ref="textRef" v-model="selectedBlock.data.text" rows="4"></textarea>
          <div class="ph-chips">
            <button
              v-for="p in PLACEHOLDER_LIST"
              :key="p.key"
              class="chip"
              :title="p.hint"
              @click="insertToken(p.token)"
            >
              {{ p.token }}
            </button>
          </div>
        </div>

        <div v-else class="muted">该积木无需配置</div>
      </template>
      <div v-else class="empty">未选中积木，在中间编排区点击积木</div>
    </div>
  </div>
</template>

<style scoped>
.library {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  gap: 12px;
}
.lib-section {
  flex: none;
  display: flex;
  flex-direction: column;
  min-height: 0;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--card);
  overflow: hidden;
}
.lib-title {
  padding: 10px 14px;
  font-size: 12px;
  font-weight: 600;
  color: var(--muted);
  border-bottom: 1px solid var(--border);
  flex: none;
}

/* 属性区：填充剩余空间（占位符/结构区自然高度，属性区弹性） */
.lib-section.props {
  flex: 1 1 0;
  min-height: 0;
  overflow: auto;
}

/* 占位符积木 */
.ph-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  padding: 12px;
  align-content: start;
}
.ph-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  text-align: left;
  padding: 9px 10px;
}
.ph-label {
  font-size: 12px;
  color: var(--text);
}
.ph-token {
  font-size: 10.5px;
  color: var(--accent);
  background: var(--accent);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  word-break: break-all;
  line-height: 1.4;
}

/* 结构积木 */
.lib-grid {
  flex: none;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  padding: 12px;
  align-content: start;
  overflow: auto;
  min-height: 0;
}
.lib-item {
  position: relative;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--card);
  padding: 10px 8px;
  cursor: pointer;
  transition: .15s;
  font-size: 12px;
  color: var(--text);
}

/* 渲染模式徽标：markdown=蓝 M、media=紫 M7 */
.lib-badge {
  position: absolute;
  top: 4px;
  right: 4px;
  font-size: 9px;
  font-weight: 600;
  line-height: 1;
  padding: 2px 4px;
  border-radius: 5px;
  background: rgba(88, 166, 255, 0.12);
  color: var(--accent);
}
.lib-badge.media {
  background: rgba(167, 139, 250, 0.14);
  color: #a78bfa;
}
.lib-item:hover {
  border-color: var(--accent);
  color: var(--accent);
  background: var(--accent);
  background-clip: padding-box;
}
.lib-label { display: block; }

/* 下：选中属性 */
.field {
  margin-bottom: 12px;
  padding: 0 14px 12px;
}
.field label {
  display: block;
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 6px;
}
.field textarea {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 12.5px;
  color: var(--text);
  background: var(--card);
  outline: none;
  transition: .15s;
  font-family: inherit;
  resize: vertical;
  line-height: 1.6;
}
.field textarea:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent);
}
.ph-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}
.chip {
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--accent);
  border-radius: 6px;
  padding: 3px 7px;
  font-size: 10.5px;
  cursor: pointer;
  transition: .15s;
  font-family: monospace;
}
.chip:hover {
  border-color: var(--accent);
  background: var(--accent);
  color: var(--card);
}

/* 占位符只读信息 */
.ph-info {
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.ph-info-token {
  font-size: 12px;
  color: var(--accent);
  font-family: monospace;
  word-break: break-all;
}
.ph-info-hint {
  font-size: 12px;
  color: var(--muted);
}
.ph-info-desc {
  font-size: 11px;
  color: var(--muted);
}
.muted {
  padding: 0 14px 12px;
  font-size: 12px;
  color: var(--muted);
}
.empty {
  padding: 20px 14px;
  text-align: center;
  font-size: 12px;
  color: var(--muted);
}
</style>
