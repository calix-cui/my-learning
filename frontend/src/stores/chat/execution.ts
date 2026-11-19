import type { AgentRunSummary, AgentStep } from '@/types/api'
import type { AgentStreamEvent, AgentStreamHandlers } from '@/api/agent'

export interface PendingApproval {
  runId: number
  approvalId: number
  tool: string
  args: Record<string, unknown> | null
  reason: string
}

export interface Execution {
  key: string
  requestId?: string
  runId: number | null
  userMessageId: number | null
  assistantMessageId: number | null
  status: AgentRunSummary['status'] | null
  transport: 'idle' | 'preparing' | 'streaming' | 'reconciling' | 'disconnected'
  steps: AgentStep[]
  detailStatus?: 'loading' | 'loaded' | 'error'
  visibleStepCount: number
  revision: number
  preview: string
  approval: PendingApproval | null
  error: string | null
}

export const VISIBLE_STEP_KINDS = new Set([
  'tool_call',
  'tool_result',
  'skill_loaded',
  'skill_load_failed',
  'skill_resource',
])

/** HTTP 开发环境可能没有 randomUUID，仍用浏览器随机源生成 UUID。 */
export function createRequestId(): string {
  if (globalThis.crypto.randomUUID) return globalThis.crypto.randomUUID()
  const bytes = globalThis.crypto.getRandomValues(new Uint8Array(16))
  bytes[6] = (bytes[6]! & 0x0f) | 0x40
  bytes[8] = (bytes[8]! & 0x3f) | 0x80
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}

export function createExecution(key: string): Execution {
  return {
    key,
    runId: null,
    userMessageId: null,
    assistantMessageId: null,
    status: null,
    transport: 'idle',
    steps: [],
    visibleStepCount: 0,
    revision: 0,
    preview: '',
    approval: null,
    error: null,
  }
}

export function isTransferring(execution: Execution) {
  return ['preparing', 'streaming', 'reconciling'].includes(execution.transport)
}

export function blocksSending(execution: Execution) {
  return (
    isTransferring(execution) ||
    execution.transport === 'disconnected' ||
    execution.status === 'running' ||
    execution.status === 'waiting_approval'
  )
}

export function applySummary(execution: Execution, summary: AgentRunSummary) {
  if (
    execution.status !== summary.status ||
    execution.visibleStepCount !== summary.visible_step_count
  ) {
    execution.revision++
    // 保留已显示的步骤和展开节点，详情过期时再加载，不以空数组代替旧值。
    execution.detailStatus = undefined
  }
  execution.runId = summary.id
  execution.userMessageId = summary.user_message_id
  execution.assistantMessageId = summary.assistant_message_id
  execution.status = summary.status
  execution.visibleStepCount = summary.visible_step_count
  if (summary.status !== 'waiting_approval') execution.approval = null
  // 失败原因以服务端为准：前端编不出「是模型出错还是网络断了」
  if (summary.status === 'failed')
    execution.error = summary.error_message ?? execution.error ?? '执行失败，可重新发送'
}

interface StreamOperation {
  previousApprovalId?: number
  current: () => boolean
  stream: (handlers: AgentStreamHandlers) => Promise<void>
  event: (event: AgentStreamEvent) => void
  reconcile: () => Promise<void>
  rejected: (error: unknown) => boolean
}

/** 首发和审批共用连接生命周期；未收到终态不能当作成功。 */
export async function runExecution(
  execution: Execution,
  operation: StreamOperation,
): Promise<boolean> {
  let boundary = false
  let accepting = true
  let transportError: string | null = null
  const handle = (event: AgentStreamEvent) => {
    if (!accepting || boundary || !operation.current()) return
    if (event.type === 'run_finished' || event.type === 'approval_required') {
      boundary = true
    }
    operation.event(event)
  }
  execution.transport = 'streaming'
  execution.error = null
  try {
    await operation.stream({ onEvent: handle, onFinished: handle, onApproval: handle })
    if (!boundary) throw new Error('回复连接已中断，正在核对执行状态')
  } catch (error) {
    if (!operation.current()) return false
    transportError = error instanceof Error ? error.message : '连接中断，请核对执行状态'
    execution.error = transportError
    if (!boundary && operation.rejected(error)) {
      execution.status = 'failed'
      execution.transport = 'idle'
      execution.preview = ''
      return false
    }
  } finally {
    accepting = false
  }
  if (!operation.current()) return false
  execution.preview = ''
  // 审批已经把决定权交回用户：这条连接不会再收到事件，核对期间也别再算「传输中」，
  // 否则卡片会在核对的那一下显示「执行中…」，用户点上去什么也不会发生。
  const handedOver = execution.status === 'waiting_approval' && execution.approval !== null
  execution.transport = handedOver ? 'idle' : 'reconciling'
  try {
    await operation.reconcile()
  } catch (error) {
    if (!operation.current()) return false
    execution.error = error instanceof Error ? error.message : '读取执行状态失败'
    // 已收到的持久终态仍可信；没有终态时保持结果未知并阻止重复发送。
    execution.transport = boundary && execution.status === 'completed' ? 'idle' : 'disconnected'
  }
  if (!operation.current()) return false
  // 服务端已经给了终态就不算断线：被终止、失败、完成都是「结束了」，
  // 不能因为连接没收到终态事件，就让发送一直锁着。
  if (
    execution.status === 'completed' ||
    execution.status === 'failed' ||
    execution.status === 'cancelled' ||
    // 审批把决定权交回用户，这条连接不会再收到事件：核对完就该松开。
    // 只有核对本身失败（disconnected）时保持锁住，等用户重新核对。
    (execution.transport !== 'disconnected' &&
      execution.status === 'waiting_approval' &&
      execution.approval !== null)
  ) {
    execution.transport = 'idle'
  }
  if (
    !boundary &&
    operation.previousApprovalId !== undefined &&
    execution.approval?.approvalId === operation.previousApprovalId
  ) {
    execution.error = transportError ?? '审批结果尚未确认，请重新核对状态'
    return false
  }
  return (
    execution.status === 'completed' ||
    (execution.status === 'waiting_approval' &&
      execution.approval !== null &&
      execution.error === null &&
      execution.transport === 'idle')
  )
}
