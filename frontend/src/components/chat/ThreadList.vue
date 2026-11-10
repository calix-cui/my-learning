<script setup lang="ts">
/** 侧栏会话区：整宽「新建会话」+ 会话列表。 */
import SoftButton from '@/components/ui/SoftButton.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import ThreadItem from '@/components/chat/ThreadItem.vue'
import { useChatStore } from '@/stores/chat'

const chat = useChatStore()

function open(id: number) {
  void chat.openConversation(id)
}
</script>

<template>
  <div class="threads">
    <SoftButton class="chat__new" block @click="chat.createNew()">
      <AppIcon name="plus" :size="16" />
      新建会话
    </SoftButton>

    <div v-loading="chat.loadingList" class="threads__list">
      <p v-if="!chat.conversations.length" class="threads__empty">还没有会话</p>

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
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.threads__empty {
  margin: 4px 10px;
  font-size: 13px;
  color: var(--ma-color-faint);
}
</style>
