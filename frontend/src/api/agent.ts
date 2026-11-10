import type { AgentRunList, ChatMessage } from '@/types/api'

/** agent 流式事件（与后端 SSE 负载一一对应） */
export type AgentStreamEvent =
  | { type: 'run_started'; run_id: number; conversation_id: number }
  | { type: 'step_started'; seq: number; kind: string }
  | { type: 'assistant_text'; seq: number; content: string }
  | { type: 'tool_call'; seq: number; tool: string; args: Record<string, unknown> | null }
  | {
      type: 'tool_result'
      seq: number
      tool: string
      ok: boolean
      content: string
      duration_ms: number
    }
  | {
      type: 'approval_required'
      run_id: number
      approval_id: number
      seq: number
      tool: string
      args: Record<string, unknown> | null
      reason: string
    }
  | {
      type: 'run_finished'
      run_id: number
      content: string
      steps: number
      model: string | null
    }
  | { type: 'error'; code: number; message: string }

export interface AgentApproval {
  id: number
  run_id: number
  seq: number
  tool_name: string
  tool_args: Record<string, unknown> | null
  status: 'pending' | 'approved' | 'rejected' | 'expired'
  note: string | null
  decided_time: string | null
  create_time: string
}

export interface AgentStreamHandlers {
  onEvent?: (event: AgentStreamEvent) => void
  onFinished: (event: Extract<AgentStreamEvent, { type: 'run_finished' }>) => void
  onApproval?: (event: Extract<AgentStreamEvent, { type: 'approval_required' }>) => void
  onError?: (message: string) => void
}

/** 一个 SSE 响应读到结尾：按 `data:` 帧解析，事件交给 handlers 分发 */
async function consume(response: Response, handlers: AgentStreamHandlers): Promise<void> {
  if (!response.ok || !response.body) {
    const text = await response.text().catch(() => '')
    try {
      const body = JSON.parse(text) as { message?: string }
      throw new Error(body.message ?? `请求失败（${response.status}）`)
    } catch (error) {
      throw error instanceof Error ? error : new Error(`请求失败（${response.status}）`)
    }
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let index = buffer.indexOf('\n\n')
    while (index >= 0) {
      const frame = buffer.slice(0, index)
      buffer = buffer.slice(index + 2)
      index = buffer.indexOf('\n\n')
      const payload = frame
        .split('\n')
        .filter((line) => line.startsWith('data:'))
        .map((line) => line.slice(5).trim())
        .join('')
      if (!payload) continue
      const event = JSON.parse(payload) as AgentStreamEvent
      handlers.onEvent?.(event)
      if (event.type === 'run_finished') {
        handlers.onFinished(event)
      } else if (event.type === 'approval_required') {
        handlers.onApproval?.(event)
      } else if (event.type === 'error') {
        handlers.onError?.(event.message)
        throw new Error(event.message)
      }
    }
  }
}

/**
 * 跑一次 agent 循环（SSE）。
 *
 * 和普通对话一样用 fetch + ReadableStream：POST 带 body，EventSource 做不到。
 * 超时给到 120s——多步循环比单次问答慢，但也不能真的无限挂。
 */
export async function sendAgentStream(
  id: number,
  content: string,
  handlers: AgentStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`/api/conversations/${id}/agent/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify({ content }),
    signal,
  })
  await consume(response, handlers)
}

/** 批准或拒绝一次工具调用：服务端接着跑，返回的还是同一套事件流 */
export async function decideApprovalStream(
  runId: number,
  approvalId: number,
  decision: 'approve' | 'reject',
  handlers: AgentStreamHandlers,
  note?: string,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`/api/agent/runs/${runId}/approvals/${approvalId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify({ decision, note: note ?? null }),
    signal,
  })
  await consume(response, handlers)
}

/** 取某次运行的审批（刷新后把待决定的卡片复原） */
export async function listApprovals(runId: number, signal?: AbortSignal): Promise<AgentApproval[]> {
  const response = await fetch(`/api/agent/runs/${runId}/approvals`, {
    headers: { Accept: 'application/json' },
    credentials: 'same-origin',
    signal,
  })
  if (!response.ok) return []
  const body = (await response.json()) as { data: { items: AgentApproval[] } }
  return body.data.items
}

/** 取最近的运行记录，用于刷新后回放（失败不打扰用户，返回空） */
export async function listAgentRuns(
  id: number,
  limit = 3,
  signal?: AbortSignal,
): Promise<AgentRunList> {
  const response = await fetch(`/api/conversations/${id}/agent/runs?limit=${limit}`, {
    headers: { Accept: 'application/json' },
    credentials: 'same-origin',
    signal,
  })
  if (!response.ok) {
    return { items: [] }
  }
  const body = (await response.json()) as { data: AgentRunList }
  return body.data
}

export type { ChatMessage }
