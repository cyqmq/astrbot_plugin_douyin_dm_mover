<script setup>
defineProps({ block: Object, disabled: Boolean })
</script>
<template>
  <div class="block-divider" :class="{ disabled }">
    <hr />
  </div>
</template>

<style scoped>
.block-divider hr {
  border: none;
  border-top: 1px solid var(--border);
  margin: 6px 0;
}
</style>
