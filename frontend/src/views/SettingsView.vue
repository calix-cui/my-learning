<script setup lang="ts">
import { computed, ref } from 'vue'

import AccountPanel from '@/components/settings/AccountPanel.vue'
import AppearancePanel from '@/components/settings/AppearancePanel.vue'
import DataPanel from '@/components/settings/DataPanel.vue'
import DevicesPanel from '@/components/settings/DevicesPanel.vue'
import ModelPanel from '@/components/settings/ModelPanel.vue'
import MarketPanel from '@/components/settings/MarketPanel.vue'
import ToolsPanel from '@/components/settings/ToolsPanel.vue'

/** 设置页分节；加新分节时往这里加一项并补组件即可 */
const sections = [
  { key: 'model', label: '模型接入', component: ModelPanel },
  { key: 'tools', label: '工具', component: ToolsPanel },
  { key: 'market', label: '工具市场', component: MarketPanel },
  { key: 'account', label: '账号资料', component: AccountPanel },
  { key: 'devices', label: '登录设备', component: DevicesPanel },
  { key: 'appearance', label: '外观', component: AppearancePanel },
  { key: 'data', label: '数据管理', component: DataPanel },
] as const

type SectionKey = (typeof sections)[number]['key']

/** 默认落在「模型接入」——它是打开设置最常改的一项 */
const active = ref<SectionKey>('model')

const activeComponent = computed(
  () => sections.find((section) => section.key === active.value)?.component ?? ModelPanel,
)
</script>

<template>
  <div class="settings">
    <nav class="settings__nav" aria-label="设置分节">
      <button
        v-for="section in sections"
        :key="section.key"
        type="button"
        class="settings__item u-tint"
        :class="{ 'is-active': section.key === active }"
        :aria-current="section.key === active ? 'page' : undefined"
        @click="active = section.key"
      >
        {{ section.label }}
      </button>
    </nav>

    <div class="settings__panel">
      <div class="settings__col">
        <component :is="activeComponent" />
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
  width: 208px;
  padding: 18px 14px;
}

.settings__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  padding: 10px 12px;
  margin-bottom: 2px;
  font: inherit;
  font-size: 14px;
  color: var(--ma-color-muted);
  text-align: left;
  cursor: pointer;
  background: transparent;
  border: 0;
  border-radius: var(--ma-radius-md);
  transition: color var(--ma-motion-hover) ease;
}

.settings__item:hover {
  color: var(--ma-color-ink);
}

.settings__item.is-active {
  font-weight: 600;
  color: var(--ma-color-accent);
  background: var(--ma-color-accent-soft);
}

.settings__item.settings__item.is-active::before,
.settings__item.settings__item.is-active:hover::before {
  opacity: 0;
}

.settings__item:focus-visible {
  outline: 2px solid var(--ma-color-accent);
  outline-offset: 1px;
}

.settings__panel {
  flex: 1;
  min-width: 0;
  padding: 32px 40px;
  overflow-y: auto;
}

.settings__col {
  max-width: 560px;
  margin: 0 auto;
}
</style>
