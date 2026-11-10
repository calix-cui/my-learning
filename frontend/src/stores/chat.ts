import { computed, reactive, ref } from 'vue'
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

/** 草稿态的伪会话键：界面已经在「一个会话」里，但后端还没有记录 */
const DRAFT_KEY = 0

/**
 * 一个会话自己的运行时状态。
 *
 * 关键点：**会话之间不能共享可变状态**。之前 messages / streamingText 是 store 上的
 * 单例，切换会话只是把它们换成另一份数据，而正在跑的流仍然往同一份里写，
 * 于是「上一个会话的回答」就落到新会话里了。现在按会话隔离，流只写自己那一份。
 */
interface ChatThread {
  messages: ChatMessage[]
  /** 流式过程中已收到的文本；空串表示还在等第一个字符 */
  streamingText: string
  /** 当前这次运行的步骤时间线（工具往返过程） */
  steps: AgentStep[]
  /** 是否正在发送（普通回答或深度回答都算） */
  sending: boolean
  runningAgent: boolean
  /** 是否已经从服务端拉过消息（避免每次切换都重复请求） */
  loaded: boolean
}

function emptyThread(): ChatThread {
  return {
    messages: [],
    streamingText: '',
    steps: [],
    sending: false,
    runningAgent: false,
    loaded: false,
  }
}

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
 * 会话状态提升到 store：侧边栏（会话列表）与对话页（消息区）要同时读写。
 * 每个会话的数据放在 threads 里按 id 隔离，视图只读「当前会话」那一份。
 */
