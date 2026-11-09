<script setup lang="ts">
import { computed } from 'vue'

import ModeSwitch from '@/components/theme/ModeSwitch.vue'
import ThemeCard from '@/components/theme/ThemeCard.vue'
import { useTheme } from '@/stores/theme'
import type { ThemeModeSetting } from '@/theme/types'

const { themes, state, resolvedMode, currentTheme, setTheme, setMode } = useTheme()

// defineModel 需要可写 ref：这里用 computed 读写 store，避免把 store 逻辑塞进模板
const mode = computed<ThemeModeSetting>({
  get: () => state.mode,
  set: (value) => setMode(value),
})
</script>

<template>
  <section class="appearance">
    <header class="appearance__head">
      <h2 class="appearance__title">外观</h2>
      <p class="appearance__desc">
        主题只改配色，不改布局。当前：{{ currentTheme.name }} ·
        {{ resolvedMode === 'dark' ? '深色' : '浅色'
        }}{{ state.mode === 'system' ? '（跟随系统）' : '' }}。
      </p>
    </header>

    <div class="appearance__block">
      <h3 class="appearance__label">明暗模式</h3>
      <ModeSwitch v-model="mode" />
      <p class="appearance__hint">选择「跟随系统」时，会随操作系统的深浅色设置自动切换。</p>
    </div>

    <div class="appearance__block">
      <h3 class="appearance__label">主题配色</h3>
      <div class="appearance__grid">
        <ThemeCard
          v-for="theme in themes"
          :key="theme.id"
          :theme="theme"
          :active="theme.id === state.themeId"
          :mode="resolvedMode"
          @select="setTheme"
        />
      </div>
      <p class="appearance__hint">
        新增主题只需在 <code>src/theme/themes/</code> 下加一个文件（浅色 +
        深色两套语义色），再注册到 <code>themes/index.ts</code>。
      </p>
    </div>
  </section>
</template>

<style scoped>
.appearance__head {
  margin-bottom: 28px;
}

.appearance__title {
  font-size: 20px;
  font-weight: 600;
  color: var(--ma-color-ink);
}

.appearance__desc {
  margin-top: 4px;
  font-size: 13px;
  color: var(--ma-color-muted);
}

.appearance__block + .appearance__block {
  margin-top: 28px;
}

.appearance__label {
  margin-bottom: 10px;
  font-size: 15px;
  font-weight: 600;
  color: var(--ma-color-ink);
}

.appearance__hint {
  margin-top: 10px;
  font-size: 12px;
  line-height: 1.7;
  color: var(--ma-color-muted);
}

.appearance__hint code {
  padding: 1px 5px;
  font-family: var(--ma-font-mono);
  font-size: 12px;
  background: var(--ma-color-sunken);
  border-radius: 4px;
}

.appearance__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
</style>
