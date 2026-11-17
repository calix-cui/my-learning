<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import AgentTimeline from '@/components/chat/AgentTimeline.vue'
import ApprovalCard from '@/components/chat/ApprovalCard.vue'
import ChatComposer from '@/components/chat/ChatComposer.vue'
import ChatEmpty from '@/components/chat/ChatEmpty.vue'
import ChatMessage from '@/components/chat/ChatMessage.vue'
import MarkdownContent from '@/components/chat/MarkdownContent.vue'
import ChatToolbar from '@/components/chat/ChatToolbar.vue'
import { listSkills, mountSkill } from '@/api/skills'
import { useChatStore } from '@/stores/chat'
import { useSettingsStore } from '@/stores/settings'
import type { ChatSkill } from '@/types/api'

const MAX_LENGTH = 4000

const chat = useChatStore()
const route = useRoute()
const router = useRouter()
const settings = useSettingsStore()
const composer = ref<InstanceType<typeof ChatComposer> | null>(null)
const scroller = ref<HTMLElement | null>(null)
const skills = ref<ChatSkill[]>([])
const autoSkills = ref(false)

const hasConversation = computed(() => chat.activeId !== null)

/** 技能列表跟着当前会话走：换会话要重拉，才能标出「哪个是挂着的」 */
let skillRequest = 0
async function loadSkills() {
  const request = ++skillRequest
  const conversationId = chat.activeId
  skills.value = []
  try {
    const { items } = await listSkills(conversationId)
    if (request === skillRequest && conversationId === chat.activeId) {
      skills.value = items
      if (import.meta.env.DEV) {
        console.debug('[my-agent] skill.view.catalog', { conversationId, count: items.length })
      }
    }
  } catch {
    // 保持空列表；手动模式仍由后端读取真实挂载状态。
  }
}

const mountedSkill = computed(() => skills.value.find((item) => item.mounted) ?? null)
const skillItems = computed(() => [
  { key: 'none', label: '不挂技能' },
  ...skills.value.map((item) => ({ key: item.slug, label: item.name })),
])

async function handleSelectSkill(slug: string | null) {
  const id = chat.activeId
  if (!id || chat.sending) return
  try {
    await mountSkill(id, slug)
    if (import.meta.env.DEV) {
      console.debug('[my-agent] skill.view.mount', { conversationId: id, mounted: slug !== null })
    }
    await loadSkills()
    ElMessage.success(slug ? '已挂上技能，下次提问生效' : '已取消技能')
  } catch {
    ElMessage.error('技能切换失败，请重试')
  }
}

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

const streamingPreview = ref('')
let renderFrame: number | null = null
let unmounting = false

/** 同一帧只提交最新累计文本，等 Markdown 进入 DOM 后再读取滚动高度。 */
function scheduleMessageRender() {
  if (unmounting || renderFrame !== null) return
  renderFrame = requestAnimationFrame(() => {
    renderFrame = null
    const conversationId = chat.activeId
    streamingPreview.value = chat.streamingText
    void nextTick(() => {
      const el = scroller.value
      if (el && chat.activeId === conversationId) el.scrollTop = el.scrollHeight
    })
  })
}

function cancelMessageRender() {
  if (renderFrame === null) return
  cancelAnimationFrame(renderFrame)
  renderFrame = null
}

onBeforeUnmount(() => {
  unmounting = true
  cancelMessageRender()
})

watch(
  () => chat.activeId,
  () => {
    // 切换时立即清除旧会话的预览，下一帧读取新会话自己的文本。
    cancelMessageRender()
    streamingPreview.value = ''
    scheduleMessageRender()
  },
  { flush: 'sync' },
)

async function handleApproval(decision: 'approve' | 'reject', note?: string) {
  const ok =
    decision === 'approve' ? await chat.approveApproval(note) : await chat.rejectApproval(note)
  if (ok) scheduleMessageRender()
}

async function handleSend() {
  const content = chat.composerText
  if (!content.trim() || chat.sending || chat.loadingMessages) return
  // 失败时保留草稿，用户不用重打；成功由 store 清掉自己会话的草稿
  const skillMode = autoSkills.value ? 'auto' : 'manual'
  if (import.meta.env.DEV) {
    console.debug('[my-agent] chat.view.send', {
      conversationId: chat.activeId,
      mode: chat.agentMode ? 'agent' : 'stream',
      skillMode: chat.agentMode ? skillMode : undefined,
      chars: content.length,
    })
  }
  // 深度回答进入支持模型工具调用的 Agent 接口，普通回答走消息流接口。
  const ok = chat.agentMode
    ? await chat.sendWithAgent(content, skillMode)
    : await chat.send(content)
  if (ok) {
    composer.value?.focus()
  }
  scheduleMessageRender()
}

watch(
  () => chat.activeId,
  () => {
    void loadSkills()
  },
)
// 深度回答的步骤是逐个到达的，来一步滚一次
watch(
  () => chat.agentSteps.length,
  () => scheduleMessageRender(),
)
watch(
  () => chat.streamingText,
  (text) => {
    if (!text) streamingPreview.value = ''
    scheduleMessageRender()
  },
  { immediate: true },
)
watch(
  () => chat.messages.length,
  () => scheduleMessageRender(),
)

// 深链、刷新和历史导航都以路由参数为准。
watch(
  () => route.params.conversationId,
  async (param) => {
    if (route.name !== 'chat') return
    if (!param) {
      if (chat.activeId !== null || !chat.draft) chat.startNew()
      return
    }
    const id = Number(param)
    if (!Number.isSafeInteger(id) || id <= 0) {
      await router.replace({ name: 'chat', params: { conversationId: '' } })
      return
    }
    if (chat.activeId === id && chat.sending) return
    await chat.openConversation(id)
    if (chat.activeId === id && !chat.sending) {
      await chat.loadAgentRuns(id).catch(() => undefined)
    }
  },
  { immediate: true },
)

// 首条消息建库后更新草稿地址；删除或无法打开当前会话时回到草稿地址。
watch(
  () => chat.activeId,
  (id, previousId) => {
    if (route.name !== 'chat') return
    const param = route.params.conversationId
    if (id !== null && !param && previousId === null) {
      void router.replace({ name: 'chat', params: { conversationId: id }, query: route.query })
    } else if (id === null && param === String(previousId)) {
      void router.replace({ name: 'chat', params: { conversationId: '' }, query: route.query })
    }
  },
  { flush: 'sync' },
)

void loadSkills()
</script>

<template>
  <div class="chat">
    <ChatToolbar
      :title="hasConversation ? chat.activeTitle : ''"
      :model="modelLabel"
      :skill-name="mountedSkill?.name ?? ''"
      :skill-items="skillItems"
      :skill-disabled="!hasConversation || chat.sending"
      @select-skill="handleSelectSkill"
    />

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

        <!-- 首批 Markdown 渲染前保留等待提示。 -->
        <div v-if="streamingPreview" class="chat__row chat__row--assistant chat__bubble--streaming">
          <MarkdownContent :content="streamingPreview" />
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
      :disabled="chat.loadingMessages"
      :max-length="MAX_LENGTH"
      :agent-mode="chat.agentMode"
      :auto-skills="autoSkills"
      @send="handleSend"
      @toggle-agent-mode="chat.toggleAgentMode(!chat.agentMode)"
      @toggle-auto-skills="autoSkills = !autoSkills"
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

.chat__bubble.chat__bubble--streaming {
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
