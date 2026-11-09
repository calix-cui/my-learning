<script setup lang="ts">
import { computed } from 'vue'

import type { ChatMessage } from '@/types/api'
import { renderMarkdown } from '@/utils/markdown'

const props = defineProps<{ message: ChatMessage }>()

const isUser = computed(() => props.message.role === 'user')
/** 后端时间「2026-11-09 21:20:05」→ 气泡下只留时分 */
const time = computed(() => props.message.create_time.slice(11, 16))
const html = computed(() => renderMarkdown(props.message.content))
</script>

<template>
  <div class="chat__row" :class="isUser ? 'chat__row--user' : 'chat__row--assistant'">
    <span v-if="!isUser" class="chat__who"><i />助手</span>

    <div class="chat__bubble">
      <!-- 用户消息按纯文本显示；助手消息是模型输出的 Markdown，经 DOMPurify 消毒 -->
      <div v-if="isUser" class="chat__content">{{ message.content }}</div>
      <div v-else class="chat__content chat__content--md" v-html="html" />
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
  margin-top: 20px;
}

.chat__row--user {
  align-items: flex-end;
}

.chat__row--assistant {
  align-items: flex-start;
}

.chat__who {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  font-size: 12px;
  color: var(--ma-color-muted);
}

.chat__who i {
  width: 6px;
  height: 6px;
  background: var(--ma-color-accent);
  border-radius: 999px;
}

.chat__bubble {
  max-width: 80%;
  padding: 12px 16px;
  font-size: 15px;
  line-height: 1.75;
  border-radius: var(--ma-radius-lg);
}

.chat__row--user .chat__bubble {
  color: var(--ma-color-on-accent);
  background: var(--ma-color-accent);
}

.chat__row--assistant .chat__bubble {
  max-width: 100%;
  color: var(--ma-color-ink);
  background: var(--ma-color-surface);
  border: 1px solid var(--ma-color-line);
}

.chat__content {
  word-break: break-word;
  white-space: pre-wrap;
}

.chat__content--md {
  white-space: normal;
}

.chat__meta {
  font-size: 12px;
  color: var(--ma-color-faint);
  font-variant-numeric: tabular-nums;
}

/* Markdown 样式（v-html 生成的内容不在 scoped 作用域里，需要 :deep） */
.chat__content--md :deep(h1),
.chat__content--md :deep(h2),
.chat__content--md :deep(h3),
.chat__content--md :deep(h4) {
  margin: 12px 0 6px;
  font-size: 15px;
  font-weight: 600;
  line-height: 1.5;
}

.chat__content--md :deep(h1:first-child),
.chat__content--md :deep(h2:first-child),
.chat__content--md :deep(h3:first-child) {
  margin-top: 0;
}

.chat__content--md :deep(p) {
  margin: 6px 0;
}

.chat__content--md :deep(ul),
.chat__content--md :deep(ol) {
  margin: 6px 0 6px 20px;
}

.chat__content--md :deep(li) {
  margin: 2px 0;
}

.chat__content--md :deep(strong) {
  font-weight: 600;
}

.chat__content--md :deep(a) {
  color: var(--ma-color-accent);
  text-decoration: underline;
  text-underline-offset: 2px;
}

.chat__content--md :deep(code) {
  padding: 1px 5px;
  font-family: var(--ma-font-mono);
  font-size: 13px;
  background: var(--ma-color-sunken);
  border-radius: 4px;
}

.chat__content--md :deep(pre) {
  padding: 12px 14px;
  margin: 8px 0;
  overflow-x: auto;
  background: var(--ma-color-sunken);
  border-radius: var(--ma-radius-sm);
}

.chat__content--md :deep(pre code) {
  padding: 0;
  background: none;
}

.chat__content--md :deep(blockquote) {
  padding-left: 12px;
  margin: 8px 0;
  color: var(--ma-color-muted);
  border-left: 3px solid var(--ma-color-line-strong);
}

.chat__content--md :deep(table) {
  margin: 8px 0;
  font-size: 14px;
  border-collapse: collapse;
}

.chat__content--md :deep(th),
.chat__content--md :deep(td) {
  padding: 6px 10px;
  text-align: left;
  border: 1px solid var(--ma-color-line);
}

.chat__content--md :deep(th) {
  font-weight: 600;
  background: var(--ma-color-sunken);
}

.chat__content--md :deep(hr) {
  margin: 12px 0;
  border: 0;
  border-top: 1px solid var(--ma-color-line);
}
</style>
