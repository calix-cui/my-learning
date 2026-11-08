<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ChatDotRound, Delete, Edit, Plus } from '@element-plus/icons-vue'

import {
  createConversation,
  deleteConversation,
  getConversation,
  listConversations,
  renameConversation,
  sendMessageStream,
} from '@/api/chat'
import type { ChatConversationListItem, ChatMessage } from '@/types/api'
import { renderMarkdown } from '@/utils/markdown'

const conversations = ref<ChatConversationListItem[]>([])
/** 当前打开的会话；null 表示还没选（空态） */
const activeId = ref<number | null>(null)
const activeTitle = ref('')
const messages = ref<ChatMessage[]>([])
const draft = ref('')
const loadingList = ref(false)
const loadingMessages = ref(false)
const sending = ref(false)
/** 流式过程中已收到的文本；空字符串表示还在等第一个字符 */
const streamingText = ref('')
const messageBody = ref<HTMLElement | null>(null)

const canSend = computed(
  () => !sending.value && activeId.value !== null && draft.value.trim() !== '',
)
const showEmptyState = computed(() => !loadingMessages.value && messages.value.length === 0)

/** 顶部标签显示真正回话的模型（流式与非流式都会写进 assistant 消息） */
const modelLabel = computed(() => {
  for (let i = messages.value.length - 1; i >= 0; i -= 1) {
    const model = messages.value[i].model
    if (model) return model
  }
  return ''
})

/** 消息区滚到底：新消息、切换会话都要滚；Markdown 渲染后高度会变，等一帧再滚 */
function scrollToBottom() {
  void nextTick(() => {
    requestAnimationFrame(() => {
      const el = messageBody.value
      if (el) {
        el.scrollTop = el.scrollHeight
      }
    })
  })
}

/** 列表里替换某条会话的本地状态，避免整表重拉 */
function patchConversation(id: number, patch: Partial<ChatConversationListItem>) {
  conversations.value = conversations.value.map((item) =>
    item.id === id ? { ...item, ...patch } : item,
  )
}

async function loadConversations() {
  loadingList.value = true
  try {
    const page = await listConversations()
    conversations.value = page.items
  } finally {
    loadingList.value = false
  }
}

async function openConversation(id: number) {
  activeId.value = id
  loadingMessages.value = true
  messages.value = []
  try {
    const detail = await getConversation(id)
    activeTitle.value = detail.title
    messages.value = detail.messages
    scrollToBottom()
  } catch {
    // 会话可能已被别处删除：退回空态并刷新列表
    activeId.value = null
    activeTitle.value = ''
    await loadConversations()
  } finally {
    loadingMessages.value = false
  }
}

async function handleCreate() {
  const created = await createConversation()
  conversations.value = [{ ...created, message_count: 0 }, ...conversations.value]
  activeId.value = created.id
  activeTitle.value = created.title
  messages.value = []
}

async function handleRename(item: ChatConversationListItem) {
  try {
    const { value } = await ElMessageBox.prompt('输入新的会话名称', '重命名会话', {
      inputValue: item.title,
      inputValidator: (input) => (input.trim() ? true : '名称不能只包含空白'),
      confirmButtonText: '保存',
      cancelButtonText: '取消',
    })
    const updated = await renameConversation(item.id, value)
    patchConversation(item.id, { title: updated.title })
    if (activeId.value === item.id) {
      activeTitle.value = updated.title
    }
    ElMessage.success('会话名称已更新')
  } catch {
    // 取消或接口失败（失败已由拦截器提示）
  }
}

