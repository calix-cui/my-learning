<script setup lang="ts">
import { computed } from 'vue'

import type { AgentStep } from '@/types/api'

const props = defineProps<{
  steps: AgentStep[]
  running: boolean
  lazy?: boolean
  loadStatus?: 'loading' | 'loaded' | 'error'
}>()
const emit = defineEmits<{ requestSteps: [] }>()

function handleToggle(event: Event) {
  if (props.lazy && (event.currentTarget as HTMLDetailsElement).open && !props.loadStatus) {
    emit('requestSteps')
  }
}

type TimelineEntry = { step: AgentStep; result?: AgentStep }

/** 历史回放和实时事件使用相同的配对规则，调用和结果合并为一行。 */
const entries = computed(() => {
  const rows: TimelineEntry[] = []
  const pending = new Map<string | null, TimelineEntry>()
  for (const step of props.steps) {
    if (step.kind === 'tool_call') {
      const entry = { step }
      rows.push(entry)
      pending.set(step.tool_name, entry)
    } else if (step.kind === 'tool_result') {
      const entry = pending.get(step.tool_name)
      if (entry) {
        entry.result = step
        pending.delete(step.tool_name)
      } else {
        rows.push({ step, result: step })
      }
    } else if (['skill_loaded', 'skill_load_failed', 'skill_resource'].includes(step.kind)) {
      rows.push({ step })
    }
  }
  return rows
})

function label(step: AgentStep) {
  if (step.kind === 'skill_loaded') return '已加载 Skill'
  if (step.kind === 'skill_load_failed') return 'Skill 未加载'
  if (step.kind === 'skill_resource') return step.ok ? '已读取参考资料' : '参考资料未读取'
  return '调用了工具'
}

function name(step: AgentStep) {
  if (step.kind.startsWith('skill_')) return step.skill_name || step.skill_key
  return step.tool_name
}

function detail({ step, result }: TimelineEntry) {
  if (result) return result.content || '（无返回内容）'
  if (step.kind === 'skill_loaded') {
    return step.skill_source === 'builtin'
      ? '内置 Skill'
      : step.skill_source === 'local'
        ? '本地 Skill'
        : '旧版 Skill'
  }
  if (step.kind === 'tool_call') return props.running ? '等待执行结果' : '暂无运行结果'
  return step.content || '（无详情）'
}

function parameters({ step, result }: TimelineEntry) {
  const args = step.tool_args ?? result?.tool_args
  return args && Object.keys(args).length ? JSON.stringify(args, null, 2) : '（无参数）'
}
</script>

<template>
  <details v-if="entries.length || lazy" class="timeline" @toggle="handleToggle">
    <summary class="timeline__summary u-text-action">
      <span>{{ running ? '正在思考...' : '执行过程' }}</span>
      <span class="timeline__chevron" aria-hidden="true">›</span>
    </summary>
    <p v-if="loadStatus === 'loading'" class="timeline__text" role="status">正在加载…</p>
    <button
      v-else-if="loadStatus === 'error'"
      type="button"
      class="timeline__summary timeline__retry u-text-action"
      @click="emit('requestSteps')"
    >
      读取失败，重试
    </button>
    <details
      v-for="entry in entries"
      :key="entry.step.seq"
      class="timeline__entry"
      :class="{ 'timeline__item--tool_result': entry.result }"
    >
      <summary class="timeline__summary u-text-action">
        <span class="timeline__label">
          {{ label(entry.step) }}
          <span v-if="name(entry.step)" class="timeline__tool">{{ name(entry.step) }}</span>
        </span>
        <span class="timeline__chevron" aria-hidden="true">›</span>
      </summary>
      <div class="timeline__detail">
        <template v-if="entry.step.kind.startsWith('tool_')">
          <div>参数</div>
          <pre>{{ parameters(entry) }}</pre>
          <div>{{ entry.result?.ok === false ? '运行失败' : '运行结果' }}</div>
        </template>
        <p class="timeline__text">{{ detail(entry) }}</p>
      </div>
    </details>
  </details>
  <div v-else-if="running" class="timeline" role="status" aria-label="正在思考">
    <span aria-hidden="true"
      >正在思考<span class="timeline__dots"><span>.</span><span>.</span><span>.</span></span></span
    >
  </div>
</template>

<style scoped>
.timeline {
  color: var(--ma-color-text);
  font-size: 14px;
  line-height: 1.5;
}
.timeline:hover {
  color: var(--ma-color-text-hover);
}

.timeline__summary {
  display: flex;
  gap: 0.5em;
  align-items: center;
  width: fit-content;
  max-width: 100%;
  list-style: none;
  border-radius: var(--ma-radius-sm);
}

.timeline__summary::-webkit-details-marker {
  display: none;
}

.timeline__summary:focus-visible {
  outline: thin solid var(--ma-color-accent);
}

.timeline__retry {
  font: inherit;
  background: transparent;
  border: 0;
}

.timeline__entry,
.timeline__detail {
  margin-inline-start: 1em;
}

.timeline__chevron,
.timeline__hint {
  flex: none;
}

details[open] > .timeline__summary > .timeline__chevron {
  transform: rotate(90deg);
}

.timeline__label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.timeline__detail pre,
.timeline__text {
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.timeline__detail pre {
  font-family: var(--ma-font-mono);
}

.timeline__dots > span {
  display: inline-block;
  animation: think-dot 1.2s ease-in-out infinite;
}

.timeline__dots > span:nth-child(2) {
  animation-delay: 0.15s;
}

.timeline__dots > span:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes think-dot {
  0%,
  60%,
  100% {
    transform: translateY(0);
  }

  30% {
    transform: translateY(-0.2em);
  }
}

@media (prefers-reduced-motion: reduce) {
  .timeline__dots > span {
    animation: none;
  }
}
</style>
