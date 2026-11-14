// 积木类型与 Schema 契约（前后端共用，保证同源）
// 积木类型固定 6 类，不可自定义新增；block = { type, data }

export const BLOCK_TYPES = {
  text: { label: '纯文本', data: { text: '' } },
  heading: { label: '标题+正文', data: { title: '', body: '' } },
  media: { label: '图文', data: { image: '', title: '', desc: '' } },
  link: { label: '链接', data: { text: '', url: '' } },
  button: { label: '按钮', data: { text: '', url: '' } },
  divider: { label: '分割线', data: {} },
}

// 积木类型列表（供积木库渲染）
export const BLOCK_TYPE_LIST = Object.entries(BLOCK_TYPES).map(([key, v]) => ({
  key,
  label: v.label,
  data: v.data,
}))

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
  // 校验 data 结构（非 divider 类型的必填字段不能缺失）
  for (const key of Object.keys(t.data)) {
    if (!(key in data)) return { ok: false, detail: `积木「${t.label}」缺少字段: ${key}` }
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
  return { ok: true }
}
