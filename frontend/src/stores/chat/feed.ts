import type { AgentStep, ChatMessage } from '@/types/api'
import { VISIBLE_STEP_KINDS, type Execution, type PendingApproval } from './execution'

export interface ExecutionItem {
  kind: 'execution'
  key: string
  runId: number | null
  message?: ChatMessage
  steps: AgentStep[]
  running: boolean
  live: boolean
  showTimeline: boolean
  lazy: boolean
  loadStatus?: 'loading' | 'loaded' | 'error'
  /** 这次运行为什么没有回话（服务端给的原因）；中断的运行不会再补正文 */
  error: string | null
  /** 终态：用来决定要不要显示「重新生成」 */
  status: Execution['status']
  /** 用户主动终止的运行：页脚要给一条可以重来的路 */
  cancelled: boolean
  approval: PendingApproval | null
  approvalBlocked: boolean
}

export type ChatFeedItem = { kind: 'message'; key: string; message: ChatMessage } | ExecutionItem

interface FeedSource {
  messages: ChatMessage[]
  executions: Execution[]
}

/** 只投影展示顺序，不复制业务状态，也不发起历史或详情请求。 */
export function buildChatFeed(source: FeedSource, conversationKey: number): ChatFeedItem[] {
  const items: ChatFeedItem[] = []
  const messages = new Map(source.messages.map((message) => [message.id, message]))
  const before = new Map<number, ExecutionItem[]>()
  const after = new Map<number, ExecutionItem[]>()
  const tail: ExecutionItem[] = []
  const consumed = new Set<number>()
  const key = (value: string) => `${conversationKey}:${value}`

  function place(item: ExecutionItem, userId: number | null, assistantId: number | null) {
    if (assistantId !== null && messages.has(assistantId)) {
      item.message = messages.get(assistantId)
      consumed.add(assistantId)
      const group = before.get(assistantId) ?? []
      group.push(item)
      before.set(assistantId, group)
    } else if (userId !== null && messages.has(userId)) {
      const group = after.get(userId) ?? []
      group.push(item)
      after.set(userId, group)
    } else if (item.live || item.approval) {
      // 活跃运行可能不在当前历史页，仍保留其过程与审批入口。
      tail.push(item)
    }
  }

  const ordered = [...source.executions].sort(
    (a, b) => (a.runId ?? Number.MAX_SAFE_INTEGER) - (b.runId ?? Number.MAX_SAFE_INTEGER),
  )
  for (const execution of ordered) {
    const steps = execution.steps.filter((step) => VISIBLE_STEP_KINDS.has(step.kind))
    const live = execution.transport === 'streaming' || execution.transport === 'preparing'
    place(
      {
        kind: 'execution',
        key: key(execution.key),
        runId: execution.runId,
        steps,
        running:
          live && execution.status !== 'completed' && execution.status !== 'waiting_approval',
        live,
        showTimeline: live || steps.length > 0 || execution.visibleStepCount > 0,
        lazy: !live && execution.visibleStepCount > 0,
        loadStatus: execution.detailStatus,
        error: execution.error,
        status: execution.status,
        cancelled: execution.status === 'cancelled',
        approval: execution.approval,
        approvalBlocked:
          execution.status !== 'waiting_approval' ||
          execution.transport !== 'idle' ||
          execution.error !== null,
      },
      execution.userMessageId,
      execution.assistantMessageId,
    )
  }

  for (const message of source.messages) {
    items.push(...(before.get(message.id) ?? []))
    if (!consumed.has(message.id)) {
      items.push({ kind: 'message', key: key(`message:${message.id}`), message })
    }
    items.push(...(after.get(message.id) ?? []))
  }
  return [...items, ...tail]
}
