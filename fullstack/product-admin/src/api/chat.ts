import client from './client'

import type {
  ApiResponse,
  ChatConversation,
  ChatConversationDetail,
  ChatConversationPage,
  ChatExchange,
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