async function handleDelete(item: ChatConversationListItem) {
  try {
    await ElMessageBox.confirm(`删除会话「${item.title}」及其全部消息？`, '删除会话', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  await deleteConversation(item.id)
  ElMessage.success('删除成功')
  conversations.value = conversations.value.filter((row) => row.id !== item.id)
  if (activeId.value === item.id) {
    const next = conversations.value[0]
    if (next) {
      await openConversation(next.id)
    } else {
      activeId.value = null
      activeTitle.value = ''
      messages.value = []
    }
  }
}

async function handleSend() {
  const content = draft.value.trim()
  if (!content || activeId.value === null || sending.value) {
    return
  }
  const id = activeId.value
  // 乐观插入用户消息：等服务端 meta 回来再换成正身（带真实 id 与时间）
  const optimisticId = -Date.now()
  messages.value = [
    ...messages.value,
    {
      id: optimisticId,
      conversation_id: id,
      role: 'user',
      content,
      model: null,
      create_time: '',
    },
  ]
  streamingText.value = ''
  sending.value = true
  scrollToBottom()

  let currentUserId = optimisticId
  try {
    await sendMessageStream(id, content, {
      onMeta: (message) => {
        currentUserId = message.id
        messages.value = messages.value.map((m) => (m.id === optimisticId ? message : m))
      },
      onDelta: (text) => {
        streamingText.value += text
        scrollToBottom()
      },
      onDone: (event) => {
        // 成功才清空输入框：失败时保留原文，用户不用重打
        draft.value = ''
        streamingText.value = ''
        messages.value = [...messages.value, event.assistant_message]
        if (activeId.value === id) {
          activeTitle.value = event.conversation_title
        }
        patchConversation(id, {
          title: event.conversation_title,
          message_count: event.message_count,
          update_time: event.assistant_message.create_time,
        })
        // 最近活动变了，重排列表让它回到第一位
        conversations.value = [...conversations.value].sort((a, b) =>
          b.update_time.localeCompare(a.update_time),
        )
        scrollToBottom()
      },
    })
  } catch (error) {
    // 后端已回滚这次提问，前端也要撤掉乐观消息
    messages.value = messages.value.filter((m) => m.id !== currentUserId)
    streamingText.value = ''
    ElMessage.error(error instanceof Error ? error.message : '发送失败，请稍后重试')
  } finally {
    sending.value = false
  }
}

/** Enter 发送，Shift+Enter 换行 */
function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    void handleSend()
  }
}

watch(activeId, () => scrollToBottom())

onMounted(async () => {
  await loadConversations()
  const first = conversations.value[0]
  if (first) {
    await openConversation(first.id)
  }
})
</script>

<template>
  <div class="chat">
    <aside class="chat__aside">
      <div class="chat__aside-head">
        <span class="chat__aside-title">会话</span>
        <el-button type="primary" :icon="Plus" size="small" class="chat__new" @click="handleCreate">
          新建会话
        </el-button>
      </div>

      <div v-loading="loadingList" class="chat__list">
        <p v-if="!conversations.length" class="chat__list-empty">还没有会话，点「新建会话」开始</p>
        <div
          v-for="item in conversations"
          :key="item.id"
          class="chat__item"
          :class="{ 'chat__item--active': item.id === activeId }"
          @click="openConversation(item.id)"
        >
          <div class="chat__item-main">
            <span class="chat__item-title">{{ item.title }}</span>
            <span class="chat__item-meta">
              {{ item.message_count }} 条 · {{ item.update_time.slice(5, 16) }}
            </span>
          </div>
          <span class="chat__item-actions" @click.stop>
            <el-button link :icon="Edit" size="small" title="重命名" @click="handleRename(item)" />
            <el-button link :icon="Delete" size="small" title="删除" @click="handleDelete(item)" />
          </span>
        </div>
      </div>
    </aside>

    <section class="chat__main">
      <header class="chat__head">
        <div class="chat__head-text">
          <h2 class="chat__title">{{ activeTitle || '对话' }}</h2>
          <span class="chat__hint">
            {{ activeId === null ? '选择或新建一个会话' : `${messages.length} 条消息` }}
          </span>
        </div>
        <el-tag v-if="modelLabel" size="small" type="info" effect="plain">
          模型：{{ modelLabel }}
        </el-tag>
      </header>

      <div ref="messageBody" v-loading="loadingMessages" class="chat__body">
        <div v-if="showEmptyState" class="chat__empty">
          <el-icon :size="34" class="chat__empty-icon"><ChatDotRound /></el-icon>
          <p class="chat__empty-title">
            {{ activeId === null ? '还没有选择会话' : '开始一个新对话' }}
          </p>
          <p class="chat__empty-desc">
            在下方输入问题，例如「帮我给可口可乐设计三档定价」。首条消息会自动作为会话标题。
          </p>
        </div>

        <div
          v-for="message in messages"
          :key="message.id"
          class="chat__row"
          :class="`chat__row--${message.role}`"
        >
          <div class="chat__avatar">{{ message.role === 'user' ? '我' : 'AI' }}</div>
          <div class="chat__bubble">
            <!-- 模型的回复是 Markdown；用户消息按纯文本显示，保留换行 -->
            <div
              v-if="message.role === 'assistant'"
              class="chat__content chat__content--md"
              v-html="renderMarkdown(message.content)"
            />
            <p v-else class="chat__content">{{ message.content }}</p>
            <span class="chat__time">
              {{ message.create_time.slice(11, 16) }}
              <template v-if="message.model"> · {{ message.model }}</template>
            </span>
          </div>
        </div>

        <div v-if="sending" class="chat__row chat__row--assistant">
          <div class="chat__avatar">AI</div>
          <div v-if="streamingText" class="chat__bubble">
            <div class="chat__content chat__content--md" v-html="renderMarkdown(streamingText)" />
            <span class="chat__time">正在输入…</span>
          </div>
          <div v-else class="chat__bubble chat__bubble--typing">
            <span class="chat__dot" />
            <span class="chat__dot" />
            <span class="chat__dot" />
            <span class="chat__typing-text">正在回复…</span>
          </div>
        </div>
      </div>

      <footer class="chat__composer">
        <el-input
          v-model="draft"
          type="textarea"
          :rows="3"
          resize="none"
          maxlength="4000"
          placeholder="输入消息，Enter 发送，Shift + Enter 换行"
          :disabled="sending || activeId === null"
          @keydown="handleKeydown"
        />
        <div class="chat__composer-foot">
          <span class="chat__counter">{{ draft.length }} / 4000</span>
          <el-button type="primary" :loading="sending" :disabled="!canSend" @click="handleSend">
            发送
          </el-button>
        </div>
      </footer>
    </section>
  </div>