export const useChatStore = defineStore('chat', () => {
  const conversations = ref<ChatConversationListItem[]>([])
  /** 当前打开的会话；null 表示草稿态（还没落库的空白会话） */
  const activeId = ref<number | null>(null)
  /**
   * 「新会话草稿」态：界面已经是一个空白会话，但后端还没有对应记录。
   * 点「新建会话」只进这个状态，等第一条消息真正发出去才落库。
   */
  const draft = ref(false)
  /** 每次点「新建会话」自增：视图据此清空输入框里的草稿文字 */
  const newChatTick = ref(0)
  const loadingList = ref(false)
  /** 正在拉某个会话的消息（只影响当前会话的骨架屏） */
  const loadingMessages = ref(false)
  /** 是否用「深度回答」（agent 循环 + 工具）代替一问一答；默认关，省 token */
  const agentMode = ref(readAgentMode())

  /** 按会话 id 存放的运行时状态；草稿态用 DRAFT_KEY */
  const threads = reactive(new Map<number, ChatThread>())

  /** 当前会话的键（草稿态是 0） */
  const activeKey = computed(() => activeId.value ?? DRAFT_KEY)

  function threadOf(key: number): ChatThread {
    const existing = threads.get(key)
    if (existing) return existing
    threads.set(key, emptyThread())
    // 必须把 reactive 代理取回来：直接改原始对象不会触发视图更新
    return threads.get(key)!
  }

  /** 当前会话的那一份（视图只读这个） */
  const activeThread = computed(() => threadOf(activeKey.value))
  const messages = computed(() => activeThread.value.messages)
  const streamingText = computed(() => activeThread.value.streamingText)
  const agentSteps = computed(() => activeThread.value.steps)
  const sending = computed(() => activeThread.value.sending)
  const agentRunning = computed(() => activeThread.value.runningAgent)

  const activeConversation = computed(
    () => conversations.value.find((item) => item.id === activeId.value) ?? null,
  )
  const activeTitle = computed(() => activeConversation.value?.title ?? '')

  /** 顶栏标签显示真正回话的模型（流式与非流式都会写进 assistant 消息） */
  const modelLabel = computed(() => {
    const rows = messages.value
    for (let i = rows.length - 1; i >= 0; i -= 1) {
      const model = rows[i].model
      if (model) return model
    }
    return ''
  })

  /** 某个会话是否正在回答（侧栏可以用它显示「生成中」） */
  function isBusy(id: number): boolean {
    return threads.get(id)?.sending ?? false
  }

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
    const thread = threadOf(id)
    // 已有缓存先显示（切回来是瞬时的），后台再刷新一次拿最新数据
    const firstLoad = !thread.loaded
    if (firstLoad) loadingMessages.value = true
    try {
      const detail = await getConversation(id)
      thread.messages = detail.messages
      thread.loaded = true
      patchConversation(id, { title: detail.title })
    } catch {
      // 会话可能已被别处删除：只有当前还停在这个会话时才退回空态
      threads.delete(id)
      if (activeId.value === id) {
        startNew()
        await loadConversations()
      }
    } finally {
      if (firstLoad) loadingMessages.value = false
    }
  }

  /** 进入新会话草稿态：不发任何请求，界面先空着，等第一条消息再建 */
  function startNew() {
    threads.delete(DRAFT_KEY)
    draft.value = true
    newChatTick.value += 1
    activeId.value = null
  }

  /** 草稿态发出第一条消息时才真正建会话；失败返回 null */
  async function ensureConversation(): Promise<number | null> {
    if (activeId.value !== null) return activeId.value
    const created = await createConversation()
    conversations.value = [{ ...created, message_count: 0 }, ...conversations.value]
    // 草稿里已经写好的用户消息搬到真实会话下，避免视觉上「跳一下」
    const draftThread = threads.get(DRAFT_KEY)
    if (draftThread?.messages.length) {
      threadOf(created.id).messages = draftThread.messages
    }
    threads.delete(DRAFT_KEY)
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
    threads.delete(item.id)
    if (activeId.value === item.id) {
      // 删掉的正是当前会话：回到空白会话，而不是硬跳去别的会话
      startNew()
    }
  }

  /** 发送一条消息；返回是否成功（失败时由调用方决定输入框保留内容） */
  async function send(content: string): Promise<boolean> {
    const text = content.trim()
    if (!text || activeThread.value.sending) return false

    let id = activeId.value
    if (id === null) {
      id = await ensureConversation()
      if (id === null) return false
    }

    // 从此处开始只认这个 id：即使中途切走，写入的也是它自己那一份
    const thread = threadOf(id)
    const optimisticId = -Date.now()
    thread.messages = [
      ...thread.messages,
      {
        id: optimisticId,
        conversation_id: id,
        role: 'user',
        content: text,
        model: null,
        create_time: '',
      },
    ]
    thread.streamingText = ''
    thread.sending = true

    let currentUserId = optimisticId
    try {
      await sendMessageStream(id, text, {
        onMeta: (message) => {
          currentUserId = message.id
          thread.messages = thread.messages.map((m) => (m.id === optimisticId ? message : m))
        },
        onDelta: (delta) => {
          thread.streamingText += delta
        },
        onDone: (event) => {
          thread.streamingText = ''
          thread.messages = [...thread.messages, event.assistant_message]
          thread.loaded = true
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
      thread.messages = thread.messages.filter((m) => m.id !== currentUserId)
      thread.streamingText = ''
      ElMessage.error(error instanceof Error ? error.message : '发送失败，请稍后重试')
      return false
    } finally {
      thread.sending = false
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
    if (!text || activeThread.value.runningAgent) return false

    let conversationId = activeId.value
    if (conversationId === null) {
      conversationId = await ensureConversation()
    }
    if (conversationId === null) return false

    // 与 send 一样：整段流程绑定 conversationId 自己的 thread
    const thread = threadOf(conversationId)
    const optimisticId = -Date.now()
    thread.messages = [
      ...thread.messages,
      {
        id: optimisticId,
        conversation_id: conversationId,
        role: 'user',
        content: text,
        model: null,
        create_time: formatNow(),
      },
    ]
    thread.steps = []
    thread.streamingText = ''
    thread.runningAgent = true
    thread.sending = true

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
            thread.steps = [
              ...thread.steps,
              {
                ...base,
                seq: event.seq,
                kind: 'tool_call',
                tool_name: event.tool,
                tool_args: event.args,
              },
            ]
          } else if (event.type === 'tool_result') {
            thread.steps = [
              ...thread.steps,
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
            thread.steps = [
              ...thread.steps,
              { ...base, seq: event.seq, kind: 'assistant_text', content: event.content },
            ]
          }
        },
        onFinished: (event) => {
          thread.messages = [
            ...thread.messages,
            {
              id: -Date.now() - 1,
              conversation_id: conversationId,
              role: 'assistant',
              content: event.content,
              model: event.model,
              create_time: formatNow(),
            },
          ]
          const row = conversations.value.find((item) => item.id === conversationId)
          patchConversation(conversationId, {
            message_count: (row?.message_count ?? 0) + 2,
            update_time: formatNow(),
          })
          sortByRecent()
        },
      })
      // 用服务端的真实 id / 时间覆盖乐观数据（写回它自己的 thread）
      const detail = await getConversation(conversationId)
      thread.messages = detail.messages
      thread.loaded = true
      patchConversation(conversationId, { title: detail.title })
      return true
    } catch (error) {
      thread.messages = thread.messages.filter((item) => item.id !== optimisticId)
      ElMessage.error(error instanceof Error ? error.message : '深度回答失败')
      return false
    } finally {
      thread.runningAgent = false
      thread.sending = false
    }
  }

  /** 打开会话时拉一次最近的运行，刷新后仍能看到上次的工具过程 */
  async function loadAgentRuns(conversationId: number) {
    const data = await listAgentRuns(conversationId)
    const latest = data.items[0]
    threadOf(conversationId).steps = latest
      ? latest.steps.filter((step) => step.kind !== 'final_answer')
      : []
  }

  /** 退出登录时清空，避免下一个账号看到上一个人的会话 */
  function reset() {
    conversations.value = []
    threads.clear()
    activeId.value = null
    draft.value = false
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
    isBusy,
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
