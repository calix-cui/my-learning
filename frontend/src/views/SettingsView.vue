<script setup lang="ts">
import { computed, ref } from 'vue'

import AppearancePanel from '@/components/settings/AppearancePanel.vue'

/** 设置页分节：本期只交付「外观」，其余分节占位，避免点进去是空白 */
const sections = [
  { key: 'appearance', label: '外观', ready: true },
  { key: 'model', label: '模型接入', ready: false },
  { key: 'account', label: '账号资料', ready: false },
  { key: 'devices', label: '登录设备', ready: false },
  { key: 'data', label: '数据管理', ready: false },
] as const

type SectionKey = (typeof sections)[number]['key']

const active = ref<SectionKey>('appearance')

const activeLabel = computed(
  () => sections.find((section) => section.key === active.value)?.label ?? '设置',
)
</script>

<template>
  <div class="settings">
    <nav class="settings__nav" aria-label="设置分节">
      <button
        v-for="section in sections"
        :key="section.key"
        type="button"
        class="settings__item"
        :class="{ 'is-active': section.key === active }"
        :aria-current="section.key === active ? 'page' : undefined"
        @click="active = section.key"
      >
        {{ section.label }}
        <span v-if="!section.ready" class="settings__soon">待建</span>
      </button>
    </nav>

    <div class="settings__panel">
      <div class="settings__col">
        <AppearancePanel v-if="active === 'appearance'" />

        <section v-else class="settings__placeholder">
          <h2 class="settings__placeholder-title">{{ activeLabel }}</h2>
          <p class="settings__placeholder-desc">
            这一节还没做。当前进度见 <code>docs/plan/TASKS.md</code> 的 T-FE-02。
          </p>
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped>
.settings {
  display: flex;
  gap: 0;
  min-height: 0;
  height: 100%;
}

.settings__nav {
  flex: none;
  width: 200px;
  padding: 20px 12px;
  border-right: 1px solid var(--ma-color-line);
}

.settings__item {
  display: flex;
  border: 0;
  background: transparent;
  font: inherit;
  cursor: pointer;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  padding: 8px 10px;
  margin-bottom: 2px;
  font-size: 14px;
  color: var(--ma-color-muted);
  text-align: left;
  border-radius: var(--ma-radius-sm);
}

.settings__item:hover {
  color: var(--ma-color-ink);
  background: var(--ma-color-sunken);
}

.settings__item.is-active {
  color: var(--ma-color-accent);
  font-weight: 600;
  background: var(--ma-color-accent-soft);
}

.settings__item:focus-visible {
  outline: 2px solid var(--ma-color-accent);
  outline-offset: 1px;
}

.settings__soon {
  font-size: 11px;
  font-weight: 400;
  color: var(--ma-color-faint);
}

.settings__item:not(.is-active):has(.settings__soon) {
  color: var(--ma-color-faint);
}

.settings__panel {
  flex: 1;
  min-width: 0;
  padding: 28px 40px;
  overflow-y: auto;
}

.settings__col {
  max-width: 560px;
  margin: 0 auto;
}

.settings__placeholder-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--ma-color-ink);
}

.settings__placeholder-desc {
  margin-top: 6px;
  font-size: 13px;
  color: var(--ma-color-muted);
}

.settings__placeholder-desc code {
  padding: 1px 5px;
  font-family: var(--ma-font-mono);
  font-size: 12px;
  background: var(--ma-color-sunken);
  border-radius: 4px;
}
</style>
