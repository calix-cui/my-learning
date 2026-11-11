<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import AgentTimeline from '@/components/chat/AgentTimeline.vue'
import ApprovalCard from '@/components/chat/ApprovalCard.vue'
import ChatComposer from '@/components/chat/ChatComposer.vue'
import ChatEmpty from '@/components/chat/ChatEmpty.vue'
import ChatMessage from '@/components/chat/ChatMessage.vue'
import ChatToolbar from '@/components/chat/ChatToolbar.vue'
import { useChatStore } from '@/stores/chat'
import { useSettingsStore } from '@/stores/settings'

const MAX_LENGTH = 4000

const chat = useChatStore()
const settings = useSettingsStore()
const composer = ref<InstanceType<typeof ChatComposer> | null>(null)
const scroller = ref<HTMLElement | null>(null)

const hasConversation = computed(() => chat.activeId !== null)

/** 优先显示账号里配置的模型；没配过才退回上一条回复用的模型 */
const modelLabel = computed(() => {
  const configured = settings.modelLabel
  return configured && configured !== '未配置' ? configured : chat.modelLabel
})
/** 空态只在「有会话但还没有消息」时出现；没有会话时也显示招呼语，让首屏不空 */
const showEmptyState = computed(
  () => !chat.loadingMessages && chat.messages.length === 0 && !chat.streamingText,
)

/** 时间线跟着「这一次运行」走：有步骤或正在跑才显示 */
const showTimeline = computed(() => chat.agentSteps.length > 0 || chat.agentRunning)

/** 时间线插在最后一条用户消息之后，保证「问 → 过程 → 答」的阅读顺序 */
const lastUserIndex = computed(() => {
  for (let i = chat.messages.length - 1; i >= 0; i -= 1) {
    if (chat.messages[i].role === 'user') return i
  }
  return -1
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

async function handleApproval(decision: 'approve' | 'reject', note?: string) {
  const ok =
    decision === 'approve' ? await chat.approveApproval(note) : await chat.rejectApproval(note)
  if (ok) scrollToBottom()
}

async function handleSend() {
  const content = chat.composerText
  if (!content.trim()) return
  // 失败时保留草稿，用户不用重打；成功由 store 清掉自己会话的草稿
  const ok = chat.agentMode ? await chat.sendWithAgent(content) : await chat.send(content)
  if (ok) {
    composer.value?.focus()
  }
  scrollToBottom()
}

watch(() => chat.activeId, scrollToBottom)
// 深度回答的步骤是逐个到达的，来一步滚一次
watch(
  () => chat.agentSteps.length,
  () => scrollToBottom(),
)
watch(() => chat.streamingText, scrollToBottom)
watch(
  () => chat.messages.length,
  () => scrollToBottom(),
)

onMounted(async () => {
  if (!chat.conversations.length) {
    await chat.loadConversations()
  }
  // 直接刷新页面时带回最后一个会话；没有就进草稿态（新会话界面）
  if (chat.activeId === null) {
    if (chat.conversations.length) await chat.openConversation(chat.conversations[0].id)
    else chat.startNew()
  }
  // 刷新回来时把上一次的工具过程也带回来
  if (chat.activeId !== null) {
    await chat.loadAgentRuns(chat.activeId)
  }
})
</script>

<template>
  <div class="chat">
    <ChatToolbar :title="hasConversation ? chat.activeTitle : ''" :model="modelLabel" />

    <div ref="scroller" v-loading="chat.loadingMessages" class="chat__scroll">
      <ChatEmpty v-if="showEmptyState" />

      <div v-else class="chat__col">
        <template v-for="(message, index) in chat.messages" :key="message.id">
          <ChatMessage :message="message" />
          <AgentTimeline
            v-if="showTimeline && index === lastUserIndex"
            class="chat__timeline"
            :steps="chat.agentSteps"
            :running="chat.agentRunning"
          />
        </template>

        <!-- 流式过程中的临时气泡：先显示已收到的半截文本，收到首字前显示三点 -->
        <div v-if="chat.streamingText" class="chat__row chat__row--assistant">
          <span class="chat__who"><i />助手</span>
          <div class="chat__bubble chat__bubble--streaming">
            <div class="chat__content">{{ chat.streamingText }}</div>
          </div>
          <span class="chat__meta">正在输入…</span>
        </div>
        <div
          v-else-if="chat.sending && !(chat.agentMode && chat.agentSteps.length)"
          class="chat__row chat__row--assistant"
        >
          <span class="chat__who"><i />助手</span>
          <div class="chat__bubble chat__bubble--streaming">
            <span class="chat__dots"><i /><i /><i /></span>
          </div>
          <!-- 首字之前也要给一句状态，否则用户只看到三个点在跳 -->
          <span class="chat__meta">正在输入…</span>
        </div>

        <!-- 写操作挂起时服务端已暂停，卡片插在消息列末尾等用户决定 -->
        <ApprovalCard
          v-if="chat.pendingApproval"
          :approval="chat.pendingApproval"
          :busy="chat.sending"
          @decide="handleApproval"
        />
      </div>
    </div>

    <ChatComposer
      ref="composer"
      v-model="chat.composerText"
      :sending="chat.sending"
      :disabled="false"
      :max-length="MAX_LENGTH"
      :agent-mode="chat.agentMode"
      @send="handleSend"
      @toggle-agent-mode="chat.toggleAgentMode(!chat.agentMode)"
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

.chat__bubble--streaming {
  max-width: 100%;
  /* 按内容收窄：三个点的占位才不会拉成一整条 */
  width: fit-content;
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
