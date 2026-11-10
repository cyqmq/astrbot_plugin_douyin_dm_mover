import { store } from './store.js'
import { refreshAll, loadConfig, loadPlatforms } from './actions.js'

const V = window.AstrBotPluginView || window.AstrBotPluginPage

function trackViewport() {
  const mql = window.matchMedia('(max-width: 768px)')
  const apply = () => { store.isMobile = mql.matches }
  apply()
  mql.addEventListener('change', apply)
}

export async function bootstrap() {
  if (!V) return
  trackViewport()
  await V.ready()
  store.ready = true
  await Promise.all([refreshAll(), loadConfig()])
  loadPlatforms()
  let tick = 0
  setInterval(async () => {
    if (!store.auto) return
    const sec = Math.max(2, parseInt(store.autoSec, 10) || 5)
    if (++tick >= sec) { tick = 0; await refreshAll() }
  }, 1000)
}
