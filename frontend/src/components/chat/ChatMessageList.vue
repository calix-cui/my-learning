<script setup lang="ts">
import ChatExecutionItem from './ChatExecutionItem.vue'
import ChatMessage from './ChatMessage.vue'
import type { ChatFeedItem } from '@/stores/chat/feed'

defineProps<{ items: ChatFeedItem[]; preview: string; busy: boolean }>()
const emit = defineEmits<{
  requestSteps: [runId: number]
  decide: [decision: 'approve' | 'reject', note?: string]
}>()
</script>

<template>
  <template v-for="item in items" :key="item.key">
    <ChatMessage v-if="item.kind === 'message'" :message="item.message" />
    <ChatExecutionItem
      v-else
      :item="item"
      :preview="preview"
      :busy="busy"
      @request-steps="emit('requestSteps', $event)"
      @decide="(decision, note) => emit('decide', decision, note)"
    />
  </template>
</template>
