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
}>()

function requestSteps() {
  if (props.item.runId !== null) emit('requestSteps', props.item.runId)
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
</template>

<style scoped>
.chat__execution-error {
  margin: var(--ma-space-sm) 0 var(--ma-space-md);
  color: var(--ma-color-muted);
}
</style>
