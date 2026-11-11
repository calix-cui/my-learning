import client from './client'

import type {
  ApiResponse,
  ChatSkill,
  ChatSkillDetail,
  ChatSkillList,
  SkillPayload,
} from '@/types/api'

/** 技能列表；传会话 ID 时顺带标出该会话挂载了哪个 */
export async function listSkills(conversationId?: number | null): Promise<ChatSkillList> {
  const { data } = await client.get<ApiResponse<ChatSkillList>>('/skills', {
    params: conversationId ? { conversation_id: conversationId } : {},
  })
  return data.data
}

/** 单个技能详情（含正文） */
export async function getSkill(slug: string): Promise<ChatSkillDetail> {
  const { data } = await client.get<ApiResponse<ChatSkillDetail>>(`/skills/${slug}`)
  return data.data
}

/** 新建自定义技能 */
export async function createSkill(payload: SkillPayload): Promise<ChatSkill> {
  const { data } = await client.post<ApiResponse<ChatSkill>>('/skills', payload)
  return data.data
}

/** 修改自定义技能，只传要改的字段 */
export async function updateSkill(id: number, payload: SkillPayload): Promise<ChatSkill> {
  const { data } = await client.patch<ApiResponse<ChatSkill>>(`/skills/${id}`, payload)
  return data.data
}

/** 删除自定义技能 */
export async function deleteSkill(id: number): Promise<void> {
  await client.delete(`/skills/${id}`)
}

/** 挂载或卸载技能：slug 传 null 表示卸载 */
export async function mountSkill(
  conversationId: number,
  slug: string | null,
): Promise<{ conversation_id: number; skill_slug: string | null }> {
  const { data } = await client.put<
    ApiResponse<{ conversation_id: number; skill_slug: string | null }>
  >(`/conversations/${conversationId}/skill`, { slug })
  return data.data
}
