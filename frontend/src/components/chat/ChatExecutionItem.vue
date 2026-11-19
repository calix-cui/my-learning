<script setup lang="ts">
import AgentTimeline from './AgentTimeline.vue'
import ApprovalCard from './ApprovalCard.vue'
import ChatMessage from './ChatMessage.vue'
import MarkdownContent from './MarkdownContent.vue'
import type { ExecutionItem } from '@/stores/chat/feed'

const props = defineProps<{ item: ExecutionItem; preview: string; busy: boolean }>()
const emit = defineEmits<{
  requestSteps: [runId: number]
  decide: [decision: 'approve' | 'reject', note?: string]
  regenerate: [runId: number]
}>()

function requestSteps() {
  if (props.item.runId !== null) emit('requestSteps', props.item.runId)
}

function regenerate() {
  if (props.item.runId !== null) emit('regenerate', props.item.runId)
}
</script>

<template>
  <AgentTimeline
    v-if="item.showTimeline"
    :steps="item.steps"
    :running="item.running"
    :lazy="item.lazy"
    :load-status="item.loadStatus"
    @request-steps="requestSteps"
  />
  <ApprovalCard
    v-if="item.approval"
    :approval="item.approval"
    :disabled="item.approvalBlocked"
    :busy="busy"
    @decide="(decision, note) => emit('decide', decision, note)"
  />
  <ChatMessage v-if="item.message" :message="item.message" />
  <MarkdownContent
    v-else-if="item.live && preview"
    class="chat__bubble--streaming"
    :content="preview"
  />
  <p v-if="item.error" class="chat__execution-error" role="status">{{ item.error }}</p>
  <div v-if="item.cancelled" class="chat__execution-stopped">
    <span class="chat__execution-stopped-text">您终止了此次会话</span>
    <button
      type="button"
      class="chat__regen"
      :disabled="busy || item.runId === null"
      @click="regenerate"
    >
      <svg class="chat__regen-icon" viewBox="0 0 16 16" aria-hidden="true">
        <path
          d="M13.5 8a5.5 5.5 0 1 1-1.6-3.9M13.5 2.5V5h-2.5"
          fill="none"
          stroke="currentColor"
          stroke-width="1.4"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
      重新生成
    </button>
  </div>
</template>

<style scoped>
.chat__execution-error {
  margin: var(--ma-space-sm) 0 var(--ma-space-md);
  color: var(--ma-color-muted);
}

.chat__execution-stopped {
  display: flex;
  align-items: center;
  gap: var(--ma-space-sm);
  margin: var(--ma-space-sm) 0 var(--ma-space-md);
}

.chat__execution-stopped-text {
  color: var(--ma-color-muted);
  font-size: 13px;
}

.chat__regen {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 28px;
  padding: 0 12px;
  border: none;
  border-radius: var(--ma-radius-xl);
  background: var(--ma-color-sunken);
  color: var(--ma-color-ink);
  font-size: 13px;
  cursor: pointer;
}

.chat__regen:hover:not(:disabled) {
  background: var(--ma-color-line);
}

.chat__regen:disabled {
  cursor: not-allowed;
  color: var(--ma-color-muted);
}

.chat__regen-icon {
  width: 14px;
  height: 14px;
}
</style>
