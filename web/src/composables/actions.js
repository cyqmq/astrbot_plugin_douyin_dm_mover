import { store, apiGet, apiPost, apiPostBody, toast, typeName, esc, fmtTs } from './store.js'

export async function refreshStatus() {
  const d = await apiGet('status')
  store.status = d
  store.authState = d.auth_state || 'idle'
  store.authUid = d.self_uid || ''
}

export async function refreshSenders() {
  const d = await apiGet('senders')
  store.senders = d.senders || []
}

export async function refreshRecords() {
  const d = await apiGet('records')
  store.records = d.records || []
}

export async function refreshQr() {
  const d = await apiGet('qrcode')
  store.qrDetail = d.detail || ''
  store.qr = d.qr || ''
}

export async function refreshLogs() {
  const d = await apiGet('logs')
  store.logs = d.logs || []
}

export async function refreshAll() {
  await Promise.all([refreshStatus(), refreshSenders(), refreshRecords(), refreshQr(), refreshLogs()])
}

export async function loadConfig() {
  const d = await apiGet('config/get')
  if (!d.config) return
  store.cfg = d.config
  store.schema = d.schema || {}
  store.routes = JSON.parse(JSON.stringify(d.config.routes || []))
  store.customSources = (d.config.custom_sources || []).map((s, i) => ({
    id: s.id || ('srcm' + (i + 1)), uid: s.uid || '', nickname: s.nickname || '', pos: s.pos || null
  }))
  store.customTargets = JSON.parse(JSON.stringify(d.config.custom_targets || []))
  store.simpleTargets = JSON.parse(JSON.stringify(d.config.simple_targets || []))
  store.advancedTargets = !!d.config.advanced_target_cards
  store.floatLog.enabled = !!d.config.float_log_enabled
}

export async function saveConfig(cfg, opts) {
  const d = await apiPostBody('config/set', { config: cfg, no_reload: !!(opts && opts.no_reload) })
  if (!(opts && opts.silent)) toast(d.detail || (d.ok ? '已保存' : '保存失败'))
}

// 实时静默保存：只落盘不重载（防高频 reload）；供路由页自动保存用
let liveTimer = null
export function scheduleLiveSave(delay = 1200) {
  clearTimeout(liveTimer)
  liveTimer = setTimeout(async () => {
    await saveConfig({ routes: JSON.parse(JSON.stringify(store.routes)),
      custom_sources: JSON.parse(JSON.stringify(store.customSources)),
      custom_targets: JSON.parse(JSON.stringify(store.customTargets)),
      simple_targets: JSON.parse(JSON.stringify(store.simpleTargets)),
      advanced_target_cards: !!store.advancedTargets }, { no_reload: true, silent: true })
    store.liveSavedAt = new Date().toLocaleTimeString('zh-CN', { hour12: false })
  }, delay)
}

export async function addSender(key, uid) {
  const cur = String(store.cfg[key] || '').split(',').map(s => s.trim()).filter(Boolean)
  if (cur.includes(uid)) { toast('已在名单中'); return }
  cur.push(uid)
  await saveConfig({ [key]: cur.join(',') })
  await loadConfig()
}

export async function loadFriends(refresh) {
  store.friendsLoading = true
  store.friendsDetail = ''
  const d = await apiGet(refresh ? 'friends?refresh=1' : 'friends')
  store.friendsLoading = false
  if (d.detail) store.friendsDetail = d.detail
  store.friends = d.friends || []
}

export async function loadGroups() {
  store.groupsLoading = true
  store.groupsDetail = ''
  const d = await apiGet('groups')
  store.groupsLoading = false
  if (d.detail) store.groupsDetail = d.detail
  store.groups = d.groups || []
}

export function pill(k, cls, v) {
  return `<span class="pill"><span class="dot dot-${cls}"></span>${esc(k)}：${v}</span>`
}
export function stat(k, cls, v) {
  return `<div class="stat"><div class="k"><span class="dot dot-${cls}"></span>${esc(k)}</div><div class="v">${v}</div></div>`
}
export function listItems(arr, renderer) { return arr.length ? arr.map(renderer).join('') : '<li class="empty">暂无</li>' }