</template>

<style scoped>
.chat {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: var(--pa-space-4);
  height: calc(100vh - var(--pa-topbar-height) - var(--pa-content-padding) * 2);
  min-height: 520px;
}

.chat__aside {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background-color: var(--pa-color-bg-card);
  border: 1px solid var(--pa-color-border);
  border-radius: var(--pa-radius);
  box-shadow: var(--pa-shadow-sm);
}

.chat__aside-head {
  display: flex;
  flex: none;
  align-items: center;
  justify-content: space-between;
  gap: var(--pa-space-2);
  padding: var(--pa-space-3) var(--pa-space-4);
  border-bottom: 1px solid var(--pa-color-border-light);
}

.chat__aside-title {
  color: var(--pa-color-text-primary);
  font-size: var(--pa-font-size-body);
  font-weight: 600;
}

.chat__list {
  flex: 1;
  min-height: 0;
  padding: var(--pa-space-2);
  overflow-y: auto;
}

.chat__list-empty {
  margin: var(--pa-space-4) 0;
  color: var(--pa-color-text-muted);
  font-size: var(--pa-font-size-caption);
  text-align: center;
}

.chat__item {
  display: flex;
  align-items: center;
  gap: var(--pa-space-2);
  padding: var(--pa-space-2) var(--pa-space-3);
  cursor: pointer;
  border-radius: var(--pa-radius-sm);
}

.chat__item:hover {
  background-color: var(--pa-color-bg-hover);
}

.chat__item--active {
  background-color: var(--pa-color-primary-soft);
}

.chat__item-main {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-width: 0;
  gap: 2px;
}

