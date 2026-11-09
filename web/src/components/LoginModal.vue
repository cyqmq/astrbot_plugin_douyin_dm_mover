<script setup>
import { computed } from 'vue'
import { store, apiGet, apiPost, apiPostBody, toast } from '../composables/store.js'
import { refreshAll } from '../composables/actions.js'

const isLoggedIn = computed(() => store.authState === 'ok')
const title = computed(() => isLoggedIn.value ? '账号信息' : '扫码登录')
const qrDetail = computed(() => isLoggedIn.value ? (store.authUid ? ('uid ' + store.authUid) : '已连接，正常搬运转发') : store.qrDetail)

async function refreshQr() {
  const d = await apiGet('qrcode')
  store.qrDetail = d.detail || ''
  store.qr = d.qr || ''
}
async function onRefresh() { const d = await apiPost('login'); toast(d.detail || '已触发'); await refreshQr() }
async function onLogout() { const d = await apiPost('logout'); toast(d.detail || '已登出'); await refreshAll() }
async function onReload() { toast('正在重载插件 …'); const d = await apiPost('reload'); toast(d.detail || (d.ok ? '重载中' : '重载失败')) }
async function onMfa() {
  const code = store.mfaCode.trim()
  if (!code) { toast('请输入验证码'); return }
  const d = await apiPostBody('mfa', { code }); toast(d.detail || (d.ok ? '已提交' : '提交失败')); store.mfaCode = ''
}
</script>

<template>
  <div class="modal-mask" :class="{ open: store.modalOpen }" @click.self="store.modalOpen = false">
    <div class="modal">
      <button class="modal-x" title="关闭" @click="store.modalOpen = false">×</button>
      <h2>{{ title }}</h2>
      <div class="modal-body">
        <div id="mQr">
          <div v-if="isLoggedIn" class="ph" style="border-style:solid">已登录</div>
          <img v-else-if="store.qr" :src="store.qr" alt="登录二维码">
          <div v-else class="ph">{{ store.qrDetail || '暂无二维码' }}</div>
        </div>
        <div class="modal-actions">
          <button v-if="!isLoggedIn" class="primary" @click="onRefresh">刷新二维码</button>
          <div class="note">{{ qrDetail }}</div>
          <button @click="onReload">重载插件</button>
          <button class="danger" @click="onLogout">登出</button>
        </div>
      </div>
      <div class="modal-foot">
        <input v-model="store.mfaCode" placeholder="短信验证码" style="flex:1" @keydown.enter="onMfa">
        <button @click="onMfa">提交</button>
      </div>
    </div>
  </div>
</template>
