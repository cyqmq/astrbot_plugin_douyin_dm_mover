import TextBlock from './TextBlock.vue'
import ImageBlock from './ImageBlock.vue'
import ButtonBlock from './ButtonBlock.vue'
import DividerBlock from './DividerBlock.vue'
import PlaceholderBlock from './PlaceholderBlock.vue'
import { PLACEHOLDERS } from '../cards/blockTypes.js'

export const componentMap = {
  // 7 个占位符积木（source/peer_name/time/title/desc/link/image_url）都复用 PlaceholderBlock
  ...Object.fromEntries(Object.keys(PLACEHOLDERS).map((k) => [k, PlaceholderBlock])),
  text: TextBlock,
  image: ImageBlock,
  button: ButtonBlock,
  divider: DividerBlock,
}

// 画布类型：占位符 + 结构积木（不含 video，视频不进画布 D1）
export const CANVAS_TYPES = Object.keys(componentMap)
