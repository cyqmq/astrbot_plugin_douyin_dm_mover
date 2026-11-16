import TextBlock from './TextBlock.vue'
import ImageBlock from './ImageBlock.vue'
import ButtonBlock from './ButtonBlock.vue'
import DividerBlock from './DividerBlock.vue'

export const componentMap = {
  text: TextBlock,
  image: ImageBlock,
  button: ButtonBlock,
  divider: DividerBlock,
}

// 用于过滤视频/旧类型，画布只认这四类
export const CANVAS_TYPES = Object.keys(componentMap)
