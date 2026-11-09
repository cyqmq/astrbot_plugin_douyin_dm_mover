import { ref, onMounted, onUnmounted } from 'vue'

// 响应式 matchMedia：query 变化时更新 ref
export function useMediaQuery(query) {
  const matches = ref(false)
  let mql = null
  const onChange = () => { if (mql) matches.value = mql.matches }
  onMounted(() => {
    mql = window.matchMedia(query)
    matches.value = mql.matches
    mql.addEventListener('change', onChange)
  })
  onUnmounted(() => { if (mql) mql.removeEventListener('change', onChange) })
  return matches
}

// 手机判定：窄视口（<=768px）
export function useIsMobile() {
  return useMediaQuery('(max-width: 768px)')
}
