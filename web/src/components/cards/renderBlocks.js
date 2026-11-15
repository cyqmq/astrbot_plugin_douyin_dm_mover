// 前端渲染器：blocks JSON → 消息内容 → 占位符 → 最小 Markdown HTML（预览用）
// 与后端 _render_blocks 按同一 Schema 契约实现，保证预览与转发同源
// 发布时后端用同一规则做最终渲染与校验

import { placeholderToken } from './blockTypes.js'

// 渲染积木序列为消息内容（与后端 _render_blocks 同规则：media 用 \n\n 连接、空块跳过）
export function renderBlocks(blocks, ctx = {}, markdown = true) {
  if (!Array.isArray(blocks)) return ''
  const parts = []
  for (const b of blocks) {
    if (!b || !b.type) continue
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
        const text = d.text || ''
        const url = d.url || ''
        s = markdown ? `[${text}](${url})` : text
        break
      }
      case 'image': {
        // 图片积木：markdown 渲染 ![alt](image_url)，位置由积木决定；plain 输出 alt
        const alt = d.alt || '{title}'
        s = markdown ? `![${alt}]({image_url})` : alt
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
    if (s) parts.push(s)
  }
  return parts.join('\n\n')
}

// 占位符替换（预览用模拟值；转发时后端用真实上下文）
export function fillPlaceholders(content, ctx = {}) {
  return content
    .replace(/\{source\}/g, ctx.source || '抖音')
    .replace(/\{peer_name\}/g, ctx.peer_name || '示例用户')
    .replace(/\{time\}/g, ctx.time || '14:32')
    .replace(/\{title\}/g, ctx.title || '示例标题')
    .replace(/\{desc\}/g, ctx.desc || '示例描述')
    .replace(/\{link\}/g, ctx.link || 'https://example.com')
    .replace(/\{image_url\}/g, ctx.image_url || 'https://example.com/cover.jpg')
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
