<script setup>
// 左栏：手机实时预览
// 用前端渲染器渲染当前消息实例，预览与转发同源（Schema 契约保证）
// 覆盖空 / 错 / 加载 / 长内容状态
// 视频积木 → 两条气泡（视频 + Markdown），顺序按积木位置（首位/末位）
import { computed } from 'vue'
import { renderPreview } from './renderBlocks.js'

const props = defineProps({
  blocks: { type: Array, default: () => [] },
  status: { type: String, default: 'idle' }, // idle | loading | error
  errorMsg: { type: String, default: '' },
})

const nowTime = '14:32'

// 拆成消息段：视频积木 → 独立气泡，其余 → Markdown 气泡（顺序按积木）
const segments = computed(() => {
  const b = props.blocks || []
  if (!b.length) return []
  const vi = b.findIndex((x) => x && x.type === 'video')
  if (vi < 0) return [{ type: 'md', html: renderPreview(b), text: '' }]
  const vData = b[vi].data || {}
  const others = b.filter((_, i) => i !== vi)
  const mdHtml = others.length ? renderPreview(others) : ''
  const videoText = `▶ ${vData.alt || '视频'}`
  const first = vi === 0
  const segs = []
  if (first) {
    segs.push({ type: 'video', html: '', text: videoText })
    if (mdHtml) segs.push({ type: 'md', html: mdHtml, text: '' })
  } else {
    if (mdHtml) segs.push({ type: 'md', html: mdHtml, text: '' })
    segs.push({ type: 'video', html: '', text: videoText })
  }
  return segs
})

// 预览 HTML（空/错/加载时不渲染，兼容旧单气泡）
const html = computed(() => {
  if (props.status === 'loading' || props.status === 'error') return ''
  return renderPreview(props.blocks || [])
})
</script>

<template>
  <div class="phone-wrap">
    <div class="phone">
      <div class="phone-screen">
        <div class="statusbar">
          <span>{{ nowTime }}</span>
          <span class="sb-right">
            <span class="signal"><i></i><i></i><i></i><i></i></span>
            <span class="battery"></span>
          </span>
        </div>
        <div class="nav">
          <span class="nav-back">‹</span>
          <div class="nav-title">接收群</div>
          <span class="nav-more">⋯</span>
        </div>

        <div class="chat">
          <!-- 状态覆盖：加载 / 错误 / 空 / 正常 -->
          <div v-if="status === 'loading'" class="state">加载中…</div>
          <div v-else-if="status === 'error'" class="state err">{{ errorMsg || '渲染失败' }}</div>
          <div v-else-if="!blocks || !blocks.length" class="state">
            暂无积木，从右侧添加积木开始拼装
          </div>
          <template v-else>
            <div class="time-divider">{{ nowTime }}</div>
            <div v-for="(seg, si) in segments" :key="si" class="msg">
              <div class="avatar">群</div>
              <div class="msg-main">
                <div class="msg-name">接收群</div>
                <div class="bubble" :class="seg.type">
                  <div v-if="seg.type === 'video'" class="video-chip">{{ seg.text }}</div>
                  <div v-else class="preview-body" v-html="seg.html"></div>
                </div>
              </div>
            </div>
          </template>
        </div>

        <div class="composer">
          <div class="composer-input">发送消息…</div>
          <div class="composer-icons">＋ ☺</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.phone-wrap {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 10px;
  min-height: 0;
}
.phone {
  width: 100%;
  aspect-ratio: 390 / 844;
  max-height: 100%;
  background: #0E1116;
  border-radius: 46px;
  padding: 9px;
  box-shadow: 0 24px 56px rgba(20, 28, 40, .20), 0 2px 6px rgba(20, 28, 40, .10);
  flex: none;
}
.phone-screen {
  width: 100%;
  height: 100%;
  background: #fff;
  border-radius: 38px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.statusbar {
  height: 42px;
  flex: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  font-size: 12px;
  font-weight: 600;
  color: #191C21;
}
.sb-right { display: flex; align-items: center; gap: 6px; }
.signal { display: flex; align-items: flex-end; gap: 1.5px; height: 10px; }
.signal i { width: 3px; background: #191C21; border-radius: 1px; }
.signal i:nth-child(1) { height: 4px; }
.signal i:nth-child(2) { height: 6px; }
.signal i:nth-child(3) { height: 8px; }
.signal i:nth-child(4) { height: 10px; }
.battery { width: 20px; height: 10px; border: 1px solid #191C21; border-radius: 3px; position: relative; }
.battery::after { content: ''; position: absolute; left: 1px; top: 1px; bottom: 1px; width: 12px; background: #191C21; border-radius: 1.5px; }
.nav {
  height: 44px;
  flex: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 14px;
  border-bottom: 1px solid #F0F2F5;
}
.nav-back { font-size: 22px; line-height: 1; color: #616A78; width: 20px; }
.nav-title { font-size: 15px; font-weight: 600; color: #191C21; }
.nav-more { color: #616A78; font-size: 16px; width: 20px; text-align: right; }
.chat {
  flex: 1;
  overflow-y: auto;
  padding: 14px 12px;
  background: #F2F3F6;
  min-height: 0;
}
.chat::-webkit-scrollbar { width: 0; }
.time-divider { text-align: center; font-size: 11px; color: #9AA1AC; margin-bottom: 12px; }
.msg { display: flex; gap: 8px; align-items: flex-start; }
.avatar {
  width: 34px; height: 34px; border-radius: 9px; flex: none;
  background: linear-gradient(135deg, #6FA0F5, #8B7BF0);
  color: #fff; display: grid; place-items: center; font-size: 13px; font-weight: 600;
}
.msg-main { min-width: 0; }
.msg-name { font-size: 11px; color: #9AA1AC; margin-bottom: 4px; }
.bubble {
  background: #fff; border-radius: 12px; overflow: hidden;
  box-shadow: 0 1px 3px rgba(16, 24, 40, .08);
  max-width: 268px;
}
.preview-body { padding: 12px; font-size: 13px; line-height: 1.6; color: #191C21; word-break: break-word; }
.video-chip {
  padding: 26px 20px;
  background: #1B1F27;
  color: #E7EAF0;
  font-size: 14px;
  font-weight: 600;
  text-align: center;
  letter-spacing: 1px;
}
.preview-body :deep(img) { max-width: 100%; border-radius: 6px; display: block; margin: 6px 0; }
.preview-body :deep(a) { color: #2E7CF6; }
.preview-body :deep(h3) { margin: 6px 0 2px; font-size: 14px; }
.preview-body :deep(code) { background: #F2F4F7; padding: 1px 5px; border-radius: 4px; font-size: 12px; }
.composer {
  flex: none;
  height: 52px;
  border-top: 1px solid #F0F2F5;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 12px;
  background: #fff;
}
.composer-input {
  flex: 1; height: 32px; border-radius: 16px; background: #F2F4F7;
  display: flex; align-items: center; padding: 0 12px; font-size: 12px; color: #9AA1AC;
}
.composer-icons { color: #9AA1AC; font-size: 16px; letter-spacing: 3px; }

/* 状态：空 / 错 / 加载 */
.state {
  height: 100%;
  min-height: 240px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #9AA1AC;
  font-size: 12px;
  text-align: center;
  padding: 0 20px;
}
.state.err { color: #F04452; }
</style>
