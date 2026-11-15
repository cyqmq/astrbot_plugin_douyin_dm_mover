// 积木类型与 Schema 契约（前后端共用，保证同源）
// 新积木库 = 占位符驱动：7 个占位符积木 + 纯文本 + 分割线
// block = { id, type, data, disabled }
// 占位符积木 data 为空（token 由 type 派生），转发时由后端 _context 替换为真实值

// 占位符 → { token, label, hint }（与后端 _ALLOWED_PLACEHOLDERS 完全一致）
export const PLACEHOLDERS = {
  source: { token: '{source}', label: '来源平台', hint: '抖音' },
  peer_name: { token: '{peer_name}', label: '对方昵称', hint: '示例用户' },
  time: { token: '{time}', label: '消息时间', hint: '14:32' },
  title: { token: '{title}', label: '卡片标题', hint: '示例标题' },
  desc: { token: '{desc}', label: '卡片描述', hint: '示例描述' },
  link: { token: '{link}', label: '视频链接', hint: 'https://example.com' },
  image_url: { token: '{image_url}', label: '封面图 URL', hint: 'https://example.com/cover.jpg' },
}

// 占位符列表（供积木库渲染）
export const PLACEHOLDER_LIST = Object.entries(PLACEHOLDERS).map(([key, v]) => ({
  key,
  ...v,
}))

// 结构积木：图片（内嵌封面图）+ 视频（内嵌原视频直链）+ 按钮（跳转链接）+ 纯文本（可含占位符）+ 分割线
export const STRUCTURAL_TYPES = ['image', 'video', 'button', 'text', 'divider']

// 积木类型：占位符 + 结构积木（旧的 heading/media/link/button 不再提供）
export const BLOCK_TYPES = {
  ...Object.fromEntries(
    Object.entries(PLACEHOLDERS).map(([key, v]) => [
      key,
      { label: v.label, token: v.token, data: {} },
    ])
  ),
  image: { label: '图片', data: { alt: '' } },
  video: { label: '视频', data: { alt: '' } },
  button: { label: '按钮', data: { text: '打开视频', url: '' } },
  text: { label: '纯文本', data: { text: '' } },
  divider: { label: '分割线', data: {} },
}

// 积木类型列表（供积木库渲染）
export const BLOCK_TYPE_LIST = Object.entries(BLOCK_TYPES).map(([key, v]) => ({
  key,
  label: v.label,
  token: v.token || null,
  data: v.data,
}))

// 类型 → 占位符 token（非占位符积木返回 null）
export function placeholderToken(type) {
  return (PLACEHOLDERS[type] && PLACEHOLDERS[type].token) || null
}

// 是否占位符积木
export function isPlaceholder(type) {
  return Boolean(PLACEHOLDERS[type])
}

// 创建积木实例（用类型默认 data 初始化，默认启用，带唯一 id）
export function createBlock(type, data = {}) {
  const t = BLOCK_TYPES[type]
  if (!t) return null
  return {
    id: 'b' + Date.now() + Math.random().toString(36).slice(2, 6),
    type,
    data: { ...t.data, ...data },
    disabled: false,
  }
}

// Schema 校验（前端预校验，后端发布时做最终校验）
// 返回 { ok, detail }
export function validateBlock(block) {
  if (!block || typeof block !== 'object') return { ok: false, detail: '积木必须是对象' }
  if (!block.type) return { ok: false, detail: '积木缺少 type' }
  if (!BLOCK_TYPES[block.type]) return { ok: false, detail: `未知积木类型: ${block.type}` }
  const t = BLOCK_TYPES[block.type]
  const data = block.data || {}
  // 校验 data 结构（非占位符类型的必填字段不能缺失；占位符/分割线 data 为空即通过）
  for (const key of Object.keys(t.data)) {
    if (!(key in data)) return { ok: false, detail: `积木「${t.label}」缺少字段: ${key}` }
  }
  if (type === 'button') {
    const label = String(data.text || '').trim()
    const url = String(data.url || '').trim()
    if (!label) return { ok: false, detail: '按钮积木缺少文案' }
    if (label.length > 10) return { ok: false, detail: '按钮文案最多 10 字' }
    // url 允许空（默认 {link} 回退）/ 占位符（{...} 转发时替换）/ http(s)
    if (url && !/^https?:\/\//.test(url) && !/^\{[^}]+\}$/.test(url)) {
      return { ok: false, detail: '按钮链接必须是 http(s) 或 {占位符}' }
    }
  }
  return { ok: true }
}

// 校验整条消息的 blocks
export function validateBlocks(blocks) {
  if (!Array.isArray(blocks)) return { ok: false, detail: 'blocks 必须是数组' }
  for (let i = 0; i < blocks.length; i++) {
    const r = validateBlock(blocks[i])
    if (!r.ok) return { ok: false, detail: `第 ${i + 1} 个积木: ${r.detail}` }
  }
  // 视频积木最多 1 个且必须在第一位或最后一位（拆两条消息，顺序决定先后）
  const vidIdx = blocks
    .map((b, i) => (b && b.type === 'video' ? i : -1))
    .filter((i) => i >= 0)
  if (vidIdx.length > 1) {
    return { ok: false, detail: '视频积木最多 1 个（拆两条消息）' }
  }
  if (vidIdx.length === 1 && vidIdx[0] !== 0 && vidIdx[0] !== blocks.length - 1) {
    return { ok: false, detail: '视频积木只能在第一位或最后一位（顺序决定两条消息先后）' }
  }
  return { ok: true }
}
