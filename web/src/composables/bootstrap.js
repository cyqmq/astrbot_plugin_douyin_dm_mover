import { store } from './store.js'
import { refreshAll, loadConfig } from './actions.js'

const V = window.AstrBotPluginView || window.AstrBotPluginPage

export async function bootstrap() {
  if (!V) return
  await V.ready()
  store.ready = true
  await Promise.all([refreshAll(), loadConfig()])
  let tick = 0
  setInterval(async () => {
    if (!store.auto) return
    const sec = Math.max(2, parseInt(store.autoSec, 10) || 5)
    if (++tick >= sec) { tick = 0; await refreshAll() }
  }, 1000)
}
