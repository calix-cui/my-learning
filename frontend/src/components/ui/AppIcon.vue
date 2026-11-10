<script setup lang="ts">
/**
 * 图标：内联 SVG，不引额外依赖。
 * 统一 24 的 viewBox、currentColor 描边，尺寸由 size 控制。
 */
type IconName =
  | 'plus'
  | 'more'
  | 'share'
  | 'send'
  | 'paperclip'
  | 'settings'
  | 'logout'
  | 'edit'
  | 'trash'
  | 'sparkle'
  | 'close'

const props = withDefaults(defineProps<{ name: IconName; size?: number }>(), { size: 18 })

const paths: Record<IconName, string[]> = {
  plus: ['M12 5v14', 'M5 12h14'],
  more: ['M6 12h.01', 'M12 12h.01', 'M18 12h.01'],
  share: ['M4 12v7a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7', 'M12 15V3', 'M8 7l4-4 4 4'],
  send: ['M12 20V5', 'M6 11l6-6 6 6'],
  paperclip: [
    'M20 11.5 12.5 19a4.5 4.5 0 0 1-6.4-6.4l7-7a3 3 0 0 1 4.3 4.3l-7 7a1.5 1.5 0 0 1-2.1-2.1l6.3-6.3',
  ],
  settings: [
    'M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z',
    'M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z',
  ],
  logout: ['M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4', 'M10 17l-5-5 5-5', 'M5 12h11'],
  edit: ['M4 20h4l10-10a2.8 2.8 0 0 0-4-4L4 16v4Z', 'M13.5 6.5l4 4'],
  trash: ['M4 7h16', 'M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2', 'M6 7l1 13h10l1-13'],
  sparkle: ['M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3Z'],
  close: ['M6 6l12 12', 'M18 6 6 18'],
}
</script>

<template>
  <svg
    :width="props.size"
    :height="props.size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.8"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    focusable="false"
  >
    <path v-for="d in paths[props.name]" :key="d" :d="d" />
  </svg>
</template>
