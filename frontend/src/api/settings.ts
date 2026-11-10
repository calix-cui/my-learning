import client from './client'

import type {
  ApiResponse,
  AppearanceSettings,
  ModelSettings,
  ModelSettingsPayload,
  ModelTestResult,
} from '@/types/api'

/** 读取当前用户的模型配置（未保存过时返回环境变量那套，并带 inherited_from_env） */
export async function fetchModelSettings(): Promise<ModelSettings> {
  const { data } = await client.get<ApiResponse<ModelSettings>>('/settings/model')
  return data.data
}

/** 保存模型配置；`api_key` 不传表示沿用已保存的那把，传空串表示清除 */
export async function saveModelSettings(payload: ModelSettingsPayload): Promise<ModelSettings> {
  const { data } = await client.put<ApiResponse<ModelSettings>>('/settings/model', payload)
  return data.data
}

/** 连通性自测：可以用已保存的配置，也可以带本次还没保存的临时值 */
export async function testModelSettings(
  payload: ModelSettingsPayload = {},
): Promise<ModelTestResult> {
  const { data } = await client.post<ApiResponse<ModelTestResult>>('/settings/model/test', payload)
  return data.data
}

/**
 * 导出地址：交给浏览器直接下载（Cookie 会带上），
 * 不走 axios——否则要把整个文件读进内存再触发一次 Blob 下载。
 */
export function exportUrl(format: 'json' | 'markdown'): string {
  return `/api/settings/export?format=${format}`
}

/** 读取账号保存的外观（没存过时两个字段都是 null） */
export async function fetchAppearance(): Promise<AppearanceSettings> {
  const { data } = await client.get<ApiResponse<AppearanceSettings>>('/settings/appearance', {
    skipAuthRedirect: true,
  })
  return data.data
}

/** 保存外观；只传要改的字段，传 null 表示清掉该字段 */
export async function saveAppearance(
  patch: Partial<Pick<AppearanceSettings, 'theme_id' | 'theme_mode'>>,
): Promise<AppearanceSettings> {
  const { data } = await client.put<ApiResponse<AppearanceSettings>>(
    '/settings/appearance',
    patch,
    {
      skipAuthRedirect: true,
    },
  )
  return data.data
}
