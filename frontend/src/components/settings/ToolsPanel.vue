<script setup lang="ts">
/**
 * 工具设置：默认全部开着，用户要收紧就逐个关掉。
 *
 * 关掉的工具不是删掉——后端注册表会过滤掉它（模型看不到也执行不了），
 * 但这里仍然列出来，否则用户没法再打开。
 */
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import AppIcon from '@/components/ui/AppIcon.vue'
import {
  fetchToolSettings,
  fetchToolStats,
  saveToolSettings,
  type ToolItem,
  type ToolSettings,
  type ToolStats,
} from '@/api/settings'

const tools = ref<ToolItem[]>([])
const budget = ref(500)
const usedToday = ref(0)
const stats = ref<ToolStats | null>(null)
const loading = ref(false)
const saving = ref(false)

const levelLabel: Record<ToolItem['level'], string> = {
  read: '只读',
  write: '写操作',
  external: '外部',
}

const usedPercent = computed(() =>
  budget.value > 0 ? Math.min(100, Math.round((usedToday.value / budget.value) * 100)) : 0,
)

function apply(data: ToolSettings) {
  tools.value = data.items
  budget.value = data.daily_tool_budget
  usedToday.value = data.used_today
}

async function load() {
  loading.value = true
  try {
    const [settings, stat] = await Promise.all([fetchToolSettings(), fetchToolStats(7)])
    apply(settings)
    stats.value = stat
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '读取工具设置失败')
  } finally {
    loading.value = false
  }
}

async function toggle(tool: ToolItem, enabled: boolean) {
  const previous = tool.enabled
  tool.enabled = enabled
  try {
    const disabled = tools.value.filter((item) => !item.enabled).map((item) => item.name)
    apply(await saveToolSettings({ disabled }))
  } catch (error) {
    tool.enabled = previous
    ElMessage.error(error instanceof Error ? error.message : '保存失败')
  }
}

async function saveBudget() {
  saving.value = true
  try {
    const disabled = tools.value.filter((item) => !item.enabled).map((item) => item.name)
    apply(await saveToolSettings({ disabled, daily_tool_budget: budget.value }))
    ElMessage.success('已保存每日上限')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <section v-loading="loading" class="tools">
    <header class="tools__head">
      <h2 class="tools__title">工具</h2>
      <p class="tools__desc">关掉的工具模型看不到也调不动；写操作类工具每次执行前都会先问你。</p>
    </header>

    <ul class="tools__list">
      <li v-for="tool in tools" :key="tool.name" class="tools__row u-tint">
        <div class="tools__main">
          <span class="tools__name">{{ tool.name }}</span>
          <span class="tools__level" :class="`tools__level--${tool.level}`">
            {{ levelLabel[tool.level] }}
          </span>
          <span v-if="tool.requires_approval" class="tools__badge">需确认</span>
        </div>
        <p class="tools__about">{{ tool.description }}</p>
        <p class="tools__meta">今日 {{ tool.calls_today }} 次</p>
        <el-switch
          :model-value="tool.enabled"
          :aria-label="`启用 ${tool.name}`"
          @update:model-value="toggle(tool, Boolean($event))"
        />
      </li>
    </ul>

    <div v-if="!tools.length && !loading" class="tools__empty">
      <AppIcon name="settings" :size="20" />
      <span>还没有可用的工具</span>
    </div>

    <section class="tools__budget">
      <div class="tools__budget-head">
        <h3 class="tools__subtitle">每日调用上限</h3>
        <span class="tools__meta">今日已用 {{ usedToday }} / {{ budget }} 次</span>
      </div>
      <div class="tools__bar"><i :style="{ width: `${usedPercent}%` }" /></div>
      <div class="tools__budget-form">
        <el-input-number v-model="budget" :min="1" :max="5000" :step="50" />
        <button class="tools__save" :disabled="saving" @click="saveBudget">
          {{ saving ? '保存中…' : '保存上限' }}
        </button>
      </div>
    </section>

    <section v-if="stats && stats.items.length" class="tools__stats">
      <h3 class="tools__subtitle">最近 {{ stats.days }} 天</h3>
      <ul class="tools__stat-list">
        <li v-for="item in stats.items" :key="item.tool_name" class="tools__stat-row">
          <span class="tools__name">{{ item.tool_name }}</span>
          <span class="tools__meta">{{ item.calls }} 次</span>
          <span v-if="item.failures" class="tools__fail">{{ item.failures }} 次失败</span>
        </li>
      </ul>
    </section>
  </section>
</template>

<style scoped>
.tools {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.tools__title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--ma-color-ink);
}

.tools__desc,
.tools__about {
  margin: 6px 0 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--ma-color-ink-muted);
}

.tools__list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.tools__row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 4px 12px;
  padding: 14px 16px;
  background: var(--ma-color-surface);
  border-radius: 14px;
}

.tools__main {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tools__name {
  font-size: 14px;
  font-weight: 600;
  color: var(--ma-color-ink);
}

.tools__level {
  padding: 1px 7px;
  font-size: 11px;
  border-radius: 6px;
}

.tools__level--read {
  color: var(--ma-color-ink-muted);
  background: var(--ma-color-canvas);
}

.tools__level--write {
  color: var(--ma-color-warning-ink, var(--ma-color-ink));
  background: var(--ma-color-warning-soft, var(--ma-color-canvas));
}

.tools__level--external {
  color: var(--ma-color-accent-ink);
  background: var(--ma-color-accent-soft);
}

.tools__badge {
  padding: 1px 7px;
  font-size: 11px;
  color: var(--ma-color-accent-ink);
  background: var(--ma-color-accent-soft);
  border-radius: 6px;
}

.tools__meta {
  margin: 0;
  font-size: 12px;
  color: var(--ma-color-ink-muted);
}

.tools__row .tools__about,
.tools__row .tools__meta {
  grid-column: 1;
}

.tools__row :deep(.el-switch) {
  grid-column: 2;
  grid-row: 1 / span 3;
  align-self: center;
}

.tools__empty {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--ma-color-ink-muted);
}

.tools__budget,
.tools__stats {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.tools__budget-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}

.tools__subtitle {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--ma-color-ink);
}

.tools__bar {
  height: 6px;
  overflow: hidden;
  background: var(--ma-color-canvas);
  border-radius: 999px;
}

.tools__bar > i {
  display: block;
  height: 100%;
  background: var(--ma-color-accent);
  border-radius: inherit;
  transition: width 0.2s ease;
}

.tools__budget-form {
  display: flex;
  align-items: center;
  gap: 10px;
}

.tools__save {
  height: 34px;
  padding: 0 16px;
  font-size: 13px;
  color: var(--ma-color-on-accent);
  cursor: pointer;
  background: var(--ma-color-accent);
  border: 0;
  border-radius: 10px;
}

.tools__save:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.tools__stat-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.tools__stat-row {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
}

.tools__fail {
  margin-left: auto;
  font-size: 12px;
  color: var(--ma-color-danger, #b3261e);
}
</style>
