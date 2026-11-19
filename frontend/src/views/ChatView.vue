<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import ChatMessageList from '@/components/chat/ChatMessageList.vue'
import ChatComposer from '@/components/chat/ChatComposer.vue'
import ChatEmpty from '@/components/chat/ChatEmpty.vue'
import ChatToolbar from '@/components/chat/ChatToolbar.vue'
import { useChatRoute } from '@/composables/useChatRoute'
import { useChatScroll } from '@/composables/useChatScroll'
import { useChatStore } from '@/stores/chat'
import { useSettingsStore } from '@/stores/settings'
import { useSkillsStore } from '@/stores/skills'

const MAX_LENGTH = 4000

const chat = useChatStore()
const settings = useSettingsStore()
const composer = ref<InstanceType<typeof ChatComposer> | null>(null)
const skillCatalog = useSkillsStore()
const autoSkills = ref(true)

const hasConversation = computed(() => chat.activeId !== null)

/** 恢复提示可以收起来：收起后不改变任何状态，只是不再占地方 */
const recoveryDismissed = ref(false)
const recoveryNotice = computed(() =>
  recoveryDismissed.value ? null : chat.recoveryMessage,
)

function dismissRecovery() {
  recoveryDismissed.value = true
}

// 提示内容变了（又一次断流、换会话、核对结果不同）就重新出现
watch(
  () => chat.recoveryMessage,
  () => {
    recoveryDismissed.value = false
  },
)

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

// 帧合并、贴底跟随、分页锚点都在这个组合式函数里；页面只把状态喂给它。
const {
  scroller,
  preview: streamingPreview,
  follow: followScroll,
  keepAnchor,
} = useChatScroll({
  conversationId: () => chat.activeId,
  streamingText: () => chat.streamingText,
  lastMessageId: () => chat.messages.at(-1)?.id,
  stepCount: () => chat.agentSteps.length,
})

async function handleApproval(decision: 'approve' | 'reject', note?: string) {
  const ok =
    decision === 'approve' ? await chat.approveApproval(note) : await chat.rejectApproval(note)
  if (ok) followScroll()
}

async function handleSend() {
  const content = chat.composerText
  if (!content.trim() || !chat.canSend || chat.loadingMessages) return
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
  followScroll()
}

/** 往上翻页：由组合式函数负责把新增高度补进 scrollTop */
function loadOlderMessages() {
  void keepAnchor(() => chat.loadOlderMessages())
}

// 地址与会话状态双向同步：深链、刷新、浏览器返回都以此为准
useChatRoute({
  activeId: () => chat.activeId,
  inDraft: () => chat.draft,
  sending: () => chat.sending,
  open: (id) => chat.openConversation(id),
  startNew: () => chat.startNew(),
})
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
          class="chat__older u-text-action"
          :disabled="chat.loadingOlderMessages || chat.sending"
          @click="loadOlderMessages"
        >
          {{ chat.loadingOlderMessages ? '正在加载…' : '加载更早消息' }}
        </button>

        <ChatMessageList
          :items="chat.feedItems"
          :preview="streamingPreview"
          :busy="chat.sending"
          @request-steps="chat.loadExecutionSteps"
          @decide="handleApproval"
          @regenerate="chat.regenerate"
        />
      </div>
    </div>

    <div v-if="recoveryNotice" class="chat__recovery" role="status">
      <div class="chat__recovery-inner">
        <span class="chat__recovery-text">{{ recoveryNotice }}</span>
        <button
          v-if="hasConversation"
          type="button"
          class="u-text-action"
          :disabled="chat.sending"
          @click="chat.recoverExecution"
        >
          重新核对状态
        </button>
        <button
          v-if="hasConversation && chat.agentRunning"
          type="button"
          class="u-text-action"
          @click="chat.stopExecution"
        >
          终止
        </button>
        <button
          type="button"
          class="chat__recovery-close"
          aria-label="收起提示"
          @click="dismissRecovery"
        >
          ×
        </button>
      </div>
    </div>

    <ChatComposer
      ref="composer"
      v-model="chat.composerText"
      :sending="chat.sending"
      :disabled="
        chat.loadingMessages ||
        !chat.canSend ||
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

.chat__recovery {
  /* 与输入区同一道左右留白，提示文字才会和输入框左边缘对齐 */
  flex: none;
  padding: 0 32px;
}

.chat__recovery-inner {
  display: flex;
  max-width: var(--ma-reading-width);
  align-items: baseline;
  gap: var(--ma-space-sm);
  padding: 0 16px var(--ma-space-sm);
  margin: 0 auto;
  color: var(--ma-color-muted);
}

.chat__recovery-text {
  flex: 1;
  min-width: 0;
}

.chat__recovery button {
  font: inherit;
  background: transparent;
  border: 0;
  flex: none;
  cursor: pointer;
}

.chat__recovery-close {
  padding: 0 var(--ma-space-xs);
  color: var(--ma-color-muted);
  opacity: 0.7;
}

.chat__recovery-close:hover {
  opacity: 1;
}

.chat__skill-status {
  padding-inline: var(--ma-space-md);
  color: var(--ma-color-muted);
}

.chat__older {
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

.chat__col {
  max-width: var(--ma-reading-width);
  margin: 0 auto;
}
</style>
