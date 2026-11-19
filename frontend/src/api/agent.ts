import type { AgentRunDetail, AgentRunSummary, AgentStepsPage, ChatMessage } from '@/types/api'

export type ReasoningEffort = 'none' | 'high'
export type AgentSkillMode = 'off' | 'manual' | 'auto'

/** agent 流式事件（与后端 SSE 负载一一对应） */
export interface AgentRunSnapshot {
  type: 'run_snapshot'
  run_id: number
  conversation_id: number
  status: AgentRunSummary['status']
  draft_content: string | null
  visible_step_count: number
  error_message: string | null
  stop_reason: string | null
  finished_time: string | null
}

export type AgentStreamEvent =
  | AgentRunSnapshot
  | { type: 'run_started'; run_id: number; conversation_id: number; user_message_id: number | null }
  | { type: 'step_started'; seq: number; kind: string }
  | { type: 'assistant_text'; seq: number; content: string }
  | { type: 'assistant_delta'; content: string }
  | { type: 'assistant_preview_reset' }
  | {
      type: 'skill_loaded'
      seq: number
      skill_key: string
      name: string
      source: string
      version: string
    }
  | {
      type: 'skill_load_failed'
      seq: number
      skill_key: string
      error_code: string
      message: string
    }
  | {
      type: 'skill_resource'
      seq: number
      skill_key: string
      name: string | null
      path: string
      ok: boolean
      message: string
    }
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
      assistant_message_id: number
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

export class AgentHttpError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
  }
}

/** 一个 SSE 响应读到结尾：按 `data:` 帧解析，事件交给 handlers 分发 */
async function consume(
  response: Response,
  handlers: AgentStreamHandlers,
  runId?: number,
): Promise<void> {
  if (!response.ok || !response.body) {
    const body = (await response.json().catch(() => null)) as { message?: string } | null
    throw new AgentHttpError(response.status, body?.message ?? `请求失败（${response.status}）`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let complete = false

  try {
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
        if (import.meta.env.DEV) {
          if ('run_id' in event) runId = event.run_id
          console.debug('[my-agent] agent.sse', {
            type: event.type,
            runId,
            seq: 'seq' in event ? event.seq : undefined,
            tool: 'tool' in event ? event.tool : undefined,
            ok: 'ok' in event ? event.ok : undefined,
            code: 'code' in event ? event.code : undefined,
          })
        }
        handlers.onEvent?.(event)
        if (event.type === 'run_snapshot') {
          // 订阅的第一帧：运行已经结束时不必再等，读一次历史就够了
          if (event.status !== 'running' && event.status !== 'waiting_approval') {
            complete = true
            return
          }
          continue
        }
        if (event.type === 'run_finished') {
          complete = true
          handlers.onFinished(event)
        } else if (event.type === 'approval_required') {
          complete = true
          handlers.onApproval?.(event)
        } else if (event.type === 'error') {
          handlers.onError?.(event.message)
          throw new Error(event.message)
        }
      }
    }
  } finally {
    if (!complete) await reader.cancel().catch(() => undefined)
    reader.releaseLock()
  }
  if (!complete) throw new Error('回复连接已中断，请刷新查看执行状态')
}

/**
 * 跑一次 agent 循环（SSE）。
 *
 * 和普通对话一样用 fetch + ReadableStream：POST 带 body，EventSource 做不到。
 * 推理强度与 Skill 选择独立传输，工具定义和执行权限由后端组装。
 */
export async function sendAgentStream(
  id: number,
  content: string,
  handlers: AgentStreamHandlers,
  signal?: AbortSignal,
  skillMode: AgentSkillMode = 'auto',
  reasoningEffort: ReasoningEffort = 'none',
  skillKeys: string[] = [],
  catalogVersion?: string,
  requestId?: string,
): Promise<void> {
  if (import.meta.env.DEV) {
    console.debug('[my-agent] agent.send', {
      conversationId: id,
      skillMode,
      reasoningEffort,
      chars: content.length,
    })
  }
  const response = await fetch(`/api/conversations/${id}/messages/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify({
      content,
      execution: 'auto',
      request_id: requestId ?? globalThis.crypto?.randomUUID?.(),
      skill_mode: skillMode,
      skill_keys: skillKeys,
      skill_catalog_version: catalogVersion,
      reasoning_effort: reasoningEffort,
    }),
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
  if (import.meta.env.DEV) {
    console.debug('[my-agent] agent.approval', { runId, approvalId, decision })
  }
  const response = await fetch(`/api/agent/runs/${runId}/approvals/${approvalId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify({ decision, note: note ?? null }),
    signal,
  })
  await consume(response, handlers, runId)
}

