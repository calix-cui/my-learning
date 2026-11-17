<script setup lang="ts">
import { computed } from 'vue'

import type { ChatMessage } from '@/types/api'
import MarkdownContent from './MarkdownContent.vue'

const props = defineProps<{ message: ChatMessage }>()

const isUser = computed(() => props.message.role === 'user')
/** 后端时间「2026-11-09 21:20:05」→ 气泡下只留时分 */
const time = computed(() => props.message.create_time.slice(11, 16))
</script>

<template>
  <div class="chat__row" :class="isUser ? 'chat__row--user' : 'chat__row--assistant'">
    <div class="chat__bubble">
      <!-- 用户消息按纯文本显示；助手消息是模型输出的 Markdown，经 DOMPurify 消毒 -->
      <div v-if="isUser" class="chat__content">{{ message.content }}</div>
      <MarkdownContent v-else class="chat__content" :content="message.content" />
    </div>

    <span v-if="time" class="chat__meta">
      {{ time }}<template v-if="!isUser && message.model"> · {{ message.model }}</template>
    </span>
  </div>
</template>

<style scoped>
.chat__row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.chat__row + .chat__row {
  margin-top: 28px;
}

.chat__row--user {
  align-items: flex-end;
}

.chat__row--assistant {
  align-items: flex-start;
}

.chat__bubble {
  max-width: 78%;
  padding: 12px 18px;
  font-size: 15px;
  line-height: 1.8;
  border-radius: var(--ma-radius-lg);
}

.chat__row--user .chat__bubble {
  color: var(--ma-color-ink);
  background: var(--ma-color-accent-soft);
  border-radius: var(--ma-radius-lg) var(--ma-radius-lg) var(--ma-radius-sm) var(--ma-radius-lg);
}

/* 助手回答不套气泡：整段正文直接落在纸面上，读长文更顺 */
.chat__row--assistant .chat__bubble {
  max-width: 100%;
  padding: 0;
  color: var(--ma-color-ink);
  background: transparent;
  border: 0;
}

.chat__row--user .chat__content {
  word-break: break-word;
  white-space: pre-wrap;
}

.chat__meta {
  font-size: 12px;
  color: var(--ma-color-faint);
  font-variant-numeric: tabular-nums;
}
</style>
