<script setup>
// 推送卡片编辑器：模板列表（一段 Markdown/纯文本）+ 卡片类型骨架 + 图片预览 + 手机预览。
// 占位符白名单与后端 templates/set 一致：source/peer_name/time/title/desc/link/image_url。
import { onMounted, ref } from 'vue'
import { apiGet, apiPostBody, toast } from '../../composables/store.js'

const templates = ref([])
const markdownEnabled = ref(true)
const sanitizeBody = ref(true)
const maxLen = ref(1000)
const loading = ref(false)
const saving = ref(false)
const error = ref('')

const PLACEHOLDERS = ['source', 'peer_name', 'time', 'title', 'desc', 'link', 'image_url']
// 卡片类型 → 模板 content 骨架（用户可再编辑；{image_url} 运行时用转发原图填充）
const CARD_TYPES = {
  text: { label: '纯文本', content: '{desc}' },
  heading: { label: '标题+正文', content: '# {title}\n\n{desc}' },
  media: { label: '图文', content: '![封面]({image_url})\n\n# {title}\n\n{desc}' },
  link: { label: '链接', content: '[{title}]({link})' },
  button: { label: '按钮（文本）', content: '[{title}]({link})' },
}

async function loadTemplates() {
  loading.value = true
  error.value = ''
  const d = await apiGet('templates/get')
  loading.value = false
  if (!d || d.ok === false) { error.value = (d && d.detail) || '加载模板失败'; return }
  templates.value = Array.isArray(d.templates) ? d.templates.map(normalize) : []
  markdownEnabled.value = !!d.markdown_enabled
  sanitizeBody.value = !!d.sanitize_body
  maxLen.value = d.max_message_length || 1000
}

function normalize(t) {
  const c = t.content || ''
  return {
    id: t.id || 't' + Math.random().toString(36).slice(2, 8),
    name: t.name || '模板',
    content: c,
    markdown: t.markdown !== false,
    for_media: !!t.for_media,
    cardType: guessCardType(c),
    previewUrl: '',
  }
}

function guessCardType(c) {
  if (c.includes('{image_url}')) return 'media'
  if (c.startsWith('# ')) return 'heading'
  if (c.includes(']({link})') || c.includes(']({link)')) return 'link'
  return 'text'
}

function addTemplate() {
  templates.value.push(normalize({ id: '', name: '新模板', content: CARD_TYPES.text.content, markdown: true, for_media: false }))
}

function removeTemplate(i) {
  templates.value.splice(i, 1)
}

// 切换卡片类型：用对应骨架填充 content（覆盖，用户可再改）
function setCardType(t, type) {
  t.cardType = type
  t.content = CARD_TYPES[type].content
}

function insertPlaceholder(t, key) {
  const tok = '{' + key + '}'
  if (t.content.includes(tok)) return
  t.content = (t.content ? t.content + '\n' : '') + tok
}

function onFile(t, ev) {
  const f = ev.target.files && ev.target.files[0]
  if (!f) return
  const r = new FileReader()
  r.onload = () => { t.previewUrl = String(r.result || '') }
  r.readAsDataURL(f)
  ev.target.value = ''
}

async function saveTemplates() {
  saving.value = true
  error.value = ''
  const payload = templates.value.map(t => ({
    id: t.id, name: t.name, content: t.content,
    markdown: !!t.markdown, for_media: !!t.for_media,
  }))
  const d = await apiPostBody('templates/set', { templates: payload })
  saving.value = false
  if (!d || d.ok === false) { error.value = (d && d.detail) || '保存失败'; toast(error.value); return }
  toast(d.detail || '已保存')
}

