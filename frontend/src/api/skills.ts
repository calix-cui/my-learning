import client from './client'
import type { ApiResponse, SkillCatalog } from '@/types/api'

/** 登录初始化和设置页重新扫描共用同一接口。 */
export async function rescanSkills(): Promise<SkillCatalog> {
  const { data } = await client.post<ApiResponse<SkillCatalog>>('/skills/catalog/rescan')
  return data.data
}

/** 列表始终只含元数据，查看说明时再加载正文。 */
export async function getSkill(key: string, version: string): Promise<{ instructions: string }> {
  const { data } = await client.get<ApiResponse<{ instructions: string }>>(
    '/skills/catalog/detail',
    {
      params: { key, version },
    },
  )
  return data.data
}

export async function exportLegacySkills(): Promise<Blob> {
  const response = await client.get('/skills/legacy/export', { responseType: 'blob' })
  return response.data
}
