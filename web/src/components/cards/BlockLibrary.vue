<script setup>
// 右栏：积木库（上） + 选中属性（下）
// 积木类型固定，点击添加到消息；选中积木后编辑属性
import { BLOCK_TYPE_LIST } from './blockTypes.js'

defineProps({
  selectedBlock: { type: Object, default: null },
})

defineEmits(['add'])

// 各积木类型的字段标签（属性表单动态生成）
const FIELD_LABELS = {
  text: { text: '文本内容' },
  heading: { title: '标题', body: '正文' },
  media: { image: '图片 URL', title: '标题', desc: '描述' },
  link: { text: '链接文字', url: '链接地址' },
  button: { text: '按钮文字', url: '跳转链接' },
  divider: {},
}

// 长文本字段用 textarea，其余用 input
function isLong(key) {
  return key === 'text' || key === 'body' || key === 'desc'
}
</script>

<template>
  <div class="library">
    <!-- 上：积木库 -->
    <div class="lib-section">
      <div class="lib-title">积木库</div>
      <div class="lib-grid">
        <button
          v-for="t in BLOCK_TYPE_LIST"
          :key="t.key"
          class="lib-item"
          @click="$emit('add', t.key)"
        >
          <span class="lib-label">{{ t.label }}</span>
        </button>
      </div>
    </div>

    <!-- 下：选中属性 -->
    <div class="lib-section">
      <div class="lib-title">积木属性</div>
      <template v-if="selectedBlock">
        <div
          v-for="(label, key) in FIELD_LABELS[selectedBlock.type]"
          :key="key"
          class="field"
        >
          <label>{{ label }}</label>
          <textarea
            v-if="isLong(key)"
            v-model="selectedBlock.data[key]"
            rows="3"
          ></textarea>
          <input v-else v-model="selectedBlock.data[key]">
        </div>
        <div
          v-if="!FIELD_LABELS[selectedBlock.type] || !Object.keys(FIELD_LABELS[selectedBlock.type]).length"
          class="muted"
        >
          该积木无需配置
        </div>
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
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  border: 1px solid #E7E9ED;
  border-radius: 12px;
  background: #FAFBFC;
  overflow: hidden;
}
.lib-title {
  padding: 10px 14px;
  font-size: 12px;
  font-weight: 600;
  color: #616A78;
  border-bottom: 1px solid #F0F2F5;
  flex: none;
}

/* 上：积木库 */
.lib-grid {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  padding: 12px;
  align-content: start;
  overflow: auto;
  min-height: 0;
}
.lib-item {
  border: 1px solid #E7E9ED;
  border-radius: 10px;
  background: #fff;
  padding: 10px 8px;
  cursor: pointer;
  transition: .15s;
  font-size: 12px;
  color: #191C21;
}
.lib-item:hover {
  border-color: #2E7CF6;
  color: #2E7CF6;
  background: #EBF2FE;
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
  color: #616A78;
  margin-bottom: 6px;
}
.field input,
.field textarea {
  width: 100%;
  border: 1px solid #E7E9ED;
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 12.5px;
  color: #191C21;
  background: #fff;
  outline: none;
  transition: .15s;
  font-family: inherit;
}
.field input:focus,
.field textarea:focus {
  border-color: #2E7CF6;
  box-shadow: 0 0 0 3px #EBF2FE;
}
.field textarea {
  resize: vertical;
  line-height: 1.6;
}
.muted {
  padding: 0 14px 12px;
  font-size: 12px;
  color: #9AA1AC;
}
.empty {
  padding: 20px 14px;
  text-align: center;
  font-size: 12px;
  color: #9AA1AC;
}
</style>
