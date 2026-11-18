import { computed, reactive, ref } from 'vue'
import { defineStore } from 'pinia'
import { ElMessage } from 'element-plus'
import { buildChatFeed } from './chat/feed'
import { applyExecutionEvent } from './chat/events'
import {
  createExecution,
  createRequestId,
  applySummary,
  blocksSending,
  isTransferring,
  runExecution,
  VISIBLE_STEP_KINDS,
  type Execution,
} from './chat/execution'
export type { PendingApproval } from './chat/execution'

import {
  createConversation,
  deleteConversation,
  getConversation,
  listConversations,
  renameConversation,
} from '@/api/chat'
import {
  AgentHttpError,
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
  ChatConversationDetail,
  ChatConversationListItem,
  ChatMessage,
} from '@/types/api'

const HISTORY_PAGE_SIZE = 50
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
  executions: Execution[]
  activeExecutionKey: string | null
  nextBeforeMessageId: number | null
  loadingOlderMessages: boolean
  historyRevision: number
  historyError: string | null
  selectedSkillKey: string | null
  draftText: string
  loaded: boolean
}

function emptyThread(): ChatThread {
  return {
    messages: [],
    executions: [],
    activeExecutionKey: null,
    nextBeforeMessageId: null,
    loadingOlderMessages: false,
    historyRevision: 0,
    historyError: null,
    selectedSkillKey: null,
    draftText: '',
    loaded: false,
  }
}

