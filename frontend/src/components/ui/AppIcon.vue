<script setup lang="ts">
/**
 * 图标：内联 SVG，不引额外依赖。
 * 统一 24 的 viewBox、currentColor 描边，尺寸由 size 控制。
 * 路径表在 `icon-paths.ts`，工具市场要按后端给的字符串渲染图标。
 */
import { iconPaths, type IconName } from './icon-paths'

const props = withDefaults(defineProps<{ name: IconName; size?: number }>(), { size: 18 })
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
    <path v-for="d in iconPaths[props.name]" :key="d" :d="d" />
  </svg>
</template>
