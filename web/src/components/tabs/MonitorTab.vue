<script setup>
import { store, typeName, fmtTs } from '../../composables/store.js'
import { addSender } from '../../composables/actions.js'
</script>

<template>
  <section>
    <div class="grid2">
      <div class="card">
        <h2>发石者明细 <span class="muted">（点「+白/+黑」加入名单）</span></h2>
        <ul class="list">
          <li v-for="s in store.senders" :key="s.peer_id + s.ts" class="clickable" :title="'peer_id=' + s.peer_id">
            {{ fmtTs(s.ts) }} · {{ s.peer_name || ('用户 ' + s.peer_id) }}
            <span class="muted">[{{ typeName(s.type) }}]</span>
            <br v-if="s.text"><span class="muted">{{ s.text }}</span>
            <div class="sender-actions">
              <button class="mini" @click="addSender('senders_whitelist', s.peer_id)">+白</button>
              <button class="mini" @click="addSender('senders_blacklist', s.peer_id)">+黑</button>
            </div>
          </li>
          <li v-if="!store.senders.length" class="empty">暂无</li>
        </ul>
      </div>
      <div class="card">
        <h2>搬运记录明细</h2>
        <ul class="list">
          <li v-for="x in store.records" :key="x.ts + x.peer" class="clickable" :title="x.error || ''">
            {{ fmtTs(x.ts) }} · [{{ x.type }}] {{ x.peer }} → {{ x.target }}
            <span class="muted">
              <span v-if="x.ok" style="color:var(--ok)">成功</span>
              <span v-else style="color:var(--bad)">失败 {{ x.error }}</span>
            </span>
          </li>
          <li v-if="!store.records.length" class="empty">暂无</li>
        </ul>
      </div>
    </div>
  </section>
</template>
