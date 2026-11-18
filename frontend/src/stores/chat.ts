import { computed, reactive, ref } from 'vue'
import { defineStore } from 'pinia'

import { buildChatFeed } from './chat/feed'
import { applyExecutionEvent } from './chat/events'
import {
  createExecution,
  createRequestId,
  blocksSending,
  isTransferring,
  runExecution,
  VISIBLE_STEP_KINDS,
  type Execution,
} from './chat/execution'
import { createConversations } from './chat/conversations'
import { createHistory } from './chat/history'
import { createThreadState, currentExecution, DRAFT_KEY, type ChatThread } from './chat/threads'
export type { PendingApproval } from './chat/execution'
export type { ChatThread } from './chat/threads'

import {
  AgentHttpError,
  decideApprovalStream,
  findRunByRequestId,
  getAgentSteps,
  sendAgentStream,
  type AgentSkillMode,
  type AgentStreamEvent,
  type ReasoningEffort,
} from '@/api/agent'

const AGENT_MODE_KEY = 'my-agent.agent-mode'
/** 断线后核对的轮询间隔与上限：30 秒内没收敛就交还给用户手动再点 */
const POLL_INTERVAL_MS = 1500
const POLL_MAX_ATTEMPTS = 20

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
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
 *
 * 这里是**组合根**，只做三件事：决定当前打开哪个会话、把发送/审批串起来、
 * 把各模块的状态投影成视图用的派生值。具体职责分在三个模块里：
 * - `chat/conversations.ts`：会话列表、当前 id、账号代次、建/改/删
 * - `chat/history.ts`：历史分页、刷新对齐、步骤详情（所有读路径）
 * - `chat/threads.ts`：每个会话的运行时状态容器与释放
 */
