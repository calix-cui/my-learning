<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { Delete, Edit, Plus } from '@element-plus/icons-vue'

import { useChatStore } from '@/stores/chat'
import type { ChatConversationListItem } from '@/types/api'

const chat = useChatStore()
const route = useRoute()
const router = useRouter()

/** 侧边栏常驻：在别的页面点会话，先回到对话页再打开 */
async function open(id: number) {
  if (route.name !== 'chat') {
    await router.push({ name: 'chat' })
  }
  await chat.openConversation(id)
}

async function handleCreate() {
  await chat.createNew()
  if (route.name !== 'chat') {
    await router.push({ name: 'chat' })
  }
}

/** 后端时间是「2026-11-09 21:20:05」，列表里只留「11-09 21:20」 */
const metaTime = (value: string) => value.slice(5, 16)

const itemMeta = (item: ChatConversationListItem) =>
  `${item.message_count} 条 · ${metaTime(item.update_time)}`
</script>

<template>
  <div class="threads">
    <div class="threads__head">
      <span class="threads__label">会话</span>
      <el-button
        class="chat__new"
        type="primary"
        plain
        size="small"
        :icon="Plus"
        @click="handleCreate"
      >
        新建
      </el-button>
    </div>

    <div v-loading="chat.loadingList" class="threads__list">
      <p v-if="!chat.conversations.length" class="threads__empty">还没有会话，点「新建」开始</p>

      <div
        v-for="item in chat.conversations"
        :key="item.id"
        class="chat__item"
        :class="{ 'chat__item--active': item.id === chat.activeId }"
      >
        <button
          type="button"
          class="chat__item-main"
          :aria-current="item.id === chat.activeId ? 'true' : undefined"
          @click="open(item.id)"
        >
          <span class="chat__item-title">{{ item.title }}</span>
          <span class="chat__item-meta">{{ itemMeta(item) }}</span>
        </button>

        <span class="chat__item-actions">
          <el-button link :icon="Edit" size="small" title="重命名" @click="chat.rename(item)" />
          <el-button link :icon="Delete" size="small" title="删除" @click="chat.remove(item)" />
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.threads {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
}

.threads__head {
  display: flex;
  flex: none;
  align-items: center;
  justify-content: space-between;
  padding: 0 8px 10px;
}

.threads__label {
  padding-left: 10px;
  font-size: 12px;
  color: var(--ma-color-faint);
  letter-spacing: 0.08em;
}

.threads__list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  scrollbar-width: thin;
}

.threads__empty {
  margin: 12px 10px;
  font-size: 13px;
  color: var(--ma-color-faint);
}

.chat__item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 4px;
  border-radius: var(--ma-radius-sm);
}

.chat__item + .chat__item {
  margin-top: 2px;
}

.chat__item:hover {
  background: color-mix(in srgb, var(--ma-color-ink) 4%, transparent);
}

.chat__item--active {
  background: var(--ma-color-accent-soft);
}

/* 选中态左侧 3px 竖条：比整块反白安静，也符合 DESIGN.md 的会话项规范 */
.chat__item--active::before {
  position: absolute;
  top: 8px;
  bottom: 8px;
  left: 0;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: var(--ma-color-accent);
  content: '';
}

.chat__item-main {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  padding: 8px 10px 8px 13px;
  font: inherit;
  color: inherit;
  text-align: left;
  cursor: pointer;
  background: none;
  border: 0;
}

.chat__item-main:focus-visible {
  outline: 2px solid var(--ma-color-accent);
  outline-offset: -2px;
  border-radius: var(--ma-radius-sm);
}

.chat__item-title {
  overflow: hidden;
  font-size: 14px;
  color: var(--ma-color-ink);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat__item--active .chat__item-title {
  font-weight: 600;
  color: var(--ma-color-accent);
}

.chat__item-meta {
  font-size: 12px;
  color: var(--ma-color-faint);
  font-variant-numeric: tabular-nums;
}

.chat__item-actions {
  display: flex;
  flex: none;
  gap: 2px;
  padding-right: 6px;
  opacity: 0;
  transition: opacity 0.15s ease;
}

.chat__item:hover .chat__item-actions,
.chat__item--active .chat__item-actions,
.chat__item:focus-within .chat__item-actions {
  opacity: 1;
}
</style>
