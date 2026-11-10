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

/** 工具清单：设置页要能逐个启停，并看到今日用量 */
export interface ToolItem {
  name: string
  description: string
  level: 'read' | 'write' | 'external'
  enabled: boolean
  requires_approval: boolean
  calls_today: number
}

export interface ToolSettings {
  items: ToolItem[]
  daily_tool_budget: number
  used_today: number
}

export interface ToolStatItem {
  tool_name: string
  calls: number
  failures: number
}

export interface ToolStats {
  days: number
  items: ToolStatItem[]
  total: number
}

export async function fetchToolSettings(): Promise<ToolSettings> {
  const { data } = await client.get<ApiResponse<ToolSettings>>('/settings/tools')
  return data.data
}

/** 整体替换「关掉的工具」列表；daily_tool_budget 不传表示不改 */
export async function saveToolSettings(payload: {
  disabled: string[]
  daily_tool_budget?: number
}): Promise<ToolSettings> {
  const { data } = await client.put<ApiResponse<ToolSettings>>('/settings/tools', payload)
  return data.data
}

export async function fetchToolStats(days = 7): Promise<ToolStats> {
  const { data } = await client.get<ApiResponse<ToolStats>>('/settings/tools/stats', {
    params: { days },
  })
  return data.data
}