export const useChatStore = defineStore('chat', () => {
  const threadState = createThreadState()
  const conversations = createConversations({
    threads: threadState,
    onActiveRemoved: () => startNew(),
  })
  const history = createHistory({
    threads: threadState,
    patchConversation: conversations.patch,
  })

  /** 是否请求模型提高推理强度。 */
  const agentMode = ref(readAgentMode())

  /** 当前会话的键（草稿态是 0） */
  const activeKey = computed(() => conversations.activeId.value ?? DRAFT_KEY)

  /** 当前会话的那一份（视图只读这个） */
  const activeThread = computed(() => threadState.threadOf(activeKey.value))
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

  let localSequence = 0

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
    return threadState.threads.get(id)?.executions.some(blocksSending) ?? false
  }

  let conversationRequest = 0

  async function openConversation(id: number) {
    const request = ++conversationRequest
    conversations.draft.value = false
    conversations.activeId.value = id
    const thread = threadState.threadOf(id)
    conversations.loadingMessages.value =
      !thread.loaded && !thread.executions.some(isTransferring)
    if (thread.executions.some(isTransferring)) return
    try {
      await history.refreshThread(id, thread)
    } catch (error) {
      if (threadState.threads.get(id) !== thread) return
      thread.historyError = error instanceof Error ? error.message : '读取会话失败，请重试'
    } finally {
      if (request === conversationRequest) conversations.loadingMessages.value = false
    }
  }

  /** 断流后的「重新核对状态」：只读服务端，不重发 */
  async function recoverExecution() {
    const id = conversations.activeId.value
    const thread = activeThread.value
    if (id === null || thread.executions.some(isTransferring)) return false
    const execution = currentExecution(thread)
    if (execution) execution.transport = 'reconciling'
    try {
      // 还不知道 runId 时先用 request_id 认领自己那次提交：
      // 查不到就是没落库（可以安全重发），查得到就把它当成这次执行去核对。
      if (execution && execution.runId === null && execution.requestId) {
        const found = await findRunByRequestId(id, execution.requestId)
        if (threadState.threads.get(id) !== thread) return false
        if (!found) {
          execution.status = 'failed'
          execution.transport = 'idle'
          execution.error = '这次提交没有落库，可以重新发送'
          return false
        }
        execution.runId = found.id
      }
      await history.refreshThread(id, thread)
      // 核对确认这条消息已经落进历史，草稿就已经发出去了：再留着会被当成新消息发第二遍。
      const sent =
        execution && execution.userMessageId !== null
          ? thread.messages.find(
              (message) => message.id === execution.userMessageId && message.role === 'user',
            )
          : undefined
      if (sent && sent.content.trim() === thread.draftText.trim()) thread.draftText = ''
      // 服务端还在跑：后台只读轮询增量步骤，跑到终态再刷新一次正文。
      // 不 await：核对按钮不该替用户等满 30 秒，轮询失败也只是停在断开态。
      if (execution && execution.status === 'running') void pollExecution(id, thread, execution)
      return (
        threadState.threads.get(id) === thread &&
        !thread.executions.some((item) => item.transport === 'disconnected')
      )
    } catch (error) {
      if (threadState.threads.get(id) !== thread) return false
      thread.historyError = error instanceof Error ? error.message : '读取执行状态失败'
      if (execution) execution.transport = 'disconnected'
      return false
    }
  }

  /**
   * 服务端仍在执行时的只读增量轮询。
   *
   * 只读：不发消息、不重跑、不改草稿。只在当前会话实例上继续，
   * 切会话或卸载后立即放弃；跑够上限就停，交给用户再点「重新核对状态」。
   */
  async function pollExecution(id: number, thread: ChatThread, execution: Execution) {
    for (let attempt = 0; attempt < POLL_MAX_ATTEMPTS; attempt++) {
      if (execution.status !== 'running' || execution.runId === null) return
      await sleep(POLL_INTERVAL_MS)
      if (threadState.threads.get(id) !== thread) return
      if (execution.status !== 'running' || execution.runId === null) return
      let page
      try {
        page = await getAgentSteps(execution.runId, lastStepSeq(execution))
      } catch {
        return
      }
      if (threadState.threads.get(id) !== thread) return
      const merged = new Map(execution.steps.map((step) => [step.seq, step]))
      for (const step of page.items) merged.set(step.seq, step)
      execution.steps = [...merged.values()].sort((a, b) => a.seq - b.seq)
      history.applyServerStatus(
        execution,
        page.status,
        page.visible_step_count,
        page.error_message,
      )
      if (page.status !== 'running') {
        // 终态后读回正文与审批，轮询本身不改展示顺序
        await history.refreshThread(id, thread)
        return
      }
    }
  }

  function lastStepSeq(execution: Execution) {
    return execution.steps.reduce((max, step) => Math.max(max, step.seq), 0)
  }

  async function loadOlderMessages() {
    const id = conversations.activeId.value
    if (id === null) return false
    return history.loadOlderMessages(id, activeThread.value)
  }

  async function loadExecutionSteps(runId: number) {
    const id = conversations.activeId.value
    if (id === null) return
    await history.loadExecutionSteps(id, activeThread.value, runId)
  }

  /** 进入新会话草稿态：不发任何请求，界面先空着，等第一条消息再建 */
  function startNew() {
    conversationRequest += 1
    conversations.loadingMessages.value = false
    threadState.detachThread(DRAFT_KEY)
    conversations.draft.value = true
    conversations.activeId.value = null
  }

  /** 草稿态发出第一条消息时才真正建会话；失败返回 null */
  function ensureConversation(): Promise<number | null> {
    return conversations.ensureConversation()
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
        const row = conversations.rows.value.find((item) => item.id === id)
        conversations.patch(id, {
          message_count: (row?.message_count ?? 0) + 2,
          update_time: formatNow(),
        })
        conversations.sortByRecent()
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
    threadState.controllers.set(execution, controller)
    const epoch = conversations.currentEpoch()
    const current = () =>
      epoch === conversations.currentEpoch() &&
      threadState.threads.get(id) === thread &&
      threadState.controllers.get(execution) === controller &&
      !controller.signal.aborted
    thread.historyRevision++
    try {
      return await runExecution(execution, {
        previousApprovalId,
        current,
        stream: (handlers) => stream(handlers, controller.signal),
        event: (event) => acceptEvent(id, thread, execution, event),
        reconcile: () => history.refreshThread(id, thread),
        rejected: (error) =>
          execution.runId === null &&
          error instanceof AgentHttpError &&
          [400, 401, 403, 404, 422].includes(error.status),
      })
    } finally {
      if (threadState.controllers.get(execution) === controller)
        threadState.controllers.delete(execution)
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
    const epoch = conversations.currentEpoch()
    const selectedKey = thread.selectedSkillKey
    const optimisticId = -++localSequence
    const execution = reactive(createExecution(`local:${-optimisticId}`))
    execution.requestId = createRequestId()
    execution.transport = 'preparing'
    thread.executions.push(execution)
    thread.activeExecutionKey = execution.key
    let id = conversations.activeId.value
    try {
      if (id === null) id = await ensureConversation()
      if (id === null || epoch !== conversations.currentEpoch())
        return false
      if (threadState.threads.get(id) !== thread) return false
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
      if (epoch !== conversations.currentEpoch() || threadState.threads.get(id) !== thread)
        return false
      if (ok) {
        thread.draftText = ''
        thread.selectedSkillKey = null
      }
      return ok
    } catch (error) {
      if (
        epoch !== conversations.currentEpoch() ||
        (id === null
          ? threadState.threads.get(DRAFT_KEY) !== thread
          : threadState.threads.get(id) !== thread)
      )
        return false
      execution.transport = 'idle'
      execution.status = 'failed'
      execution.error = error instanceof Error ? error.message : '创建会话失败，请重试'
      return false
    }
  }

  async function decideApproval(decision: 'approve' | 'reject', note?: string): Promise<boolean> {
    const id = conversations.activeId.value
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
      await history.readSteps(id, thread, execution)
      if (threadState.threads.get(id) !== thread) return false
    } catch (error) {
      if (threadState.threads.get(id) !== thread) return false
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
    conversationRequest += 1
    conversations.resetAccount()
    threadState.clearThreads()
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
    conversations: conversations.rows,
    activeId: conversations.activeId,
    draft: conversations.draft,
    composerText,
    selectedSkillKey,
    messages,
    loadingList: conversations.loadingList,
    loadingMessages: conversations.loadingMessages,
    sending,
    streamingText,
    activeConversation: conversations.activeConversation,
    activeTitle: conversations.activeTitle,
    modelLabel,
    isBusy,
    loadConversations: conversations.load,
    ensureConversationsLoaded: conversations.ensureLoaded,
    openConversation,
    startNew,
    ensureConversation,
    rename: conversations.rename,
    remove: conversations.remove,
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
