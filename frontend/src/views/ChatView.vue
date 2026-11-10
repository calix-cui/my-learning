<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { ChatDotRound, Plus } from '@element-plus/icons-vue'

import ChatComposer from '@/components/chat/ChatComposer.vue'
import ChatMessage from '@/components/chat/ChatMessage.vue'
import { useChatStore } from '@/stores/chat'

const MAX_LENGTH = 4000

const chat = useChatStore()
const draft = ref('')
const composer = ref<InstanceType<typeof ChatComposer> | null>(null)
const scroller = ref<HTMLElement | null>(null)

const hasConversation = computed(() => chat.activeId !== null)
const showEmptyState = computed(
  () => !chat.loadingMessages && chat.messages.length === 0 && !chat.streamingText,
)

const subtitle = computed(() => {
  if (!hasConversation.value) return '选择或新建一个会话'
  return `${chat.messages.length} 条消息`
})

/** 消息区滚到底：新消息、切换会话、Markdown 渲染后高度变化都要滚 */
function scrollToBottom() {
  void nextTick(() => {
    requestAnimationFrame(() => {
      const el = scroller.value
      if (el) el.scrollTop = el.scrollHeight
    })
  })
}

async function handleSend() {
  const content = draft.value
  if (!content.trim()) return
  // 失败时保留草稿，用户不用重打；成功才清空
  const ok = await chat.send(content)
  if (ok) {
    draft.value = ''
    composer.value?.focus()
  }
  scrollToBottom()
}

async function handleCreate() {
  await chat.createNew()
  composer.value?.focus()
}

watch(() => chat.activeId, scrollToBottom)
watch(() => chat.streamingText, scrollToBottom)
watch(
  () => chat.messages.length,
  () => scrollToBottom(),
)

onMounted(async () => {
  if (!chat.conversations.length) {
    await chat.loadConversations()
  }
  // 直接刷新页面时带回最后一个会话；没有就留在空态
  if (chat.activeId === null && chat.conversations.length) {
    await chat.openConversation(chat.conversations[0].id)
  }
})
</script>

<template>
  <div class="chat">
    <header class="chat__head">
      <div class="chat__head-text">
        <h2 class="chat__title">
          <el-icon class="chat__title-icon"><ChatDotRound /></el-icon>
          {{ hasConversation ? chat.activeTitle : '对话' }}
        </h2>
        <p class="chat__sub">{{ subtitle }}</p>
      </div>
    </header>

    <div ref="scroller" v-loading="chat.loadingMessages" class="chat__scroll">
      <div v-if="showEmptyState" class="chat__empty">
        <p class="chat__empty-title">
          {{ hasConversation ? '还没有消息' : '还没有选择会话' }}
        </p>
        <p class="chat__empty-desc">
          {{
            hasConversation
              ? '在下方输入框说点什么，助手会记住这次对话的前后文。'
              : '在左侧选一个会话，或新建一个。首条消息会自动作为会话标题。'
          }}
        </p>
        <el-button v-if="!hasConversation" type="primary" :icon="Plus" @click="handleCreate">
          新建会话
        </el-button>
      </div>

      <div v-else class="chat__col">
        <ChatMessage v-for="message in chat.messages" :key="message.id" :message="message" />

        <!-- 流式过程中的临时气泡：先显示已收到的半截文本，收到首字前显示三点 -->
        <div v-if="chat.streamingText" class="chat__row chat__row--assistant">
          <span class="chat__who"><i />助手</span>
          <div class="chat__bubble chat__bubble--streaming">
            <div class="chat__content">{{ chat.streamingText }}</div>
          </div>
          <span class="chat__meta">正在输入…</span>
        </div>
        <div v-else-if="chat.sending" class="chat__row chat__row--assistant">
          <span class="chat__who"><i />助手</span>
          <div class="chat__bubble chat__bubble--streaming">
            <span class="chat__dots"><i /><i /><i /></span>
          </div>
          <!-- 首字之前也要给一句状态，否则用户只看到三个点在跳 -->
          <span class="chat__meta">正在输入…</span>
        </div>
      </div>
    </div>

    <ChatComposer
      ref="composer"
      v-model="draft"
      :sending="chat.sending"
      :disabled="!hasConversation"
      :max-length="MAX_LENGTH"
      @send="handleSend"
    />
  </div>
</template>

<style scoped>
.chat {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
}

.chat__head {
  display: flex;
  flex: none;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 40px 12px;
}

.chat__title {
  display: flex;
  gap: 8px;
  align-items: center;
  margin: 0;
  overflow: hidden;
  font-size: 17px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat__title-icon {
  color: var(--ma-color-faint);
}

.chat__sub {
  margin: 2px 0 0;
  font-size: 13px;
  color: var(--ma-color-muted);
}

.chat__scroll {
  flex: 1;
  min-height: 0;
  padding: 12px 40px 24px;
  overflow-y: auto;
}

.chat__col {
  max-width: var(--ma-reading-width);
  margin: 0 auto;
}

/* 空态：标题用衬线，与登录页呼应；不放大插图 */
.chat__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  max-width: 420px;
  margin: 0 auto;
  text-align: center;
}

.chat__empty-title {
  margin: 0 0 8px;
  font-family: var(--ma-font-serif);
  font-size: 22px;
  font-weight: 600;
  letter-spacing: 0.01em;
}

.chat__empty-desc {
  margin: 0 0 20px;
  font-size: 13px;
  line-height: 1.8;
  color: var(--ma-color-muted);
}

.chat__bubble--streaming {
  max-width: 100%;
  padding: 12px 16px;
  background: var(--ma-color-surface);
  border: 1px solid var(--ma-color-line);
  border-radius: var(--ma-radius-lg);
}

.chat__dots {
  display: inline-flex;
  gap: 4px;
  align-items: center;
}

.chat__dots i {
  width: 6px;
  height: 6px;
  background: var(--ma-color-faint);
  border-radius: 999px;
  animation: chat-dot 1.2s ease-in-out infinite;
}

.chat__dots i:nth-child(2) {
  animation-delay: 0.15s;
}

.chat__dots i:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes chat-dot {
  0%,
  60%,
  100% {
    opacity: 0.25;
    transform: translateY(0);
  }

  30% {
    opacity: 1;
    transform: translateY(-2px);
  }
}

@media (prefers-reduced-motion: reduce) {
  .chat__dots i {
    animation: none;
  }
}
</style>
