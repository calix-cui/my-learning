<script setup lang="ts">
/** 对话区顶部的一行工具栏：左侧会话标题，右侧模型标签与分享。 */
import AppIcon from '@/components/ui/AppIcon.vue'
import IconButton from '@/components/ui/IconButton.vue'

defineProps<{ title: string; model: string }>()
</script>

<template>
  <div class="chat__bar">
    <h2 v-if="title" class="chat__title" :title="title">{{ title }}</h2>
    <span v-else class="chat__title" aria-hidden="true" />

    <div class="chat__bar-right">
      <span class="layout__model" :title="`当前模型：${model}`">{{ model }}</span>
      <IconButton label="分享（待实现）">
        <AppIcon name="share" :size="17" />
      </IconButton>
    </div>
  </div>
</template>

<style scoped>
.chat__bar {
  display: flex;
  flex: none;
  gap: 16px;
  align-items: center;
  justify-content: space-between;
  padding: 14px 32px 6px;
}

.chat__title {
  margin: 0;
  overflow: hidden;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: -0.01em;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat__bar-right {
  display: flex;
  flex: none;
  gap: 6px;
  align-items: center;
}

.layout__model {
  padding: 3px 10px;
  font-size: 12px;
  color: var(--ma-color-muted);
  background: color-mix(in srgb, var(--ma-color-ink) 6%, transparent);
  border-radius: 999px;
}
</style>