// 预览：转义 HTML 后做最小 Markdown 渲染（仅预览；QQ 实际渲染以收到为准）
function esc(s) { return String(s || '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])) }
function renderMd(s) {
  let h = esc(s)
  h = h.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" style="max-width:100%;border-radius:6px;display:block">')
  h = h.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
  h = h.replace(/^# (.+)$/gm, '<h3 style="margin:4px 0">$1</h3>')
  h = h.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')
  h = h.replace(/`(.+?)`/g, '<code>$1</code>')
  h = h.replace(/\n/g, '<br>')
  return h
}

onMounted(loadTemplates)
</script>

<template>
  <section>
    <div class="bar" style="margin-bottom:10px">
      <div style="font-weight:600">推送模板</div>
      <button class="mini" :disabled="loading" @click="loadTemplates">↻ 刷新</button>
      <button class="mini" @click="addTemplate">＋ 添加模板</button>
      <button class="mini" :disabled="saving" style="background:var(--acc,#3b82f6);color:#fff" @click="saveTemplates">
        {{ saving ? '保存中…' : '保存' }}
      </button>
      <span class="muted">Markdown 通道: {{ markdownEnabled ? '开' : '关' }} · 正文净化: {{ sanitizeBody ? '开' : '关' }}</span>
    </div>

    <div v-if="error" class="card" style="padding:10px;margin-bottom:10px;color:#ef4444;border:1px solid #ef4444">
      {{ error }}
    </div>
    <div v-if="loading" class="card muted" style="padding:16px;text-align:center">加载中…</div>

    <!-- 模板卡列表 -->
    <div v-for="(t, i) in templates" :key="t.id" class="card" style="padding:14px;margin-bottom:12px">
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
        <input v-model="t.name" class="fr-search" style="flex:1;min-width:160px" placeholder="模板名称">
        <select v-model="t.cardType" class="fr-search" style="width:auto" @change="setCardType(t, t.cardType)">
          <option v-for="(v, k) in CARD_TYPES" :key="k" :value="k">{{ v.label }}</option>
        </select>
        <label class="muted" style="font-size:12px"><input type="checkbox" v-model="t.markdown"> Markdown</label>
        <label class="muted" style="font-size:12px"><input type="checkbox" v-model="t.for_media"> 媒体链</label>
        <button class="mini" style="color:#ef4444" @click="removeTemplate(i)">删除</button>
      </div>

      <div style="display:flex;gap:12px;margin-top:10px;flex-wrap:wrap">
        <div style="flex:2;min-width:260px">
          <textarea v-model="t.content" rows="5" class="fr-search" style="width:100%;font-family:monospace"
            placeholder="模板内容：一段 Markdown/纯文本，占位符见下方"></textarea>
          <div class="muted" style="margin-top:6px;font-size:12px">
            占位符:
            <button v-for="p in PLACEHOLDERS" :key="p" class="mini" style="margin:2px" @click="insertPlaceholder(t, p)">{{ '{' + p + '}' }}</button>
          </div>
          <div class="muted" style="margin-top:4px;font-size:12px">长度上限 {{ maxLen }}；<code>&#123;&#123;</code>/<code>&#125;&#125;</code> 为转义字面量</div>
        </div>

        <div style="flex:1;min-width:180px">
          <div class="muted" style="font-size:12px;margin-bottom:4px">封面预览（本地图仅预览，运行时用 {{ '{image_url}' }} 原图填充）</div>
          <img v-if="t.previewUrl" :src="t.previewUrl" alt="预览" style="max-width:120px;border-radius:6px;display:block">
          <input type="file" accept="image/*" style="font-size:12px;margin-top:4px" @change="onFile(t, $event)">
          <div class="muted" style="font-size:11px;margin-top:4px">实际图片以转发消息原图为准</div>
        </div>

        <!-- 手机预览 -->
        <div style="flex:1;min-width:220px">
          <div class="muted" style="font-size:12px;margin-bottom:4px">手机预览（Web 渲染，与 QQ 实际渲染有差异）</div>
          <div class="card" style="padding:10px;border:1px solid #ddd;background:#fafafa">
            <div v-html="renderMd(t.content)" style="font-size:13px;line-height:1.5;color:#111"></div>
          </div>
          <div class="muted" style="font-size:11px;margin-top:4px">以实际收到为准</div>
        </div>
      </div>
    </div>

    <div v-if="!loading && !templates.length" class="card" style="padding:16px;text-align:center">
      <span class="muted">暂无模板，点「添加模板」创建；保存后转发消息头即用模板渲染</span>
    </div>
  </section>
</template>
