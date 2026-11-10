<script setup lang="ts">
/** 侧栏会话区：整宽「新建会话」+ 会话列表。 */
import SoftButton from '@/components/ui/SoftButton.vue'
import ThreadItem from '@/components/chat/ThreadItem.vue'
import { useChatStore } from '@/stores/chat'

const chat = useChatStore()

function open(id: number) {
  void chat.openConversation(id)
}
</script>

<template>
  <div class="threads">
    <SoftButton class="chat__new" block @click="chat.startNew()">
      <AppIcon name="plus" :size="16" />
      新建会话
    </SoftButton>

    <div v-loading="chat.loadingList" class="threads__list">
      <div v-if="!chat.conversations.length" class="threads__empty">
        <span class="threads__empty-mark" aria-hidden="true" />
        <p class="threads__empty-text">暂无历史对话</p>
      </div>

      <ThreadItem
        v-for="item in chat.conversations"
        :key="item.id"
        :item="item"
        :active="item.id === chat.activeId"
        @open="open(item.id)"
        @rename="chat.rename(item)"
        @remove="chat.remove(item)"
      />
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

.chat__new {
  flex: none;
  margin-bottom: 14px;
}

.threads__list {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
  overflow-y: auto;
}

.threads__empty {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 12px;
  align-items: center;
  justify-content: center;
  min-height: 220px;
  color: var(--ma-color-faint);
}

/* 虚线圈 + 小尾巴，做成「空对话气泡」的记号；不额外引图标 */
.threads__empty-mark {
  position: relative;
  display: block;
  width: 44px;
  height: 44px;
  border: 2px dashed var(--ma-color-line-strong);
  border-radius: 50%;
}

.threads__empty-mark::after {
  position: absolute;
  bottom: -3px;
  left: 6px;
  width: 8px;
  height: 8px;
  content: '';
  background: var(--ma-color-sunken);
  border-bottom: 2px dashed var(--ma-color-line-strong);
  border-left: 2px dashed var(--ma-color-line-strong);
  border-bottom-left-radius: 3px;
  transform: rotate(-18deg);
}

.threads__empty-text {
  margin: 0;
  font-size: 13px;
  color: var(--ma-color-faint);
}
</style>
