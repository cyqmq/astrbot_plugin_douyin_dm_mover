<script setup>
import TopologyFlow from '../flow/TopologyFlow.vue'
</script>

<template>
  <section>
    <div class="card">
      <h2>转发拓扑与路由编辑
        <span class="muted">来源 <strong>连接桩 →</strong> 路由 <strong>→</strong> 目标群 · 贝塞尔连线 · 卡片可编辑 · 实时保存</span>
      </h2>
      <TopologyFlow />
    </div>
  </section>
</template>