.chat__item-title {
  overflow: hidden;
  color: var(--pa-color-text-primary);
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat__item--active .chat__item-title {
  color: var(--pa-color-primary);
  font-weight: 600;
}

.chat__item-meta {
  color: var(--pa-color-text-muted);
  font-size: 11px;
}

.chat__item-actions {
  display: flex;
  flex: none;
  align-items: center;
  gap: 2px;
  opacity: 0;
  transition: opacity 0.15s ease;
}

.chat__item:hover .chat__item-actions,
.chat__item--active .chat__item-actions {
  opacity: 1;
}

.chat__main {
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
  background-color: var(--pa-color-bg-card);
  border: 1px solid var(--pa-color-border);
  border-radius: var(--pa-radius);
  box-shadow: var(--pa-shadow-sm);
}

.chat__head {
  display: flex;
  flex: none;
  align-items: center;
  justify-content: space-between;
  gap: var(--pa-space-4);
  padding: var(--pa-space-3) var(--pa-space-4);
  border-bottom: 1px solid var(--pa-color-border-light);
}

.chat__head-text {
  display: flex;
  align-items: baseline;
  gap: var(--pa-space-2);
  min-width: 0;
}

.chat__title {
  margin: 0;
  overflow: hidden;
  color: var(--pa-color-text-primary);
  font-size: var(--pa-font-size-subtitle);
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat__hint {
  flex: none;
  color: var(--pa-color-text-muted);
  font-size: var(--pa-font-size-caption);
}

.chat__body {
  flex: 1;
  min-height: 0;
  padding: var(--pa-space-4);
  overflow-y: auto;
  background-color: var(--pa-color-bg-page);
}

.chat__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: var(--pa-space-2);
  text-align: center;
}

.chat__empty-icon {
  color: var(--pa-color-primary-100);
}

.chat__empty-title {
  margin: 0;
  color: var(--pa-color-text-regular);
  font-size: var(--pa-font-size-body);
  font-weight: 600;
}

.chat__empty-desc {
  max-width: 380px;
  margin: 0;
  color: var(--pa-color-text-muted);
  font-size: var(--pa-font-size-caption);
  line-height: 1.7;
}

.chat__row {
  display: flex;
  gap: var(--pa-space-2);
  margin-bottom: var(--pa-space-4);
}

.chat__row--user {
  flex-direction: row-reverse;
}

.chat__avatar {
  display: flex;
  flex: none;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  color: var(--pa-color-primary-dark);
  font-size: var(--pa-font-size-caption);
  font-weight: 600;
  background-color: var(--pa-color-primary-100);
  border-radius: 50%;
}

.chat__row--assistant .chat__avatar {
  color: var(--pa-color-success);
  background-color: var(--pa-color-success-soft);
}

.chat__bubble {
  max-width: min(620px, 72%);
  padding: 10px var(--pa-space-3);
  background-color: var(--pa-color-bg-card);
  border: 1px solid var(--pa-color-border);
  border-radius: var(--pa-radius);
  box-shadow: var(--pa-shadow-sm);
}

.chat__row--user .chat__bubble {
  background-color: var(--pa-color-primary-soft);
  border-color: var(--pa-color-primary-100);
}

.chat__content {
  margin: 0;
  color: var(--pa-color-text-primary);
  font-size: 13px;
  line-height: 1.75;
  white-space: pre-wrap;
  word-break: break-word;
}

.chat__content--md {
  white-space: normal;
}

.chat__content--md :deep(p) {
  margin: 0 0 8px;
}

.chat__content--md :deep(p:last-child) {
  margin-bottom: 0;
}

.chat__content--md :deep(h1),
.chat__content--md :deep(h2),
.chat__content--md :deep(h3),
.chat__content--md :deep(h4) {
  margin: 12px 0 6px;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.5;
}

.chat__content--md :deep(h1:first-child),
.chat__content--md :deep(h2:first-child),
.chat__content--md :deep(h3:first-child),
.chat__content--md :deep(h4:first-child) {
  margin-top: 0;
}

.chat__content--md :deep(ul),
.chat__content--md :deep(ol) {
  margin: 0 0 8px;
  padding-left: 20px;
}

.chat__content--md :deep(li) {
  margin-bottom: 2px;
}

.chat__content--md :deep(strong) {
  font-weight: 600;
  color: var(--pa-color-text-primary);
}

.chat__content--md :deep(a) {
  color: var(--pa-color-primary);
  text-decoration: underline;
}

.chat__content--md :deep(code) {
  padding: 1px 5px;
  border-radius: 4px;
  background-color: var(--pa-color-border-light);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
}

.chat__content--md :deep(pre) {
  margin: 0 0 8px;
  padding: 10px 12px;
  border-radius: 8px;
  background-color: var(--pa-color-border-light);
  overflow-x: auto;
}

.chat__content--md :deep(pre code) {
  padding: 0;
  background: none;
}

.chat__content--md :deep(blockquote) {
  margin: 0 0 8px;
  padding-left: 10px;
  border-left: 3px solid var(--pa-color-border);
  color: var(--pa-color-text-secondary);
}

.chat__content--md :deep(hr) {
  margin: 10px 0;
  border: none;
  border-top: 1px solid var(--pa-color-border);
}

.chat__content--md :deep(table) {
  margin: 0 0 8px;
  border-collapse: collapse;
  font-size: 12px;
}

.chat__content--md :deep(th),
.chat__content--md :deep(td) {
  padding: 4px 8px;
  border: 1px solid var(--pa-color-border);
  text-align: left;
}

.chat__time {
  display: block;
  margin-top: var(--pa-space-1);
  color: var(--pa-color-text-muted);
  font-size: 11px;
}

.chat__bubble--typing {
  display: flex;
  align-items: center;
  gap: 4px;
}

.chat__dot {
  width: 5px;
  height: 5px;
  background-color: var(--pa-color-text-muted);
  border-radius: 50%;
  animation: chat-blink 1.2s infinite ease-in-out;
}

.chat__dot:nth-child(2) {
  animation-delay: 0.2s;
}

.chat__dot:nth-child(3) {
  animation-delay: 0.4s;
}

.chat__typing-text {
  margin-left: var(--pa-space-2);
  color: var(--pa-color-text-muted);
  font-size: var(--pa-font-size-caption);
}

@keyframes chat-blink {
  0%,
  100% {
    opacity: 0.25;
  }
  50% {
    opacity: 1;
  }
}

.chat__composer {
  flex: none;
  padding: var(--pa-space-3) var(--pa-space-4) var(--pa-space-4);
  border-top: 1px solid var(--pa-color-border-light);
}

.chat__composer-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: var(--pa-space-2);
}

.chat__counter {
  color: var(--pa-color-text-muted);
  font-size: 11px;
}
</style>
