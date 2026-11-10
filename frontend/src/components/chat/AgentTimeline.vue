<script setup lang="ts">
import { computed } from 'vue'

import type { AgentStep } from '@/types/api'

const props = defineProps<{
  steps: AgentStep[]
  running: boolean
}>()

/** 只展示「过程」：工具调用/结果与模型的思考，最终答复另有气泡 */
const visible = computed(() =>
  props.steps.filter(
    (step) =>
      step.kind === 'tool_call' || step.kind === 'tool_result' || step.kind === 'assistant_text',
  ),
)

function argsText(step: AgentStep): string {
  if (!step.tool_args) return ''
  return Object.entries(step.tool_args)
    .map(([key, value]) => `${key}: ${typeof value === 'string' ? value : JSON.stringify(value)}`)
    .join('，')
}

function kindLabel(step: AgentStep): string {
  if (step.kind === 'assistant_text') return '思考'
  if (step.kind === 'tool_call') return '调用工具'
  return step.ok ? '工具结果' : '工具失败'
}
</script>

<template>
  <section v-if="visible.length || running" class="timeline" aria-live="polite">
    <header class="timeline__head">
      <span class="timeline__title">执行过程</span>
      <span v-if="running" class="timeline__badge">进行中</span>
    </header>

    <ol class="timeline__list">
      <li
        v-for="step in visible"
        :key="step.seq"
        class="timeline__item"
        :class="`timeline__item--${step.kind}`"
      >
        <span class="timeline__dot" aria-hidden="true" />
        <div class="timeline__body">
          <p class="timeline__label">
            {{ kindLabel(step) }}
            <code v-if="step.tool_name" class="timeline__tool">{{ step.tool_name }}</code>
            <span v-if="step.duration_ms !== null" class="timeline__time"
              >{{ step.duration_ms }}ms</span
            >
          </p>
          <p v-if="step.kind === 'tool_call'" class="timeline__text timeline__text--muted">
            {{ argsText(step) || '（无参数）' }}
          </p>
          <p v-else class="timeline__text">{{ step.content }}</p>
        </div>
      </li>
      <li v-if="running && !visible.length" class="timeline__item">
        <span class="timeline__dot" aria-hidden="true" />
        <div class="timeline__body">
          <p class="timeline__text timeline__text--muted">正在思考…</p>
        </div>
      </li>
    </ol>
  </section>
</template>

<style scoped>
.timeline {
  border: 1px solid var(--ma-color-line);
  border-radius: var(--ma-radius-md);
  background: var(--ma-color-surface);
  padding: 12px 14px;
}

.timeline__head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.timeline__title {
  font-size: 13px;
  font-weight: 600;
  color: var(--ma-color-ink);
}

.timeline__badge {
  font-size: 12px;
  color: var(--ma-color-accent);
  background: var(--ma-color-accent-soft);
  border-radius: 999px;
  padding: 1px 8px;
}

.timeline__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.timeline__item {
  display: flex;
  gap: 8px;
  position: relative;
}

.timeline__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--ma-color-faint);
  margin-top: 7px;
  flex: none;
}

.timeline__item--tool_result .timeline__dot,
.timeline__item--tool_call .timeline__dot {
  background: var(--ma-color-accent);
}

.timeline__body {
  min-width: 0;
}

.timeline__label {
  margin: 0;
  font-size: 12px;
  color: var(--ma-color-muted);
  display: flex;
  align-items: center;
  gap: 6px;
}

.timeline__tool {
  font-family: var(--ma-font-mono);
  font-size: 12px;
  color: var(--ma-color-ink);
  background: var(--ma-color-sunken);
  border-radius: 4px;
  padding: 0 4px;
}

.timeline__time {
  color: var(--ma-color-faint);
  font-variant-numeric: tabular-nums;
}

.timeline__text {
  margin: 2px 0 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--ma-color-ink);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.timeline__text--muted {
  color: var(--ma-color-muted);
}
</style>
