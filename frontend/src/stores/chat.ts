import { computed, reactive, ref } from 'vue'
import { defineStore } from 'pinia'
import { ElMessage } from 'element-plus'

import {
  createConversation,
  deleteConversation,
  getConversation,
  listConversations,
  renameConversation,
} from '@/api/chat'
import {
  decideApprovalStream,
  getAgentSteps,
  listApprovals,
  sendAgentStream,
  type AgentSkillMode,
  type AgentStreamEvent,
  type ReasoningEffort,
} from '@/api/agent'
import { confirmDialog, promptDialog } from '@/components/ui/messageBox'
import type {
  AgentRunSummary,
  AgentStep,
  ChatConversationDetail,
  ChatConversationListItem,
  ChatMessage,
} from '@/types/api'

const HISTORY_PAGE_SIZE = 50
const VISIBLE_STEP_KINDS = new Set([
  'tool_call',
  'tool_result',
  'skill_loaded',
  'skill_load_failed',
  'skill_resource',
])

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
interface ReplayDetail {
  status: 'loading' | 'loaded' | 'error'
  steps: AgentStep[]
}

interface ChatThread {
  messages: ChatMessage[]
  /** 流式过程中已收到的文本；空串表示还在等第一个字符 */
  streamingText: string
  /** 当前这次运行的步骤时间线（工具往返过程） */
  steps: AgentStep[]
  activeUserMessageId: number | null
  runs: Record<number, AgentRunSummary>
  replayDetails: Record<number, ReplayDetail>
  nextBeforeMessageId: number | null
  loadingOlderMessages: boolean
  historyRevision: number
  /** 输入框草稿：切走再切回来，写了一半的字还在 */
  selectedSkillKey: string | null
  draftText: string
  /** 是否正在发送（普通回答或深度回答都算） */
  sending: boolean
  runningAgent: boolean
  /** 是否已经从服务端拉过消息（避免每次切换都重复请求） */
  loaded: boolean
  /** 等待用户决定的工具调用；null 表示没有挂起的审批 */
  approval: PendingApproval | null
}

/** 一次待审批的工具调用（服务端已暂停，等用户点） */
export interface PendingApproval {
  runId: number
  approvalId: number
  tool: string
  args: Record<string, unknown> | null
  reason: string
}