function currentExecution(thread: ChatThread) {
  return thread.executions.find((execution) => execution.key === thread.activeExecutionKey)
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
  const feedItems = computed(() => buildChatFeed(activeThread.value, activeKey.value))
  const messages = computed(() => activeThread.value.messages)
  const activeExecution = computed(() => currentExecution(activeThread.value))
  const streamingText = computed(() => activeExecution.value?.preview ?? '')
  const agentSteps = computed(() => activeExecution.value?.steps ?? [])
  const hasOlderMessages = computed(() => activeThread.value.nextBeforeMessageId !== null)
  const loadingOlderMessages = computed(() => activeThread.value.loadingOlderMessages)
  const sending = computed(() => activeThread.value.executions.some(isTransferring))
  const canSend = computed(
    () => !activeThread.value.historyError && !activeThread.value.executions.some(blocksSending),
  )
  const pendingApproval = computed(() => activeExecution.value?.approval ?? null)
  const agentRunning = computed(
    () =>
      activeExecution.value?.transport === 'streaming' &&
      activeExecution.value.status === 'running',
  )
  const recoveryMessage = computed(
    () =>
      activeThread.value.historyError ??
      activeExecution.value?.error ??
      activeThread.value.executions.find((execution) => execution.transport === 'disconnected')
        ?.error ??
      null,
  )
  let accountEpoch = 0
  let localSequence = 0
  const controllers = new Map<Execution, AbortController>()
  const stepRequests = new WeakMap<Execution, { revision: number; promise: Promise<void> }>()
  const creations = new WeakMap<ChatThread, Promise<number | null>>()

  function disposeThread(thread: ChatThread) {
    for (const execution of thread.executions) {
      controllers.get(execution)?.abort()
      controllers.delete(execution)
    }
    thread.historyRevision++
  }

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
    return threads.get(id)?.executions.some(blocksSending) ?? false
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
    const epoch = accountEpoch
    loadingList.value = true
    try {
      const page = await listConversations()
      if (epoch === accountEpoch) conversations.value = page.items
    } finally {
      if (epoch === accountEpoch) loadingList.value = false
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
    const epoch = accountEpoch
    conversationsInFlight = loadConversations()
      .then(() => {
        if (epoch === accountEpoch) conversationsLoaded = true
      })
      .finally(() => {
        if (epoch === accountEpoch) conversationsInFlight = null
      })
    return conversationsInFlight
  }

  let conversationRequest = 0

  async function openConversation(id: number) {
    const request = ++conversationRequest
    draft.value = false
    activeId.value = id
    const thread = threadOf(id)
    loadingMessages.value = !thread.loaded && !thread.executions.some(isTransferring)
    if (thread.executions.some(isTransferring)) return
    try {
      await refreshThread(id, thread)
    } catch (error) {
      if (threads.get(id) !== thread) return
      thread.historyError = error instanceof Error ? error.message : '读取会话失败，请重试'
    } finally {
      if (request === conversationRequest) loadingMessages.value = false
    }
  }

  function applyRunSummaries(thread: ChatThread, runs: AgentRunSummary[]) {
    for (const run of runs) {
      let execution = thread.executions.find((item) => item.runId === run.id)
      if (!execution) {
        execution = reactive(createExecution(`run:${run.id}`))
        thread.executions.push(execution)
      }
      applySummary(execution, run)
      if (run.status === 'running' || run.status === 'waiting_approval')
        thread.activeExecutionKey = execution.key
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
    applyRunSummaries(thread, detail.runs ?? [])
    const pendingMessages = thread.messages.filter(
      (message) =>
        message.id < 0 &&
        thread.executions.some(
          (execution) => execution.userMessageId === message.id && execution.status !== 'failed',
        ),
    )
    thread.messages = [...(overlaps ? older : []), ...detail.messages, ...pendingMessages]
    if (!overlaps || !older.length)
      thread.nextBeforeMessageId = detail.next_before_message_id ?? null
    thread.loaded = true
    patchConversation(id, { title: detail.title })
  }

  async function refreshThread(id: number, thread: ChatThread) {
    const revision = ++thread.historyRevision
    const valid = () => threads.get(id) === thread && thread.historyRevision === revision
    const detail = await getConversation(id, { message_limit: HISTORY_PAGE_SIZE })
    if (!valid()) return
    applyLatestHistory(id, thread, detail)
    thread.historyError = null
    for (const execution of thread.executions) {
      if (!valid()) return
      if (execution.status === 'waiting_approval') {
        try {
          const approvals = await listApprovals(execution.runId!)
          if (!valid()) return
          const pending = approvals.find((item) => item.status === 'pending')
          if (!pending) throw new Error('待审批运行没有可用审批，请重新核对状态')
          execution.approval = {
            runId: pending.run_id,
            approvalId: pending.id,
            tool: pending.tool_name,
            args: pending.tool_args,
            reason: pending.note ?? '',
          }
          execution.transport = 'idle'
          execution.error = null
        } catch (error) {
          if (!valid()) return
          execution.transport = 'disconnected'
          execution.error = error instanceof Error ? error.message : '读取审批失败'
          throw error
        }
      } else if (execution.status === 'running' || execution.status === null) {
        execution.transport = 'disconnected'
        execution.error =
          execution.runId === null
            ? '连接已中断，提交结果尚未确认，请刷新页面核对，勿重复发送'
            : '执行尚未结束，连接已中断，请重新核对状态'
      } else {
        execution.transport = 'idle'
        execution.error =
          execution.status === 'failed'
            ? (execution.error ?? '执行失败，可重新发送')
            : execution.status === 'cancelled'
              ? '执行已取消'
              : null
        execution.preview = ''
      }
      if (
        execution.visibleStepCount > 0 &&
        execution.steps.length > 0 &&
        execution.detailStatus !== 'loaded'
      ) {
        try {
          await readSteps(id, thread, execution)
        } catch {
          /* 保留步骤，时间线显示读取失败和重试。 */
        }
        if (!valid()) return
      }
    }
  }

  async function recoverExecution() {
    const id = activeId.value
    const thread = activeThread.value
    if (id === null || thread.executions.some(isTransferring)) return false
    const execution = currentExecution(thread)
    if (execution) execution.transport = 'reconciling'
    try {
      await refreshThread(id, thread)
      // 核对确认这条消息已经落进历史，草稿就已经发出去了：再留着会被当成新消息发第二遍。
      const sent =
        execution && execution.userMessageId !== null
          ? thread.messages.find(
              (message) => message.id === execution.userMessageId && message.role === 'user',
            )
          : undefined
      if (sent && sent.content.trim() === thread.draftText.trim()) thread.draftText = ''
      return (
        threads.get(id) === thread &&
        !thread.executions.some((item) => item.transport === 'disconnected')
      )
    } catch (error) {
      if (threads.get(id) !== thread) return false
      thread.historyError = error instanceof Error ? error.message : '读取执行状态失败'
      if (execution) execution.transport = 'disconnected'
      return false
    }
  }

  async function loadOlderMessages() {
    const id = activeId.value
    const thread = activeThread.value
    const before = thread.nextBeforeMessageId
    if (
      id === null ||
      before === null ||
      thread.loadingOlderMessages ||
      thread.executions.some(isTransferring)
    )
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
    } catch (error) {
      if (threads.get(id) === thread)
        thread.historyError = error instanceof Error ? error.message : '加载历史失败'
      return false
    } finally {
      thread.loadingOlderMessages = false
    }
  }

  async function readSteps(id: number, thread: ChatThread, execution: Execution) {
    if (execution.runId === null || execution.detailStatus === 'loaded') return
    const revision = execution.revision
    const existing = stepRequests.get(execution)
    if (existing?.revision === revision) return existing.promise
    execution.detailStatus = 'loading'
    const runId = execution.runId
    const promise = (async () => {
      try {
        const steps = await getAgentSteps(runId)
        if (threads.get(id) !== thread || execution.revision !== revision) return
        execution.steps = [
          ...new Map([...execution.steps, ...steps].map((step) => [step.seq, step])).values(),
        ].sort((a, b) => a.seq - b.seq)
        execution.detailStatus = 'loaded'
      } catch (error) {
        if (threads.get(id) === thread && execution.revision === revision)
          execution.detailStatus = 'error'
        throw error
      }
    })()
    stepRequests.set(execution, { revision, promise })
    try {
      await promise
    } finally {
      if (stepRequests.get(execution)?.promise === promise) stepRequests.delete(execution)
    }
  }

  async function loadExecutionSteps(runId: number) {
    const id = activeId.value
    const thread = activeThread.value
    const execution = thread.executions.find((item) => item.runId === runId)
    if (id === null || !execution || execution.detailStatus === 'loading') return
    try {
      await readSteps(id, thread, execution)
    } catch {
      /* 错误由时间线的重试入口显示。 */
    }
  }

  /** 进入新会话草稿态：不发任何请求，界面先空着，等第一条消息再建 */
  function startNew() {
    conversationRequest += 1
    loadingMessages.value = false
    const previous = threads.get(DRAFT_KEY)
    if (previous) disposeThread(previous)
    threads.delete(DRAFT_KEY)
    draft.value = true
    activeId.value = null
  }

  /** 草稿态发出第一条消息时才真正建会话；失败返回 null */
  async function ensureConversation(): Promise<number | null> {
    if (activeId.value !== null) return activeId.value
    const thread = threadOf(DRAFT_KEY)
    const existing = creations.get(thread)
    if (existing) return existing
    const epoch = accountEpoch
    const promise = (async () => {
      const created = await createConversation()
      if (epoch !== accountEpoch || threads.get(DRAFT_KEY) !== thread) return null
      conversations.value = [{ ...created, message_count: 0 }, ...conversations.value]
      threads.set(created.id, thread)
      threads.delete(DRAFT_KEY)
      if (activeId.value === null) {
        activeId.value = created.id
        draft.value = false
      }
      return created.id
    })()
    creations.set(thread, promise)
    try {
      return await promise
    } finally {
      creations.delete(thread)
    }
  }

  async function rename(item: ChatConversationListItem) {
    const epoch = accountEpoch
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
      if (epoch !== accountEpoch) return
      const updated = await renameConversation(item.id, value)
      if (epoch !== accountEpoch) return
      patchConversation(item.id, { title: updated.title })
      ElMessage.success('会话名称已更新')
    } catch {
      // 取消或接口失败（失败已由拦截器提示）
    }
  }

  async function remove(item: ChatConversationListItem) {
    const epoch = accountEpoch
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
    if (epoch !== accountEpoch) return
    await deleteConversation(item.id)
    if (epoch !== accountEpoch) return
    ElMessage.success('删除成功')
    conversations.value = conversations.value.filter((row) => row.id !== item.id)
    const removed = threads.get(item.id)
    if (removed) disposeThread(removed)
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

  function acceptEvent(
    id: number,
    thread: ChatThread,
    execution: Execution,
    event: AgentStreamEvent,
  ) {
    if (event.type === 'run_started') {
      const optimisticId = execution.userMessageId
      execution.runId = event.run_id
      execution.status = 'running'
      if (event.user_message_id !== null) {
        execution.userMessageId = event.user_message_id
        thread.messages = thread.messages.map((message) =>
          message.id === optimisticId ? { ...message, id: event.user_message_id! } : message,
        )
      }
    } else if (event.type === 'run_finished') {
      if (execution.status === 'completed') return
      execution.runId = event.run_id
      execution.assistantMessageId = event.assistant_message_id
      execution.status = 'completed'
      execution.approval = null
      execution.preview = ''
      execution.detailStatus = 'loaded'
      execution.visibleStepCount = execution.steps.filter((step) =>
        VISIBLE_STEP_KINDS.has(step.kind),
      ).length
      execution.revision++
      if (!thread.messages.some((message) => message.id === event.assistant_message_id)) {
        thread.messages.push({
          id: event.assistant_message_id,
          conversation_id: id,
          role: 'assistant',
          content: event.content,
          model: event.model,
          create_time: formatNow(),
        })
        const row = conversations.value.find((item) => item.id === id)
        patchConversation(id, {
          message_count: (row?.message_count ?? 0) + 2,
          update_time: formatNow(),
        })
        sortByRecent()
      }
    } else if (event.type === 'approval_required') {
      execution.runId = event.run_id
      execution.status = 'waiting_approval'
      execution.preview = ''
      execution.approval = {
        runId: event.run_id,
        approvalId: event.approval_id,
        tool: event.tool,
        args: event.args,
        reason: event.reason,
      }
      execution.revision++
    } else {
      applyExecutionEvent(execution, event)
    }
  }

  async function performExecution(
    id: number,
    thread: ChatThread,
    execution: Execution,
    stream: (handlers: Parameters<typeof sendAgentStream>[2], signal: AbortSignal) => Promise<void>,
    previousApprovalId?: number,
  ) {
    const controller = new AbortController()
    controllers.set(execution, controller)
    const epoch = accountEpoch
    const current = () =>
      epoch === accountEpoch &&
      threads.get(id) === thread &&
      controllers.get(execution) === controller &&
      !controller.signal.aborted
    thread.historyRevision++
    try {
      return await runExecution(execution, {
        previousApprovalId,
        current,
        stream: (handlers) => stream(handlers, controller.signal),
        event: (event) => acceptEvent(id, thread, execution, event),
        reconcile: () => refreshThread(id, thread),
        rejected: (error) =>
          execution.runId === null &&
          error instanceof AgentHttpError &&
          [400, 401, 403, 404, 422].includes(error.status),
      })
    } finally {
      if (controllers.get(execution) === controller) controllers.delete(execution)
    }
  }

  async function send(
    content: string,
    skillMode: AgentSkillMode = 'auto',
    reasoningEffort: ReasoningEffort = 'none',
    skillCatalogVersion?: string,
  ): Promise<boolean> {
    const text = content.trim()
    const thread = activeThread.value
    if (!text || !canSend.value) return false
    const epoch = accountEpoch
    const selectedKey = thread.selectedSkillKey
    const optimisticId = -++localSequence
    const execution = reactive(createExecution(`local:${-optimisticId}`))
    execution.requestId = createRequestId()
    execution.transport = 'preparing'
    thread.executions.push(execution)
    thread.activeExecutionKey = execution.key
    let id = activeId.value
    try {
      if (id === null) id = await ensureConversation()
      if (id === null || epoch !== accountEpoch || threads.get(id) !== thread) return false
      execution.userMessageId = optimisticId
      execution.status = 'running'
      thread.messages.push({
        id: execution.userMessageId,
        conversation_id: id,
        role: 'user',
        content: text,
        model: null,
        create_time: formatNow(),
      })
      const ok = await performExecution(id, thread, execution, (handlers, signal) =>
        sendAgentStream(
          id!,
          text,
          handlers,
          signal,
          skillMode,
          reasoningEffort,
          selectedKey ? [selectedKey] : [],
          skillCatalogVersion,
          execution.requestId,
        ),
      )
      if (epoch !== accountEpoch || threads.get(id) !== thread) return false
      if (ok) {
        thread.draftText = ''
        thread.selectedSkillKey = null
      }
      return ok
    } catch (error) {
      if (
        epoch !== accountEpoch ||
        (id === null ? threads.get(DRAFT_KEY) !== thread : threads.get(id) !== thread)
      )
        return false
      execution.transport = 'idle'
      execution.status = 'failed'
      execution.error = error instanceof Error ? error.message : '创建会话失败，请重试'
      return false
    }
  }

  async function decideApproval(decision: 'approve' | 'reject', note?: string): Promise<boolean> {
    const id = activeId.value
    const thread = activeThread.value
    const execution = currentExecution(thread)
    const pending = execution?.approval
    if (
      id === null ||
      !execution ||
      !pending ||
      execution.status !== 'waiting_approval' ||
      execution.transport !== 'idle' ||
      execution.error
    )
      return false
    execution.transport = 'preparing'
    thread.historyRevision++
    try {
      await readSteps(id, thread, execution)
      if (threads.get(id) !== thread) return false
    } catch (error) {
      if (threads.get(id) !== thread) return false
      execution.transport = 'disconnected'
      execution.error = error instanceof Error ? error.message : '读取执行过程失败，请重试'
      return false
    }
    execution.approval = null
    execution.status = 'running'
    return performExecution(
      id,
      thread,
      execution,
      (handlers, signal) =>
        decideApprovalStream(pending.runId, pending.approvalId, decision, handlers, note, signal),
      pending.approvalId,
    )
  }

  function approveApproval(note?: string) {
    return decideApproval('approve', note)
  }

  function rejectApproval(note?: string) {
    return decideApproval('reject', note)
  }

  /** 退出登录时清空，避免下一个账号看到上一个人的会话 */
  function reset() {
    accountEpoch++
    conversationRequest++
    for (const thread of threads.values()) disposeThread(thread)
    loadingMessages.value = false
    loadingList.value = false
    conversations.value = []
    threads.clear()
    activeId.value = null
    draft.value = false
    conversationsLoaded = false
    conversationsInFlight = null
  }

  return {
    feedItems,
    canSend,
    recoveryMessage,
    recoverExecution,
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
    loadExecutionSteps,
    hasOlderMessages,
    loadingOlderMessages,
    loadOlderMessages,
    toggleAgentMode,
  }
})
