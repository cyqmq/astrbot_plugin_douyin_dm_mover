<script setup>
import { Handle, Position } from '@vue-flow/core'
import { store } from '../../composables/store.js'
import { addSender } from '../../composables/actions.js'

const props = defineProps({ data: { type: Object, required: true } })
const isFriend = store.sourceMode === 'friends'
const name = props.data.name || '抖音来源'
const sub = props.data.sub || '抖音私信'
const avatar = props.data.avatar || ''
const uid = props.data.uid || ''
</script>

<template>
  <div class="vf-src">
    <img v-if="avatar" :src="avatar" class="src-avatar" alt="">
    <span v-else class="src-avatar src-avatar-ph">{{ name.charAt(0) }}</span>
    <div style="min-width:0;flex:1">
      <div class="sc-name">{{ name.slice(0, 16) }}</div>
      <div class="sc-sub">{{ sub.slice(0, 30) }}</div>
    </div>
    <div class="sender-actions" v-if="uid">
      <button class="mini" @click="addSender('senders_whitelist', uid)">+白</button>
      <button class="mini" @click="addSender('senders_blacklist', uid)">+黑</button>
    </div>
    <button v-if="data.custom && data.del" class="mini danger" title="移除该来源" @click="data.del(uid)">×</button>
    <Handle type="source" :position="Position.Right" />
  </div>
</template>
