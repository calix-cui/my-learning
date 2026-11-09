<script setup lang="ts">
import type { ThemeModeSetting } from '@/theme/types'

const model = defineModel<ThemeModeSetting>({ required: true })

const options: { value: ThemeModeSetting; label: string }[] = [
  { value: 'light', label: '浅色' },
  { value: 'dark', label: '深色' },
  { value: 'system', label: '跟随系统' },
]
</script>

<template>
  <!-- 分段控件：三档互斥选择，键盘可用（原生 radio 语义 + 外观靠 CSS） -->
  <div class="mode-switch" role="group" aria-label="明暗模式">
    <label
      v-for="option in options"
      :key="option.value"
      :for="`theme-mode-${option.value}`"
      class="mode-switch__item"
      :class="{ 'is-active': model === option.value }"
    >
      <input
        :id="`theme-mode-${option.value}`"
        v-model="model"
        class="mode-switch__radio"
        type="radio"
        name="theme-mode"
        :value="option.value"
      />
      {{ option.label }}
    </label>
  </div>
</template>

<style scoped>
.mode-switch {
  display: inline-flex;
  gap: 2px;
  padding: 3px;
  background: var(--ma-color-sunken);
  border-radius: var(--ma-radius-sm);
}

.mode-switch__item {
  position: relative;
  padding: 6px 14px;
  font-size: 13px;
  color: var(--ma-color-muted);
  border-radius: 4px;
  cursor: pointer;
  transition:
    background-color 0.15s ease,
    color 0.15s ease;
}

.mode-switch__item:hover {
  color: var(--ma-color-ink);
}

.mode-switch__item.is-active {
  color: var(--ma-color-ink);
  font-weight: 600;
  background: var(--ma-color-surface);
  box-shadow: 0 1px 2px rgb(28 27 24 / 6%);
}

.mode-switch__radio {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}

.mode-switch__item:focus-within {
  outline: 2px solid var(--ma-color-accent);
  outline-offset: 1px;
}
</style>
