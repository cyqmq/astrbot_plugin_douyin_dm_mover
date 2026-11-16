<script setup>
import { computed } from 'vue'
import { renderBlockToHtml } from '../cards/renderBlocks.js'

const props = defineProps({ block: Object, disabled: Boolean })
const html = computed(() => renderBlockToHtml(props.block))
</script>
<template>
  <div class="block-text" :class="{ disabled }" v-html="html" />
</template>
