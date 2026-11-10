import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { ElMessage } from 'element-plus'

import {
  createConversation,
  deleteConversation,
  getConversation,
  listConversations,
  renameConversation,
  sendMessageStream,
} from '@/api/chat'
import { listAgentRuns, sendAgentStream, type AgentStreamEvent } from '@/api/agent'
import { confirmDialog, promptDialog } from '@/components/ui/messageBox'
import type { AgentStep, ChatConversationListItem, ChatMessage } from '@/types/api'

const AGENT_MODE_KEY = 'my-agent.agent-mode'

/** 读回上次的「深度回答」开关；读不到就当关（省 token 是默认值） */
function readAgentMode(): boolean {
  try {
    return window.localStorage.getItem(AGENT_MODE_KEY) === '1'
  } catch {
    return false
  }
}

/** 前端本地时间，格式与后端一致：YYYY-MM-DD HH:mm:ss */
function formatNow(): string {
  const now = new Date()
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`
}

/**
 * 会话状态提升到 store：侧边栏（会话列表）与对话页（消息区）要同时读写，
 * 放在视图里就得靠 props/emit 来回传，反而更难维护。
 */
export const useChatStore = defineStore('chat', () => {
  const conversations = ref<ChatConversationListItem[]>([])
  /** 当前打开的会话；null 表示还没选（空态） */
  const activeId = ref<number | null>(null)
  /**
   * 「新会话草稿」态：界面已经是一个空白会话，但后端还没有对应记录。
   * 点「新建会话」只进这个状态，等第一条消息真正发出去才落库。
   */
  const draft = ref(false)
  /** 每次点「新建会话」自增：视图据此清空输入框里的草稿文字 */
  const newChatTick = ref(0)
  const messages = ref<ChatMessage[]>([])
  const loadingList = ref(false)
  const loadingMessages = ref(false)
  const sending = ref(false)
  /** 流式过程中已收到的文本；空字符串表示还在等第一个字符 */
  const streamingText = ref('')
  /** 是否用「深度回答」（agent 循环 + 工具）代替一问一答；默认关，省 token */
  const agentMode = ref(readAgentMode())
  /** 当前这次运行的步骤时间线（工具往返过程） */
  const agentSteps = ref<AgentStep[]>([])
  const agentRunning = ref(false)

  const activeConversation = computed(
    () => conversations.value.find((item) => item.id === activeId.value) ?? null,
  )
  const activeTitle = computed(() => activeConversation.value?.title ?? '')

  /** 顶栏标签显示真正回话的模型（流式与非流式都会写进 assistant 消息） */
  const modelLabel = computed(() => {
    for (let i = messages.value.length - 1; i >= 0; i -= 1) {
      const model = messages.value[i].model
      if (model) return model
    }
    return ''
  })

  /** 列表里替换某条会话的本地状态，避免整表重拉 */
  function patchConversation(id: number, patch: Partial<ChatConversationListItem>) {
    conversations.value = conversations.value.map((item) =>
      item.id === id ? { ...item, ...patch } : item,
    )
  }

  /** 最近活动时间倒序：发完消息把会话顶到第一位 */
  function sortByRecent() {
    conversations.value = [...conversations.value].sort((a, b) =>
      b.update_time.localeCompare(a.update_time),
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
    draft.value = false
    activeId.value = id
    loadingMessages.value = true
    messages.value = []
    try {
      const detail = await getConversation(id)
      messages.value = detail.messages
      patchConversation(id, { title: detail.title })
    } catch {
      // 会话可能已被别处删除：退回空态并刷新列表
      activeId.value = null
      messages.value = []
      await loadConversations()
    } finally {
      loadingMessages.value = false
    }
  }

  /** 进入新会话草稿态：不发任何请求，界面先空着，等第一条消息再建 */
  function startNew() {
    draft.value = true
    newChatTick.value += 1
    activeId.value = null
    messages.value = []
    agentSteps.value = []
    streamingText.value = ''
  }

  /** 草稿态发出第一条消息时才真正建会话；失败返回 null */
  async function ensureConversation(): Promise<number | null> {
    if (activeId.value !== null) return activeId.value
    const created = await createConversation()
    conversations.value = [{ ...created, message_count: 0 }, ...conversations.value]
    activeId.value = created.id
    draft.value = false
    return created.id
  }

  async function rename(item: ChatConversationListItem) {
    try {
      const value = await promptDialog({
        title: '重命名会话',
        confirmText: '保存',
        input: {
          label: '会话名称',
          value: item.title,
          placeholder: '给这个会话起个名字',
          validator: (next: string) => (next.trim() ? true : '名称不能只包含空白'),
        },
      })
      const updated = await renameConversation(item.id, value)
      patchConversation(item.id, { title: updated.title })
      ElMessage.success('会话名称已更新')
    } catch {
      // 取消或接口失败（失败已由拦截器提示）
    }
  }

  async function remove(item: ChatConversationListItem) {
    try {
      await confirmDialog({
        title: '删除后，该会话将不可恢复',
        description: '这个会话里的消息会一起删除。',
        confirmText: '删除该会话',
        danger: true,
      })
    } catch {
      return
    }
    await deleteConversation(item.id)
    ElMessage.success('删除成功')
    conversations.value = conversations.value.filter((row) => row.id !== item.id)
    if (activeId.value === item.id) {
      // 删掉的正是当前会话：回到空白会话，而不是硬跳去别的会话
      startNew()
    }
  }

  /** 发送一条消息；返回是否成功（失败时由调用方决定输入框保留内容） */
  async function send(content: string): Promise<boolean> {
    const text = content.trim()
    if (!text || sending.value) return false

    let id = activeId.value
    if (id === null) {
      id = await ensureConversation()
      if (id === null) return false
    }

    // 乐观插入用户消息：等服务端 meta 回来再换成正身（带真实 id 与时间）
    const optimisticId = -Date.now()
    messages.value = [
      ...messages.value,
      {
        id: optimisticId,
        conversation_id: id,
        role: 'user',
        content: text,
        model: null,
        create_time: '',
      },
    ]
    streamingText.value = ''
    sending.value = true

    let currentUserId = optimisticId
    try {
      await sendMessageStream(id, text, {
        onMeta: (message) => {
          currentUserId = message.id
          messages.value = messages.value.map((m) => (m.id === optimisticId ? message : m))
        },
        onDelta: (delta) => {
          streamingText.value += delta
        },
        onDone: (event) => {
          streamingText.value = ''
          messages.value = [...messages.value, event.assistant_message]
          patchConversation(id, {
            title: event.conversation_title,
            message_count: event.message_count,
            update_time: event.assistant_message.create_time,
          })
          sortByRecent()
        },
      })
      return true
    } catch (error) {
      // 后端已回滚这次提问，前端也要撤掉乐观消息
      messages.value = messages.value.filter((m) => m.id !== currentUserId)
      streamingText.value = ''
      ElMessage.error(error instanceof Error ? error.message : '发送失败，请稍后重试')
      return false
    } finally {
      sending.value = false
    }
  }

  function toggleAgentMode(value: boolean) {
    agentMode.value = value
    // 记住选择：刷新后仍是同一模式（用户刚开过就说明正在用）
    try {
      window.localStorage.setItem(AGENT_MODE_KEY, value ? '1' : '0')
    } catch {
      // 隐私模式下 localStorage 可能不可写，忽略即可
    }
  }

  /** 用 agent 循环发一条消息：过程进时间线，最终答复进 messages */
  async function sendWithAgent(content: string): Promise<boolean> {
    const text = content.trim()
    if (!text || agentRunning.value) return false

    let conversationId = activeId.value
    if (conversationId === null) {
      conversationId = await ensureConversation()
    }
    if (conversationId === null) return false

    const optimisticId = -Date.now()
    messages.value = [
      ...messages.value,
      {
        id: optimisticId,
        conversation_id: conversationId,
        role: 'user',
        content: text,
        model: null,
        create_time: formatNow(),
      },
    ]
    agentSteps.value = []
    agentRunning.value = true
    sending.value = true

    try {
      await sendAgentStream(conversationId, text, {
        onEvent: (event: AgentStreamEvent) => {
          const base = {
            seq: 0,
            content: null,
            tool_name: null,
            tool_args: null,
            ok: null,
            duration_ms: null,
            create_time: formatNow(),
          }
          if (event.type === 'tool_call') {
            agentSteps.value = [
              ...agentSteps.value,
              {
                ...base,
                seq: event.seq,
                kind: 'tool_call',
                tool_name: event.tool,
                tool_args: event.args,
              },
            ]
          } else if (event.type === 'tool_result') {
            agentSteps.value = [
              ...agentSteps.value,
              {
                ...base,
                seq: event.seq,
                kind: 'tool_result',
                tool_name: event.tool,
                content: event.content,
                ok: event.ok,
                duration_ms: event.duration_ms,
              },
            ]
          } else if (event.type === 'assistant_text') {
            agentSteps.value = [
              ...agentSteps.value,
              { ...base, seq: event.seq, kind: 'assistant_text', content: event.content },
            ]
          }
        },
        onFinished: (event) => {
          messages.value = [
            ...messages.value,
            {
              id: -Date.now() - 1,
              conversation_id: conversationId,
              role: 'assistant',
              content: event.content,
              model: event.model,
              create_time: formatNow(),
            },
          ]
          patchConversation(conversationId, {
            message_count: (activeConversation.value?.message_count ?? 0) + 2,
            update_time: formatNow(),
          })
          sortByRecent()
        },
      })
      // 用服务端的真实 id / 时间覆盖乐观数据
      const detail = await getConversation(conversationId)
      messages.value = detail.messages
      patchConversation(conversationId, { title: detail.title })
      return true
    } catch (error) {
      messages.value = messages.value.filter((item) => item.id !== optimisticId)
      ElMessage.error(error instanceof Error ? error.message : '深度回答失败')
      return false
    } finally {
      agentRunning.value = false
      sending.value = false
    }
  }

  /** 打开会话时拉一次最近的运行，刷新后仍能看到上次的工具过程 */
  async function loadAgentRuns(conversationId: number) {
    const data = await listAgentRuns(conversationId)
    const latest = data.items[0]
    agentSteps.value = latest ? latest.steps.filter((step) => step.kind !== 'final_answer') : []
  }

  /** 退出登录时清空，避免下一个账号看到上一个人的会话 */
  function reset() {
    conversations.value = []
    activeId.value = null
    messages.value = []
    streamingText.value = ''
    agentSteps.value = []
    agentRunning.value = false
    sending.value = false
  }

  return {
    agentMode,
    agentRunning,
    agentSteps,
    conversations,
    activeId,
    draft,
    newChatTick,
    messages,
    loadingList,
    loadingMessages,
    sending,
    streamingText,
    activeConversation,
    activeTitle,
    modelLabel,
    loadConversations,
    openConversation,
    startNew,
    ensureConversation,
    rename,
    remove,
    send,
    reset,
    sendWithAgent,
    loadAgentRuns,
    toggleAgentMode,
  }
})
