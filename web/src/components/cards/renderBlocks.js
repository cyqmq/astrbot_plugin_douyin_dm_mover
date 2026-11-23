// 前端渲染器：blocks JSON → 消息内容 → 占位符 → 最小 Markdown HTML（预览用）
// 与后端 _render_blocks 按同一 Schema 契约实现，保证预览与转发同源
// 发布时后端用同一规则做最终渲染与校验

import { placeholderToken } from './blockTypes.js'

// 按钮预设色（与后端 model.BUTTON_STYLES 一致；仅白名单可下发，任意 hex 无法被 AstrBot 渲染）
export const BUTTON_STYLES = ['primary', 'default', 'success', 'danger']

// 渲染积木序列为消息内容（与后端 _render_blocks 同规则：media 用 \n\n 连接、空块跳过）
export function renderBlocks(blocks, ctx = {}, markdown = true) {
  if (!Array.isArray(blocks)) return ''
  return (blocks || [])
    .map((b) => renderSingleBlock(b, ctx, markdown))
    .filter((s) => s)
    .join('\n\n')
}

// 单块渲染（原 switch 原样搬入，不改变任何 case 行为）
export function renderSingleBlock(b, ctx = {}, markdown = true) {
  if (!b || !b.type) return ''
  // 扁平卡（测试页几何装配）：无 data 且有 kind → 按 kind 渲染（与后端 _render_flat_block 对齐）
  if (!b.data && b.kind) return renderFlatSingle(b, markdown)
  const d = b.data || {}
  let s = ''
  switch (b.type) {
    case 'text':
      s = d.text || ''
      break
    case 'heading': {
      const title = d.title || ''
      const body = d.body || ''
      const head = markdown ? `# ${title}` : title
      s = body ? `${head}\n${body}` : head
      break
    }
    case 'media': {
      const img = d.image || ''
      const title = d.title || ''
      const desc = d.desc || ''
      if (markdown && img) s += `![${title}](${img})`
      if (title) s += (s ? '\n\n' : '') + (markdown ? `# ${title}` : title)
      if (desc) s += (s ? '\n\n' : '') + desc
      break
    }
    case 'button': {
      // 按钮不可配置：恒渲染 [[button:打开视频|{link}]]；plain 只出文案
      s = markdown ? '[[button:打开视频|{link}]]' : '打开视频'
      break
    }
    case 'image': {
      // 图片积木：markdown 渲染 ![alt](image_url)，位置由积木决定；plain 输出 alt
      const alt = d.alt || '{title}'
      s = markdown ? `![${alt}]({image_url})` : alt
      break
    }
    case 'video': {
      // 视频积木：markdown 渲染 [[video:{video_url}]]（_chain_from_markdown 解析成 Video 节点）；plain 输出 alt
      const alt = d.alt || '视频'
      s = markdown ? `[[video:{video_url}]]` : alt
      break
    }
    case 'divider':
      s = markdown ? '***' : '—'
      break
    default:
      // 占位符积木：输出其 token（fillPlaceholders 随后替换为模拟/真实值）
      s = placeholderToken(b.type) || ''
      break
  }
  return s
}

// 扁平卡单块渲染（与后端 _render_flat_block 逐 kind 对齐）
function renderFlatSingle(b, markdown = true) {
  const kind = b.kind || ''
  const label = String(b.label || '').trim()
  const url = String(b.url || '').trim()
  if (kind === 'text' || kind === 'desc') return label
  if (kind === 'title') return markdown ? `# ${label}` : label
  if (kind === 'image') {           // 转发图片：说明(label) 可选，图源 {image_url}
    const alt = label || '{title}'
    return markdown ? `![${alt}]({image_url})` : alt
  }
  if (kind === 'image_url') {       // 自定义地址图片
    const alt = label || '图片'
    return markdown ? `![${alt}](${url})` : alt
  }
  if (kind === 'video') {           // 转发视频：视频源 {video_url}
    const alt = label || '视频'
    return markdown ? '[[video:{video_url}]]' : alt
  }
  if (kind === 'video_url') {       // 自定义地址视频
    const alt = label || '视频'
    return markdown ? `[[video:${url}]]` : alt
  }
  if (kind === 'gif') {
    const alt = label || '动图'
    return markdown ? `![${alt}](${url})` : alt
  }
  if (kind === 'button' || kind === 'link') {   // 自定义文字+跳转链接（url 空回退 {link}）；style 预设色（非法回退 primary）
    const btn = label || '按钮'
    const btnUrl = url || '{link}'
    const style = (BUTTON_STYLES.includes(b.style) ? b.style : 'primary')
    return markdown ? `[[button:${btn}|${btnUrl}|${style}]]` : btn
  }
  if (kind === 'divider') return markdown ? '***' : '—'
  if (kind === 'gap') return ''    // 间距：纵向占位，无文本输出
  return label
}

// 占位符替换：ctx 有值用真实值；ctx 无该键（undefined）保留 {token} 原样。
// 诚实化：预览/画布/导出不再显示模拟值，避免「预览 ≠ 转发」失真（转发时后端用真实上下文替换）。
export function fillPlaceholders(content, ctx = {}) {
  const TOKENS = ['source', 'peer_name', 'time', 'title', 'desc', 'link', 'image_url', 'video_url']
  return TOKENS.reduce((acc, k) => {
    const v = ctx[k]
    return acc.split(`{${k}}`).join(v !== undefined ? String(v) : `{${k}}`)
  }, content)
}

// HTML 转义
function esc(s) {
  return String(s || '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]))
}

// 最小 Markdown → HTML（预览用，规则与后端渲染一致）
export function mdToHtml(s) {
  let h = esc(s)
  // 视频/按钮标记 → 组件 HTML（esc 后替换，标记内 url 已转义 &amp; 正确进 href）
  h = h.replace(/\[\[video:[^\])]*\]\]/g, '<div class="video-chip"><span class="vc-play">▶</span> 视频</div>')
  h = h.replace(/\[\[button:([^\]|]*)\|([^\]|]*)(?:\|([^\]|]*))?\]\]/g, (_, label, url, style) => {
    const s = BUTTON_STYLES.includes(style) ? style : 'primary'
    return `<a class="btn btn--${s}" href="${url}">${label}</a>`
  })
  h = h.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" style="max-width:100%;border-radius:6px;display:block">')
  h = h.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
  h = h.replace(/^# (.+)$/gm, '<h3 style="margin:4px 0">$1</h3>')
  h = h.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')
  h = h.replace(/`(.+?)`/g, '<code>$1</code>')
  h = h.replace(/\n/g, '<br>')
  return h
}

// 完整预览：blocks → 内容 → 占位符 → HTML
export function renderPreview(blocks, ctx = {}) {
  const content = renderBlocks(blocks, ctx)
  const filled = fillPlaceholders(content, ctx)
  return mdToHtml(filled)
}

// 单块 → 预览 HTML，与 renderPreview 中单块走同一条 fillPlaceholders → mdToHtml
export function renderBlockToHtml(block, ctx = {}) {
  const md = renderSingleBlock(block, ctx, true)
  return mdToHtml(fillPlaceholders(md, ctx))
}
