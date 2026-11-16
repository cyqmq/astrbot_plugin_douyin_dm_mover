<script setup>
import { computed } from 'vue'
import { renderBlockToHtml } from '../cards/renderBlocks.js'

const props = defineProps({ block: Object, disabled: Boolean })
const html = computed(() => renderBlockToHtml(props.block))
</script>
<template>
  <div class="block-image" :class="{ disabled }" v-html="html" />
</template>

<style scoped>
.block-image :deep(img) {
  max-width: 100%;
  border-radius: 6px;
  display: block;
  margin: 6px 0;
}
</style>
