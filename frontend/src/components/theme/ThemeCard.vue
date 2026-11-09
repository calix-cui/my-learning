<script setup lang="ts">
import type { ThemeDefinition, ThemeMode } from '@/theme/types'

const props = defineProps<{
  theme: ThemeDefinition
  active: boolean
  /** 预览用当前模式下的配色，避免深色界面里出现一排浅色块 */
  mode: ThemeMode
}>()

const emit = defineEmits<{ select: [id: string] }>()

/** 卡片上的小色块：底色 / 侧栏 / 强调 / 文字，一眼看出气质差异 */
const swatches = (theme: ThemeDefinition) => {
  const colors = props.mode === 'dark' ? theme.dark : theme.light
  return [colors.canvas, colors.sunken, colors.accent, colors.ink]
}
</script>

<template>
  <button
    type="button"
    class="theme-card"
    :class="{ 'is-active': props.active }"
    :aria-pressed="props.active"
    @click="emit('select', props.theme.id)"
  >
    <span class="theme-card__swatches" aria-hidden="true">
      <i v-for="color in swatches(props.theme)" :key="color" :style="{ background: color }" />
    </span>
    <span class="theme-card__head">
      <span class="theme-card__name">{{ props.theme.name }}</span>
      <span v-if="props.active" class="theme-card__badge">使用中</span>
    </span>
    <span class="theme-card__desc">{{ props.theme.description }}</span>
  </button>
</template>

<style scoped>
.theme-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 14px 16px 16px;
  text-align: left;
  background: var(--ma-color-surface);
  border: 1px solid var(--ma-color-line);
  border-radius: var(--ma-radius-md);
  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease;
}

.theme-card:hover {
  border-color: var(--ma-color-line-strong);
}

.theme-card:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px var(--ma-color-accent-soft);
  border-color: var(--ma-color-accent);
}

.theme-card.is-active {
  border-color: var(--ma-color-accent);
  box-shadow: 0 0 0 1px var(--ma-color-accent);
}

.theme-card__swatches {
  display: flex;
  gap: 0;
  height: 28px;
  margin-bottom: 4px;
  border-radius: var(--ma-radius-sm);
  overflow: hidden;
  border: 1px solid var(--ma-color-line);
}

.theme-card__swatches i {
  flex: 1;
}

.theme-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.theme-card__name {
  font-size: 14px;
  font-weight: 600;
  color: var(--ma-color-ink);
}

.theme-card__desc {
  font-size: 12px;
  line-height: 1.6;
  color: var(--ma-color-muted);
}

.theme-card__badge {
  flex: none;
  padding: 1px 8px;
  font-size: 11px;
  border-radius: 999px;
  color: var(--ma-color-accent);
  background: var(--ma-color-accent-soft);
}
</style>
