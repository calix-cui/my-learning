import client from './client'

import type {
  ApiResponse,
  ChatConversation,
  ChatConversationDetail,
  ChatConversationPage,
  ChatExchange,
  ChatMessage,
} from '@/types/api'

/** 新建会话，标题缺省由后端填「新会话」 */
export async function createConversation(title?: string): Promise<ChatConversation> {
  const { data } = await client.post<ApiResponse<ChatConversation>>(
    '/conversations',
    title ? { title } : {},
  )
  return data.data
}

/** 分页查询会话，按最后活动时间倒序 */
export async function listConversations(page = 1, page_size = 50): Promise<ChatConversationPage> {
  const { data } = await client.get<ApiResponse<ChatConversationPage>>('/conversations', {
    params: { page, page_size },
  })
  return data.data
}

/** 会话详情（含全部消息） */
export async function getConversation(id: number): Promise<ChatConversationDetail> {
  const { data } = await client.get<ApiResponse<ChatConversationDetail>>(`/conversations/${id}`)
  return data.data
}

/** 重命名会话 */
export async function renameConversation(id: number, title: string): Promise<ChatConversation> {
  const { data } = await client.patch<ApiResponse<ChatConversation>>(`/conversations/${id}`, {
    title,
  })
  return data.data
}

/** 删除会话及其全部消息 */
export async function deleteConversation(id: number): Promise<void> {
  await client.delete<ApiResponse<null>>(`/conversations/${id}`)
}

/** 发送一条消息，同步拿回用户消息与助手回复 */
export async function sendMessage(id: number, content: string): Promise<ChatExchange> {
  // 后端模型超时是 30s，全局 axios 只给了 10s：这里放宽到 35s，避免前端先报「网络异常」
  const { data } = await client.post<ApiResponse<ChatExchange>>(
    `/conversations/${id}/messages`,
    { content },
    { timeout: 35000 },
  )
  return data.data
}

/** 流式事件（与后端 SSE 的 data 负载一一对应） */
export type ChatStreamEvent =
  | { type: 'meta'; user_message: ChatMessage }
  | { type: 'delta'; content: string }
  | {
      type: 'done'
      conversation_id: number
      conversation_title: string
      message_count: number
      assistant_message: ChatMessage
    }
  | { type: 'error'; code: number; message: string }

/** 流式回调：meta 先到（带回用户消息 id），delta 逐块，done 收尾 */
export interface ChatStreamHandlers {
  onMeta?: (message: ChatMessage) => void
  onDelta: (text: string) => void
  onDone: (event: Extract<ChatStreamEvent, { type: 'done' }>) => void
}

/**
 * 流式发送消息（SSE）。
 *
 * 用 fetch + ReadableStream 而不是 EventSource：EventSource 只能发 GET，
 * 而消息内容最长 4000 字，塞进 query string 既超长又会进访问日志。
 */
export async function sendMessageStream(
  id: number,
  content: string,
  handlers: ChatStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`/api/conversations/${id}/messages/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify({ content }),
    signal,
  })

  if (!response.ok || !response.body) {
    // 校验失败（400/404）走的是普通 JSON，不是事件流
    const fallback = `请求失败（${response.status}）`
    const text = await response.text().catch(() => '')
    try {
      const body = JSON.parse(text) as { message?: string }
      throw new Error(body.message ?? fallback)
    } catch (error) {
      throw error instanceof Error ? error : new Error(fallback)
    }
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  for (;;) {
    const { done, value } = await reader.read()
    if (done) {
      break
    }
    buffer += decoder.decode(value, { stream: true })

    // SSE 以空行分帧；一次 read 可能只拿到半帧，剩下的留在 buffer 里
    let index = buffer.indexOf('\n\n')
    while (index >= 0) {
      const frame = buffer.slice(0, index)
      buffer = buffer.slice(index + 2)
      const payload = frame
        .split('\n')
        .filter((line) => line.startsWith('data:'))
        .map((line) => line.slice(5).trim())
        .join('')
      if (payload) {
        const event = JSON.parse(payload) as ChatStreamEvent
        if (event.type === 'meta') {
          handlers.onMeta?.(event.user_message)
        } else if (event.type === 'delta') {
          handlers.onDelta(event.content)
        } else if (event.type === 'done') {
          handlers.onDone(event)
        } else {
          throw new Error(event.message)
        }
      }
      index = buffer.indexOf('\n\n')
    }
  }
}
