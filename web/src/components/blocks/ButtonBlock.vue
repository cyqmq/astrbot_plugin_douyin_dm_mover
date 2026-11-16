<script setup>
defineProps({ block: Object, disabled: Boolean })
</script>
<template>
  <div class="block-button-wrap" :class="{ disabled }">
    <button class="block-button" type="button" disabled>打开视频</button>
  </div>
</template>

<style scoped>
.block-button {
  border: none;
  background: #2E7CF6;
  color: #fff;
  border-radius: 8px;
  padding: 7px 16px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  opacity: 0.85;
}
</style>
