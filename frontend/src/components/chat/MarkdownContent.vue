<script setup lang="ts">
import { computed } from 'vue'

import { renderMarkdown } from '@/utils/markdown'

const props = defineProps<{ content: string }>()
const html = computed(() => renderMarkdown(props.content))
</script>

<template>
  <!-- renderMarkdown 已清理生成的 HTML。 -->
  <div class="markdown-content" v-html="html" />
</template>

<style scoped>
.markdown-content {
  min-width: 0;
  overflow-x: auto;
  overflow-wrap: anywhere;
  font-size: 15px;
  line-height: 1.8;
}

/* Markdown 样式（v-html 生成的内容不在 scoped 作用域里，需要 :deep） */
.markdown-content :deep(h1),
.markdown-content :deep(h2),
.markdown-content :deep(h3),
.markdown-content :deep(h4) {
  margin: 12px 0 6px;
  font-size: 15px;
  font-weight: 600;
  line-height: 1.5;
}

.markdown-content :deep(h1:first-child),
.markdown-content :deep(h2:first-child),
.markdown-content :deep(h3:first-child) {
  margin-top: 0;
}

.markdown-content :deep(p) {
  margin: 6px 0;
}

.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  margin: 6px 0 6px 20px;
}

.markdown-content :deep(li) {
  margin: 2px 0;
}

.markdown-content :deep(strong) {
  font-weight: 600;
}

.markdown-content :deep(a) {
  color: var(--ma-color-accent);
  text-decoration: underline;
  text-underline-offset: 2px;
}

.markdown-content :deep(code) {
  padding: 1px 5px;
  font-family: var(--ma-font-mono);
  font-size: 13px;
  background: var(--ma-color-sunken);
  border-radius: 4px;
}

.markdown-content :deep(pre) {
  padding: 12px 14px;
  margin: 8px 0;
  overflow-x: auto;
  background: var(--ma-color-sunken);
  border-radius: var(--ma-radius-sm);
}

.markdown-content :deep(pre code) {
  padding: 0;
  background: none;
}

.markdown-content :deep(blockquote) {
  padding-left: 12px;
  margin: 8px 0;
  color: var(--ma-color-muted);
  border-left: 3px solid var(--ma-color-line-strong);
}

.markdown-content :deep(table) {
  margin: 8px 0;
  font-size: 14px;
  border-collapse: collapse;
}

.markdown-content :deep(th),
.markdown-content :deep(td) {
  padding: 6px 10px;
  text-align: left;
  border: 1px solid var(--ma-color-line);
}

.markdown-content :deep(th) {
  font-weight: 600;
  background: var(--ma-color-sunken);
}

.markdown-content :deep(hr) {
  margin: 12px 0;
  border: 0;
  border-top: 1px solid var(--ma-color-line);
}
</style>
