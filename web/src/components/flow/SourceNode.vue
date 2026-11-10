<script setup>
import { Handle, Position } from '@vue-flow/core'
import { addSender, scheduleLiveSave } from '../../composables/actions.js'

const props = defineProps({ data: { type: Object, required: true } })
const d = props.data

function setNick(e) { if (d.source) { d.source.nickname = e.target.value; scheduleLiveSave() } }
function setUid(e) { if (d.source) { d.source.uid = e.target.value.trim(); scheduleLiveSave() } }
</script>

<template>
  <div class="vf-src">
    <template v-if="d.custom && d.source">
      <input :value="d.source.nickname" placeholder="昵称" class="nodrag src-nick" @change="setNick($event)">
      <input :value="d.source.uid" placeholder="uid" class="nodrag src-uid" @change="setUid($event)">
      <button class="mini danger nodrag" title="移除该来源" @click="d.del(d.source)">×</button>
    </template>
    <template v-else>
      <img v-if="d.avatar" :src="d.avatar" class="src-avatar" alt="">
      <span v-else class="src-avatar src-avatar-ph">{{ (d.name || '源').charAt(0) }}</span>
      <div style="min-width:0;flex:1">
        <div class="sc-name">{{ (d.name || '抖音来源').slice(0, 16) }}</div>
        <div class="sc-sub">{{ (d.sub || '抖音私信').slice(0, 30) }}</div>
      </div>
      <div class="sender-actions" v-if="d.uid">
        <button class="mini" @click="addSender('senders_whitelist', d.uid)">+白</button>
        <button class="mini" @click="addSender('senders_blacklist', d.uid)">+黑</button>
      </div>
    </template>
    <Handle type="source" :position="Position.Right" />
  </div>
</template>