/**
 * 挂到一次正在跑的运行上（刷新、重连、换设备都用它）。
 *
 * 第一帧是 `run_snapshot`（状态 + 已生成正文），之后才是实时事件；
 * 运行已经结束时只发快照，这里直接读完返回，不当作断线。
 */
export async function subscribeAgentRun(
  runId: number,
  handlers: AgentStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`/api/agent/runs/${runId}/stream`, {
    headers: { Accept: 'text/event-stream' },
    credentials: 'same-origin',
    signal,
  })
  await consume(response, handlers, runId)
}

/** 终止一次运行：只有用户点这个按钮才会停，断线不算 */
export async function stopAgentRun(runId: number, signal?: AbortSignal): Promise<void> {
  const response = await fetch(`/api/agent/runs/${runId}/stop`, {
    method: 'POST',
    headers: { Accept: 'application/json' },
    credentials: 'same-origin',
    signal,
  })
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { message?: string } | null
    throw new AgentHttpError(response.status, body?.message ?? '终止失败，请重试')
  }
}

/** 按同一条提问重新生成：服务端删掉旧的问答，再开一次新运行 */
export async function regenerateAgentRun(
  runId: number,
  handlers: AgentStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`/api/agent/runs/${runId}/regenerate`, {
    method: 'POST',
    headers: { Accept: 'text/event-stream' },
    credentials: 'same-origin',
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
  if (!response.ok) throw new AgentHttpError(response.status, '读取审批失败，请重试')
  const body = (await response.json()) as { code?: number; data: { items: AgentApproval[] } }
  if (body.code !== undefined && body.code !== 200) throw new Error('读取执行数据失败')
  if (!Array.isArray(body.data?.items)) throw new Error('读取执行数据失败：响应格式无效')
  return body.data.items
}

/**
 * 按运行标识读取执行步骤。
 *
 * 返回的不只是步骤：同一份响应里带运行状态，轮询时一个请求就能同时判断
 * 「有新步骤吗」和「跑完了吗」。`sinceSeq` 只取该步之后的增量，空轮询的响应体很小。
 */
export async function getAgentSteps(runId: number, sinceSeq?: number): Promise<AgentStepsPage> {
  const query = sinceSeq === undefined ? '' : `?since_seq=${sinceSeq}`
  const response = await fetch(`/api/agent/runs/${runId}/steps${query}`, {
    headers: { Accept: 'application/json' },
    credentials: 'same-origin',
  })
  if (!response.ok) throw new Error('读取执行过程失败')
  const body = (await response.json()) as { code?: number; data: AgentStepsPage }
  if (body.code !== undefined && body.code !== 200) throw new Error('读取执行数据失败')
  if (!Array.isArray(body.data?.items)) throw new Error('读取执行数据失败：响应格式无效')
  return body.data
}

/** 读单次运行的完整状态，断线后定点核对用。 */
export async function getAgentRun(runId: number): Promise<AgentRunDetail> {
  const response = await fetch(`/api/agent/runs/${runId}`, {
    headers: { Accept: 'application/json' },
    credentials: 'same-origin',
  })
  if (!response.ok) throw new AgentHttpError(response.status, '读取运行状态失败，请重试')
  const body = (await response.json()) as { code?: number; data: AgentRunDetail }
  if (body.code !== undefined && body.code !== 200) throw new Error('读取执行数据失败')
  if (!body.data || typeof body.data.id !== 'number')
    throw new Error('读取执行数据失败：响应格式无效')
  return body.data
}

/**
 * 用客户端手里的 request_id 找回自己那次提交。
 *
 * 返回 `null` 表示服务端没有这条记录（404）——这次提交没落库，可以安全重发。
 * 其它错误照常抛出，不能把「查不到」和「查不了」混为一谈。
 */
export async function findRunByRequestId(
  conversationId: number,
  requestId: string,
): Promise<AgentRunDetail | null> {
  const response = await fetch(
    `/api/conversations/${conversationId}/agent/runs?request_id=${encodeURIComponent(requestId)}`,
    { headers: { Accept: 'application/json' }, credentials: 'same-origin' },
  )
  if (response.status === 404) return null
  if (!response.ok) throw new AgentHttpError(response.status, '核对提交结果失败，请重试')
  const body = (await response.json()) as { code?: number; data: { items?: AgentRunDetail[] } }
  if (body.code !== undefined && body.code !== 200) throw new Error('读取执行数据失败')
  return body.data?.items?.[0] ?? null
}

export type { ChatMessage }