function emptyThread(): ChatThread {
  return {
    messages: [],
    streamingText: '',
    steps: [],
    activeUserMessageId: null,
    runs: {},
    replayDetails: {},
    nextBeforeMessageId: null,
    loadingOlderMessages: false,
    historyRevision: 0,
    selectedSkillKey: null,
    draftText: '',
    sending: false,
    runningAgent: false,
    loaded: false,
    approval: null,
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
  const loadingList = ref(false)
  /** 正在拉某个会话的消息（只影响当前会话的骨架屏） */
  const loadingMessages = ref(false)
  /** 是否请求模型提高推理强度。 */
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
  const activeUserMessageId = computed(() => activeThread.value.activeUserMessageId)
  const hasOlderMessages = computed(() => activeThread.value.nextBeforeMessageId !== null)
  const loadingOlderMessages = computed(() => activeThread.value.loadingOlderMessages)
  const replayDetails = computed(() => activeThread.value.replayDetails)
  const runsByMessage = computed(() => {
    const grouped: Record<number, AgentRunSummary[]> = {}
    for (const run of Object.values(activeThread.value.runs)) {
      const messageId = run.assistant_message_id ?? run.user_message_id
      if (messageId !== null && run.visible_step_count > 0) {
        const runs = (grouped[messageId] ??= [])
        runs.push(run)
      }
    }
    return grouped
  })
  const legacyRuns = computed(() =>
    Object.values(activeThread.value.runs)
      .filter((run) => run.user_message_id === null && run.assistant_message_id === null)
      .filter((run) => run.visible_step_count > 0)
      .sort((a, b) => b.id - a.id),
  )
  const sending = computed(() => activeThread.value.sending)
  const pendingApproval = computed(() => activeThread.value.approval)

  const agentRunning = computed(() => activeThread.value.runningAgent)

  /** 输入框内容也是会话状态的一部分：每个会话各存各的草稿 */
  const selectedSkillKey = computed({
    get: () => activeThread.value.selectedSkillKey,
    set: (key: string | null) => {
      activeThread.value.selectedSkillKey = key
    },
  })

  const composerText = computed({
    get: () => activeThread.value.draftText,
    set: (value: string) => {
      activeThread.value.draftText = value
    },
  })

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

  /**
   * 会话列表只拉一次。
   *
   * 侧栏和对话页都会在挂载时用到它，各自调用会造成两次请求；这里合并成同一个
   * Promise，谁先到谁发请求，后来者等结果。登出时 `reset()` 把标记清掉。
   */
  let conversationsLoaded = false
  let conversationsInFlight: Promise<void> | null = null

  function ensureConversationsLoaded(): Promise<void> {
    if (conversationsLoaded) return Promise.resolve()
    if (conversationsInFlight) return conversationsInFlight
    conversationsInFlight = loadConversations()
      .then(() => {
        conversationsLoaded = true
      })
      .finally(() => {
        conversationsInFlight = null
      })
    return conversationsInFlight
  }

  let conversationRequest = 0

  async function openConversation(id: number) {
    const request = ++conversationRequest
    draft.value = false
    activeId.value = id
    const thread = threadOf(id)
    // 已有缓存先显示（切回来是瞬时的），后台再刷新一次拿最新数据
    const firstLoad = !thread.loaded
    loadingMessages.value = firstLoad && !thread.sending
    if (thread.sending) return
    const revision = ++thread.historyRevision
    try {
      const detail = await getConversation(id, { message_limit: HISTORY_PAGE_SIZE })
      if (threads.get(id) !== thread || thread.historyRevision !== revision) return
      applyLatestHistory(id, thread, detail)
      await restoreApproval(thread, detail, revision)
    } catch {
      // 会话可能已被别处删除：只有当前还停在这个会话时才退回空态
      if (
        request === conversationRequest &&
        activeId.value === id &&
        thread.historyRevision === revision
      ) {
        startNew()
        await loadConversations()
      }
    } finally {
      if (request === conversationRequest) loadingMessages.value = false
    }
  }

  function applyRunSummaries(thread: ChatThread, runs: AgentRunSummary[]) {
    for (const run of runs) {
      const previous = thread.runs[run.id]
      if (
        previous &&
        (previous.status !== run.status || previous.visible_step_count !== run.visible_step_count)
      ) {
        delete thread.replayDetails[run.id]
      }
      thread.runs[run.id] = run
    }
  }

  function applyLatestHistory(id: number, thread: ChatThread, detail: ChatConversationDetail) {
    const firstId = detail.messages[0]?.id
    const older =
      detail.next_before_message_id && firstId !== undefined
        ? thread.messages.filter((message) => message.id > 0 && message.id < firstId)
        : []
    // 只有新页与已加载消息有交集，才保留已加载的旧页。
    const overlaps =
      firstId !== undefined && thread.messages.some((message) => message.id === firstId)
    thread.messages = [...(overlaps ? older : []), ...detail.messages]
    if (!overlaps || !older.length)
      thread.nextBeforeMessageId = detail.next_before_message_id ?? null
    applyRunSummaries(thread, [...(detail.runs ?? []), ...(detail.legacy_runs ?? [])])
    thread.loaded = true
    patchConversation(id, { title: detail.title })
  }

  async function restoreApproval(
    thread: ChatThread,
    detail: ChatConversationDetail,
    revision: number,
  ) {
    if (!detail.runs) return
    const run = detail.runs.find((item) => item.status === 'waiting_approval')
    if (!run) {
      thread.approval = null
      if (!thread.runningAgent) thread.activeUserMessageId = null
      return
    }
    const approvals = await listApprovals(run.id).catch(() => null)
    if (approvals === null || thread.historyRevision !== revision) return
    const waiting = approvals.find((item) => item.status === 'pending')
    thread.approval = waiting
      ? {
          runId: waiting.run_id,
          approvalId: waiting.id,
          tool: waiting.tool_name,
          args: waiting.tool_args,
          reason: waiting.note ?? '',
        }
      : null
  }

  async function loadOlderMessages() {
    const id = activeId.value
    const thread = activeThread.value
    const before = thread.nextBeforeMessageId
    if (id === null || before === null || thread.loadingOlderMessages || thread.sending)
      return false

    const revision = thread.historyRevision
    thread.loadingOlderMessages = true
    try {
      const detail = await getConversation(id, {
        message_limit: HISTORY_PAGE_SIZE,
        before_message_id: before,
      })
      if (threads.get(id) !== thread || thread.historyRevision !== revision) return false
      thread.messages = [...detail.messages, ...thread.messages]
      thread.nextBeforeMessageId = detail.next_before_message_id ?? null
      applyRunSummaries(thread, detail.runs ?? [])
      return true
    } catch {
      return false
    } finally {
      thread.loadingOlderMessages = false
    }
  }

  async function loadExecutionSteps(runId: number) {
    const thread = activeThread.value
    const cached = thread.replayDetails[runId]
    if (cached && cached.status !== 'error') return

    const request: ReplayDetail = reactive({ status: 'loading', steps: [] })
    thread.replayDetails[runId] = request
    try {
      request.steps = await getAgentSteps(runId)
      request.status = 'loaded'
    } catch {
      request.status = 'error'
    }
  }

  /** 进入新会话草稿态：不发任何请求，界面先空着，等第一条消息再建 */
  function startNew() {
    conversationRequest += 1
    loadingMessages.value = false
    threads.delete(DRAFT_KEY)
    draft.value = true
    activeId.value = null
  }

  /** 草稿态发出第一条消息时才真正建会话；失败返回 null */
  async function ensureConversation(): Promise<number | null> {
    if (activeId.value !== null) return activeId.value
    const draftThread = threadOf(DRAFT_KEY)
    const created = await createConversation()
    if (import.meta.env.DEV) {
      console.debug('[my-agent] chat.store.created', { conversationId: created.id })
    }
    conversations.value = [{ ...created, message_count: 0 }, ...conversations.value]
    // 草稿里已经写好的用户消息搬到真实会话下，避免视觉上「跳一下」
    threadOf(created.id).draftText = draftThread.draftText
    if (activeId.value === null && threads.get(DRAFT_KEY) === draftThread) {
      threads.delete(DRAFT_KEY)
      activeId.value = created.id
      draft.value = false
    }
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
  /** 将后端工具调用和结果映射到所属会话的时间线，供执行过程组件展示。 */
  function applyAgentEvent(conversationId: number, thread: ChatThread, event: AgentStreamEvent) {
    const base = {
      seq: 0,
      content: null,
      tool_name: null,
      tool_args: null,
      skill_key: null,
      skill_name: null,
      skill_source: null,
      skill_version: null,
      ok: null,
      duration_ms: null,
      create_time: formatNow(),
    }
    if (event.type === 'run_started') {
      const optimisticId = thread.activeUserMessageId
      const messageId = event.user_message_id
      if (optimisticId !== null && messageId != null) {
        thread.messages = thread.messages.map((message) =>
          message.id === optimisticId ? { ...message, id: messageId } : message,
        )
        thread.activeUserMessageId = messageId
      }
    } else if (event.type === 'assistant_delta') {
      thread.streamingText += event.content
    } else if (event.type === 'assistant_preview_reset') {
      thread.streamingText = ''
    } else if (event.type === 'tool_call') {
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
    } else if (event.type === 'skill_loaded') {
      thread.steps = [
        ...thread.steps,
        {
          ...base,
          seq: event.seq,
          kind: 'skill_loaded',
          skill_key: event.skill_key,
          skill_name: event.name,
          skill_source: event.source,
          skill_version: event.version,
        },
      ]
    } else if (event.type === 'skill_load_failed') {
      thread.steps = [
        ...thread.steps,
        {
          ...base,
          seq: event.seq,
          kind: 'skill_load_failed',
          skill_key: event.skill_key,
          content: event.message,
        },
      ]
    } else if (event.type === 'skill_resource') {
      thread.steps = [
        ...thread.steps,
        {
          ...base,
          seq: event.seq,
          kind: 'skill_resource',
          skill_key: event.skill_key,
          skill_name: event.name,
          tool_args: { skill_key: event.skill_key, path: event.path },
          ok: event.ok,
          content: event.message,
        },
      ]
    } else if (event.type === 'approval_required') {
      thread.approval = {
        runId: event.run_id,
        approvalId: event.approval_id,
        tool: event.tool,
        args: event.args,
        reason: event.reason,
      }
    }
    if (import.meta.env.DEV) {
      console.debug('[my-agent] agent.store.applyAgentEvent', {
        conversationId,
        event: event,
        stepCount: thread.steps.length,
        awaitingApproval: thread.approval !== null,
      })
    }
  }

  /** 最终答复落进消息列表，并更新会话列表里的条数与时间 */
  function appendAssistantMessage(
    thread: ChatThread,
    conversationId: number,
    event: Extract<AgentStreamEvent, { type: 'run_finished' }>,
  ) {
    thread.streamingText = ''
    const steps = thread.steps.filter((step) => VISIBLE_STEP_KINDS.has(step.kind))
    const previous = thread.runs[event.run_id]
    thread.runs[event.run_id] = {
      id: event.run_id,
      status: 'completed',
      user_message_id: thread.activeUserMessageId ?? previous?.user_message_id ?? null,
      assistant_message_id: event.assistant_message_id,
      visible_step_count: steps.length,
    }
    thread.replayDetails[event.run_id] = { status: 'loaded', steps }
    thread.activeUserMessageId = null
    thread.messages = [
      ...thread.messages,
      {
        id: event.assistant_message_id,
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
    if (import.meta.env.DEV) {
      console.debug('[my-agent] agent.store.complete', {
        conversationId,
        runId: event.run_id,
        chars: event.content.length,
      })
    }
  }

  async function send(
    content: string,
    skillMode: AgentSkillMode = 'auto',
    reasoningEffort: ReasoningEffort = 'none',
    skillCatalogVersion?: string,
  ): Promise<boolean> {
    const text = content.trim()
    if (!text || activeThread.value.sending || activeThread.value.approval) return false

    const selectedKey = activeThread.value.selectedSkillKey
    let conversationId = activeId.value
    if (conversationId === null) {
      conversationId = await ensureConversation()
    }
    if (conversationId === null) return false

    // 整段流程绑定 conversationId 自己的状态，切走也继续更新原会话。
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
    thread.selectedSkillKey = selectedKey
    thread.steps = []
    thread.activeUserMessageId = optimisticId
    thread.historyRevision++
    thread.streamingText = ''
    thread.runningAgent = true
    thread.sending = true

    // 事件回调绑定本次发送的会话，切换页面时也继续更新原会话。
    try {
      await sendAgentStream(
        conversationId,
        text,
        {
          onEvent: (event: AgentStreamEvent) => applyAgentEvent(conversationId, thread, event),
          onApproval: () => {
            // 服务端已经暂停：流结束，等用户点批准/拒绝
            thread.streamingText = ''
            thread.runningAgent = false
          },
          onFinished: (event) => appendAssistantMessage(thread, conversationId, event),
        },
        undefined,
        skillMode,
        reasoningEffort,
        selectedKey ? [selectedKey] : [],
        skillCatalogVersion,
      )
      await refreshAfterAgent(conversationId, thread)
      thread.draftText = ''
      thread.selectedSkillKey = null
      return true
    } catch (error) {
      thread.streamingText = ''
      thread.messages = thread.messages.filter((item) => item.id !== optimisticId)
      thread.activeUserMessageId = null
      await refreshAfterAgent(conversationId, thread)
      ElMessage.error(error instanceof Error ? error.message : '生成回复失败')
      return false
    } finally {
      thread.streamingText = ''
      thread.runningAgent = false
      if (!thread.approval) thread.activeUserMessageId = null
      thread.sending = false
    }
  }

  async function refreshAfterAgent(id: number, thread: ChatThread) {
    const detail = await getConversation(id, { message_limit: HISTORY_PAGE_SIZE }).catch(() => null)
    if (detail && threads.get(id) === thread) {
      applyLatestHistory(id, thread, detail)
      await restoreApproval(thread, detail, thread.historyRevision)
    }
  }

  /** 批准或拒绝当前会话的挂起审批；服务端会接着跑完这次运行 */
  async function decideApproval(decision: 'approve' | 'reject', note?: string): Promise<boolean> {
    const conversationId = activeId.value
    const pending = activeThread.value.approval
    if (conversationId === null || pending === null || activeThread.value.sending) return false

    const thread = threadOf(conversationId)
    thread.historyRevision++
    thread.approval = null
    thread.runningAgent = true
    thread.sending = true
    try {
      const run = thread.runs[pending.runId]
      if (run && thread.activeUserMessageId === null) {
        thread.activeUserMessageId = run.user_message_id
        const cached = thread.replayDetails[run.id]
        thread.steps =
          cached?.status === 'loaded' ? cached.steps : await getAgentSteps(run.id).catch(() => [])
      }
      await decideApprovalStream(
        pending.runId,
        pending.approvalId,
        decision,
        {
          onEvent: (event: AgentStreamEvent) => applyAgentEvent(conversationId, thread, event),
          onApproval: () => {
            thread.streamingText = ''
            thread.runningAgent = false
          },
          onFinished: (event) => appendAssistantMessage(thread, conversationId, event),
        },
        note,
      )
      await refreshAfterAgent(conversationId, thread)
      return true
    } catch (error) {
      thread.streamingText = ''
      thread.approval = pending
      await refreshAfterAgent(conversationId, thread)
      ElMessage.error(error instanceof Error ? error.message : '处理审批失败')
      return false
    } finally {
      thread.streamingText = ''
      thread.runningAgent = false
      if (!thread.approval) thread.activeUserMessageId = null
      thread.sending = false
    }
  }

  function approveApproval(note?: string) {
    return decideApproval('approve', note)
  }

  function rejectApproval(note?: string) {
    return decideApproval('reject', note)
  }

  /** 退出登录时清空，避免下一个账号看到上一个人的会话 */
  function reset() {
    conversations.value = []
    threads.clear()
    activeId.value = null
    draft.value = false
    conversationsLoaded = false
    conversationsInFlight = null
  }

  return {
    agentMode,
    agentRunning,
    pendingApproval,
    agentSteps,
    conversations,
    activeId,
    draft,
    composerText,
    selectedSkillKey,
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
    ensureConversationsLoaded,
    openConversation,
    startNew,
    ensureConversation,
    rename,
    remove,
    send,
    reset,
    approveApproval,
    rejectApproval,
    decideApproval,
    activeUserMessageId,
    runsByMessage,
    legacyRuns,
    replayDetails,
    loadExecutionSteps,
    hasOlderMessages,
    loadingOlderMessages,
    loadOlderMessages,
    toggleAgentMode,
  }
})
