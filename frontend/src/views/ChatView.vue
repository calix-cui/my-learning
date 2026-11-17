<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AgentTimeline from '@/components/chat/AgentTimeline.vue'
import ApprovalCard from '@/components/chat/ApprovalCard.vue'
import ChatComposer from '@/components/chat/ChatComposer.vue'
import ChatEmpty from '@/components/chat/ChatEmpty.vue'
import ChatMessage from '@/components/chat/ChatMessage.vue'
import MarkdownContent from '@/components/chat/MarkdownContent.vue'
import ChatToolbar from '@/components/chat/ChatToolbar.vue'
import { useChatStore } from '@/stores/chat'
import { useSettingsStore } from '@/stores/settings'
import { useSkillsStore } from '@/stores/skills'

const MAX_LENGTH = 4000

const chat = useChatStore()
const route = useRoute()
const router = useRouter()
const settings = useSettingsStore()
const composer = ref<InstanceType<typeof ChatComposer> | null>(null)
const scroller = ref<HTMLElement | null>(null)
const skillCatalog = useSkillsStore()
const autoSkills = ref(true)

const hasConversation = computed(() => chat.activeId !== null)

const selectedSkill = computed(
  () => skillCatalog.items.find((item) => item.key === chat.selectedSkillKey) ?? null,
)
const skillItems = computed(() => [
  { key: 'none', label: '取消本次选择' },
  ...skillCatalog.items.map((item) => ({
    key: item.key,
    label: `${item.name} · ${item.source === 'builtin' ? '内置' : '本地'} (${item.key})`,
  })),
])

function handleSelectSkill(key: string | null) {
  if (!chat.sending) chat.selectedSkillKey = key
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
  if (!content.trim() || chat.sending || chat.loadingMessages || chat.pendingApproval) return
  // 失败时保留草稿，用户不用重打；成功由 store 清掉自己会话的草稿
  const skillMode = autoSkills.value ? 'auto' : 'manual'
  const effort = chat.agentMode && settings.model?.supports_reasoning_effort ? 'high' : 'none'
  if (import.meta.env.DEV) {
    console.debug('[my-agent] chat.view.send', {
      conversationId: chat.activeId,
      reasoningEffort: effort,
      skillMode,
      chars: content.length,
    })
  }
  if (chat.selectedSkillKey && !selectedSkill.value) return
  const ok = await chat.send(content, skillMode, effort, skillCatalog.version || undefined)
  if (ok) {
    composer.value?.focus()
  }
  scheduleMessageRender()
}

// 执行步骤逐个到达，新增步骤时跟随滚动。
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
  () => chat.messages.at(-1)?.id,
  () => scheduleMessageRender(),
)

async function loadOlderMessages() {
  const el = scroller.value
  const conversationId = chat.activeId
  if (!el) return
  const previousHeight = el.scrollHeight
  const previousTop = el.scrollTop
  if (await chat.loadOlderMessages()) {
    await nextTick()
    if (chat.activeId === conversationId && scroller.value === el) {
      el.scrollTop = previousTop + el.scrollHeight - previousHeight
    }
  }
}

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
</script>

<template>
  <div class="chat">
    <ChatToolbar
      :title="hasConversation ? chat.activeTitle : ''"
      :model="modelLabel"
      :skill-name="selectedSkill?.name ?? chat.selectedSkillKey ?? ''"
      :skill-items="skillItems"
      :skill-disabled="chat.sending || skillCatalog.loading || !!chat.pendingApproval"
      @select-skill="handleSelectSkill"
    />

    <p
      v-if="chat.selectedSkillKey && !selectedSkill && !skillCatalog.loading"
      class="chat__skill-status"
      role="status"
    >
      选中的 Skill 已移除或不可用，请重新选择。
    </p>
    <p v-else-if="skillCatalog.error" class="chat__skill-status" role="status">
      Skill 目录读取失败，可在设置中重新扫描。
    </p>

    <div ref="scroller" v-loading="chat.loadingMessages" class="chat__scroll">
      <ChatEmpty v-if="showEmptyState" />

      <div v-else class="chat__col">
        <button
          v-if="chat.hasOlderMessages"
          type="button"
          class="chat__older u-tint"
          :disabled="chat.loadingOlderMessages || chat.sending"
          @click="loadOlderMessages"
        >
          {{ chat.loadingOlderMessages ? '正在加载…' : '加载更早消息' }}
        </button>

        <details v-if="chat.legacyRuns.length" class="chat__legacy">
          <summary>旧执行记录</summary>
          <AgentTimeline
            v-for="run in chat.legacyRuns"
            :key="run.id"
            :steps="chat.replayDetails[run.id]?.steps ?? []"
            :running="false"
            lazy
            :load-status="chat.replayDetails[run.id]?.status"
            @request-steps="chat.loadExecutionSteps(run.id)"
          />
        </details>

        <template v-for="message in chat.messages" :key="message.id">
          <ChatMessage :message="message" />
          <AgentTimeline
            v-if="message.id === chat.activeUserMessageId"
            :steps="chat.agentSteps"
            :running="chat.agentRunning"
          />
          <template v-else>
            <AgentTimeline
              v-for="run in chat.runsByMessage[message.id]"
              :key="run.id"
              :steps="chat.replayDetails[run.id]?.steps ?? []"
              :running="false"
              lazy
              :load-status="chat.replayDetails[run.id]?.status"
              @request-steps="chat.loadExecutionSteps(run.id)"
            />
          </template>
        </template>

        <MarkdownContent
          v-if="streamingPreview"
          class="chat__bubble--streaming"
          :content="streamingPreview"
        />

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
      :disabled="
        chat.loadingMessages ||
        !!chat.pendingApproval ||
        skillCatalog.loading ||
        (!!chat.selectedSkillKey && !selectedSkill)
      "
      :max-length="MAX_LENGTH"
      :agent-mode="chat.agentMode"
      :supports-reasoning="settings.model?.supports_reasoning_effort"
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

.chat__skill-status {
  padding-inline: var(--ma-space-md);
  color: var(--ma-color-muted);
}

.chat__older,
.chat__legacy {
  color: var(--ma-color-muted);
  font: inherit;
}

.chat__older {
  display: block;
  margin-inline: auto;
  background: transparent;
  border: 0;
  border-radius: var(--ma-radius-sm);
  cursor: pointer;
}

.chat__legacy > summary {
  cursor: pointer;
}

.chat__col {
  max-width: var(--ma-reading-width);
  margin: 0 auto;
}
</style>
