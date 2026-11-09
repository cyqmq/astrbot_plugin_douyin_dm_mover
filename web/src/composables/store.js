import { reactive, computed } from 'vue'

// ---- 桥接 SDK ----
const V = window.AstrBotPluginView || window.AstrBotPluginPage

export const toastMsg = reactive({ text: '', on: false })

export function toast(msg) {
  toastMsg.text = msg || ''
  toastMsg.on = true
  setTimeout(() => { toastMsg.on = false }, 2400)
}

export async function apiGet(ep) {
  try { return await V.apiGet(ep) } catch (e) { toast('请求失败: ' + e); return {} }
}
export async function apiPost(ep) {
  try { return await V.apiPost(ep, {}) } catch (e) { toast('请求失败: ' + e); return {} }
}
export async function apiPostBody(ep, body) {
  try { return await V.apiPost(ep, body) } catch (e) { toast('请求失败: ' + e); return {} }
}

// ---- 常量 ----
export const TYPE_NAMES = { text: '文本', video_card: '视频卡片', image: '图片', emoji: '表情', voice: '语音', other: '其他' }
export const typeName = t => TYPE_NAMES[t] || t || '其他'
export const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]))
export const fmtTs = ts => ts ? new Date(ts * 1000).toLocaleString('zh-CN', { hour12: false }) : '—'

export const ROUTE_TYPES = [['text', '文本'], ['video_card', '视频卡片'], ['image', '图片'], ['emoji', '表情'], ['voice', '语音'], ['other', '其他']]

export const TITLES = {
  overview: ['总览', '登录态与最近搬运概览'],
  routes: ['路由', '转发路由表'],
  policy: ['策略', '限流 / 去重 / 过滤 / 告警'],
  monitor: ['监控', '发石者与搬运明细'],
  logs: ['日志', '运行日志'],
  settings: ['设置', '登录 / 转发 / 来源配置']
}

export const LABELS = {
  douyin_cookies: '登录 Cookie', douyin_web_protect: 'Web 防护', douyin_keys: '密钥',
  self_uid: '本机 UID', device_id: '设备 ID', gateway_mode: '网关模式', login_backend: '登录后端',
  mfa_mode: 'MFA 模式', login_timeout: '登录超时(秒)', login_mfa_timeout: 'MFA 超时(秒)',
  auth_watchdog_minutes: '看门狗(分)', auth_failure_close_codes: '失效关闭码', auth_failure_keywords: '失效关键词',
  max_message_length: '最大消息长度', include_link: '附带链接', header_template: '转发模板',
  default_target_group: '默认目标群', rate_limit_global_enabled: '全局限流', rate_limit_global_max_per_min: '全局限流(次/分)',
  rate_limit_sender_enabled: '单人限流', rate_limit_sender_max_per_min: '单人限流(次/分)',
  dedup_enabled: '去重', dedup_window_seconds: '去重窗口(秒)', retry_enabled: '失败重试',
  retry_interval_seconds: '重试间隔(秒)', senders_whitelist: '发送者白名单', senders_blacklist: '发送者黑名单',
  keyword_filters: '关键词过滤', alert_target: '告警目标', alert_only_once: '仅告警一次',
  qq_adapter_id: 'QQ 适配器', sources: '来源配置', routes: '路由表'
}
export const lbl = k => LABELS[k] || k

export const SELECTS = {
  login_backend: [['alemonjs', '@alemonjs/douyin（纯 Python）'], ['alemonjs_node', 'Node 桥接（可选回退）'], ['douyin_spider', '旧 vendored']],
  gateway_mode: [['inprocess', '进程内（默认）'], ['subprocess', '子进程隔离']],
  mfa_mode: [['auto_sms', '自动短信'], ['manual_command', '手动指令'], ['alert_wait', '仅告警等 App']],
  qq_adapter_id: [['aiocqhttp', 'NapCat (aiocqhttp)'], ['qq_official', 'QQ 官方机器人'], ['telegram', 'Telegram'], ['wecom', '企业微信']]
}

export const UMO_KEYS = ['default_target_group', 'alert_target']
export const SENDER_KEYS = ['senders_whitelist', 'senders_blacklist']
export const JSON_KEYS = ['sources', 'keyword_filters']

export const POLICY_KEYS = ['rate_limit_global_enabled', 'rate_limit_global_max_per_min', 'rate_limit_sender_enabled',
  'rate_limit_sender_max_per_min', 'dedup_enabled', 'dedup_window_seconds', 'retry_enabled',
  'retry_interval_seconds', 'senders_whitelist', 'senders_blacklist', 'keyword_filters',
  'alert_target', 'alert_only_once', 'qq_adapter_id']
export const SETTINGS_KEYS = ['douyin_cookies', 'douyin_web_protect', 'douyin_keys', 'self_uid', 'device_id',
  'gateway_mode', 'login_backend', 'mfa_mode', 'login_timeout', 'login_mfa_timeout',
  'auth_watchdog_minutes', 'auth_failure_close_codes', 'auth_failure_keywords',
  'max_message_length', 'include_link', 'header_template', 'default_target_group', 'sources']

export const SETTINGS_GROUPS = [
  ['登录', ['douyin_cookies', 'douyin_web_protect', 'douyin_keys', 'self_uid', 'device_id', 'login_backend', 'mfa_mode', 'login_timeout', 'login_mfa_timeout', 'auth_watchdog_minutes', 'auth_failure_close_codes', 'auth_failure_keywords']],
  ['转发', ['max_message_length', 'include_link', 'header_template', 'default_target_group', 'sources']]
]
export const POLICY_GROUPS = [
  ['限流', ['rate_limit_global_enabled', 'rate_limit_global_max_per_min', 'rate_limit_sender_enabled', 'rate_limit_sender_max_per_min']],
  ['去重', ['dedup_enabled', 'dedup_window_seconds']],
  ['重试', ['retry_enabled', 'retry_interval_seconds']],
  ['过滤', ['senders_whitelist', 'senders_blacklist', 'keyword_filters']],
  ['告警与适配', ['alert_target', 'alert_only_once', 'qq_adapter_id']]
]

export const ST_MAP = {
  ok: ['ok', '已登录', '已连接'],
  expired: ['bad', '登录失效', '点击重新登录'],
  unknown: ['warn', '未知', '状态未知'],
  idle: ['idle', '未登录', '点击扫码登录']
}

export const umoSplit = val => {
  const m = String(val || '').match(/^([^:]*):GroupMessage:(.*)$/)
  return { adapter: m ? m[1] : 'aiocqhttp', group: m ? m[2] : (String(val || '')) }
}

// ---- 全局单例状态 ----
export const store = reactive({
  ready: false,
  isMobile: false,
  tab: 'overview',
  authState: 'idle',
  authUid: '',
  profile: { uid: '', nickname: '', avatar: '' },
  status: {},
  senders: [],
  records: [],
  logs: [],
  qr: '',
  qrDetail: '',
  mfaCode: '',
  modalOpen: false,
  friends: [],
  friendsDetail: '',
  friendsLoading: false,
  sourceMode: 'senders',
  cfg: {},
  schema: {},
  routes: [],
  auto: true,
  autoSec: 5
})

export const sendersTop = computed(() => store.senders.slice(0, 6))

export function senderVals(wrap) {
  return Array.from(wrap.querySelectorAll('.chip')).map(c => c.textContent.replace('×', '').trim()).filter(Boolean)
}
